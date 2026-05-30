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

# 1. PENGATURAN HALAMAN
st.set_page_config(page_title="Safe-Drive", layout="centered", page_icon="🛡️")

hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            .block-container {
                padding-top: 1rem;
                padding-bottom: 1rem;
            }
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

FILE_CSV = 'hasil_survei_tembalang.csv'

# ==========================================
# 🚀 FUNGSI AI PEMBACA TEKS KOORDINAT (OCR)
# ==========================================
def read_coordinates_from_image(img):
    try:
        text = pytesseract.image_to_string(img)
        matches = re.findall(r'-?\d{1,3}\.\d{4,}', text)
        if len(matches) >= 2:
            val1 = float(matches[0])
            val2 = float(matches[1])
            if abs(val1) < 90 and abs(val2) > 90: return val1, val2
            elif abs(val2) < 90 and abs(val1) > 90: return val2, val1
        return None, None
    except: return None, None

def load_csv():
    if os.path.exists(FILE_CSV):
        df = pd.read_csv(FILE_CSV)
        if 'status' not in df.columns:
            df['status'] = 'approved'
            df.to_csv(FILE_CSV, index=False)
        return df
    else: return pd.DataFrame(columns=['lokasi', 'lat', 'lon', 'pesan', 'status'])

df_bahaya = load_csv()
df_aktif = df_bahaya[df_bahaya['status'] == 'approved'].copy()

# ==========================================
# INISIALISASI OTAK MEMORI
# ==========================================
if 'halaman' not in st.session_state: st.session_state.halaman = 'Home'
if 'rute_data' not in st.session_state: st.session_state.rute_data = None 
if 'role' not in st.session_state: st.session_state.role = 'User'

# HEADER & MENU NAVIGASI
st.markdown("<h3 style='text-align: center; color: #E74C3C; margin-bottom: 10px;'>🛡️ Safe-Drive</h3>", unsafe_allow_html=True)

col1, col2, col3, col4, col5 = st.columns(5)
if col1.button("🏠 Home", use_container_width=True): st.session_state.halaman = 'Home'
if col2.button("🗺️ Rute", use_container_width=True): st.session_state.halaman = 'Rute'
if col3.button("📂 Data", use_container_width=True): st.session_state.halaman = 'Data'
if col4.button("➕ Lapor", use_container_width=True): st.session_state.halaman = 'Lapor'

if st.session_state.role == 'Admin':
    if col5.button("🛡️ Admin", use_container_width=True): st.session_state.halaman = 'Admin'
else:
    if col5.button("🔐 Login", use_container_width=True): st.session_state.halaman = 'Login'
st.markdown("---")

# 📡 SENSOR GPS GLOBAL
user_lat, user_lon = None, None
if st.session_state.halaman in ['Home', 'Lapor', 'Rute']: 
    col_teks, col_gps = st.columns([1, 2])
    col_teks.markdown("**📡 Sensor GPS Anda:**")
    with col_gps:
        location = streamlit_geolocation()
        user_lat = location.get('latitude')
        user_lon = location.get('longitude')

