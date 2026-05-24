import streamlit as st
import pandas as pd
import folium
import os
import requests
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

# 2. BACA DATA CSV
def load_csv():
    if os.path.exists(FILE_CSV):
        return pd.read_csv(FILE_CSV)
    else:
        return pd.DataFrame(columns=['lokasi', 'lat', 'lon', 'pesan'])

df_bahaya = load_csv()

# ==========================================
# INISIALISASI OTAK MEMORI (Mencegah Amnesia)
# ==========================================
if 'halaman' not in st.session_state:
    st.session_state.halaman = 'Home'
if 'rute_data' not in st.session_state:
    st.session_state.rute_data = None # Memori untuk menyimpan hasil pencarian rute

# 3. HEADER APLIKASI
st.markdown("<h3 style='text-align: center; color: #E74C3C; margin-bottom: 10px;'>🛡️ Safe-Drive</h3>", unsafe_allow_html=True)

# 4. MENU NAVIGASI 
col1, col2, col3, col4 = st.columns(4)
if col1.button("🏠 Home", use_container_width=True): st.session_state.halaman = 'Home'
if col2.button("🗺️ Rute", use_container_width=True): st.session_state.halaman = 'Rute'
if col3.button("📂 Data", use_container_width=True): st.session_state.halaman = 'Data'
if col4.button("⚙️ Set", use_container_width=True): st.session_state.halaman = 'Setting'

st.markdown("---")

# ==========================================
# 5. KONTEN HALAMAN
# ==========================================
if st.session_state.halaman == 'Home':
    st_autorefresh(interval=2000, key="datarefresh") 
    
    st.markdown("**Status GPS Anda:**")
    location = streamlit_geolocation()
    user_lat = location.get('latitude')
    user_lon = location.get('longitude')

    m = folium.Map(location=[-7.049, 110.441], zoom_start=15)

    if user_lat and user_lon:
        st.success(f"Sinyal Terkunci: {user_lat:.5f}, {user_lon:.5f}")
        
        if not df_bahaya.empty:
            df_bahaya['jarak'] = df_bahaya.apply(lambda row: geodesic((user_lat, user_lon), (row['lat'], row['lon'])).meters, axis=1)
            titik_terdekat = df_bahaya.loc[df_bahaya['jarak'].idxmin()]
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
                data = res.json()
                if data.get("code") == "Ok":
                    folium.GeoJson(data["routes"][0]["geometry"], name="Rute Navigasi", style_function=lambda x: {'color': '#0078FF', 'weight': 7, 'opacity': 0.8}).add_to(m)
            except:
                pass

        folium.Marker([user_lat, user_lon], popup="Posisi Motor", icon=folium.Icon(color='blue', icon='motorcycle', prefix='fa')).add_to(m)
    else:
        st.info("Menunggu sinyal GPS... Pastikan izin lokasi aktif.")

    for _, p in df_bahaya.iterrows():
        folium.Marker([p['lat'], p['lon']], popup=p['lokasi'], tooltip=p['pesan'], icon=folium.Icon(color='red', icon='exclamation-triangle', prefix='fa')).add_to(m)
    
    # Tambahan paramater agar map tidak me-refresh halaman saat diklik
    st_folium(m, width=700, height=450, returned_objects=[])

