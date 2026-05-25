import streamlit as st
import pandas as pd
import folium
from folium import plugins # <--- KITA PAKAI PLUGIN DEWA INI BIAR BISA GERAK
import os
import requests
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from streamlit_folium import st_folium
from streamlit_geolocation import streamlit_geolocation
from geopy.distance import geodesic
from geopy.geocoders import ArcGIS
from streamlit_autorefresh import st_autorefresh

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
# FUNGSI PEMBONGKAR EXIF FOTO
# ==========================================
def get_exif_location(img):
    try:
        exif = img._getexif()
        if not exif: return None, None
        geotagging = {}
        for (idx, tag) in TAGS.items():
            if tag == 'GPSInfo':
                if idx not in exif: return None, None
                for (key, val) in GPSTAGS.items():
                    if key in exif[idx]:
                        geotagging[val] = exif[idx][key]
        if 'GPSLatitude' not in geotagging or 'GPSLongitude' not in geotagging: return None, None
        def convert_to_degrees(value):
            d = float(value[0])
            m = float(value[1])
            s = float(value[2])
            return d + (m / 60.0) + (s / 3600.0)
        lat = convert_to_degrees(geotagging['GPSLatitude'])
        if geotagging.get('GPSLatitudeRef', 'N') != 'N': lat = -lat
        lon = convert_to_degrees(geotagging['GPSLongitude'])
        if geotagging.get('GPSLongitudeRef', 'E') != 'E': lon = -lon
        return lat, lon
    except Exception as e: return None, None

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

# INISIALISASI OTAK MEMORI & ROLE
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
if st.session_state.halaman in ['Home', 'Lapor']: 
    col_teks, col_gps = st.columns([1, 2])
    col_teks.markdown("**📡 Sensor GPS Alarm:**")
    with col_gps:
        location = streamlit_geolocation()
        user_lat = location.get('latitude')
        user_lon = location.get('longitude')

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
    st_autorefresh(interval=3000, key="home_refresh") 
    m = folium.Map(location=[-7.049, 110.441], zoom_start=15)
    
    # 🌟 MAGIC: Plugin ini bikin titik biru lu gerak mulus kayak Google Maps!
    plugins.LocateControl(auto_start=True, position='bottomright', strings={'title': 'Lokasi Saya', 'popup': 'Anda di sini'}, flyTo=True).add_to(m)

    if user_lat and user_lon:
        if not df_aktif.empty:
            df_aktif['jarak'] = df_aktif.apply(lambda row: geodesic((user_lat, user_lon), (row['lat'], row['lon'])).meters, axis=1)
            titik_terdekat = df_aktif.loc[df_aktif['jarak'].idxmin()]
            
            if titik_terdekat['jarak'] < 200:
                st.error(f"⚠️ BAHAYA: Dekat {titik_terdekat['lokasi']} (Sisa {int(titik_terdekat['jarak'])}m)!")
                st.components.v1.html("""<script>var audio = new Audio('https://www.soundjay.com/buttons/beep-01a.mp3'); audio.play();</script>""", height=0)
            else:
                st.info(f"Titik terdekat: {titik_terdekat['lokasi']} ({int(titik_terdekat['jarak'])}m)")

    for _, p in df_aktif.iterrows():
        folium.Marker([p['lat'], p['lon']], popup=p['lokasi'], tooltip=p['pesan'], icon=folium.Icon(color='red', icon='exclamation-triangle')).add_to(m)
    st_folium(m, width=700, height=450, returned_objects=[])