# ==========================================
# 🌟 JS INJECTION: SUPER ALARM HARDWARE
# ==========================================
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
            const a = Math.sin(dLat/2) * Math.sin(dLat/2) + Math.cos(lat1*(Math.PI/180)) * Math.cos(lat2*(Math.PI/180)) * Math.sin(dLon/2) * Math.sin(dLon/2);
            return R * (2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a)));
        }}

        let alarmActive = false;
        let overlayDiv = null;
        const parentDoc = window.parent.document; 

        if (navigator.geolocation) {{
            navigator.geolocation.watchPosition(
                function(pos) {{
                    const uLat = pos.coords.latitude;
                    const uLon = pos.coords.longitude;
                    
                    let nearHazard = false;
                    let msg = "";
                    let locName = "";
                    let sisaJarak = 0;

                    for(let i=0; i<hazards.length; i++) {{
                        const dist = getDistance(uLat, uLon, hazards[i].lat, hazards[i].lon);
                        if(dist < 200) {{ 
                            nearHazard = true;
                            msg = hazards[i].pesan;
                            locName = hazards[i].lokasi;
                            sisaJarak = Math.round(dist);
                            break;
                        }}
                    }}

                    if (nearHazard && !alarmActive) {{
                        alarmActive = true;
                        
                        if(navigator.vibrate) navigator.vibrate([1000, 500, 1000, 500, 1000]);
                        
                        const audio = new Audio('https://www.soundjay.com/buttons/beep-01a.mp3');
                        audio.play().catch(e=>console.log("Audio diblokir browser"));
                        
                        overlayDiv = parentDoc.createElement('div');
                        overlayDiv.style.cssText = 'position:fixed;top:0;left:0;width:100vw;height:100vh;background-color:rgba(231,76,60,0.95);z-index:999999;display:flex;flex-direction:column;align-items:center;justify-content:center;color:white;text-align:center;pointer-events:none;';
                        
                        overlayDiv.innerHTML = '<h1 style="font-size:3rem;margin:0;animation:blinker 0.4s linear infinite;">⚠️ AWAS BAHAYA ⚠️</h1>' +
                                               '<h2 style="margin:10px 0;">Sisa ' + sisaJarak + ' m ke ' + locName + '</h2>' +
                                               '<p style="font-size:1.5rem;font-style:italic;">"' + msg + '"</p>';
                        
                        let style = parentDoc.createElement('style');
                        style.innerHTML = '@keyframes blinker {{ 50% {{ opacity: 0; }} }}';
                        overlayDiv.appendChild(style);
                        parentDoc.body.appendChild(overlayDiv);

                    }} else if (!nearHazard && alarmActive) {{
                        alarmActive = false;
                        if(overlayDiv) {{
                            parentDoc.body.removeChild(overlayDiv);
                            overlayDiv = null;
                        }}
                    }}
                }},
                function(err) {{ console.log(err); }},
                {{enableHighAccuracy: true, maximumAge: 2000, timeout: 5000}} 
            );
        }}
        </script>
    """, height=0, width=0)

# ==========================================
# HALAMAN LOGIN ADMIN
# ==========================================
if st.session_state.halaman == 'Login':
    st.subheader("🔐 Login Admin")
    with st.form("form_login"):
        pwd = st.text_input("Password", type="password")
        if st.form_submit_button("Masuk") and pwd == "admin123":
            st.session_state.role, st.session_state.halaman = 'Admin', 'Admin'
            st.rerun()

# ==========================================
# HALAMAN HOME
# ==========================================
elif st.session_state.halaman == 'Home':
    inject_super_alarm() 
    
    m = folium.Map(location=[-7.049, 110.441], zoom_start=15)
    plugins.LocateControl(auto_start=True, position='bottomright', strings={'title': 'Lokasi Saya', 'popup': 'Anda di sini'}, flyTo=True).add_to(m)

    for _, p in df_aktif.iterrows():
        folium.Marker([p['lat'], p['lon']], popup=p['lokasi'], tooltip=p['pesan'], icon=folium.Icon(color='red', icon='exclamation-triangle')).add_to(m)
    
    if user_lat and user_lon:
        folium.Marker([user_lat, user_lon], popup="Posisi Motor", icon=folium.Icon(color='blue', icon='motorcycle', prefix='fa')).add_to(m)
    
    st_folium(m, width=700, height=450, returned_objects=[])

# ==========================================
# HALAMAN RUTE
# ==========================================
elif st.session_state.halaman == 'Rute':
    st.subheader("📍 Navigasi Rute Live")
    
    if not st.session_state.rute_data:
        st.info("Ketik lokasi tujuan. Rute akan otomatis menghindari atau menandai bahaya.")
        with st.form("form_cek_rute"):
            tujuan = st.text_input("Mau ke mana? (Contoh: UNDIP Tembalang)")
            submit_rute = st.form_submit_button("Cari Rute & Mulai Jalan")

        if submit_rute and tujuan:
            if not user_lat or not user_lon:
                st.error("⚠️ Tolong klik ikon Target (Sensor GPS) di atas dulu sebelum mencari rute!")
            else:
                geolocator = ArcGIS() 
                with st.spinner("Menganalisis tujuan dari lokasi Anda..."):
                    try:
                        query_lokasi = f"{tujuan}, Semarang, Jawa Tengah, Indonesia"
                        lokasi_tujuan = geolocator.geocode(query_lokasi)
                        if lokasi_tujuan:
                            st.session_state.rute_data = {
                                'nama_tujuan': lokasi_tujuan.address, 
                                'dest_lat': lokasi_tujuan.latitude, 
                                'dest_lon': lokasi_tujuan.longitude
                            }
                            st.rerun() 
                        else: st.error("Lokasi tidak ditemukan.")
                    except Exception as e: st.error("Terjadi kesalahan sistem pencarian.")

    if st.session_state.rute_data:
        inject_super_alarm() 
        
        rd = st.session_state.rute_data
        col_info, col_btn = st.columns([3, 1])
        col_info.success(f"Menuju: {rd['nama_tujuan']}")
        if col_btn.button("🛑 Selesai"): 
            st.session_state.rute_data = None
            st.rerun()

        start_lat = user_lat if user_lat else -7.049000
        start_lon = user_lon if user_lon else 110.441000

        m_rute = folium.Map(location=[start_lat, start_lon], zoom_start=15) 
        plugins.LocateControl(auto_start=True, position='bottomright', strings={'title': 'Lokasi', 'popup': 'Anda di sini'}, flyTo=True).add_to(m_rute)

        url = f"http://router.project-osrm.org/route/v1/driving/{start_lon},{start_lat};{rd['dest_lon']},{rd['dest_lat']}?overview=full&geometries=geojson&alternatives=2"
        try:
            res = requests.get(url)
            if res.status_code == 200:
                semua_rute = res.json().get("routes", [])
                for idx, rute in enumerate(semua_rute):
                    route_coords = rute["geometry"]["coordinates"]
                    bahaya_dilewati = []
                    
                    for _, p in df_aktif.iterrows():
                        for coord in route_coords:
                            if geodesic((p['lat'], p['lon']), (coord[1], coord[0])).meters < 200:
                                bahaya_dilewati.append(p.to_dict()); break 

                    is_primary = (idx == 0)
                    
                    warna = '#0078FF'
                    if not is_primary: warna = '#95A5A6'
                    if bahaya_dilewati and is_primary: warna = '#E74C3C'

                    folium.GeoJson(rute["geometry"], style_function=lambda x, c=warna, w=7 if is_primary else 5: {'color': c, 'weight': w, 'opacity': 0.8}).add_to(m_rute)

                    if is_primary and bahaya_dilewati:
                        st.error(f"⚠️ RUTE MENGARAH KE DAERAH RAWAN! (Garis Merah)")
                        for b in bahaya_dilewati:
                            folium.Marker([b['lat'], b['lon']], tooltip=b['pesan'], icon=folium.Icon(color='red', icon='exclamation-triangle')).add_to(m_rute)
                    elif is_primary and not bahaya_dilewati:
                        st.success("✅ Rute Terpantau Aman! (Garis Biru)")
        except: pass

        folium.Marker([rd['dest_lat'], rd['dest_lon']], popup=rd['nama_tujuan'], icon=folium.Icon(color='green', icon='flag')).add_to(m_rute)
        if user_lat and user_lon: 
            folium.Marker([user_lat, user_lon], popup="Posisi Anda", icon=folium.Icon(color='blue', icon='motorcycle', prefix='fa')).add_to(m_rute)
            
        st_folium(m_rute, width=700, height=450, returned_objects=[])

# ==========================================
# HALAMAN DATA
# ==========================================
elif st.session_state.halaman == 'Data':
    st.subheader("Database Titik Bahaya Terverifikasi")
    if not df_aktif.empty:
        df_tampil = df_aktif.drop(columns=['jarak', 'status'], errors='ignore') 
        st.dataframe(df_tampil, use_container_width=True)
    else: st.info("Belum ada data titik bahaya yang disetujui.")

# ==========================================
# HALAMAN LAPOR 
# ==========================================
elif st.session_state.halaman == 'Lapor':
    st.subheader("📸 Pelaporan Berbasis Teks Koordinat Foto")
    st.warning("Gunakan aplikasi kamera GPS. Mesin akan membaca teks koordinat yang tertulis di foto!")
    
    foto_upload = st.file_uploader("Pilih File Foto Kejadian", type=['jpg', 'jpeg', 'png'])
    
    if foto_upload is not None:
        try:
            img = Image.open(foto_upload)
            with st.spinner("AI sedang membaca teks koordinat di foto Anda..."):
                exif_lat, exif_lon = read_coordinates_from_image(img)
            
            if exif_lat and exif_lon:
                st.success(f"✅ AI Berhasil membaca teks! (Lat: {exif_lat:.5f}, Lon: {exif_lon:.5f})")
                with st.form("form_tambah_geotag"):
                    new_lok = st.text_input("Nama Lokasi")
                    st.text_input("Latitude", value=f"{exif_lat:.6f}", disabled=True)
                    st.text_input("Longitude", value=f"{exif_lon:.6f}", disabled=True)
                    new_pesan = st.text_input("Pesan Peringatan")
                    if st.form_submit_button("Kirim Laporan"):
                        if new_lok and new_pesan:
                            data_baru = pd.DataFrame([{"lokasi": new_lok, "lat": exif_lat, "lon": exif_lon, "pesan": new_pesan, "status": "pending"}])
                            df_simpan = pd.concat([df_bahaya, data_baru], ignore_index=True)
                            df_simpan.to_csv(FILE_CSV, index=False)
                            st.success("Laporan berhasil dikirim ke Admin.")
            else: 
                st.error("❌ TEKS TIDAK DITEMUKAN: Pastikan di foto Anda tertulis angka koordinat desimal.")
        except Exception as e: st.error("Gagal menjalankan AI pembaca teks.")

# ==========================================
# 🛡️ HALAMAN KHUSUS ADMIN
# ==========================================
elif st.session_state.halaman == 'Admin':
    if st.session_state.role != 'Admin': st.error("Anda tidak memiliki akses.")
    else:
        col_judul, col_logout = st.columns([3, 1])
        col_judul.subheader("🛡️ Panel Admin")
        if col_logout.button("🚪 Logout"):
            st.session_state.role, st.session_state.halaman = 'User', 'Home'
            st.rerun()

        st.markdown("#### ⏳ Laporan Menunggu")
        df_pending = df_bahaya[df_bahaya['status'] == 'pending']
        if not df_pending.empty:
            for index, row in df_pending.iterrows():
                col_teks, col_acc, col_tolak = st.columns([3, 1, 1])
                info_text = f"**{row['lokasi']}** | {row['pesan']} [🗺️ Cek Google Maps](https://www.google.com/maps?q={row['lat']},{row['lon']})"
                col_teks.info(info_text)
                
                if col_acc.button("✅", key=f"acc_{index}"):
                    df_bahaya.at[index, 'status'] = 'approved'
                    df_bahaya.to_csv(FILE_CSV, index=False)
                    st.rerun()
                if col_tolak.button("❌", key=f"tolak_{index}"):
                    df_bahaya = df_bahaya.drop(index)
                    df_bahaya.to_csv(FILE_CSV, index=False)
                    st.rerun()
        else: st.success("Aman! Tidak ada laporan pending.")

        st.markdown("#### 🗑️ Hapus Titik")
        if not df_aktif.empty:
            with st.form("form_hapus_admin"):
                pilihan_aktif = df_aktif.apply(lambda x: f"{x['lokasi']}", axis=1)
                pilih_hapus_str = st.selectbox("Pilih lokasi yang mau dihapus:", pilihan_aktif)
                if st.form_submit_button("Cabut Titik"):
                    df_bahaya = df_bahaya[df_bahaya['lokasi'] != pilih_hapus_str]
                    df_bahaya.to_csv(FILE_CSV, index=False)
                    st.success("Titik dicabut dari peta!")
