import streamlit as st
import pandas as pd
import folium
from folium import plugins
import os
import requests
import re
import pytesseract
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
            if abs(val1) < 90 and abs(val2) > 90:
                return val1, val2
            elif abs(val2) < 90 and abs(val1) > 90:
                return val2, val1
        return None, None
    except Exception as e:
        return None, None

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

# 📡 SENSOR GPS AWAL (Buat ngunci kordinat)
user_lat, user_lon = None, None
if st.session_state.halaman in ['Home', 'Lapor', 'Rute']: 
    col_teks, col_gps = st.columns([1, 2])
    col_teks.markdown("**📡 Sensor Lokasi Saat Ini:**")
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
    m = folium.Map(location=[-7.049, 110.441], zoom_start=15)
    
    # MAGIC: Motor lu bakal tetep gerak mulus karena plugin ini ngebaca GPS langsung dari Browser (bukan Python)
    plugins.LocateControl(auto_start=True, position='bottomright', strings={'title': 'Lokasi Saya', 'popup': 'Anda di sini'}, flyTo=True).add_to(m)

    if user_lat and user_lon:
        if not df_aktif.empty:
            df_aktif['jarak'] = df_aktif.apply(lambda row: geodesic((user_lat, user_lon), (row['lat'], row['lon'])).meters, axis=1)
            titik_terdekat = df_aktif.loc[df_aktif['jarak'].idxmin()]
            
            if titik_terdekat['jarak'] < 200:
                st.error(f"⚠️ BAHAYA: Dekat {titik_terdekat['lokasi']} (Sisa {int(titik_terdekat['jarak'])}m)!")
            else:
                st.info(f"Titik terdekat: {titik_terdekat['lokasi']} ({int(titik_terdekat['jarak'])}m)")

    for _, p in df_aktif.iterrows():
        folium.Marker([p['lat'], p['lon']], popup=p['lokasi'], tooltip=p['pesan'], icon=folium.Icon(color='red', icon='exclamation-triangle')).add_to(m)
    st_folium(m, width=700, height=450, returned_objects=[])

