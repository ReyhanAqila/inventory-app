import streamlit as st

st.markdown("""
<style>
body, .stApp {
    background: #f8fafc !important;
    color: #1f2937 !important;
    font-family: "Inter", sans-serif;
}
section[data-testid="stSidebar"] > div {
    background: #ffffff !important;
    border-right: 1px solid #e5e7eb;
    padding: 18px;
}
.metric-card {
    background: #ffffff;
    border-radius: 12px;
    padding: 16px;
    box-shadow: 0px 4px 14px rgba(0,0,0,0.08);
}
.metric-title { color:#6b7280; font-weight:600; }
.metric-value { font-size:26px; font-weight:800; color:#1f2937; }
</style>
""", unsafe_allow_html=True)


# --- Futuristic Dashboard Styling (Dark + Neon Accents) ---
st.markdown("""

""", unsafe_allow_html=True)
# --- end css ---

# Modern UI Styling
st.markdown(
    """
    
    """,
    unsafe_allow_html=True
)

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import time
from io import BytesIO
import os
import sys

def get_resource_path(relative_path):
    """
    Dapatkan jalur absolut ke sumber daya, bekerja untuk pengembangan
    dan untuk PyInstaller di jalur tmp-nya.
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # Jika bukan PyInstaller (misalnya, development environment)
        base_path = os.path.abspath(".")

    # Pastikan database disimpan di direktori root saat diekstrak
    return os.path.join(base_path, relative_path)

# Gunakan variabel global untuk jalur database
DB_PATH = get_resource_path('inventory_rumah.db')

# Konfigurasi halaman
st.set_page_config(
    page_title="Inventory Gudang",
    page_icon="📦",
    layout="wide"
)

# Session state
if 'last_submission' not in st.session_state:
    st.session_state.last_submission = None
if 'form_submitted' not in st.session_state:
    st.session_state.form_submitted = False
if 'submission_success' not in st.session_state:
    st.session_state.submission_success = False
if 'import_config' not in st.session_state:
    st.session_state.import_config = {}
if 'selected_sheets' not in st.session_state:
    st.session_state.selected_sheets = {}
if 'import_barang_config' not in st.session_state:
    st.session_state.import_barang_config = {}
if 'selected_sheets_barang' not in st.session_state:
    st.session_state.selected_sheets_barang = {}


# ================= LOGIN & ROLE SYSTEM =================
# User database (simple dictionary)
users = {
    "admin": {"password": "admin123", "role": "editor"},
    "viewer1": {"password": "viewer123", "role": "viewer"},
    "viewer2": {"password": "viewer456", "role": "viewer"}
}

if "user_role" not in st.session_state:
    st.session_state.user_role = None

if st.session_state.user_role is None:
    st.title("🔐 Login Aplikasi Inventory")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if username in users and users[username]["password"] == password:
            st.session_state.user_role = users[username]["role"]
            st.rerun()
        else:
            st.error("❌ Username atau Password salah")
    st.stop()

# ================= END LOGIN SYSTEM =================

# Fungsi untuk format tanggal tanpa jam
def format_date_only(df, date_columns):
    """Convert datetime columns to date only format (YYYY-MM-DD)"""
    for col in date_columns:
        if col in df.columns:
            # Menggunakan .dt.date untuk mengonversi datetime/timestamp ke objek date Python
            df[col] = pd.to_datetime(df[col], errors='coerce').apply(lambda x: x.date() if pd.notna(x) else None)
    return df

# Fungsi untuk export ke Excel dengan download button
def create_excel_download(df, filename_prefix, button_label):
    """Create Excel file and return download button"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Data')
        worksheet = writer.sheets['Data']

        # Aktifkan Autofilter
        if not df.empty:
            max_row = len(df)
            max_col = len(df.columns) - 1
            worksheet.autofilter(0, 0, max_row, max_col)

    output.seek(0)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{filename_prefix}_{timestamp}.xlsx"

    st.download_button(
        label=button_label,
        data=output,
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# Inisialisasi database
def init_db():
    conn = sqlite3.connect('inventory_rumah.db')
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS barang (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nama_barang TEXT NOT NULL,
                stok INTEGER NOT NULL,
                besaran_stok TEXT NOT NULL,
                gudang TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')

    c.execute('''CREATE TABLE IF NOT EXISTS peminjaman (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                barang_id INTEGER,
                nama_barang TEXT NOT NULL,
                jumlah_pinjam INTEGER NOT NULL,
                tanggal_pinjam DATE NOT NULL,
                unit TEXT NOT NULL,
                besaran_stok TEXT NOT NULL,
                gudang TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (barang_id) REFERENCES barang (id)
                )''')

    c.execute('''CREATE TABLE IF NOT EXISTS riwayat_stok (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                barang_id INTEGER,
                nama_barang TEXT NOT NULL,
                jumlah_tambah INTEGER NOT NULL,
                stok_sebelum INTEGER NOT NULL,
                stok_sesudah INTEGER NOT NULL,
                gudang TEXT NOT NULL,
                tanggal_tambah TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (barang_id) REFERENCES barang (id)
                )''')

    conn.commit()
    conn.close()

def generate_unit_options():
    units = []
    for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I']:
        for number in range(1, 15):
            units.append(f"{letter}{number}")
    return units

def add_barang(nama, stok, besaran, gudang, tanggal_dibuat):
    conn = sqlite3.connect('inventory_rumah.db')
    c = conn.cursor()
    # Menambahkan tanggal_dibuat ke kueri INSERT
    c.execute("INSERT INTO barang (nama_barang, stok, besaran_stok, gudang, created_at) VALUES (?, ?, ?, ?, ?)",
              (nama, stok, besaran, gudang, tanggal_dibuat))

st.sidebar.write("---")
if st.sidebar.button("🚪 Logout"):
    st.session_state.user_role = None
    st.rerun()
    barang_id = c.lastrowid

    # Catat riwayat stok awal jika stok > 0
    if stok > 0:
        c.execute("""INSERT INTO riwayat_stok
                  (barang_id, nama_barang, jumlah_tambah, stok_sebelum, stok_sesudah, gudang, tanggal_tambah)
                  VALUES (?, ?, ?, ?, ?, ?, ?)""",
                  (barang_id, nama, stok, 0, stok, gudang, tanggal_dibuat))

    conn.commit()
    conn.close()

def kurangi_stok(barang_id, stok_dikurangi, tanggal_transaksi):
    conn = sqlite3.connect('inventory_rumah.db')
    c = conn.cursor()

    c.execute("SELECT nama_barang, stok, gudang FROM barang WHERE id = ?", (barang_id,))
    barang_data = c.fetchone()

    if barang_data:
        nama_barang, stok_sebelum, gudang = barang_data

        if stok_sebelum < stok_dikurangi:
            conn.close()
            return False, f"Stok tidak mencukupi. Stok tersedia: {stok_sebelum}"

        stok_sesudah = stok_sebelum - stok_dikurangi

        c.execute("UPDATE barang SET stok = stok - ? WHERE id = ?", (stok_dikurangi, barang_id))

        # Menambahkan tanggal_transaksi ke riwayat stok
        c.execute("""INSERT INTO riwayat_stok
                  (barang_id, nama_barang, jumlah_tambah, stok_sebelum, stok_sesudah, gudang, tanggal_tambah)
                  VALUES (?, ?, ?, ?, ?, ?, ?)""",
                  (barang_id, nama_barang, -stok_dikurangi, stok_sebelum, stok_sesudah, gudang, tanggal_transaksi))

        conn.commit()
        conn.close()
        return True, f"Stok berhasil dikurangi {stok_dikurangi}"

    conn.close()
    return False, "Barang tidak ditemukan"

def update_stok(barang_id, stok_tambahan, tanggal_transaksi):
    conn = sqlite3.connect('inventory_rumah.db')
    c = conn.cursor()

    c.execute("SELECT nama_barang, stok, gudang FROM barang WHERE id = ?", (barang_id,))
    barang_data = c.fetchone()

    if barang_data:
        nama_barang, stok_sebelum, gudang = barang_data
        stok_sesudah = stok_sebelum + stok_tambahan

        c.execute("UPDATE barang SET stok = stok + ? WHERE id = ?", (stok_tambahan, barang_id))

        # Menambahkan tanggal_transaksi ke riwayat stok
        c.execute("""INSERT INTO riwayat_stok
                  (barang_id, nama_barang, jumlah_tambah, stok_sebelum, stok_sesudah, gudang, tanggal_tambah)
                  VALUES (?, ?, ?, ?, ?, ?, ?)""",
                  (barang_id, nama_barang, stok_tambahan, stok_sebelum, stok_sesudah, gudang, tanggal_transaksi))

        conn.commit()
        conn.close()

def get_barang():
    conn = sqlite3.connect('inventory_rumah.db')
    df = pd.read_sql_query("SELECT * FROM barang ORDER BY nama_barang", conn)
    conn.close()
    # Jangan format tanggal di sini, biarkan format asli untuk ekspor dan pemrosesan.
    return df

def get_barang_by_id(barang_id):
    conn = sqlite3.connect('inventory_rumah.db')
    c = conn.cursor()
    c.execute("SELECT * FROM barang WHERE id = ?", (barang_id,))
    result = c.fetchone()
    conn.close()
    return result

def get_riwayat_stok():
    conn = sqlite3.connect('inventory_rumah.db')
    df = pd.read_sql_query("SELECT * FROM riwayat_stok ORDER BY tanggal_tambah DESC", conn)
    conn.close()
    df = format_date_only(df, ['tanggal_tambah'])
    return df

def delete_barang(barang_id):
    conn = sqlite3.connect('inventory_rumah.db')
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM peminjaman WHERE barang_id = ?", (barang_id,))
    has_transactions = c.fetchone()[0] > 0

    if has_transactions:
        conn.close()
        return False, "Barang tidak bisa dihapus karena masih ada riwayat penggunaan"

    c.execute("SELECT nama_barang FROM barang WHERE id = ?", (barang_id,))
    nama_barang = c.fetchone()[0]

    c.execute("DELETE FROM barang WHERE id = ?", (barang_id,))
    conn.commit()
    conn.close()
    return True, f"Barang '{nama_barang}' berhasil dihapus"

def delete_penggunaan(penggunaan_id):
    conn = sqlite3.connect('inventory_rumah.db')
    c = conn.cursor()
    c.execute("DELETE FROM peminjaman WHERE id = ?", (penggunaan_id,))
    conn.commit()
    conn.close()
    return True, "Riwayat penggunaan berhasil dihapus"

def delete_riwayat_stok(riwayat_id):
    conn = sqlite3.connect('inventory_rumah.db')
    c = conn.cursor()
    c.execute("DELETE FROM riwayat_stok WHERE id = ?", (riwayat_id,))
    conn.commit()
    conn.close()
    return True, "Riwayat penambahan stok berhasil dihapus"

def add_peminjaman(barang_id, nama_barang, jumlah, tanggal, unit, besaran, gudang):
    conn = sqlite3.connect('inventory_rumah.db')
    c = conn.cursor()

    try:
        c.execute("SELECT stok FROM barang WHERE id = ?", (barang_id,))
        current_stock = c.fetchone()

        if not current_stock or current_stock[0] < jumlah:
            conn.close()
            return False, f"Stok tidak mencukupi. Stok tersedia: {current_stock[0] if current_stock else 0}"

        c.execute("""INSERT INTO peminjaman
                    (barang_id, nama_barang, jumlah_pinjam, tanggal_pinjam, unit, besaran_stok, gudang)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                  (barang_id, nama_barang, jumlah, tanggal, unit, besaran, gudang))

        c.execute("UPDATE barang SET stok = stok - ? WHERE id = ?", (jumlah, barang_id))

        conn.commit()
        conn.close()

        return True, f"Berhasil menggunakan {jumlah} {besaran} {nama_barang} untuk unit {unit}"

    except Exception as e:
        conn.rollback()
        conn.close()
        return False, f"Error: {str(e)}"

def get_peminjaman():
    conn = sqlite3.connect('inventory_rumah.db')
    df = pd.read_sql_query("SELECT * FROM peminjaman ORDER BY created_at DESC", conn)
    conn.close()
    df = format_date_only(df, ['tanggal_pinjam', 'created_at'])
    return df

def check_stok_rendah():
    conn = sqlite3.connect('inventory_rumah.db')
    df = pd.read_sql_query("SELECT * FROM barang WHERE stok < 20", conn)
    conn.close()
    return df

def add_sample_data():
    conn = sqlite3.connect('inventory_rumah.db')
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM barang")
    if c.fetchone()[0] == 0:
        # Masukkan data sampel dengan tanggal saat ini
        today = datetime.now().date()
        sample_data = [
            ('Semen', 50, 'Sak', 'Gudang 1', today),
            ('Bata', 15, 'PCS', 'Gudang 1', today),
            ('Paving', 25, 'PCS', 'Gudang 2', today),
            ('Besi', 8, 'PCS', 'Gudang 1', today),
            ('Cat', 30, 'Kaleng', 'Gudang 2', today),
            ('Pasir', 12, 'Sak', 'Gudang 1', today),
        ]

        for item in sample_data:
            add_barang(item[0], item[1], item[2], item[3], item[4])

    conn.commit()
    conn.close()

# Inisialisasi
init_db()
add_sample_data()

# Header aplikasi
st.title("📦 Aplikasi Inventory Gudang")
st.markdown("*🚀 Running on Google Colab - Version 3.7 (Chart Update)*")
st.markdown("---")

# Sidebar

st.sidebar.title("📋 Menu Navigasi")

if st.session_state.user_role == "viewer":
    menu = st.sidebar.radio(
        "Pilih Menu:",
        [
            "🏠 Dashboard",
            "📊 Laporan",
            "⚠️ Stok Rendah"
        ]
    )
else:
    menu = st.sidebar.radio(
        "Pilih Menu:",
        [
            "🏠 Dashboard",
            "📦 Kelola Barang",
            "📝 Penggunaan",
            "📊 Laporan",
            "⚠️ Stok Rendah",
            "📥 Import/Export Data"
        ]
    )

st.sidebar.write("---")
st.sidebar.caption("Gunakan menu untuk navigasi sistem")

# Dashboard
if menu == "🏠 Dashboard":
    st.header("🏠 Dashboard Inventory")

    df_barang = get_barang()
    df_peminjaman = get_peminjaman()
    stok_rendah = check_stok_rendah()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        total_item = len(df_barang)
        st.metric("📦 Total Item", total_item)

    with col2:
        total_stok = df_barang['stok'].sum() if not df_barang.empty else 0
        st.metric("📊 Total Stok", total_stok)

    with col3:
        # Konversi tanggal pinjam di DataFrame menjadi objek date untuk perbandingan
        penggunaan_hari_ini = len(df_peminjaman[pd.to_datetime(df_peminjaman['tanggal_pinjam'], errors='coerce').dt.date == datetime.now().date()]) if not df_peminjaman.empty else 0
        st.metric("📝 Penggunaan Hari Ini", penggunaan_hari_ini)

    with col4:
        item_stok_rendah = len(stok_rendah)
        st.metric("⚠️ Stok Rendah", item_stok_rendah, delta_color="inverse")

    if not stok_rendah.empty:
        st.error(f"⚠️ PERINGATAN! Ada {len(stok_rendah)} barang dengan stok kurang dari 20!")
        with st.expander("👁️ Lihat Detail Stok Rendah"):
            st.dataframe(stok_rendah[['nama_barang', 'stok', 'besaran_stok', 'gudang']], use_container_width=True)
    else:
        st.success("✅ Semua stok barang mencukupi!")

    if not df_barang.empty:
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("📊 Distribusi Stok per Gudang")
            stok_gudang = df_barang.groupby('gudang')['stok'].sum().reset_index()
            fig = px.pie(stok_gudang, values='stok', names='gudang',
                         title="Distribusi Total Stok per Gudang",
                         color_discrete_sequence=px.colors.qualitative.Set3)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("📋 Status Stok Semua Barang")
            fig2 = px.bar(df_barang, x='nama_barang', y='stok', color='gudang',
                          title="Jumlah Stok per Barang",
                          labels={'stok': 'Jumlah Stok', 'nama_barang': 'Nama Barang'})
            fig2.add_hline(y=20, line_dash="dash", line_color="red",
                           annotation_text="⚠️ Batas Minimum (20)")
            st.plotly_chart(fig2, use_container_width=True)

    st.subheader("📋 Ringkasan Barang")
    if not df_barang.empty:
        st.dataframe(df_barang[['nama_barang', 'stok', 'besaran_stok', 'gudang']], use_container_width=True)
    else:
        st.info("🔭 Belum ada data barang.")

# Kelola Barang
elif menu == "📦 Kelola Barang":
    st.header("📦 Kelola Barang")

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["➕ Tambah Barang", "👁️ Lihat Barang", "🔄 Tambah Stok", "➖ Kurangi Stok", "🗑️ Hapus Barang", "📜 Riwayat Stok"])

    with tab1:
        st.subheader("➕ Tambah Barang Baru")

        with st.form("form_tambah_barang", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                nama_barang = st.text_input("🏷 Nama Barang")
                stok = st.number_input("📊 Stok Awal", min_value=0, value=0, step=1)
                # PERBAIKAN 1: Tambahkan input tanggal
                tanggal_dibuat = st.date_input("📅 Tanggal Masuk/Dibuat", value=datetime.now().date())
            with col2:
                besaran_stok = st.selectbox("📏 Besaran Stok",
                                             ["kg", "sak", "pcs", "liter", "box", "karung", "dus", "meter", "botol", "kaleng"])
                gudang = st.selectbox("🏭 Gudang", ["Gudang 1", "Gudang 2"])

            submitted = st.form_submit_button("➕ Tambah Barang", use_container_width=True)

            if submitted:
                if nama_barang.strip():
                    # Panggil fungsi dengan argumen tanggal_dibuat
                    add_barang(nama_barang.strip(), stok, besaran_stok, gudang, tanggal_dibuat)
                    st.success(f"✅ Barang '{nama_barang}' berhasil ditambahkan!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Nama barang harus diisi!")

    with tab2:
        st.subheader("👁️ Daftar Semua Barang")
        # PERBAIKAN 2: Hanya tampilkan kolom yang relevan (tanpa created_at)
        display_cols_barang = ['id', 'nama_barang', 'stok', 'besaran_stok', 'gudang']
        df_barang = get_barang()

        if not df_barang.empty:
            col1, col2, col3 = st.columns(3)
            with col1:
                filter_gudang = st.selectbox("🏭 Filter Gudang", ["Semua", "Gudang 1", "Gudang 2"])
            with col2:
                search_nama = st.text_input("🔍 Cari Nama Barang")
            with col3:
                show_low_stock = st.checkbox("⚠️ Hanya Stok Rendah")

            df_filtered = df_barang.copy()
            if filter_gudang != "Semua":
                df_filtered = df_filtered[df_filtered['gudang'] == filter_gudang]
            if search_nama:
                df_filtered = df_filtered[df_filtered['nama_barang'].str.contains(search_nama, case=False)]
            if show_low_stock:
                df_filtered = df_filtered[df_filtered['stok'] < 20]

            st.info(f"📊 Menampilkan {len(df_filtered)} dari {len(df_barang)} barang")
            st.dataframe(df_filtered[display_cols_barang], use_container_width=True)

            # Download Excel
            if not df_filtered.empty:
                create_excel_download(df_filtered[display_cols_barang], "data_barang", "📥 Download Excel")
        else:
            st.info("🔭 Belum ada data barang. Silakan tambah barang baru.")

    with tab3:
        st.subheader("🔄 Tambah Stok Barang")
        st.info("💡 Masukkan jumlah stok yang akan DITAMBAHKAN ke stok saat ini")
        df_barang = get_barang()

        if not df_barang.empty:
            barang_options = {f"{row['nama_barang']} ({row['gudang']}) - Sisa: {row['stok']} {row['besaran_stok']}": row['id']
                            for _, row in df_barang.iterrows()}

            with st.form("form_update_stok"):
                col1, col2 = st.columns(2)
                with col1:
                    selected_barang = st.selectbox("📦 Pilih Barang", list(barang_options.keys()))

                barang_id = barang_options[selected_barang]
                current_barang = get_barang_by_id(barang_id)
                stok_sekarang = current_barang[2]
                satuan = current_barang[3]

                with col2:
                    stok_tambahan = st.number_input("📊 Tambah Stok", min_value=0, value=0, step=1,
                                                     help="Masukkan jumlah yang akan ditambahkan ke stok saat ini")

                # PERBAIKAN 4: Tambahkan input tanggal transaksi
                tanggal_transaksi = st.date_input("📅 Tanggal Penambahan", value=datetime.now().date())

                submitted = st.form_submit_button("🔄 Tambah Stok", use_container_width=True)

                if submitted:
                    if stok_tambahan > 0:
                        # Panggil fungsi dengan tanggal transaksi
                        update_stok(barang_id, stok_tambahan, tanggal_transaksi)
                        new_stock = stok_sekarang + stok_tambahan
                        st.success(f"✅ Stok berhasil diupdate dari {stok_sekarang} menjadi {new_stock}!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Jumlah tambah stok harus lebih dari 0!")
        else:
            st.info("🔭 Belum ada barang untuk diupdate.")

    with tab4:
        st.subheader("➖ Kurangi Stok Barang (Koreksi)")
        st.warning("⚠️ Fitur ini untuk koreksi kesalahan input stok, bukan untuk pencatatan penggunaan!")

        df_barang = get_barang()

        if not df_barang.empty:
            barang_options = {f"{row['nama_barang']} ({row['gudang']}) - Sisa: {row['stok']} {row['besaran_stok']}": row['id']
                            for _, row in df_barang.iterrows()}

            with st.form("form_kurangi_stok"):
                col1, col2 = st.columns(2)
                with col1:
                    selected_barang = st.selectbox("📦 Pilih Barang", list(barang_options.keys()), key="kurangi_barang")

                barang_id = barang_options[selected_barang]
                current_barang = get_barang_by_id(barang_id)
                stok_sekarang = current_barang[2]
                satuan = current_barang[3]

                with col2:
                    stok_dikurangi = st.number_input("📉 Kurangi Stok", min_value=0, max_value=stok_sekarang, value=0, step=1,
                                                     help="Masukkan jumlah yang akan dikurangi dari stok saat ini")

                # PERBAIKAN 4: Tambahkan input tanggal transaksi
                tanggal_transaksi = st.date_input("📅 Tanggal Pengurangan", value=datetime.now().date())

                submitted = st.form_submit_button("➖ Kurangi Stok", use_container_width=True)

                if submitted:
                    if stok_dikurangi > 0:
                        # Panggil fungsi dengan tanggal transaksi
                        success, message = kurangi_stok(barang_id, stok_dikurangi, tanggal_transaksi)
                        if success:
                            st.success(f"✅ {message}. Stok sekarang: {stok_sekarang - stok_dikurangi}")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"❌ {message}")
                    else:
                        st.error("❌ Jumlah pengurangan stok harus lebih dari 0!")
        else:
            st.info("🔭 Belum ada barang untuk diupdate.")

    with tab5:
        st.subheader("🗑️ Hapus Barang")
        st.warning("⚠️ **PERINGATAN:** Barang yang memiliki riwayat penggunaan tidak bisa dihapus!")

        df_barang = get_barang()

        if not df_barang.empty:
            barang_options = {f"{row['nama_barang']} ({row['gudang']}) - Stok: {row['stok']} {row['besaran_stok']}": row['id']
                            for _, row in df_barang.iterrows()}

            with st.form("form_hapus_barang"):
                selected_barang = st.selectbox("🗑️ Pilih Barang yang akan dihapus", list(barang_options.keys()))

                st.markdown("**Konfirmasi penghapusan:**")
                confirm = st.checkbox("✅ Saya yakin ingin menghapus barang ini")

                submitted = st.form_submit_button("🗑️ HAPUS BARANG", type="secondary", use_container_width=True)

                if submitted:
                    if confirm:
                        barang_id = barang_options[selected_barang]
                        success, message = delete_barang(barang_id)

                        if success:
                            st.success(f"✅ {message}")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"❌ {message}")
                    else:
                        st.error("❌ Harap centang konfirmasi untuk menghapus barang!")
        else:
            st.info("🔭 Belum ada barang untuk dihapus.")

    with tab6:
        st.subheader("📜 Riwayat Perubahan Stok")

        tab_view, tab_delete = st.tabs(["👁️ Lihat Riwayat", "🗑️ Hapus Riwayat"])

        with tab_view:
            df_riwayat = get_riwayat_stok()

            if not df_riwayat.empty:
                col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
                with col1:
                    start_date = st.date_input("📅 Dari Tanggal", value=datetime.now().date() - timedelta(days=30), key="riwayat_start")
                with col2:
                    end_date = st.date_input("📅 Sampai Tanggal", value=datetime.now().date(), key="riwayat_end")
                with col3:
                    filter_jenis = st.selectbox("Jenis Transaksi", ["Semua", "Tambah", "Kurang"], key="filter_jenis_stok")
                with col4:
                    search_barang = st.text_input("🔍 Cari Barang", key="riwayat_search")

                mask = (pd.to_datetime(df_riwayat['tanggal_tambah'], errors='coerce').dt.date >= start_date) & (pd.to_datetime(df_riwayat['tanggal_tambah'], errors='coerce').dt.date <= end_date)
                df_filtered = df_riwayat.loc[mask]

                if filter_jenis == "Tambah":
                    df_filtered = df_filtered[df_filtered['jumlah_tambah'] > 0]
                elif filter_jenis == "Kurang":
                    df_filtered = df_filtered[df_filtered['jumlah_tambah'] < 0]

                if search_barang:
                    df_filtered = df_filtered[df_filtered['nama_barang'].str.contains(search_barang, case=False)]

                if not df_filtered.empty:
                    st.info(f"📊 Menampilkan {len(df_filtered)} riwayat perubahan stok")

                    display_df = df_filtered.copy()
                    display_df['Jenis'] = display_df['jumlah_tambah'].apply(lambda x: '➕ Tambah' if x > 0 else '➖ Kurang')
                    display_df['Jumlah'] = display_df['jumlah_tambah'].abs()

                    display_df = display_df.rename(columns={
                        'id': 'ID',
                        'nama_barang': 'Nama Barang',
                        'stok_sebelum': 'Stok Sebelum',
                        'stok_sesudah': 'Stok Sesudah',
                        'gudang': 'Gudang',
                        'tanggal_tambah': 'Tanggal'
                    })

                    display_cols = ['ID', 'Jenis', 'Nama Barang', 'Jumlah', 'Stok Sebelum', 'Stok Sesudah', 'Gudang', 'Tanggal']
                    st.dataframe(display_df[display_cols], use_container_width=True)

                    total_penambahan = display_df[display_df['Jenis'] == '➕ Tambah']['Jumlah'].sum()
                    total_pengurangan = display_df[display_df['Jenis'] == '➖ Kurang']['Jumlah'].sum()

                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("📊 Total Stok Ditambahkan", total_penambahan)
                    with col2:
                        st.metric("📉 Total Stok Dikurangi", total_pengurangan)

                    # Download Excel
                    create_excel_download(display_df[display_cols], "riwayat_stok", "📥 Download Excel")
                else:
                    st.info("🔭 Tidak ada riwayat perubahan stok dalam rentang tanggal tersebut.")
            else:
                st.info("🔭 Belum ada riwayat perubahan stok.")

        with tab_delete:
            st.warning("⚠️ **PERHATIAN:** Hapus riwayat hanya untuk koreksi kesalahan input. Stok barang TIDAK akan berubah!")

            df_riwayat = get_riwayat_stok()

            if not df_riwayat.empty:
                riwayat_options = {}
                for _, row in df_riwayat.iterrows():
                    jenis = "Tambah" if row['jumlah_tambah'] > 0 else "Kurang"
                    jumlah = abs(row['jumlah_tambah'])
                    label = f"ID-{row['id']}: {jenis} {row['nama_barang']} ({jumlah}) - {row['tanggal_tambah']}"
                    riwayat_options[label] = row['id']

                with st.form("form_hapus_riwayat_stok"):
                    selected_riwayat = st.selectbox("🗑️ Pilih riwayat yang akan dihapus", list(riwayat_options.keys()))

                    st.markdown("**Konfirmasi penghapusan:**")
                    confirm = st.checkbox("✅ Saya yakin ingin menghapus riwayat ini")

                    submitted = st.form_submit_button("🗑️ HAPUS RIWAYAT", type="secondary", use_container_width=True)

                    if submitted:
                        if confirm:
                            riwayat_id = riwayat_options[selected_riwayat]
                            success, message = delete_riwayat_stok(riwayat_id)

                            if success:
                                st.success(f"✅ {message}")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(f"❌ {message}")
                        else:
                            st.error("❌ Harap centang konfirmasi untuk menghapus riwayat!")
            else:
                st.info("🔭 Belum ada riwayat untuk dihapus.")

# Penggunaan
elif menu == "📝 Penggunaan":
    st.header("📝 Kelola Penggunaan")

    tab1, tab2 = st.tabs(["📤 Gunakan Barang", "📜 Riwayat Penggunaan"])

    with tab1:
        st.subheader("📤 Gunakan Barang")

        if st.session_state.get('submission_success', False):
            st.success("✅ Penggunaan berhasil diproses!")
            st.balloons()
            st.session_state.submission_success = False

        df_barang = get_barang()
        df_available = df_barang[df_barang['stok'] > 0] if not df_barang.empty else pd.DataFrame()

        if not df_available.empty:
            barang_options = {f"{row['nama_barang']} ({row['gudang']}) - Tersedia: {row['stok']} {row['besaran_stok']}": row['id']
                            for _, row in df_available.iterrows()}

            with st.form("form_penggunaan_fixed", clear_on_submit=False):
                col1, col2 = st.columns(2)
                with col1:
                    selected_barang = st.selectbox("📦 Pilih Barang", list(barang_options.keys()))
                    jumlah_pinjam = st.number_input("📊 Jumlah Gunakan", min_value=1, value=1, step=1)
                    unit_options = generate_unit_options()
                    unit = st.selectbox("🏠 Digunakan untuk Unit", unit_options)
                with col2:
                    tanggal_pinjam = st.date_input("📅 Tanggal Gunakan", value=datetime.now().date())
                    st.write("")

                submitted = st.form_submit_button("📤 Konfirmasi Penggunaan", use_container_width=True)

                if submitted and not st.session_state.get('form_submitted', False):
                    st.session_state.form_submitted = True

                    barang_id = barang_options[selected_barang]
                    barang_data = get_barang_by_id(barang_id)

                    if barang_data:
                        success, message = add_peminjaman(
                            barang_id,
                            barang_data[1],
                            jumlah_pinjam,
                            tanggal_pinjam,
                            unit,
                            barang_data[3],
                            barang_data[4]
                        )

                        if success:
                            st.session_state.submission_success = True
                            st.session_state.form_submitted = False
                            st.rerun()
                        else:
                            st.error(f"❌ {message}")
                            st.session_state.form_submitted = False
                    else:
                        st.error("❌ Barang tidak ditemukan!")
                        st.session_state.form_submitted = False

                elif submitted:
                    st.info("⏳ Penggunaan sedang diproses...")

        else:
            st.warning("⚠️ Tidak ada barang yang tersedia untuk digunakan.")

    with tab2:
        st.subheader("📜 Riwayat Penggunaan")

        tab_view, tab_delete = st.tabs(["👁️ Lihat Riwayat", "🗑️ Hapus Riwayat"])

        with tab_view:
            df_peminjaman = get_peminjaman()

            if not df_peminjaman.empty:
                col1, col2, col3 = st.columns(3)
                with col1:
                    start_date = st.date_input("📅 Dari Tanggal", value=datetime.now().date() - timedelta(days=30))
                with col2:
                    end_date = st.date_input("📅 Sampai Tanggal", value=datetime.now().date())
                with col3:
                    search_barang = st.text_input("🔍 Cari Barang")

                mask = (pd.to_datetime(df_peminjaman['tanggal_pinjam'], errors='coerce').dt.date >= start_date) & (pd.to_datetime(df_peminjaman['tanggal_pinjam'], errors='coerce').dt.date <= end_date)
                df_filtered = df_peminjaman.loc[mask]

                if search_barang:
                    df_filtered = df_filtered[df_filtered['nama_barang'].str.contains(search_barang, case=False)]

                if not df_filtered.empty:
                    st.info(f"📊 Menampilkan {len(df_filtered)} transaksi penggunaan")

                    display_df = df_filtered.copy()
                    display_df = display_df.rename(columns={
                        'id': 'ID',
                        'nama_barang': 'Nama Barang',
                        'jumlah_pinjam': 'Jumlah Penggunaan',
                        'tanggal_pinjam': 'Tanggal Penggunaan',
                        'unit': 'Unit',
                        'besaran_stok': 'Satuan',
                        'gudang': 'Gudang'
                    })

                    st.dataframe(display_df[['ID', 'Nama Barang', 'Jumlah Penggunaan', 'Tanggal Penggunaan', 'Unit', 'Satuan', 'Gudang']], use_container_width=True)

                    total_transaksi = len(df_filtered)
                    total_barang = df_filtered['jumlah_pinjam'].sum()

                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("📊 Total Transaksi", total_transaksi)
                    with col2:
                        st.metric("📦 Total Barang Digunakan", total_barang)

                    # Download Excel
                    create_excel_download(display_df[['ID', 'Nama Barang', 'Jumlah Penggunaan', 'Tanggal Penggunaan', 'Unit', 'Satuan', 'Gudang']], "riwayat_penggunaan", "📥 Download Excel")
                else:
                    st.info("🔭 Tidak ada penggunaan dalam rentang tanggal tersebut.")
            else:
                st.info("🔭 Belum ada riwayat penggunaan.")

        with tab_delete:
            st.warning("⚠️ **PERHATIAN:** Hapus riwayat hanya untuk koreksi kesalahan input. Stok barang TIDAK akan dikembalikan!")

            df_peminjaman = get_peminjaman()

            if not df_peminjaman.empty:
                penggunaan_options = {f"ID-{row['id']}: {row['nama_barang']} ({row['jumlah_pinjam']} {row['besaran_stok']}) - Unit {row['unit']} - {row['tanggal_pinjam']}": row['id']
                                     for _, row in df_peminjaman.iterrows()}

                with st.form("form_hapus_penggunaan"):
                    selected_penggunaan = st.selectbox("🗑️ Pilih riwayat penggunaan yang akan dihapus", list(penggunaan_options.keys()))

                    st.markdown("**Konfirmasi penghapusan:**")
                    confirm = st.checkbox("✅ Saya yakin ingin menghapus riwayat ini")

                    submitted = st.form_submit_button("🗑️ HAPUS RIWAYAT", type="secondary", use_container_width=True)

                    if submitted:
                        if confirm:
                            penggunaan_id = penggunaan_options[selected_penggunaan]
                            success, message = delete_penggunaan(penggunaan_id)

                            if success:
                                st.success(f"✅ {message}")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(f"❌ {message}")
                        else:
                            st.error("❌ Harap centang konfirmasi untuk menghapus riwayat!")
            else:
                st.info("🔭 Belum ada riwayat untuk dihapus.")

# Laporan
elif menu == "📊 Laporan":
    st.header("📊 Laporan Penggunaan")

    df_peminjaman = get_peminjaman()

    if not df_peminjaman.empty:
        df_peminjaman['tanggal_pinjam'] = pd.to_datetime(df_peminjaman['tanggal_pinjam'], errors='coerce')

        st.sidebar.subheader("🏠 Filter Unit")
        unit_options = ["Semua Unit"] + sorted(df_peminjaman['unit'].unique().tolist())
        selected_unit = st.sidebar.selectbox("Pilih Unit", unit_options)

        if selected_unit != "Semua Unit":
            df_peminjaman = df_peminjaman[df_peminjaman['unit'] == selected_unit]
            st.info(f"📋 Menampilkan data untuk unit: {selected_unit}")

        st.subheader("📅 Laporan Harian")
        tanggal_pilih = st.date_input("📅 Pilih Tanggal", value=datetime.now().date())

        df_harian = df_peminjaman[df_peminjaman['tanggal_pinjam'].dt.date == tanggal_pilih]

        if not df_harian.empty:
            col1, col2 = st.columns(2)
            with col1:
                st.metric("📊 Transaksi Hari Ini", len(df_harian))
            with col2:
                st.metric("📦 Total Barang", df_harian['jumlah_pinjam'].sum())

            display_harian = df_harian.copy()
            display_harian['tanggal_pinjam'] = display_harian['tanggal_pinjam'].dt.date
            display_harian = display_harian.rename(columns={
                'nama_barang': 'Nama Barang',
                'jumlah_pinjam': 'Jumlah Penggunaan',
                'tanggal_pinjam': 'Tanggal Penggunaan',
                'unit': 'Unit',
                'besaran_stok': 'Satuan',
                'gudang': 'Gudang'
            })
            st.dataframe(display_harian[['Nama Barang', 'Jumlah Penggunaan', 'Tanggal Penggunaan', 'Unit', 'Satuan', 'Gudang']], use_container_width=True)

            # Download Excel
            create_excel_download(display_harian[['Nama Barang', 'Jumlah Penggunaan', 'Tanggal Penggunaan', 'Unit', 'Satuan', 'Gudang']], "laporan_harian", "📥 Download Excel")

            chart_data = df_harian.groupby('nama_barang')['jumlah_pinjam'].sum().reset_index()
            chart_data = chart_data.rename(columns={'jumlah_pinjam': 'Jumlah Penggunaan', 'nama_barang': 'Nama Barang'})
            if len(chart_data) > 0:
                fig = px.bar(chart_data, x='Nama Barang', y='Jumlah Penggunaan',
                             title=f"📊 Penggunaan per Barang - {tanggal_pilih}",
                             labels={'Jumlah Penggunaan': 'Jumlah Digunakan', 'Nama Barang': 'Nama Barang'})
                fig.update_layout(xaxis_tickangle=-45, height=400, margin=dict(l=20, r=20, t=40, b=80))
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info(f"🔭 Tidak ada penggunaan pada tanggal {tanggal_pilih}")

        st.markdown("---")

        st.subheader("📅 Laporan Mingguan")

        col1, col2, col3 = st.columns(3)
        with col1:
            df_weekly = df_peminjaman.copy()
            available_months = df_weekly['tanggal_pinjam'].dt.to_period('M').unique()
            if len(available_months) > 0:
                month_options = [str(month) for month in sorted(available_months)]
                selected_month = st.selectbox("📅 Pilih Bulan", month_options, index=len(month_options)-1 if month_options else 0)

                year, month = map(int, selected_month.split('-'))

                df_month = df_weekly[
                    (df_weekly['tanggal_pinjam'].dt.year == year) &
                    (df_weekly['tanggal_pinjam'].dt.month == month)
                ]

        with col2:
            week_filter = st.selectbox("📊 Filter Minggu", ["Semua Minggu", "Minggu 1", "Minggu 2", "Minggu 3", "Minggu 4"])

        if 'df_month' in locals() and not df_month.empty:
            df_month = df_month.copy()
            df_month['iso_week'] = df_month['tanggal_pinjam'].dt.isocalendar().week
            df_month['week_of_month'] = ((df_month['tanggal_pinjam'].dt.day - 1) // 7) + 1
            df_month['minggu'] = df_month['tanggal_pinjam'].apply(
                lambda x: f"{x.year}-W{x.isocalendar()[1]:02d}"
            )

            if week_filter != "Semua Minggu":
                week_num = int(week_filter.split()[1])
                df_month = df_month[df_month['week_of_month'] == week_num]

            weekly_data = df_month.groupby(['minggu', 'nama_barang'])['jumlah_pinjam'].sum().reset_index()

            weekly_data = weekly_data.rename(columns={
                'minggu': 'Minggu',
                'nama_barang': 'Nama Barang',
                'jumlah_pinjam': 'Jumlah Penggunaan'
            })

            if not weekly_data.empty:
                filter_text = f" - {week_filter}" if week_filter != "Semua Minggu" else ""
                st.info(f"📊 Laporan mingguan untuk {selected_month}{filter_text}")
                st.dataframe(weekly_data, use_container_width=True)

                # Download Excel
                create_excel_download(weekly_data, "laporan_mingguan", "📥 Download Excel")

                # CHART BARU - Style seperti Dashboard
                fig_weekly = px.bar(weekly_data, x='Nama Barang', y='Jumlah Penggunaan',
                                    color='Minggu',
                                    title=f"📈 Trend Penggunaan Mingguan - {selected_month}{filter_text}",
                                    labels={'Jumlah Penggunaan': 'Jumlah Digunakan', 'Nama Barang': 'Nama Barang'},
                                    barmode='group')
                fig_weekly.update_layout(
                    xaxis_tickangle=-45,
                    height=400,
                    margin=dict(l=20, r=20, t=40, b=80),
                    showlegend=True
                )
                st.plotly_chart(fig_weekly, use_container_width=True)
            else:
                st.info(f"🔭 Tidak ada data penggunaan untuk {week_filter} bulan {selected_month}")
        elif 'available_months' in locals() and len(available_months) == 0:
            st.info("🔭 Belum ada data penggunaan untuk laporan mingguan")

        st.markdown("---")

        st.subheader("📅 Laporan Bulanan")

        df_monthly = df_peminjaman.copy()
        df_monthly['bulan'] = df_monthly['tanggal_pinjam'].dt.strftime('%Y-%m')
        available_months_monthly = sorted(df_monthly['bulan'].unique().tolist())

        if available_months_monthly:
            col1, col2 = st.columns([1, 2])
            with col1:
                selected_month_filter = st.selectbox(
                    "📅 Pilih Bulan untuk Laporan",
                    ["Semua Bulan"] + available_months_monthly,
                    index=0
                )

            if selected_month_filter != "Semua Bulan":
                df_monthly_filtered = df_monthly[df_monthly['bulan'] == selected_month_filter]
                monthly_data = df_monthly_filtered.groupby(['bulan', 'nama_barang'])['jumlah_pinjam'].sum().reset_index()
                monthly_data = monthly_data.rename(columns={
                    'bulan': 'Bulan',
                    'nama_barang': 'Nama Barang',
                    'jumlah_pinjam': 'Jumlah Penggunaan'
                })
                chart_title = f"📈 Penggunaan Bulanan - {selected_month_filter}"
            else:
                monthly_data = df_monthly.groupby(['bulan', 'nama_barang'])['jumlah_pinjam'].sum().reset_index()
                monthly_data = monthly_data.rename(columns={
                    'bulan': 'Bulan',
                    'nama_barang': 'Nama Barang',
                    'jumlah_pinjam': 'Jumlah Penggunaan'
                })
                chart_title = "📈 Trend Penggunaan Bulanan (Semua Bulan)"

            if not monthly_data.empty:
                st.dataframe(monthly_data, use_container_width=True)

                # Download Excel
                create_excel_download(monthly_data, "laporan_bulanan", "📥 Download Excel")

                # CHART BARU - Style seperti Dashboard
                fig_monthly = px.bar(monthly_data, x='Nama Barang', y='Jumlah Penggunaan',
                                     color='Bulan',
                                     title=chart_title,
                                     labels={'Jumlah Penggunaan': 'Jumlah Digunakan', 'Nama Barang': 'Nama Barang'},
                                     barmode='group')
                fig_monthly.update_layout(
                    xaxis_tickangle=-45,
                    height=400,
                    margin=dict(l=20, r=20, t=40, b=80),
                    showlegend=True
                )
                st.plotly_chart(fig_monthly, use_container_width=True)

                if selected_month_filter != "Semua Bulan":
                    total_penggunaan = monthly_data['Jumlah Penggunaan'].sum()
                    total_jenis = len(monthly_data['Nama Barang'].unique())

                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("📦 Total Penggunaan", total_penggunaan)
                    with col2:
                        st.metric("📋 Jenis Barang", total_jenis)

    else:
        st.info("🔭 Belum ada data penggunaan untuk membuat laporan.")

# Stok Rendah
elif menu == "⚠️ Stok Rendah":
    st.header("⚠️ Monitor Stok Rendah")

    stok_rendah = check_stok_rendah()

    if not stok_rendah.empty:
        st.error(f"🚨 PERINGATAN! Ada {len(stok_rendah)} barang dengan stok kurang dari 20!")

        for _, item in stok_rendah.iterrows():
            with st.container():
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.markdown(f"**📦 {item['nama_barang']}**")
                with col2:
                    st.markdown(f"**📊 Stok:** {item['stok']} {item['besaran_stok']}")
                with col3:
                    st.markdown(f"**🏭 Gudang:** {item['gudang']}")
                st.markdown("---")

        fig = px.bar(stok_rendah, x='nama_barang', y='stok',
                     color='gudang', title="📊 Barang dengan Stok Rendah")
        fig.add_hline(y=20, line_dash="dash", line_color="red", annotation_text="⚠️ Batas Minimum (20)")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("💡 Saran Restock")
        for _, item in stok_rendah.iterrows():
            saran_restock = max(50, item['stok'] * 3)
            st.info(f"**{item['nama_barang']}**: Disarankan menambah stok hingga **{saran_restock} {item['besaran_stok']}**")
    else:
        st.success("🎉 Semua barang memiliki stok yang mencukupi!")

        df_barang = get_barang()
        if not df_barang.empty:
            df_aman = df_barang[df_barang['stok'] >= 20].nsmallest(5, 'stok')
            if not df_aman.empty:
                st.subheader("📊 5 Barang dengan Stok Terendah (Masih Aman)")
                st.dataframe(df_aman[['nama_barang', 'stok', 'besaran_stok', 'gudang']], use_container_width=True)

# Import/Export Data
elif menu == "📥 Import/Export Data":
    st.header("📥 Import/Export Data")

    tab1, tab2, tab3 = st.tabs(["📦 Import Data Barang", "📤 Import Riwayat Penggunaan", "💾 Export/Backup Data"])

    # TAB 1: IMPORT DATA BARANG (BARU)
    with tab1:
        st.subheader("📦 Import Data Barang Masuk dari Excel")
        st.warning("⚠️ **Format Excel Multi-Baris:** Header dibaca dari Baris 3 (Nama Barang, Jumlah, Satuan) dan Baris 4 (Sen-Min)")
        st.info("📋 Barang yang diimport akan ditambahkan ke stok yang sudah ada berdasarkan hari barang masuk.")

        st.markdown("""
        **Catatan Penting:**
        - **Kolom A**: Diabaikan (biasanya untuk nomor urut)
        - **Baris 3**: Mulai dari **Kolom B** → NAMA BARANG, JUMLAH (diabaikan), SATUAN
        - **Baris 4**: SEN, SEL, RAB, KAM, JUM, SAB, MIN (hari barang masuk)
        - Data dimulai dari **Baris 5**
        - Pilih **tanggal Senin** untuk setiap sheet
        - Stok barang akan **ditambahkan** sesuai hari barang masuk
        """)

        uploaded_file_barang = st.file_uploader("Upload File Excel untuk Data Barang Masuk", type=['xlsx', 'xls'], key="upload_barang")

        if uploaded_file_barang is not None:
            try:
                excel_file = pd.ExcelFile(uploaded_file_barang)
                sheet_names = excel_file.sheet_names

                st.success(f"✅ File berhasil diupload! Ditemukan {len(sheet_names)} sheet.")

                for name in sheet_names:
                    if name not in st.session_state.selected_sheets_barang:
                        st.session_state.selected_sheets_barang[name] = True

                st.markdown("---")
                st.subheader("🔧 Konfigurasi Import per Sheet")

                selected_sheets_barang = []

                for sheet_name in sheet_names:
                    default_date = st.session_state.import_barang_config.get(sheet_name, {}).get('tanggal_senin', datetime.now().date())
                    default_gudang = st.session_state.import_barang_config.get(sheet_name, {}).get('gudang', 'Gudang 1')

                    is_selected = st.checkbox(f"✅ Pilih Sheet: **{sheet_name}**",
                                              value=st.session_state.selected_sheets_barang[sheet_name],
                                              key=f"check_barang_{sheet_name}")
                    st.session_state.selected_sheets_barang[sheet_name] = is_selected

                    if is_selected:
                        selected_sheets_barang.append(sheet_name)
                        with st.expander(f"⚙️ Konfigurasi untuk {sheet_name}", expanded=False):
                            col1, col2 = st.columns(2)

                            with col1:
                                tanggal_senin = st.date_input(
                                    f"📅 Tanggal Senin minggu ini",
                                    value=default_date,
                                    key=f"date_barang_{sheet_name}",
                                    help="Pilih tanggal hari Senin dari minggu data barang masuk"
                                )

                            with col2:
                                gudang = st.selectbox(
                                    f"🏭 Gudang untuk sheet '{sheet_name}'",
                                    ["Gudang 1", "Gudang 2"],
                                    index=0 if default_gudang == "Gudang 1" else 1,
                                    key=f"gudang_barang_{sheet_name}"
                                )

                            # Preview data dengan multi-header
                            try:
                                df_row3 = pd.read_excel(uploaded_file_barang, sheet_name=sheet_name, header=2, nrows=0)
                                header_row3 = df_row3.columns.tolist()

                                df_row4 = pd.read_excel(uploaded_file_barang, sheet_name=sheet_name, header=3, nrows=0)
                                header_row4 = df_row4.columns.tolist()

                                combined_header = []
                                num_cols = max(len(header_row3), len(header_row4))

                                for i in range(num_cols):
                                    h3 = header_row3[i] if i < len(header_row3) else ''
                                    h4 = header_row4[i] if i < len(header_row4) else ''

                                    h3_clean = str(h3).lower().strip().replace(' ', '')
                                    h4_clean = str(h4).lower().strip().replace(' ', '')

                                    if i == 0:
                                        combined_header.append('skip_a')
                                    elif i == 1:
                                        combined_header.append('namabarang')
                                    elif i == 2:
                                        combined_header.append('skip_jumlah')
                                    elif i == 3:
                                        combined_header.append('satuan')
                                    elif h4_clean in ['sen', 'sel', 'rab', 'kam', 'jum', 'sab', 'min']:
                                        combined_header.append(h4_clean)
                                    else:
                                        combined_header.append('skip_' + str(i))

                                df_preview = pd.read_excel(uploaded_file_barang, sheet_name=sheet_name, header=None, skiprows=4, nrows=5)

                                num_data_cols = len(df_preview.columns)
                                if len(combined_header) >= num_data_cols:
                                    df_preview.columns = combined_header[:num_data_cols]
                                else:
                                    df_preview.columns = combined_header + [f'extra_{j}' for j in range(len(combined_header), num_data_cols)]

                                st.write("**Preview Data (5 Baris Pertama):**")
                                st.dataframe(df_preview.head(5), use_container_width=True)

                            except Exception as e:
                                st.error(f"Error membaca preview: {str(e)}")

                            st.session_state.import_barang_config[sheet_name] = {
                                'tanggal_senin': tanggal_senin,
                                'gudang': gudang
                            }
                    else:
                        if sheet_name in st.session_state.import_barang_config:
                            del st.session_state.import_barang_config[sheet_name]

                st.markdown("---")
                st.info(f"Total {len(selected_sheets_barang)} sheet terpilih untuk diimpor.")

                col1, col2, col3 = st.columns([1, 2, 1])
                with col2:
                    if st.button("🚀 Proses Import Data Barang Masuk", type="primary", use_container_width=True, key="import_barang_btn"):
                        if not selected_sheets_barang:
                            st.error("❌ Tidak ada sheet yang dipilih untuk diimpor!")
                            st.stop()

                        with st.spinner("Memproses import data barang masuk..."):
                            total_imported = 0
                            total_updated = 0
                            errors = []

                            conn = sqlite3.connect('inventory_rumah.db')
                            c = conn.cursor()

                            for sheet_name in selected_sheets_barang:
                                try:
                                    # Baca multi-header
                                    df_row3 = pd.read_excel(uploaded_file_barang, sheet_name=sheet_name, header=2, nrows=0)
                                    header_row3 = df_row3.columns.tolist()

                                    df_row4 = pd.read_excel(uploaded_file_barang, sheet_name=sheet_name, header=3, nrows=0)
                                    header_row4 = df_row4.columns.tolist()

                                    combined_header = []
                                    num_cols = max(len(header_row3), len(header_row4))

                                    for i in range(num_cols):
                                        h3 = header_row3[i] if i < len(header_row3) else ''
                                        h4 = header_row4[i] if i < len(header_row4) else ''

                                        h3_clean = str(h3).lower().strip().replace(' ', '')
                                        h4_clean = str(h4).lower().strip().replace(' ', '')

                                        if i == 0:
                                            combined_header.append('skip_a')
                                        elif i == 1:
                                            combined_header.append('namabarang')
                                        elif i == 2:
                                            combined_header.append('skip_jumlah')
                                        elif i == 3:
                                            combined_header.append('satuan')
                                        elif h4_clean in ['sen', 'sel', 'rab', 'kam', 'jum', 'sab', 'min']:
                                            combined_header.append(h4_clean)
                                        else:
                                            combined_header.append('skip_' + str(i))

                                    df = pd.read_excel(uploaded_file_barang, sheet_name=sheet_name, header=None, skiprows=4)
                                    num_data_cols = len(df.columns)

                                    if len(combined_header) >= num_data_cols:
                                        df.columns = combined_header[:num_data_cols]
                                    else:
                                        df.columns = combined_header + [f'extra_{j}' for j in range(len(combined_header), num_data_cols)]

                                    config = st.session_state.import_barang_config.get(sheet_name)
                                    if not config:
                                        errors.append(f"Sheet '{sheet_name}': Konfigurasi tidak ditemukan.")
                                        continue

                                    tanggal_senin = config['tanggal_senin']
                                    gudang = config['gudang']

                                    hari_cols = ['sen', 'sel', 'rab', 'kam', 'jum', 'sab', 'min']

                                    for idx, row in df.iterrows():
                                        nama_barang = str(row.get('namabarang', '')).strip()
                                        satuan = str(row.get('satuan', '')).strip()

                                        if not nama_barang or nama_barang == 'nan':
                                            continue

                                        if not satuan or satuan == 'nan':
                                            satuan = 'pcs'

                                        for day_idx, hari in enumerate(hari_cols):
                                            if hari not in df.columns:
                                                continue

                                            jumlah = row.get(hari, 0)

                                            try:
                                                if pd.isna(jumlah) or jumlah is None or str(jumlah).strip() == '':
                                                    jumlah = 0
                                                else:
                                                    jumlah = int(float(jumlah))
                                            except Exception:
                                                jumlah = 0

                                            if jumlah <= 0:
                                                continue

                                            tanggal_masuk = tanggal_senin + timedelta(days=day_idx)

                                            c.execute("SELECT id, stok FROM barang WHERE LOWER(nama_barang) = LOWER(?) AND LOWER(gudang) = LOWER(?)",
                                                      (nama_barang, gudang))
                                            existing = c.fetchone()

                                            if existing:
                                                # Update stok yang sudah ada
                                                barang_id, stok_lama = existing
                                                stok_baru = stok_lama + jumlah
                                                c.execute("UPDATE barang SET stok = ?, besaran_stok = ? WHERE id = ?",
                                                          (stok_baru, satuan, barang_id))

                                                # Catat riwayat
                                                c.execute("""INSERT INTO riwayat_stok
                                                            (barang_id, nama_barang, jumlah_tambah, stok_sebelum, stok_sesudah, gudang, tanggal_tambah)
                                                            VALUES (?, ?, ?, ?, ?, ?, ?)""",
                                                            (barang_id, nama_barang, jumlah, stok_lama, stok_baru, gudang, tanggal_masuk))

                                                total_updated += 1
                                            else:
                                                # Tambah barang baru
                                                c.execute("INSERT INTO barang (nama_barang, stok, besaran_stok, gudang, created_at) VALUES (?, ?, ?, ?, ?)",
                                                          (nama_barang, jumlah, satuan, gudang, tanggal_masuk))

                                                barang_id = c.lastrowid

                                                # Catat riwayat
                                                c.execute("""INSERT INTO riwayat_stok
                                                            (barang_id, nama_barang, jumlah_tambah, stok_sebelum, stok_sesudah, gudang, tanggal_tambah)
                                                            VALUES (?, ?, ?, ?, ?, ?, ?)""",
                                                            (barang_id, nama_barang, jumlah, 0, jumlah, gudang, tanggal_masuk))

                                                total_imported += 1

                                except Exception as e:
                                    errors.append(f"Sheet '{sheet_name}': {str(e)}")

                            conn.commit()
                            conn.close()

                            if total_imported > 0 or total_updated > 0:
                                st.success(f"✅ Berhasil import barang masuk! **{total_imported}** barang baru dan **{total_updated}** penambahan stok!")
                                st.balloons()
                            else:
                                st.warning("⚠️ Tidak ada barang yang berhasil diimport. Cek format file Excel Anda.")

                            if errors:
                                st.error("⚠️ Beberapa **error** terjadi selama import:")
                                for error in errors:
                                    st.write(f"- {error}")

                            st.session_state.import_barang_config = {}
                            st.session_state.selected_sheets_barang = {}
                            time.sleep(2)
                            st.rerun()

            except Exception as e:
                st.error(f"❌ Error membaca file: {str(e)}")
                st.write("Pastikan file Excel Anda memiliki format yang benar dan tidak rusak.")

    # TAB 2: IMPORT RIWAYAT PENGGUNAAN
    with tab2:
        st.subheader("📤 Import Riwayat Penggunaan dari Excel")
        st.warning("⚠️ **Format Excel Multi-Baris:** Header dibaca dari Baris 2 (Nama Barang, Satuan) dan Baris 3 (Sen-Min)")
        st.info("📋 Sistem akan mencoba menggabungkan header dari kedua baris untuk membaca data dengan benar.")

        st.markdown("""
        **Catatan Penting:**
        - **Baris 2**: NAMA BARANG dimulai dari **Kolom B**. Kolom A diabaikan.
        - **Baris 3**: SEN, SEL, RAB, KAM, JUM, SAB, MIN
        - Kolom `JUMLAH` (Qty) di **Kolom C** akan **diabaikan**.
        - Stok barang **TIDAK** akan dikurangi.
        """)

        uploaded_file = st.file_uploader("Upload File Excel", type=['xlsx', 'xls'], key="upload_penggunaan")

        if uploaded_file is not None:
            try:
                excel_file = pd.ExcelFile(uploaded_file)
                sheet_names = excel_file.sheet_names

                st.success(f"✅ File berhasil diupload! Ditemukan {len(sheet_names)} sheet.")

                for name in sheet_names:
                    if name not in st.session_state.selected_sheets:
                        st.session_state.selected_sheets[name] = True

                st.markdown("---")
                st.subheader("🔧 Konfigurasi Import per Sheet")

                selected_sheets_for_import = []

                for sheet_name in sheet_names:
                    default_unit = st.session_state.import_config.get(sheet_name, {}).get('unit', 'A1')
                    default_date = st.session_state.import_config.get(sheet_name, {}).get('tanggal_senin', datetime.now().date())

                    is_selected = st.checkbox(f"✅ Pilih Sheet: **{sheet_name}**",
                                              value=st.session_state.selected_sheets[sheet_name],
                                              key=f"check_{sheet_name}")
                    st.session_state.selected_sheets[sheet_name] = is_selected

                    if is_selected:
                        selected_sheets_for_import.append(sheet_name)
                        with st.expander(f"⚙️ Konfigurasi untuk {sheet_name}", expanded=False):
                            col1, col2 = st.columns(2)

                            with col1:
                                unit_options = generate_unit_options()
                                unit = st.selectbox(
                                    f"🏠 Unit untuk sheet '{sheet_name}'",
                                    unit_options,
                                    index=unit_options.index(default_unit) if default_unit in unit_options else 0,
                                    key=f"unit_{sheet_name}"
                                )

                            with col2:
                                tanggal_senin = st.date_input(
                                    f"📅 Tanggal Senin minggu ini",
                                    value=default_date,
                                    key=f"date_{sheet_name}",
                                    help="Pilih tanggal hari Senin dari minggu data ini"
                                )

                            try:
                                df_row2 = pd.read_excel(uploaded_file, sheet_name=sheet_name, header=1, nrows=0)
                                header_row2 = df_row2.columns.tolist()

                                df_row3 = pd.read_excel(uploaded_file, sheet_name=sheet_name, header=2, nrows=0)
                                header_row3 = df_row3.columns.tolist()

                                combined_header = []
                                num_cols = max(len(header_row2), len(header_row3))

                                for i in range(num_cols):
                                    h2 = header_row2[i] if i < len(header_row2) else ''
                                    h3 = header_row3[i] if i < len(header_row3) else ''

                                    h2_clean = str(h2).lower().strip().replace(' ', '')
                                    h3_clean = str(h3).lower().strip().replace(' ', '')

                                    if i == 0:
                                        combined_header.append('skip_a')
                                    elif i == 1:
                                        combined_header.append('namabarang')
                                    elif i == 2:
                                        combined_header.append('skip_jumlah')
                                    elif i == 3:
                                        combined_header.append('satuan')
                                    elif h3_clean in ['sen', 'sel', 'rab', 'kam', 'jum', 'sab', 'min']:
                                        combined_header.append(h3_clean)
                                    else:
                                        combined_header.append('skip_' + str(i))

                                df_preview = pd.read_excel(uploaded_file, sheet_name=sheet_name, header=None, skiprows=3, nrows=5)

                                num_data_cols = len(df_preview.columns)
                                if len(combined_header) >= num_data_cols:
                                    df_preview.columns = combined_header[:num_data_cols]
                                else:
                                    df_preview.columns = combined_header + [f'extra_{j}' for j in range(len(combined_header), num_data_cols)]

                                st.write("**Preview Data (5 Baris Pertama):**")
                                st.dataframe(df_preview.head(5), use_container_width=True)

                            except Exception as e:
                                st.error(f"Error membaca preview: {str(e)}")

                            st.session_state.import_config[sheet_name] = {
                                'unit': unit,
                                'tanggal_senin': tanggal_senin
                            }
                    else:
                        if sheet_name in st.session_state.import_config:
                            del st.session_state.import_config[sheet_name]

                st.markdown("---")
                st.info(f"Total {len(selected_sheets_for_import)} sheet terpilih untuk diimpor.")

                col1, col2, col3 = st.columns([1, 2, 1])
                with col2:
                    if st.button("🚀 Proses Import Sheet Terpilih", type="primary", use_container_width=True, key="import_penggunaan_btn"):
                        if not selected_sheets_for_import:
                            st.error("❌ Tidak ada sheet yang dipilih untuk diimpor!")
                            st.stop()

                        with st.spinner("Memproses import data..."):
                            total_imported = 0
                            errors = []

                            conn = sqlite3.connect('inventory_rumah.db')
                            c = conn.cursor()

                            for sheet_name in selected_sheets_for_import:
                                try:
                                    df_row2 = pd.read_excel(uploaded_file, sheet_name=sheet_name, header=1, nrows=0)
                                    header_row2 = df_row2.columns.tolist()

                                    df_row3 = pd.read_excel(uploaded_file, sheet_name=sheet_name, header=2, nrows=0)
                                    header_row3 = df_row3.columns.tolist()

                                    combined_header = []
                                    num_cols = max(len(header_row2), len(header_row3))

                                    for i in range(num_cols):
                                        h2 = header_row2[i] if i < len(header_row2) else ''
                                        h3 = header_row3[i] if i < len(header_row3) else ''

                                        h2_clean = str(h2).lower().strip().replace(' ', '')
                                        h3_clean = str(h3).lower().strip().replace(' ', '')

                                        if i == 0:
                                            combined_header.append('skip_a')
                                        elif i == 1:
                                            combined_header.append('namabarang')
                                        elif i == 2:
                                            combined_header.append('skip_jumlah')
                                        elif i == 3:
                                            combined_header.append('satuan')
                                        elif h3_clean in ['sen', 'sel', 'rab', 'kam', 'jum', 'sab', 'min']:
                                            combined_header.append(h3_clean)
                                        else:
                                            combined_header.append('skip_' + str(i))

                                    df = pd.read_excel(uploaded_file, sheet_name=sheet_name, header=None, skiprows=3)
                                    num_data_cols = len(df.columns)

                                    if len(combined_header) >= num_data_cols:
                                        df.columns = combined_header[:num_data_cols]
                                    else:
                                        df.columns = combined_header + [f'extra_{j}' for j in range(len(combined_header), num_data_cols)]

                                    config = st.session_state.import_config.get(sheet_name)
                                    if not config:
                                        errors.append(f"Sheet '{sheet_name}': Konfigurasi tidak ditemukan.")
                                        continue

                                    unit = config['unit']
                                    tanggal_senin = config['tanggal_senin']

                                    hari_cols = ['sen', 'sel', 'rab', 'kam', 'jum', 'sab', 'min']

                                    for idx, row in df.iterrows():
                                        nama_barang = str(row.get('namabarang', '')).strip()
                                        satuan = str(row.get('satuan', '')).strip()

                                        if not nama_barang or nama_barang == 'nan':
                                            continue

                                        if not satuan or satuan == 'nan':
                                            satuan = 'pcs'

                                        for day_idx, hari in enumerate(hari_cols):
                                            if hari not in df.columns:
                                                continue

                                            jumlah = row.get(hari, 0)

                                            try:
                                                if pd.isna(jumlah) or jumlah is None or str(jumlah).strip() == '':
                                                    jumlah = 0
                                                else:
                                                    jumlah = int(float(jumlah))
                                            except Exception:
                                                jumlah = 0

                                            if jumlah <= 0:
                                                continue

                                            tanggal_penggunaan = tanggal_senin + timedelta(days=day_idx)

                                            c.execute("""INSERT INTO peminjaman
                                                             (barang_id, nama_barang, jumlah_pinjam, tanggal_pinjam,
                                                              unit, besaran_stok, gudang)
                                                             VALUES (NULL, ?, ?, ?, ?, ?, 'Gudang 1')""",
                                                            (nama_barang, jumlah, tanggal_penggunaan, unit, satuan))

                                            total_imported += 1

                                except Exception as e:
                                    errors.append(f"Sheet '{sheet_name}': {str(e)}")

                            conn.commit()
                            conn.close()

                            if total_imported > 0:
                                st.success(f"✅ Berhasil import **{total_imported}** transaksi penggunaan dari {len(selected_sheets_for_import)} sheet!")
                                st.balloons()
                            else:
                                st.warning("⚠️ Tidak ada transaksi yang berhasil diimport. Cek format file Excel Anda.")

                            if errors:
                                st.error("⚠️ Beberapa **error** terjadi selama import:")
                                for error in errors:
                                    st.write(f"- {error}")

                            st.session_state.import_config = {}
                            st.session_state.selected_sheets = {}
                            time.sleep(2)
                            st.rerun()

            except Exception as e:
                st.error(f"❌ Error membaca file: {str(e)}")
                st.write("Pastikan file Excel Anda memiliki format yang benar dan tidak rusak.")

    with tab3:
        st.subheader("💾 Export/Backup Data")
        st.info("💡 Pastikan pustaka `xlsxwriter` dan `openpyxl` sudah terinstal di lingkungan Anda untuk fungsi export ini.")
        st.code("!pip install xlsxwriter openpyxl", language='bash')
        st.markdown("---")

        st.markdown("""
        **Export data aplikasi ke Excel untuk backup atau analisis lebih lanjut.**

        File akan berisi 3 sheet:
        1. **Data Barang**
        2. **Riwayat Penggunaan**
        3. **Riwayat Kelola Barang**
        """)

        col1, col2 = st.columns(2)

        with col1:
            if st.button("📥 Buat File Backup Excel", type="primary", use_container_width=True):
                st.session_state['ready_to_download_excel'] = True

            if st.session_state.get('ready_to_download_excel'):
                try:
                    df_barang = get_barang()
                    df_penggunaan = get_peminjaman()
                    df_riwayat = get_riwayat_stok()

                    df_penggunaan_export = df_penggunaan.copy().rename(columns={
                        'tanggal_pinjam': 'Tanggal Penggunaan'
                    })

                    df_riwayat_export = df_riwayat.copy().rename(columns={
                        'jumlah_tambah': 'Jumlah Perubahan (+/-)',
                        'tanggal_tambah': 'Tanggal Transaksi',
                        'stok_sebelum': 'Stok Sebelum',
                        'stok_sesudah': 'Stok Sesudah',
                    })

                    sheets_to_export = [
                        ('Data Barang', df_barang),
                        ('Riwayat Penggunaan', df_penggunaan_export),
                        ('Riwayat Kelola Barang', df_riwayat_export)
                    ]

                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        for sheet_name, df in sheets_to_export:
                            if not df.empty:
                                df.to_excel(writer, sheet_name=sheet_name, index=False)

                                worksheet = writer.sheets[sheet_name]

                                max_row = len(df)
                                max_col = len(df.columns) - 1

                                worksheet.autofilter(0, 0, max_row, max_col)

                    output.seek(0)

                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"backup_inventory_{timestamp}.xlsx"

                    st.download_button(
                        label="⬇️ Klik untuk Download Excel",
                        data=output,
                        file_name=filename,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

                    st.success("✅ File backup Excel siap didownload!")
                    if 'ready_to_download_excel' in st.session_state:
                        del st.session_state['ready_to_download_excel']

                except Exception as e:
                    st.error(f"❌ Error membuat backup Excel: {str(e)}. Coba jalankan perintah instalasi di atas!")

        with col2:
            if st.button("📄 Download Database File (.db)", use_container_width=True):
                st.session_state['ready_to_download_db'] = True

            if st.session_state.get('ready_to_download_db'):
                try:
                    with open('inventory_rumah.db', 'rb') as f:
                        db_data = f.read()

                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"inventory_database_{timestamp}.db"

                    st.download_button(
                        label="⬇️ Klik untuk Download DB",
                        data=db_data,
                        file_name=filename,
                        mime="application/x-sqlite3"
                    )

                    st.success("✅ Database file siap didownload!")
                    if 'ready_to_download_db' in st.session_state:
                        del st.session_state['ready_to_download_db']

                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")

            st.markdown("---")
            st.info("💡 **Tips:** Simpan backup secara rutin (minimal seminggu sekali) untuk keamanan data Anda.")

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; padding: 20px;">
    <h4>🏭 Aplikasi Inventory Gudang v3.7</h4>
    <p>🚀 Running on Google Colab | Built with ❤️ using Streamlit & SQLite</p>
    <p>📱 Kelola inventory Gudang Anda dengan mudah!</p>
    <br>
    <p><strong>✨ Update v3.7:</strong></p>
    <p>✅ Chart Laporan Mingguan & Bulanan Diperbaiki | ✅ Style Sama dengan Dashboard | ✅ Grouped Bar Chart</p>
</div>
""", unsafe_allow_html=True)