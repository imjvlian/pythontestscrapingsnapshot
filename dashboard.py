
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from glob import glob
import os

st.set_page_config(
    page_title="Dashboard Penjualan Perumahan Lumajang",
    layout="wide",
    initial_sidebar_state="expanded"
)

DATA_DIR = "data"

@st.cache_data(ttl=300)
def load_csv(filename):
    path = os.path.join(DATA_DIR, filename)
    if os.path.exists(path):
        try:
            return pd.read_csv(path)
        except:
            return pd.DataFrame()
    return pd.DataFrame()

@st.cache_data(ttl=300)
def load_latest(pattern):
    files = sorted(glob(os.path.join(DATA_DIR, pattern)))

    if not files:
        return pd.DataFrame()

    try:
        return pd.read_csv(files[-1])
    except:
        return pd.DataFrame()

@st.cache_data(ttl=300)
def load_all_data():

    inventory = load_csv("inventory.csv")

    if inventory.empty:
        inventory = load_latest("snapshot*.csv")

    return {

        "inventory": inventory,

        "history": load_csv("history.csv"),

        "statistics": load_csv("statistics.csv"),

        "summary": load_csv("summary.csv"),

        "ranking_harian":
            load_csv("ranking_harian.csv")
            if os.path.exists(os.path.join(DATA_DIR, "ranking_harian.csv"))
            else load_latest("ranking_*.csv"),

        "ranking_bulanan":
            load_csv("ranking_bulanan.csv")
            if os.path.exists(os.path.join(DATA_DIR, "ranking_bulanan.csv"))
            else load_latest("top10_*.csv"),

        "developer_rank":
            load_csv("developer_rank.csv"),

        "kecamatan_rank":
            load_csv("kecamatan_rank.csv")
            if os.path.exists(os.path.join(DATA_DIR, "kecamatan_rank.csv"))
            else load_latest("kecamatan_*.csv"),

        "top_sales":
            load_csv("top_sales.csv")
            if os.path.exists(os.path.join(DATA_DIR, "top_sales.csv"))
            else load_latest("sales_*.csv"),

        "weekly_growth":
            load_csv("weekly_growth.csv"),
    }

data = load_all_data()

st.title("🏠 Dashboard Monitoring Penjualan Perumahan Kabupaten Lumajang")

with st.sidebar:
    st.header("Filter")
    inventory = data["inventory"]

    kecamatan_options = ["Semua"]
    developer_options = ["Semua"]

    if not inventory.empty:
        for col in inventory.columns:
            if col.lower() == "kecamatan":
                kecamatan_options += sorted(inventory[col].dropna().astype(str).unique().tolist())
            if col.lower() == "developer":
                developer_options += sorted(inventory[col].dropna().astype(str).unique().tolist())

    selected_kecamatan = st.selectbox("Kecamatan", kecamatan_options)
    selected_developer = st.selectbox("Developer", developer_options)

    search_text = st.text_input("Cari Nama Perumahan")

    if st.button("🔄 Refresh"):
        st.cache_data.clear()
        st.rerun()

inventory_filtered = inventory.copy()

if not inventory_filtered.empty:

    if selected_kecamatan != "Semua" and "kecamatan" in [c.lower() for c in inventory_filtered.columns]:
        real_col = [c for c in inventory_filtered.columns if c.lower()=="kecamatan"][0]
        inventory_filtered = inventory_filtered[inventory_filtered[real_col].astype(str)==selected_kecamatan]

    if selected_developer != "Semua" and "developer" in [c.lower() for c in inventory_filtered.columns]:
        real_col = [c for c in inventory_filtered.columns if c.lower()=="developer"][0]
        inventory_filtered = inventory_filtered[inventory_filtered[real_col].astype(str)==selected_developer]

    if search_text:
        match_cols = [c for c in inventory_filtered.columns if "perumahan" in c.lower() or "nama" in c.lower()]
        if match_cols:
            inventory_filtered = inventory_filtered[
                inventory_filtered[match_cols[0]].astype(str).str.contains(search_text, case=False, na=False)
            ]

stats = data["statistics"]

st.subheader("📊 KPI")

c1,c2,c3,c4 = st.columns(4)

