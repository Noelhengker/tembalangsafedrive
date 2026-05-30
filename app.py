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

st.set_page_config(page_title="Safe-Drive", layout="centered", page_icon="🛡️")

FILE_CSV = 'hasil_survei_tembalang.csv'

# PENGATURAN CSS UNTUK HIDE HEADER
st.markdown("""<style>
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    .block-container {padding-top: 1rem; padding-bottom: 1rem;}
</style>""", unsafe_allow_html=True)

# LOAD & PROTEKSI CSV
def load_csv():
    if os.path.exists(FILE_CSV):
        df = pd.read_csv(FILE_CSV)
        if 'status' not in df.columns:
            df['status'] = 'approved'
            df.to_csv(FILE_CSV, index=False)
        return df
    else: 
        return pd.DataFrame(columns=['lokasi', 'lat', 'lon', 'pesan', 'status'])

df_bahaya = load_csv()
df_aktif = df_bahaya[df_bahaya['status'] == 'approved'].copy() if not df_bahaya.empty else pd.DataFrame()

# JS INJECTION UNTUK ALARM (FIXED ESCAPING)
def inject_super_alarm():
    if df_aktif.empty: return
    hazards_json = json.dumps(df_aktif[['lat', 'lon', 'pesan', 'lokasi']].to_dict(orient='records'))
    components.html(f"""
        <script>
        const hazards = {hazards_json};
        function getDistance(lat1, lon1, lat2, lon2) {{
            const R = 6371000;
            const dLat = (lat2-lat1) * (Math.PI/180);
            const dLon = (lon2-lon1) * (Math.PI/180);
            const a = Math.sin(dLat/2)*Math.sin(dLat/2) + Math.cos(lat1*(Math.PI/180))*Math.cos(lat2*(Math.PI/180))*Math.sin(dLon/2)*Math.sin(dLon/2);
            return R * (2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a)));
        }}
        if (navigator.geolocation) {{
            navigator.geolocation.watchPosition(function(pos) {{
                const uLat = pos.coords.latitude;
                const uLon = pos.coords.longitude;
                hazards.forEach(h => {{
                    if(getDistance(uLat, uLon, h.lat, h.lon) < 200) {{
                        if(navigator.vibrate) navigator.vibrate([1000]);
                        const a = new Audio('https://www.soundjay.com/buttons/beep-01a.mp3');
                        a.play();
                    }}
                }});
            }}, null, {{enableHighAccuracy: true}});
        }}
        </script>
    """, height=0, width=0)

# MENU NAVIGASI
if 'halaman' not in st.session_state: st.session_state.halaman = 'Home'
menu = st.columns(4)
if menu[0].button("🏠 Home"): st.session_state.halaman = 'Home'
if menu[1].button("🗺️ Rute"): st.session_state.halaman = 'Rute'
if menu[2].button("📂 Data"): st.session_state.halaman = 'Data'
if menu[3].button("➕ Lapor"): st.session_state.halaman = 'Lapor'

# SENSOR GPS
loc = streamlit_geolocation()
u_lat, u_lon = loc.get('latitude'), loc.get('longitude')

if st.session_state.halaman == 'Home':
    inject_super_alarm()
    m = folium.Map(location=[-7.049, 110.441], zoom_start=15)
    if u_lat: folium.Marker([u_lat, u_lon], icon=folium.Icon(color='blue', icon='motorcycle', prefix='fa')).add_to(m)
    for _, p in df_aktif.iterrows(): folium.Marker([p['lat'], p['lon']], icon=folium.Icon(color='red', icon='exclamation-triangle')).add_to(m)
    st_folium(m, width=700, height=450)

elif st.session_state.halaman == 'Rute':
    inject_super_alarm()
    tujuan = st.text_input("Tujuan Anda:")
    if st.button("Cari Rute") and u_lat:
        geo = ArcGIS().geocode(f"{tujuan}, Semarang")
        if geo:
            m = folium.Map(location=[u_lat, u_lon], zoom_start=15)
            url = f"http://router.project-osrm.org/route/v1/driving/{u_lon},{u_lat};{geo.longitude},{geo.latitude}?geometries=geojson"
            res = requests.get(url).json()
            if 'routes' in res: folium.GeoJson(res['routes'][0]['geometry'], style_function=lambda x: {'color': 'red', 'weight': 7}).add_to(m)
            folium.Marker([u_lat, u_lon], icon=folium.Icon(color='blue')).add_to(m)
            folium.Marker([geo.latitude, geo.longitude], icon=folium.Icon(color='green')).add_to(m)
            st_folium(m, width=700, height=450)
        else: st.error("Lokasi tidak ditemukan!")

elif st.session_state.halaman == 'Lapor':
    foto = st.file_uploader("Upload Foto Koordinat", type=['jpg', 'jpeg', 'png'])
    if foto:
        st.success("Foto berhasil diunggah!")
        # (Logika OCR dipersingkat agar tidak error)

elif st.session_state.halaman == 'Admin':
    st.subheader("🛡️ Panel Admin")
    st.write("Data diatur dari CSV langsung.")
