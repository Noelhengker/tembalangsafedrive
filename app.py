import streamlit as st
import pandas as pd
import folium
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
        
        if 'GPSLatitude' not in geotagging or 'GPSLongitude' not in geotagging:
            return None, None

        def convert_to_degrees(value):
            d = float(value[0])
            m = float(value[1])
            s = float(value[2])
            return d + (m / 60.0) + (s / 3600.0)

        lat = convert_to_degrees(geotagging['GPSLatitude'])
        if geotagging['GPSLatitudeRef'] != 'N': lat = -lat
        
        lon = convert_to_degrees(geotagging['GPSLongitude'])
        if geotagging['GPSLongitudeRef'] != 'E': lon = -lon
        
        return lat, lon
    except:
        return None, None

# 2. BACA DATA CSV
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
df_aktif = df_bahaya[df_bahaya['status'] == 'approved'].copy()

# ==========================================
# INISIALISASI OTAK MEMORI & ROLE
# ==========================================
if 'halaman' not in st.session_state:
    st.session_state.halaman = 'Home'
if 'rute_data' not in st.session_state:
    st.session_state.rute_data = None 
if 'role' not in st.session_state:
    st.session_state.role = 'User'

# 3. HEADER APLIKASI
st.markdown("<h3 style='text-align: center; color: #E74C3C; margin-bottom: 10px;'>🛡️ Safe-Drive</h3>", unsafe_allow_html=True)

# 4. MENU NAVIGASI (Login pindah ke menu utama 5 kolom)
col1, col2, col3, col4, col5 = st.columns(5)

if col1.button("🏠 Home", use_container_width=True): st.session_state.halaman = 'Home'
if col2.button("🗺️ Rute", use_container_width=True): st.session_state.halaman = 'Rute'
if col3.button("📂 Data", use_container_width=True): st.session_state.halaman = 'Data'
if col4.button("➕ Lapor", use_container_width=True): st.session_state.halaman = 'Lapor'

# Tombol ke-5 berubah wujud tergantung status login
if st.session_state.role == 'Admin':
    if col5.button("🛡️ Admin", use_container_width=True): st.session_state.halaman = 'Admin'
else:
    if col5.button("🔐 Login", use_container_width=True): st.session_state.halaman = 'Login'

st.markdown("---")

# ==========================================
# HALAMAN LOGIN ADMIN
# ==========================================
if st.session_state.halaman == 'Login':
    st.subheader("🔐 Login Admin")
    st.info("Halaman ini khusus untuk verifikator lapangan.")
    with st.form("form_login"):
        pwd = st.text_input("Password", type="password")
        submit_login = st.form_submit_button("Masuk")
        
        if submit_login:
            if pwd == "admin123":
                st.session_state.role = 'Admin'
                st.session_state.halaman = 'Admin' # Otomatis langsung lompat ke halaman Admin
                st.rerun()
            else:
                st.error("Password salah!")

# ==========================================
# HALAMAN HOME
# ==========================================
elif st.session_state.halaman == 'Home':
    st_autorefresh(interval=2000, key="home_refresh") 
    
    st.markdown("**Status GPS Anda:**")
    # PERBAIKAN: Menambahkan parameter KEY agar tidak hilang
    location = streamlit_geolocation(key="gps_home")
    user_lat = location.get('latitude')
    user_lon = location.get('longitude')

    m = folium.Map(location=[-7.049, 110.441], zoom_start=15)

    if user_lat and user_lon:
        st.success(f"Sinyal Terkunci: {user_lat:.5f}, {user_lon:.5f}")
        if not df_aktif.empty:
            df_aktif['jarak'] = df_aktif.apply(lambda row: geodesic((user_lat, user_lon), (row['lat'], row['lon'])).meters, axis=1)
            titik_terdekat = df_aktif.loc[df_aktif['jarak'].idxmin()]
            jarak_terdekat = titik_terdekat['jarak']
            
            if jarak_terdekat < 200:
                st.error(f"⚠️ BAHAYA: Anda mendekati {titik_terdekat['lokasi']} (Sisa {int(jarak_terdekat)} meter)!")
                st.warning(f"Instruksi: {titik_terdekat['pesan']}")
                st.components.v1.html("""<script>var audio = new Audio('https://www.soundjay.com/buttons/beep-01a.mp3'); audio.play();</script>""", height=0)
            else:
                st.info(f"Titik rawan terdekat: {titik_terdekat['lokasi']} (Berjarak {int(jarak_terdekat)} meter)")

            url = f"http://router.project-osrm.org/route/v1/driving/{user_lon},{user_lat};{titik_terdekat['lon']},{titik_terdekat['lat']}?overview=full&geometries=geojson"
            try:
                res = requests.get(url)
                if res.status_code == 200:
                    folium.GeoJson(res.json()["routes"][0]["geometry"], name="Rute Navigasi", style_function=lambda x: {'color': '#0078FF', 'weight': 7, 'opacity': 0.8}).add_to(m)
            except: pass

        folium.Marker([user_lat, user_lon], popup="Posisi Motor", icon=folium.Icon(color='blue', icon='motorcycle', prefix='fa')).add_to(m)
    else:
        st.info("Menunggu sinyal GPS... Pastikan izin lokasi aktif.")

    for _, p in df_aktif.iterrows():
        folium.Marker([p['lat'], p['lon']], popup=p['lokasi'], tooltip=p['pesan'], icon=folium.Icon(color='red', icon='exclamation-triangle', prefix='fa')).add_to(m)
    st_folium(m, width=700, height=450, returned_objects=[])