# ==========================================
# HALAMAN RUTE (NAVIGASI)
# ==========================================
elif st.session_state.halaman == 'Rute':
    st.subheader("📍 Navigasi Rute")
    
    # Refresh dimatikan biar lu ngetik ngga keganggu berkedip!
    if not st.session_state.rute_data:
        st.info("Ketik lokasi tujuan. (Otomatis nyari di area Semarang & sekitarnya)")
        with st.form("form_cek_rute"):
            tujuan = st.text_input("Mau ke mana? (Contoh: UNDIP Tembalang)")
            submit_rute = st.form_submit_button("Cari Rute & Mulai Jalan")

        if submit_rute and tujuan:
            geolocator = ArcGIS() 
            with st.spinner("Menyiapkan rute navigasi..."):
                try:
                    # 🌟 MAGIC 2: Kunci area pencarian di Semarang biar ngga nyasar ke luar kota
                    query_lokasi = f"{tujuan}, Semarang, Jawa Tengah, Indonesia"
                    lokasi_tujuan = geolocator.geocode(query_lokasi)
                    
                    if lokasi_tujuan:
                        dest_lat, dest_lon = lokasi_tujuan.latitude, lokasi_tujuan.longitude
                        
                        # Posisikan titik awal navigasi dari tengah Tembalang jika GPS belum nyala
                        start_lat = user_lat if user_lat else -7.049000
                        start_lon = user_lon if user_lon else 110.441000

                        url = f"http://router.project-osrm.org/route/v1/driving/{start_lon},{start_lat};{dest_lon},{dest_lat}?overview=full&geometries=geojson"
                        res = requests.get(url)
                        if res.status_code == 200:
                            route_coords = res.json()["routes"][0]["geometry"]["coordinates"]
                            bahaya_dilewati = []
                            for _, p in df_aktif.iterrows():
                                for coord in route_coords:
                                    if geodesic((p['lat'], p['lon']), (coord[1], coord[0])).meters < 200:
                                        bahaya_dilewati.append(p.to_dict()); break 

                            st.session_state.rute_data = {
                                'nama_tujuan': lokasi_tujuan.address, 'dest_lat': dest_lat, 'dest_lon': dest_lon,
                                'geojson': res.json()["routes"][0]["geometry"], 'bahaya': bahaya_dilewati
                            }
                            st.rerun() 
                        else: st.error("Server rute OSRM gagal merespons.")
                    else: st.error("Lokasi tidak ditemukan di area Semarang. Coba kata kunci lain.")
                except Exception as e: st.error("Terjadi kesalahan sistem pencarian.")

    if st.session_state.rute_data:
        rd = st.session_state.rute_data
        col_info, col_btn = st.columns([3, 1])
        col_info.success(f"Menuju: {rd['nama_tujuan']}")
        if col_btn.button("🛑 Selesai"): st.session_state.rute_data = None; st.rerun()

        m_rute = folium.Map(location=[-7.049, 110.441], zoom_start=15) 
        
        # 🌟 MAGIC 3: Tracker GPS Live diaktifkan di halaman Rute!
        plugins.LocateControl(auto_start=True, position='bottomright', strings={'title': 'Lokasi Saya', 'popup': 'Anda di sini'}, flyTo=True).add_to(m_rute)

        warna_rute = '#E74C3C' if rd['bahaya'] else '#2ECC71' 
        if rd['bahaya']: st.error(f"⚠️ PERINGATAN! Rute ini melewati {len(rd['bahaya'])} titik rawan.")

        folium.GeoJson(rd['geojson'], name="Jalur", style_function=lambda x: {'color': warna_rute, 'weight': 7, 'opacity': 0.8}).add_to(m_rute)
        folium.Marker([rd['dest_lat'], rd['dest_lon']], popup=rd['nama_tujuan'], icon=folium.Icon(color='green', icon='flag')).add_to(m_rute)
        for b in rd['bahaya']: folium.Marker([b['lat'], b['lon']], tooltip=b['pesan'], icon=folium.Icon(color='red', icon='exclamation-triangle')).add_to(m_rute)
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
    st.subheader("📸 Pelaporan Berbasis Geotag")
    st.warning("PENTING: Sistem hanya menerima foto asli dari kamera HP yang memiliki data koordinat GPS (Geotag).")
    foto_upload = st.file_uploader("Pilih File Foto Kejadian", type=['jpg', 'jpeg', 'png'])
    
    if foto_upload is not None:
        try:
            img = Image.open(foto_upload)
            exif_lat, exif_lon = get_exif_location(img)
            if exif_lat and exif_lon:
                st.success(f"✅ Data GPS Tervalidasi! (Lat: {exif_lat:.5f}, Lon: {exif_lon:.5f})")
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
            else: st.error("❌ FOTO DITOLAK: Tidak mengandung data GPS.")
        except Exception as e: st.error("Masalah saat memproses foto.")

# ==========================================
# HALAMAN KHUSUS ADMIN 
# ==========================================
elif st.session_state.halaman == 'Admin':
    if st.session_state.role != 'Admin': st.error("Anda tidak memiliki akses ke halaman ini.")
    else:
        col_judul, col_logout = st.columns([3, 1])
        col_judul.subheader("🛡️ Panel Validasi Admin")
        if col_logout.button("🚪 Logout"):
            st.session_state.role, st.session_state.halaman = 'User', 'Home'
            st.rerun()

        st.markdown("#### ⏳ Laporan Menunggu")
        df_pending = df_bahaya[df_bahaya['status'] == 'pending']
        if not df_pending.empty:
            for index, row in df_pending.iterrows():
                col_teks, col_acc, col_tolak = st.columns([3, 1, 1])
                col_teks.info(f"**{row['lokasi']}** | {row['pesan']}")
                if col_acc.button("✅ Terima", key=f"acc_{index}"):
                    df_bahaya.at[index, 'status'] = 'approved'
                    df_bahaya.to_csv(FILE_CSV, index=False)
                    st.rerun()
                if col_tolak.button("❌ Tolak", key=f"tolak_{index}"):
                    df_bahaya = df_bahaya.drop(index)
                    df_bahaya.to_csv(FILE_CSV, index=False)
                    st.rerun()
        else: st.success("Tidak ada antrean laporan.")

        st.markdown("#### 🗑️ Hapus Titik Aktif")
        if not df_aktif.empty:
            with st.form("form_hapus_admin"):
                pilih_hapus = st.selectbox("Pilih lokasi:", df_aktif['lokasi'])
                if st.form_submit_button("Cabut Titik"):
                    df_bahaya = df_bahaya[df_bahaya['lokasi'] != pilih_hapus]
                    df_bahaya.to_csv(FILE_CSV, index=False)
                    st.success("Berhasil dihapus!")
        csv_data = df_bahaya.to_csv(index=False).encode('utf-8')
        st.download_button("⬇️ Download CSV", data=csv_data, file_name=FILE_CSV, mime='text/csv')