# ==========================================
# HALAMAN RUTE (Memori Diperkuat)
# ==========================================
elif st.session_state.halaman == 'Rute':
    st.subheader("📍 Cek Keamanan Rute")
    st.info("Ketik lokasi tujuan untuk melihat apakah jalur yang akan dilewati aman dari titik rawan.")
    
    location = streamlit_geolocation()
    user_lat = location.get('latitude')
    user_lon = location.get('longitude')

    with st.form("form_cek_rute"):
        tujuan = st.text_input("Mau ke mana? (Contoh: UNDIP Tembalang)")
        submit_rute = st.form_submit_button("Cari Rute & Analisis")

    # 1. JIKA TOMBOL DIKLIK, KITA CARI DATANYA DAN SIMPAN KE MEMORI
    if submit_rute and tujuan:
        if not user_lat or not user_lon:
            st.error("GPS belum terkunci. Tunggu sebentar lalu coba lagi.")
        else:
            geolocator = ArcGIS() 
            with st.spinner("Menganalisis keamanan jalur..."):
                try:
                    lokasi_tujuan = geolocator.geocode(f"{tujuan}, Indonesia")
                    if lokasi_tujuan:
                        dest_lat = lokasi_tujuan.latitude
                        dest_lon = lokasi_tujuan.longitude

                        url = f"http://router.project-osrm.org/route/v1/driving/{user_lon},{user_lat};{dest_lon},{dest_lat}?overview=full&geometries=geojson"
                        res = requests.get(url)
                        data = res.json()

                        if data.get("code") == "Ok":
                            route_coords = data["routes"][0]["geometry"]["coordinates"]
                            
                            bahaya_dilewati = []
                            for _, p in df_bahaya.iterrows():
                                for coord in route_coords:
                                    jarak = geodesic((p['lat'], p['lon']), (coord[1], coord[0])).meters
                                    if jarak < 200:
                                        bahaya_dilewati.append(p.to_dict()) # Diubah ke kamus agar bisa disimpan
                                        break 

                            # SIMPAN SEMUA HASIL KERAS KE DALAM MEMORI OTAK
                            st.session_state.rute_data = {
                                'nama_tujuan': lokasi_tujuan.address,
                                'dest_lat': dest_lat,
                                'dest_lon': dest_lon,
                                'user_lat': user_lat,
                                'user_lon': user_lon,
                                'geojson': data["routes"][0]["geometry"],
                                'bahaya': bahaya_dilewati
                            }
                        else:
                            st.error("Server rute sedang sibuk atau gagal mencari jalan.")
                    else:
                        st.error("Lokasi tidak ditemukan. Coba ketik nama tempat yang lebih umum.")
                except Exception as e:
                    st.error(f"Terjadi kesalahan saat memproses rute.")

    # 2. MENGGAMBAR PETA BERDASARKAN MEMORI (Aman dari scroll & zoom)
    if st.session_state.rute_data:
        rd = st.session_state.rute_data
        st.success(f"Tujuan Ditemukan: {rd['nama_tujuan']}")
        
        m_rute = folium.Map(location=[rd['user_lat'], rd['user_lon']], zoom_start=14)
        
        if rd['bahaya']:
            warna_rute = '#E74C3C' 
            st.error(f"⚠️ PERINGATAN! Rute ini akan melewati {len(rd['bahaya'])} titik rawan.")
            for b in rd['bahaya']:
                st.warning(f"🚨 Area {b['lokasi']}: {b['pesan']}")
        else:
            warna_rute = '#2ECC71' 
            st.success(f"✅ RUTE AMAN! Jalur menuju tujuanmu bebas dari titik rawan yang terdata.")

        folium.GeoJson(
            rd['geojson'],
            name="Hasil Analisis Rute",
            style_function=lambda x: {'color': warna_rute, 'weight': 6, 'opacity': 0.8}
        ).add_to(m_rute)

        folium.Marker([rd['user_lat'], rd['user_lon']], popup="Mulai", icon=folium.Icon(color='blue', icon='play')).add_to(m_rute)
        folium.Marker([rd['dest_lat'], rd['dest_lon']], popup=rd['nama_tujuan'], icon=folium.Icon(color='green', icon='flag')).add_to(m_rute)
        
        for b in rd['bahaya']:
            folium.Marker([b['lat'], b['lon']], tooltip=b['pesan'], icon=folium.Icon(color='red', icon='exclamation-triangle')).add_to(m_rute)

        # Parameter returned_objects=[] mematikan interaksi balik ke sistem, anti-hilang!
        st_folium(m_rute, width=700, height=450, returned_objects=[])

elif st.session_state.halaman == 'Data':
    st.subheader("Database Titik Bahaya")
    if not df_bahaya.empty:
        df_tampil = df_bahaya.drop(columns=['jarak'], errors='ignore') 
        st.metric(label="Total Titik Dipantau", value=f"{len(df_tampil)} Lokasi")
        st.dataframe(df_tampil, use_container_width=True)
    else:
        st.info("Data masih kosong.")

elif st.session_state.halaman == 'Setting':
    st.subheader("➕ Tambah Titik Baru")
    with st.form("form_tambah"):
        new_lok = st.text_input("Nama Lokasi")
        new_lat = st.number_input("Latitude", format="%.6f", value=-7.049000, step=0.000100)
        new_lon = st.number_input("Longitude", format="%.6f", value=110.441000, step=0.000100)
        new_pesan = st.text_input("Pesan Peringatan")
        submit_tambah = st.form_submit_button("Simpan Titik")

        if submit_tambah:
            if new_lok and new_pesan:
                df_simpan = df_bahaya.drop(columns=['jarak'], errors='ignore') if not df_bahaya.empty else df_bahaya
                data_baru = pd.DataFrame([{"lokasi": new_lok, "lat": new_lat, "lon": new_lon, "pesan": new_pesan}])
                df_simpan = pd.concat([df_simpan, data_baru], ignore_index=True)
                df_simpan.to_csv(FILE_CSV, index=False)
                st.success(f"Lokasi '{new_lok}' berhasil ditambahkan!")
            else:
                st.error("Nama Lokasi dan Pesan tidak boleh kosong!")

    st.markdown("---")
    
    st.subheader("🗑️ Hapus Titik")
    if not df_bahaya.empty:
        with st.form("form_hapus"):
            pilih_hapus = st.selectbox("Pilih lokasi yang ingin dihapus:", df_bahaya['lokasi'])
            submit_hapus = st.form_submit_button("Hapus Titik")

            if submit_hapus:
                df_simpan = df_bahaya.drop(columns=['jarak'], errors='ignore')
                df_simpan = df_simpan[df_simpan['lokasi'] != pilih_hapus]
                df_simpan.to_csv(FILE_CSV, index=False)
                st.success(f"Lokasi '{pilih_hapus}' berhasil dihapus!")
    else:
        st.info("Belum ada data titik bahaya.")
        
    st.markdown("---")
    st.subheader("💾 Unduh Data CSV")
    if not df_bahaya.empty:
        csv_data = df_bahaya.drop(columns=['jarak'], errors='ignore').to_csv(index=False).encode('utf-8')
        st.download_button(label="⬇️ Download hasil_survei_tembalang.csv", data=csv_data, file_name=FILE_CSV, mime='text/csv')
