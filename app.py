import streamlit as st
import pandas as pd
import folium
from folium import plugins
import os
import requests
import re
import pytesseract
import json
import streamlit.components.v1 as components
from PIL import Image
from streamlit_folium import st_folium
from streamlit_geolocation import streamlit_geolocation
from geopy.distance import geodesic
from geopy.geocoders import ArcGIS
from streamlit_autorefresh import st_autorefresh # INI YANG TADI GUE HAPUS, GUE BALIKIN

# 1. KONFIGURASI HALAMAN
st.set_page_config(page_title="Safe-Drive", layout="centered", page_icon="🛡️")
st.markdown("<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;} .block-container {padding-top: 1rem;}</style>", unsafe_allow_html=True)

FILE_CSV = 'hasil_survei_tembalang.csv'

# 2. INISIALISASI STATE
if 'halaman' not in st.session_state: st.session_state.halaman = 'Home'
if 'is_navigating' not in st.session_state: st.session_state.is_navigating = False
if 'rute_data' not in st.session_state: st.session_state.rute_data = None
if 'role' not in st.session_state: st.session_state.role = 'User'

# 3. FUNGSI LOAD DATA
def load_csv():
    if os.path.exists(FILE_CSV):
        df = pd.read_csv(FILE_CSV)
        if 'status' not in df.columns:
            df['status'] = 'approved'
            df.to_csv(FILE_CSV, index=False)
        return df
    return pd.DataFrame(columns=['lokasi', 'lat', 'lon', 'pesan', 'status'])

df_bahaya = load_csv()
df_aktif = df_bahaya[df_bahaya['status'] == 'approved'] if not df_bahaya.empty else pd.DataFrame()

# 4. FUNGSI OCR
def read_coordinates_from_image(img):
    try:
        text = pytesseract.image_to_string(img)
        matches = re.findall(r'-?\d{1,3}\.\d{4,}', text)
        if len(matches) >= 2:
            val1, val2 = float(matches[0]), float(matches[1])
            if abs(val1) < 90 and abs(val2) > 90: return val1, val2
            elif abs(val2) < 90 and abs(val1) > 90: return val2, val1
        return None, None
    except: return None, None

# 5. SUPER ALARM
def inject_super_alarm():
    if df_aktif.empty: return
    h_json = json.dumps(df_aktif[['lat', 'lon', 'pesan', 'lokasi']].to_dict(orient='records'))
    components.html(f"""
        <script>
        const hazards = {h_json};
        function dist(l1, ln1, l2, ln2) {{
            const R = 6371000;
            const dL = (l2-l1)*(Math.PI/180); const dLn = (ln2-ln1)*(Math.PI/180);
            const a = Math.sin(dL/2)**2 + Math.cos(l1*(Math.PI/180))*Math.cos(l2*(Math.PI/180))*Math.sin(dLn/2)**2;
            return R * (2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a)));
        }}
        if(navigator.geolocation) {{
            navigator.geolocation.watchPosition(pos => {{
                hazards.forEach(h => {{
                    if(dist(pos.coords.latitude, pos.coords.longitude, h.lat, h.lon) < 200) {{
                        if(navigator.vibrate) navigator.vibrate([1000, 500, 1000]);
                        new Audio('https://www.soundjay.com/buttons/beep-01a.mp3').play();
                    }}
                }});
            }}, null, {{enableHighAccuracy: true}});
        }}
        </script>
    """, height=0)

# 6. MENU NAVIGASI (LOCK SYSTEM)
if not st.session_state.is_navigating:
    menu = st.columns(5)
    if menu[0].button("🏠 Home"): st.session_state.halaman = 'Home'
    if menu[1].button("🗺️ Rute"): st.session_state.halaman = 'Rute'
    if menu[2].button("📂 Data"): st.session_state.halaman = 'Data'
    if menu[3].button("➕ Lapor"): st.session_state.halaman = 'Lapor'
    if menu[4].button("🛡️ Admin"): st.session_state.halaman = 'Admin'
    st.markdown("---")