# ==========================================
# HALAMAN RUTE 
# ==========================================
elif st.session_state.halaman == 'Rute':
    st.subheader("📍 Analisis Rute & Alternatif")
    
    if not st.session_state.rute_data:
        st.info("Ketik lokasi tujuan. Mesin akan mencari Rute Utama & Alternatif di sekitar Semarang.")
        with st.form("form_cek_rute"):
            tujuan = st.text_input("Mau ke mana? (Contoh: UNDIP Tembalang)")
            submit_rute = st.form_submit_button("Analisis Rute")

        if submit_rute and tujuan:
            geolocator = ArcGIS() 
            with st.spinner("Menyiapkan rute navigasi..."):
                try:
                    query_lokasi = f"{tujuan}, Semarang, Jawa Tengah, Indonesia"
                    lokasi_tujuan = geolocator.geocode(query_lokasi)
                    
                    if lokasi_tujuan:
                        dest_lat = lokasi_tujuan.latitude
                        dest_lon = lokasi_tujuan.longitude
                        start_lat = user_lat if user_lat else -7.049000
                        start_lon = user_lon if user_lon else 110.441000

                        # Cari maksimal 3 alternatif rute
                        url = f"http://router.project-osrm.org/route/v1/driving/{start_lon},{start_lat};{dest_lon},{dest_lat}?overview=full&geometries=geojson&alternatives=3"
                        res = requests.get(url)
                        
                        if res.status_code == 200:
                            semua_rute = res.json().get("routes", [])
                            rute_list_jadi = []
                            
                            for idx, rute in enumerate(semua_rute):
                                route_coords = rute["geometry"]["coordinates"]
                                bahaya_dilewati = []
                                for _, p in df_aktif.iterrows():
                                    for coord in route_coords:
                                        if geodesic((p['lat'], p['lon']), (coord[1], coord[0])).meters < 200:
                                            bahaya_dilewati.append(p.to_dict())
                                            break 
                                
                                rute_list_jadi.append({
                                    'geojson': rute["geometry"],
                                    'bahaya': bahaya_dilewati,
                                    'is_primary': (idx == 0),
                                    'jarak_km': rute.get('distance', 0) / 1000
                                })

                            st.session_state.rute_data = {
                                'nama_tujuan': lokasi_tujuan.address, 
                                'dest_lat': dest_lat, 
                                'dest_lon': dest_lon,
                                'start_lat': start_lat,
                                'start_lon': start_lon,
                                'rute_list': rute_list_jadi
                            }
                            st.rerun() 
                        else: st.error("Server OSRM gagal mencari jalan.")
                    else: st.error("Lokasi tidak ditemukan.")
                except Exception as e: st.error("Terjadi kesalahan sistem.")

    if st.session_state.rute_data:
        rd = st.session_state.rute_data
        col_info, col_btn = st.columns([3, 1])
        col_info.success(f"Menuju: {rd['nama_tujuan']}")
        if col_btn.button("🛑 Tutup Peta"): st.session_state.rute_data = None; st.rerun()

        m_rute = folium.Map(location=[rd['start_lat'], rd['start_lon']], zoom_start=15) 
        plugins.LocateControl(auto_start=True, position='bottomright', strings={'title': 'Lokasi Saya', 'popup': 'Anda di sini'}, flyTo=True).add_to(m_rute)

        # Menggambar semua rute
        for rute in rd['rute_list']:
            if rute['is_primary']:
                warna = '#E74C3C' if rute['bahaya'] else '#0078FF' 
                ketebalan = 7
                st.write(f"**Rute Utama** ({rute['jarak_km']:.1f} km) - {'⚠️ RAWAN' if rute['bahaya'] else '✅ AMAN'}")
            else:
                warna = '#95A5A6' 
                ketebalan = 5
                st.write(f"Rute Alternatif ({rute['jarak_km']:.1f} km) - {'⚠️ RAWAN' if rute['bahaya'] else '✅ AMAN'}")

            folium.GeoJson(rute['geojson'], style_function=lambda x, c=warna, w=ketebalan: {'color': c, 'weight': w, 'opacity': 0.8}).add_to(m_rute)
            
            for b in rute['bahaya']: 
                folium.Marker([b['lat'], b['lon']], tooltip=b['pesan'], icon=folium.Icon(color='red', icon='exclamation-triangle')).add_to(m_rute)

        folium.Marker([rd['dest_lat'], rd['dest_lon']], popup=rd['nama_tujuan'], icon=folium.Icon(color='green', icon='flag')).add_to(m_rute)
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
    st.warning("Gunakan aplikasi kamera GPS. Mesin akan membaca teks koordinat (angka desimal) yang tertulis di foto Anda secara otomatis!")
    
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
                st.error("❌ TEKS TIDAK DITEMUKAN: Pastikan di foto Anda tertulis angka koordinat desimal (contoh: -7.0490, 110.4410) yang terbaca jelas.")
        except Exception as e: st.error("Gagal menjalankan AI pembaca teks. Pastikan packages.txt sudah dibuat.")

# ==========================================
# 🛡️ HALAMAN KHUSUS ADMIN
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
                info_text = f"""
                **{row['lokasi']}** | {row['pesan']}
                📍 Lat: `{row['lat']:.6f}`, Lon: `{row['lon']:.6f}`
                [🗺️ Cek Titik di Google Maps](https://www.google.com/maps?q={row['lat']},{row['lon']})
                """
                col_teks.info(info_text)
                
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
                pilihan_aktif = df_aktif.apply(lambda x: f"{x['lokasi']} (Lat: {x['lat']:.5f}, Lon: {x['lon']:.5f})", axis=1)
                pilih_hapus_str = st.selectbox("Pilih lokasi yang mau dihapus:", pilihan_aktif)
                
                if st.form_submit_button("Cabut Titik"):
                    nama_asli = pilih_hapus_str.split(" (Lat:")[0]
                    df_bahaya = df_bahaya[df_bahaya['lokasi'] != nama_asli]
                    df_bahaya.to_csv(FILE_CSV, index=False)
                    st.success("Titik berhasil dicabut dari peta!")
        
        st.markdown("---")
        csv_data = df_bahaya.to_csv(index=False).encode('utf-8')
        st.download_button("⬇️ Download Database CSV", data=csv_data, file_name=FILE_CSV, mime='text/csv')
