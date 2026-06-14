import requests
import pandas as pd
import os
from datetime import datetime

BASE_URL = "https://sikumbang.tapera.go.id/ajax/lokasi/search"

headers = {
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0"
}

# support Render disk (/data) atau lokal
SAVE_DIR = "/data" if os.path.exists("/data") else "data"
os.makedirs(SAVE_DIR, exist_ok=True)


# =========================
# FETCH DATA API
# =========================
def fetch_data():
    page = 1
    limit = 100
    results = []

    while True:
        params = {
            "sort": "terbaru",
            "page": page,
            "limit": limit
        }

        try:
            res = requests.get(BASE_URL, headers=headers, params=params, timeout=30)
        except Exception as e:
            print(f"Request error: {e}")
            break

        if res.status_code != 200:
            print(f"Request gagal: {res.status_code}")
            break

        data = res.json().get("data", [])

        if not data:
            break

        for item in data:
            wilayah = item.get("wilayah", {})

            if "KAB LUMAJANG" not in wilayah.get("kabupaten", "").upper():
                continue

            results.append({
                "kode": item.get("idLokasi"),
                "nama": item.get("namaPerumahan"),
                "developer": item.get("pengembang", {}).get("nama"),
                "kecamatan": wilayah.get("kecamatan"),
                "subsidi": item.get("jumlahUnit"),
                "komersil": item.get("jumlahUnitKomersil")
            })

        print(f"Fetch page {page}")
        page += 1

    df = pd.DataFrame(results)

    if df.empty:
        print("Tidak ada data ditemukan")
    else:
        print(f"Total data: {len(df)}")

    return df


# =========================
# SAVE SNAPSHOT HARIAN
# =========================
def save_snapshot(df):
    today = datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(SAVE_DIR, f"snapshot_{today}.csv")

    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"Snapshot saved: {path}")

    return path


# =========================
# GENERATE SALES FILES
# =========================
def auto_generate_sales_files():
    files = sorted([f for f in os.listdir(SAVE_DIR) if f.startswith("snapshot_")])

    if len(files) < 2:
        print("Snapshot belum cukup untuk generate sales")
        return

    for i in range(1, len(files)):
        date = files[i].replace("snapshot_", "").replace(".csv", "")
        sales_file = os.path.join(SAVE_DIR, f"sales_{date}.csv")

        # skip kalau sudah ada
        if os.path.exists(sales_file):
            continue

        df_old = pd.read_csv(os.path.join(SAVE_DIR, files[i-1]))
        df_new = pd.read_csv(os.path.join(SAVE_DIR, files[i]))

        merged = df_old.merge(df_new, on="kode", suffixes=("_old", "_new"))

        merged["terjual_subsidi"] = merged["subsidi_old"] - merged["subsidi_new"]
        merged["terjual_komersil"] = merged["komersil_old"] - merged["komersil_new"]
        merged["total_terjual"] = merged["terjual_subsidi"] + merged["terjual_komersil"]

        sold = merged[merged["total_terjual"] > 0]

        if sold.empty:
            print(f"Tidak ada penjualan untuk {date}")
            continue

        sold[[
            "kode",
            "nama_old",
            "developer_old",
            "kecamatan_old",
            "terjual_subsidi",
            "terjual_komersil",
            "total_terjual"
        ]].to_csv(sales_file, index=False, encoding="utf-8-sig")

        print(f"Generated sales: {sales_file}")


# =========================
# MAIN
# =========================
def main():
    print("Start job")

    df = fetch_data()

    if df.empty:
        print("Stop karena data kosong")
        return

    save_snapshot(df)

    auto_generate_sales_files()

    print("Job selesai")


if __name__ == "__main__":
    main()