if not stats.empty and len(stats) > 0:
    row = stats.iloc[0]
    cols = stats.columns.tolist()

    c1.metric(cols[0], row.iloc[0])
    c2.metric(cols[1] if len(cols)>1 else "Metric 2", row.iloc[1] if len(cols)>1 else 0)
    c3.metric(cols[2] if len(cols)>2 else "Metric 3", row.iloc[2] if len(cols)>2 else 0)
    c4.metric(cols[3] if len(cols)>3 else "Metric 4", row.iloc[3] if len(cols)>3 else 0)
else:
    c1.metric("Total Unit", 0)
    c2.metric("Terjual", 0)
    c3.metric("Tersedia", 0)
    c4.metric("Developer", 0)

summary = data["summary"]
history = data["history"]

left,right = st.columns(2)

with left:
    st.subheader("📈 Tren Penjualan")

    if not history.empty and len(history.columns) >= 2:
        fig = px.line(
            history,
            x=history.columns[0],
            y=history.columns[1]
        )
        st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("📅 Ringkasan Harian")

    if not summary.empty:
        st.dataframe(summary, use_container_width=True)

col1,col2 = st.columns(2)

with col1:
    st.subheader("🏆 Top 10 Harian")
    ranking_harian = data["ranking_harian"]

    if not ranking_harian.empty and len(ranking_harian.columns)>=2:
        fig = px.bar(
            ranking_harian.head(10),
            x=ranking_harian.columns[1],
            y=ranking_harian.columns[0],
            orientation="h"
        )
        st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("🏅 Top 10 Bulanan")
    ranking_bulanan = data["ranking_bulanan"]

    if not ranking_bulanan.empty and len(ranking_bulanan.columns)>=2:
        fig = px.bar(
            ranking_bulanan.head(10),
            x=ranking_bulanan.columns[1],
            y=ranking_bulanan.columns[0],
            orientation="h"
        )
        st.plotly_chart(fig, use_container_width=True)

col3,col4 = st.columns(2)

with col3:
    st.subheader("👨‍💼 Ranking Developer")

    df = data["developer_rank"]

    if not df.empty and len(df.columns)>=2:
        fig = px.bar(df, x=df.columns[0], y=df.columns[1])
        st.plotly_chart(fig, use_container_width=True)

with col4:
    st.subheader("📍 Ranking Kecamatan")

    df = data["kecamatan_rank"]

    if not df.empty and len(df.columns)>=2:
        fig = px.bar(df, x=df.columns[0], y=df.columns[1])
        st.plotly_chart(fig, use_container_width=True)

st.subheader("🚀 Weekly Growth")

weekly = data["weekly_growth"]

if not weekly.empty and len(weekly.columns)>=2:
    fig = px.line(
        weekly,
        x=weekly.columns[0],
        y=weekly.columns[1],
        markers=True
    )
    st.plotly_chart(fig, use_container_width=True)

st.subheader("💰 Top Sales")

top_sales = data["top_sales"]

if not top_sales.empty:
    st.dataframe(top_sales, use_container_width=True)

st.subheader("🏠 Inventory")

st.dataframe(
    inventory_filtered,
    use_container_width=True,
    height=500
)

if not inventory_filtered.empty:
    csv = inventory_filtered.to_csv(index=False).encode("utf-8")

    st.download_button(
        "⬇ Download Inventory CSV",
        csv,
        file_name="inventory_filtered.csv",
        mime="text/csv"
    )

st.subheader("📖 History Per Perumahan")

if not history.empty:

    name_col = None

    for col in history.columns:
        if "perumahan" in col.lower() or "nama" in col.lower():
            name_col = col
            break

    if name_col:

        selected = st.selectbox(
            "Pilih Perumahan",
            sorted(history[name_col].dropna().astype(str).unique())
        )

        df_hist = history[history[name_col].astype(str)==selected]

        st.dataframe(df_hist, use_container_width=True)

        numeric_cols = df_hist.select_dtypes(include="number").columns

        if len(numeric_cols) > 0:
            fig = px.line(df_hist, y=numeric_cols[0])
            st.plotly_chart(fig, use_container_width=True)

st.caption(
    f"Last refresh: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
)

st.markdown(
    """
    <script>
    setTimeout(function(){
       window.location.reload();
    },300000);
    </script>
    """,
    unsafe_allow_html=True
)