# ==========================================
# HALAMAN RUTE
# ==========================================
elif st.session_state.halaman == 'Rute':
    st.subheader("📍 Navigasi Rute")
    sedang_navigasi = st.session_state.rute_data is not None

    if sedang_navigasi: st_autorefresh(interval=2000, key="rute_refresh")
    
    # PERBAIKAN: Menambahkan parameter KEY agar tidak hilang
    location = streamlit_geolocation(key="gps_rute")
    user_lat = location.get('latitude')
    user_lon = location.get('longitude')

    if not sedang_navigasi:
        st.info("Ketik lokasi tujuan untuk memulai navigasi.")
        with st.form("form_cek_rute"):
            tujuan = st.text_input("Mau ke mana? (Contoh: UNDIP Tembalang)")
            submit_rute = st.form_submit_button("Cari Rute & Mulai Jalan")

        if submit_rute and tujuan:
            if not user_lat or not user_lon: st.error("GPS belum terkunci. Tunggu sebentar lalu coba lagi.")
            else:
                geolocator = ArcGIS() 
                with st.spinner("Menyiapkan rute navigasi..."):
                    try:
                        lokasi_tujuan = geolocator.geocode(f"{tujuan}, Indonesia")
                        if lokasi_tujuan:
                            dest_lat = lokasi_tujuan.latitude
                            dest_lon = lokasi_tujuan.longitude
                            url = f"http://router.project-osrm.org/route/v1/driving/{user_lon},{user_lat};{dest_lon},{dest_lat}?overview=full&geometries=geojson"
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
                            else: st.error("Server rute gagal mencari jalan.")
                        else: st.error("Lokasi tidak ditemukan.")
                    except: st.error("Terjadi kesalahan sistem.")

    if sedang_navigasi:
        rd = st.session_state.rute_data
        col_info, col_btn = st.columns([3, 1])
        col_info.success(f"Menuju: {rd['nama_tujuan']}")
        if col_btn.button("🛑 Selesai"): st.session_state.rute_data = None; st.rerun()

        map_center_lat = user_lat if user_lat else rd.get('dest_lat', -7.049)
        map_center_lon = user_lon if user_lon else rd.get('dest_lon', 110.441)
        m_rute = folium.Map(location=[map_center_lat, map_center_lon], zoom_start=16) 
        
        warna_rute = '#E74C3C' if rd['bahaya'] else '#2ECC71' 
        if rd['bahaya']: st.error(f"⚠️ PERINGATAN! Rute ini melewati {len(rd['bahaya'])} titik rawan.")

        folium.GeoJson(rd['geojson'], name="Jalur", style_function=lambda x: {'color': warna_rute, 'weight': 7, 'opacity': 0.8}).add_to(m_rute)
        folium.Marker([rd['dest_lat'], rd['dest_lon']], popup=rd['nama_tujuan'], icon=folium.Icon(color='green', icon='flag')).add_to(m_rute)
        for b in rd['bahaya']: folium.Marker([b['lat'], b['lon']], tooltip=b['pesan'], icon=folium.Icon(color='red', icon='exclamation-triangle')).add_to(m_rute)
        if user_lat and user_lon: folium.Marker([user_lat, user_lon], popup="Posisi Motor", icon=folium.Icon(color='blue', icon='motorcycle', prefix='fa')).add_to(m_rute)
        st_folium(m_rute, width=700, height=450, returned_objects=[])

# ==========================================
# HALAMAN DATA
# ==========================================
elif st.session_state.halaman == 'Data':
    st.subheader("Database Titik Bahaya Terverifikasi")
    if not df_aktif.empty:
        df_tampil = df_aktif.drop(columns=['jarak', 'status'], errors='ignore') 
        st.metric(label="Total Titik Aktif", value=f"{len(df_tampil)} Lokasi")
        st.dataframe(df_tampil, use_container_width=True)
    else: st.info("Belum ada data titik bahaya yang disetujui.")

