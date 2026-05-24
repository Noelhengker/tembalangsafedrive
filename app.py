import streamlit as st
import pandas as pd
import folium
import os
from streamlit_folium import st_folium
from streamlit_geolocation import streamlit_geolocation
from geopy.distance import geodesic
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

# INISIALISASI OTAK NAVIGASI
if 'halaman' not in st.session_state:
    st.session_state.halaman = 'Home'

# 3. HEADER APLIKASI
st.markdown("<h3 style='text-align: center; color: #E74C3C; margin-bottom: 10px;'>🛡️ Safe-Drive</h3>", unsafe_allow_html=True)

# ==========================================
# 4. MENU NAVIGASI
# ==========================================
col1, col2, col3, col4 = st.columns(4)
if col1.button("🏠 Home", use_container_width=True): st.session_state.halaman = 'Home'
if col2.button("📂 Data", use_container_width=True): st.session_state.halaman = 'Data'
if col3.button("⚙️ Set", use_container_width=True): st.session_state.halaman = 'Setting'
if col4.button("🚪 Exit", use_container_width=True): st.session_state.halaman = 'Exit'

st.markdown("---")

# ==========================================
# 5. KONTEN HALAMAN
# ==========================================
if st.session_state.halaman == 'Home':
    st_autorefresh(interval=2000, key="datarefresh") # Diatur 2 detik agar responsif!
    
    st.markdown("**Status GPS Anda:**")
    location = streamlit_geolocation()
    user_lat = location.get('latitude')
    user_lon = location.get('longitude')

    if user_lat and user_lon:
        st.success(f"Sinyal Terkunci: {user_lat:.5f}, {user_lon:.5f}")
        for _, point in df_bahaya.iterrows():
            jarak = geodesic((user_lat, user_lon), (point['lat'], point['lon'])).meters
            if jarak < 200:
                st.error(f"⚠️ BAHAYA: Anda mendekati {point['lokasi']}!")
                st.warning(f"Instruksi: {point['pesan']}")
                st.components.v1.html(
                    """<script>var audio = new Audio('https://www.soundjay.com/buttons/beep-01a.mp3'); audio.play();</script>""",
                    height=0
                )
    else:
        st.info("Menunggu sinyal GPS... Pastikan izin lokasi aktif.")

    m = folium.Map(location=[-7.049, 110.441], zoom_start=15)
    
    # -----------------------------------------------------------
    # FITUR BARU: GARIS RUTE BIRU (MENGHUBUNGKAN TITIK-TITIK)
    # -----------------------------------------------------------
    if len(df_bahaya) > 1:
        route_coords = df_bahaya[['lat', 'lon']].values.tolist()
        folium.PolyLine(
            route_coords, 
            color='#3498db', # Warna biru khas peta digital
            weight=6,        # Ketebalan garis
            opacity=0.7,     # Agak transparan agar jalan di bawahnya tetap terlihat
            tooltip="Jalur Rawan"
        ).add_to(m)
    # -----------------------------------------------------------

    for _, p in df_bahaya.iterrows():
        folium.Marker(
            [p['lat'], p['lon']], 
            popup=p['lokasi'], 
            tooltip=p['pesan'],
            icon=folium.Icon(color='red', icon='exclamation-triangle', prefix='fa')
        ).add_to(m)

    if user_lat and user_lon:
        folium.Marker(
            [user_lat, user_lon], 
            popup="Lokasi Anda", 
            icon=folium.Icon(color='blue', icon='motorcycle', prefix='fa')
        ).add_to(m)

    st_folium(m, width=700, height=450)

elif st.session_state.halaman == 'Data':
    st.subheader("Database Titik Bahaya")
    st.metric(label="Total Titik Dipantau", value=f"{len(df_bahaya)} Lokasi")
    st.dataframe(df_bahaya, use_container_width=True)

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
                data_baru = pd.DataFrame([{"lokasi": new_lok, "lat": new_lat, "lon": new_lon, "pesan": new_pesan}])
                df_bahaya = pd.concat([df_bahaya, data_baru], ignore_index=True)
                df_bahaya.to_csv(FILE_CSV, index=False)
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
                df_bahaya = df_bahaya[df_bahaya['lokasi'] != pilih_hapus]
                df_bahaya.to_csv(FILE_CSV, index=False)
                st.success(f"Lokasi '{pilih_hapus}' berhasil dihapus!")
    else:
        st.info("Belum ada data titik bahaya.")
        
    st.markdown("---")
    st.subheader("💾 Unduh Data CSV")
    csv_data = df_bahaya.to_csv(index=False).encode('utf-8')
    st.download_button(label="⬇️ Download hasil_survei_tembalang.csv", data=csv_data, file_name=FILE_CSV, mime='text/csv')

elif st.session_state.halaman == 'Exit':
    st.error("🔒 Sistem Peringatan Dini Dihentikan.")
    st.markdown("<h4 style='text-align: center; color: gray; margin-top: 50px;'>Anda telah keluar dari aplikasi.</h4>", unsafe_allow_html=True)