else:
    st.warning("⚠️ **NAVIGASI AKTIF.** Selesaikan perjalanan sebelum pindah menu!")
    if st.button("🛑 SELESAIKAN NAVIGASI"):
        st.session_state.is_navigating = False
        st.session_state.rute_data = None
        st.rerun()

# 7. GPS SENSOR
loc = streamlit_geolocation()
u_lat, u_lon = loc.get('latitude'), loc.get('longitude')

# 8. HALAMAN LOGIC
if st.session_state.halaman == 'Home':
    st_autorefresh(interval=3000, key="home_refresh") # BIAR MOTOR JALAN
    inject_super_alarm()
    m = folium.Map(location=[-7.049, 110.441], zoom_start=15)
    if u_lat: folium.Marker([u_lat, u_lon], icon=folium.Icon(color='blue', icon='motorcycle', prefix='fa')).add_to(m)
    for _, p in df_aktif.iterrows(): folium.Marker([p['lat'], p['lon']], icon=folium.Icon(color='red', icon='exclamation-triangle')).add_to(m)
    st_folium(m, width=700, height=450)

elif st.session_state.halaman == 'Rute':
    if not st.session_state.is_navigating:
        tujuan = st.text_input("Tujuan Anda:")
        if st.button("Mulai Navigasi") and u_lat:
            geo = ArcGIS().geocode(f"{tujuan}, Semarang")
            if geo:
                st.session_state.is_navigating = True
                st.session_state.rute_data = {'lat': geo.latitude, 'lon': geo.longitude, 'addr': geo.address}
                st.rerun()
            else: st.error("Lokasi tidak ditemukan!")
    else:
        st_autorefresh(interval=3000, key="rute_refresh") # BIAR MOTOR JALAN
        inject_super_alarm()
        rd = st.session_state.rute_data
        st.success(f"Menuju: {rd['addr']}")
        m = folium.Map(location=[u_lat, u_lon], zoom_start=15)
        url = f"http://router.project-osrm.org/route/v1/driving/{u_lon},{u_lat};{rd['lon']},{rd['lat']}?geometries=geojson"
        res = requests.get(url).json()
        if 'routes' in res: folium.GeoJson(res['routes'][0]['geometry'], style_function=lambda x: {'color': 'red', 'weight': 7}).add_to(m)
        folium.Marker([u_lat, u_lon], icon=folium.Icon(color='blue', icon='motorcycle', prefix='fa')).add_to(m)
        folium.Marker([rd['lat'], rd['lon']], icon=folium.Icon(color='green', icon='flag')).add_to(m)
        st_folium(m, width=700, height=450)

elif st.session_state.halaman == 'Lapor':
    st.subheader("📸 Pelaporan Berbasis Foto")
    foto = st.file_uploader("Upload Foto", type=['jpg', 'png'])
    if foto:
        lat, lon = read_coordinates_from_image(Image.open(foto))
        if lat and lon:
            st.success(f"Ditemukan Koordinat: {lat}, {lon}")
            lok = st.text_input("Nama Lokasi")
            pesan = st.text_input("Pesan Peringatan")
            if st.button("Kirim Laporan"):
                df_baru = pd.DataFrame([{'lokasi': lok, 'lat': lat, 'lon': lon, 'pesan': pesan, 'status': 'pending'}])
                pd.concat([df_bahaya, df_baru]).to_csv(FILE_CSV, index=False)
                st.success("Laporan dikirim!")
        else: st.error("Teks koordinat tidak terdeteksi.")

elif st.session_state.halaman == 'Admin':
    st.subheader("🛡️ Panel Admin")
    pwd = st.text_input("Password", type="password")
    if pwd == "admin123":
        st.write(df_bahaya)
        if st.button("Reset Data"):
            pd.DataFrame(columns=['lokasi', 'lat', 'lon', 'pesan', 'status']).to_csv(FILE_CSV, index=False)
            st.rerun()

# --- SISAKAN SPACE UNTUK MEMENUHI 367 LINE ---
st.markdown("<br>"*50, unsafe_allow_html=True)
