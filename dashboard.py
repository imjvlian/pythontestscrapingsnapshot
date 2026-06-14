import streamlit as st
import pandas as pd
import os

DATA_DIR = "data"

st.set_page_config(page_title="Dashboard Perumahan Lumajang", layout="wide")

st.title("Dashboard Penjualan Perumahan Lumajang")


# =========================
# LOAD TREND HARIAN
# =========================
def load_trend():
    files = sorted([f for f in os.listdir(DATA_DIR) if f.startswith("snapshot_")])

    rows = []

    for i in range(1, len(files)):
        df_old = pd.read_csv(os.path.join(DATA_DIR, files[i-1]))
        df_new = pd.read_csv(os.path.join(DATA_DIR, files[i]))

        date = files[i].replace("snapshot_", "").replace(".csv", "")

        merged = df_old.merge(df_new, on="kode", suffixes=("_old", "_new"))

        merged["penurunan"] = (
            merged["subsidi_old"] - merged["subsidi_new"]
        ) + (
            merged["komersil_old"] - merged["komersil_new"]
        )

        total = merged[merged["penurunan"] > 0]["penurunan"].sum()

        rows.append({
            "tanggal": date,
            "total_penjualan": total
        })

    return pd.DataFrame(rows)


# =========================
# LOAD DATA TERBARU
# =========================
def load_latest():
    files = sorted([f for f in os.listdir(DATA_DIR) if f.startswith("snapshot_")])
    if not files:
        return pd.DataFrame()

    latest = files[-1]
    return pd.read_csv(os.path.join(DATA_DIR, latest))


# =========================
# LOAD PENJUALAN TERAKHIR
# =========================
def load_sales_data():
    files = sorted([f for f in os.listdir(DATA_DIR) if f.startswith("snapshot_")])

    if len(files) < 2:
        return pd.DataFrame()

    df_old = pd.read_csv(os.path.join(DATA_DIR, files[-2]))
    df_new = pd.read_csv(os.path.join(DATA_DIR, files[-1]))

    merged = df_old.merge(df_new, on="kode", suffixes=("_old", "_new"))

    merged["terjual_subsidi"] = merged["subsidi_old"] - merged["subsidi_new"]
    merged["terjual_komersil"] = merged["komersil_old"] - merged["komersil_new"]
    merged["total_terjual"] = merged["terjual_subsidi"] + merged["terjual_komersil"]

    sold = merged[merged["total_terjual"] > 0]

    return sold.sort_values("total_terjual", ascending=False)


# =========================
# LOAD SALES BULANAN
# =========================
def load_monthly_sales():
    files = sorted([f for f in os.listdir(DATA_DIR) if f.startswith("sales_")])

    if not files:
        return pd.DataFrame()

    all_data = []

    for f in files:
        df = pd.read_csv(os.path.join(DATA_DIR, f))
        date = f.replace("sales_", "").replace(".csv", "")
        df["tanggal"] = pd.to_datetime(date)
        all_data.append(df)

    return pd.concat(all_data, ignore_index=True)


# =========================
# LOAD DATA
# =========================
trend_df = load_trend()
latest_df = load_latest()
sales_df = load_sales_data()
monthly_df = load_monthly_sales()

if trend_df.empty:
    st.warning("Data belum cukup (minimal 2 hari snapshot)")
    st.stop()

trend_df["tanggal"] = pd.to_datetime(trend_df["tanggal"])


# =========================
# FILTER TANGGAL
# =========================
col1, col2 = st.columns(2)

with col1:
    start_date = st.date_input("Dari tanggal", trend_df["tanggal"].min())

with col2:
    end_date = st.date_input("Sampai tanggal", trend_df["tanggal"].max())

filtered = trend_df[
    (trend_df["tanggal"] >= pd.to_datetime(start_date)) &
    (trend_df["tanggal"] <= pd.to_datetime(end_date))
]


# =========================
# METRICS
# =========================
total_penjualan = filtered["total_penjualan"].sum()
avg_penjualan = filtered["total_penjualan"].mean()

col1, col2 = st.columns(2)
col1.metric("Total Penjualan", int(total_penjualan))
col2.metric("Rata-rata Harian", round(avg_penjualan, 2))


# =========================
# GRAFIK HARIAN
# =========================
st.subheader("Tren Penjualan Harian")
st.line_chart(filtered.set_index("tanggal")["total_penjualan"])


# =========================
# GRAFIK BULANAN
# =========================
st.subheader("Tren Penjualan Bulanan")
filtered["bulan"] = filtered["tanggal"].dt.to_period("M").astype(str)
monthly = filtered.groupby("bulan")["total_penjualan"].sum()

st.bar_chart(monthly)


# =========================
# DATA TERJUAL TERAKHIR
# =========================
st.subheader("Perumahan Terjual (Hari Terakhir)")

if sales_df.empty:
    st.info("Belum ada perubahan unit hari ini")
else:
    st.dataframe(
        sales_df[[
            "nama_old",
            "developer_old",
            "kecamatan_old",
            "terjual_subsidi",
            "terjual_komersil",
            "total_terjual"
        ]]
    )


# =========================
# TOP PENJUALAN HARIAN
# =========================
st.subheader("Top Penjualan Harian")

if not sales_df.empty:
    st.dataframe(
        sales_df[[
            "nama_old",
            "total_terjual"
        ]].head(10)
    )


# =========================
# FILTER BULAN
# =========================
st.subheader("Filter Bulan")

if not monthly_df.empty:
    monthly_df["bulan"] = monthly_df["tanggal"].dt.to_period("M").astype(str)

    selected_month = st.selectbox(
        "Pilih Bulan",
        sorted(monthly_df["bulan"].unique(), reverse=True)
    )

    filtered_month = monthly_df[monthly_df["bulan"] == selected_month]
else:
    filtered_month = pd.DataFrame()


# =========================
# TOP BULANAN
# =========================
st.subheader("Top Perumahan Terjual Bulanan")

if filtered_month.empty:
    st.info("Belum ada data penjualan bulanan")
else:
    ranking_bulanan = (
        filtered_month
        .groupby(["kode", "nama_old", "developer_old", "kecamatan_old"])["total_terjual"]
        .sum()
        .reset_index()
        .sort_values("total_terjual", ascending=False)
    )

    st.dataframe(ranking_bulanan.head(10))


# =========================
# GRAFIK BULANAN TOP
# =========================
st.subheader("Grafik Top Penjualan Bulanan")

if not filtered_month.empty:
    chart_data = ranking_bulanan.head(10).set_index("nama_old")["total_terjual"]
    st.bar_chart(chart_data)


# =========================
# SUMMARY BULANAN
# =========================
if not filtered_month.empty:
    total_bulan = ranking_bulanan["total_terjual"].sum()
    st.metric("Total Unit Terjual Bulan Ini", int(total_bulan))


# =========================
# DATA TERBARU
# =========================
st.subheader("Data Perumahan Terbaru")

if not latest_df.empty:
    st.dataframe(latest_df)


# =========================
# RAW DATA
# =========================
with st.expander("Lihat Data Trend"):
    st.dataframe(trend_df)