# ==========================================
# HALAMAN LAPOR 
# ==========================================
elif st.session_state.halaman == 'Lapor':
    st.subheader("📣 Laporkan Titik Rawan Baru")
    st.info("Punya foto kejadian? Upload di sini, sistem akan otomatis mendeteksi koordinat lokasinya!")
    
    foto_upload = st.file_uploader("Upload Foto Lokasi Kejadian (Opsional)", type=['jpg', 'jpeg'])
    
    default_lat = -7.049000
    default_lon = 110.441000

    if foto_upload is not None:
        try:
            img = Image.open(foto_upload)
            exif_lat, exif_lon = get_exif_location(img)
            
            if exif_lat and exif_lon:
                default_lat = exif_lat
                default_lon = exif_lon
                st.success(f"✅ Koordinat berhasil ditemukan dari foto! (Lat: {exif_lat:.5f}, Lon: {exif_lon:.5f})")
            else:
                st.warning("⚠️ Foto ini tidak mengandung data GPS. Silakan pakai fitur GPS di bawah.")
        except Exception as e:
            st.error("Terjadi kesalahan saat membaca foto.")

    st.markdown("---")
    st.write("**Atau klik tombol ini jika Anda sedang berada di lokasi kejadian:**")
    # PERBAIKAN: Menambahkan parameter KEY agar tidak hilang
    loc = streamlit_geolocation(key="gps_lapor")
    if loc.get('latitude'):
        default_lat = loc.get('latitude')
        default_lon = loc.get('longitude')
        st.success("✅ Koordinat HP Anda berhasil dikunci!")

    with st.form("form_tambah"):
        new_lok = st.text_input("Nama Lokasi (Contoh: Jalan Menurun Sigar Bencah)")
        new_lat = st.number_input("Latitude", format="%.6f", value=default_lat, step=0.000100)
        new_lon = st.number_input("Longitude", format="%.6f", value=default_lon, step=0.000100)
        new_pesan = st.text_input("Pesan Peringatan (Contoh: Jalanan berlubang cukup dalam di sisi kiri)")
        submit_tambah = st.form_submit_button("Kirim Laporan")

        if submit_tambah:
            if new_lok and new_pesan:
                data_baru = pd.DataFrame([{"lokasi": new_lok, "lat": new_lat, "lon": new_lon, "pesan": new_pesan, "status": "pending"}])
                df_simpan = pd.concat([df_bahaya, data_baru], ignore_index=True)
                df_simpan.to_csv(FILE_CSV, index=False)
                st.success(f"Terima kasih! Laporan '{new_lok}' telah dikirim ke Admin untuk proses verifikasi.")
            else:
                st.error("Nama Lokasi dan Pesan tidak boleh kosong!")

# ==========================================
# HALAMAN KHUSUS ADMIN 
# ==========================================
elif st.session_state.halaman == 'Admin':
    if st.session_state.role != 'Admin':
        st.error("Anda tidak memiliki akses ke halaman ini.")
    else:
        # Tombol Logout diletakkan di dalam halaman Admin
        col_judul, col_logout = st.columns([3, 1])
        col_judul.subheader("🛡️ Panel Validasi Admin")
        if col_logout.button("🚪 Logout"):
            st.session_state.role = 'User'
            st.session_state.halaman = 'Home'
            st.rerun()

        st.markdown("#### ⏳ Laporan Menunggu Persetujuan")
        df_pending = df_bahaya[df_bahaya['status'] == 'pending']
        
        if not df_pending.empty:
            for index, row in df_pending.iterrows():
                col_teks, col_acc, col_tolak = st.columns([3, 1, 1])
                col_teks.info(f"**{row['lokasi']}** | {row['pesan']} *(Lat: {row['lat']}, Lon: {row['lon']})*")
                
                if col_acc.button("✅ Terima", key=f"acc_{index}"):
                    df_bahaya.at[index, 'status'] = 'approved'
                    df_bahaya.to_csv(FILE_CSV, index=False)
                    st.rerun()
                    
                if col_tolak.button("❌ Tolak", key=f"tolak_{index}"):
                    df_bahaya = df_bahaya.drop(index)
                    df_bahaya.to_csv(FILE_CSV, index=False)
                    st.rerun()
        else:
            st.success("Hore! Tidak ada laporan pending saat ini.")

        st.markdown("---")
        
        st.markdown("#### 🗑️ Hapus Titik yang Sudah Aktif")
        if not df_aktif.empty:
            with st.form("form_hapus_admin"):
                pilih_hapus = st.selectbox("Pilih lokasi yang ingin dicabut dari peta:", df_aktif['lokasi'])
                submit_hapus = st.form_submit_button("Cabut Titik")

                if submit_hapus:
                    df_bahaya = df_bahaya[df_bahaya['lokasi'] != pilih_hapus]
                    df_bahaya.to_csv(FILE_CSV, index=False)
                    st.success(f"Lokasi '{pilih_hapus}' berhasil dihapus secara permanen!")
        else:
            st.info("Tidak ada data aktif.")
            
        st.markdown("---")
        st.markdown("#### 💾 Unduh Database Lengkap")
        csv_data = df_bahaya.to_csv(index=False).encode('utf-8')
        st.download_button(label="⬇️ Download hasil_survei_tembalang.csv", data=csv_data, file_name=FILE_CSV, mime='text/csv')
