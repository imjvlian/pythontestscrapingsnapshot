import requests
import pandas as pd
import os
from datetime import datetime, timedelta

BASE_URL = "https://sikumbang.tapera.go.id/ajax/lokasi/search"

headers = {
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0"
}

SAVE_DIR = "data"
os.makedirs(SAVE_DIR, exist_ok=True)


# =========================
# 1. FETCH DATA (Lumajang)
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

        res = requests.get(BASE_URL, headers=headers, params=params)

        if res.status_code != 200:
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

    return pd.DataFrame(results)


# =========================
# 2. SAVE SNAPSHOT
# =========================
def save_snapshot(df):
    today = datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(SAVE_DIR, f"snapshot_{today}.csv")
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


# =========================
# 3. LOAD YESTERDAY
# =========================
def load_yesterday():
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    path = os.path.join(SAVE_DIR, f"snapshot_{yesterday}.csv")

    if not os.path.exists(path):
        print("⚠️ Tidak ada data kemarin")
        return None

    return pd.read_csv(path)


# =========================
# 4. COMPARE + STATISTIK
# =========================
def generate_statistics(today_df, yesterday_df):
    if yesterday_df is None:
        print("❌ Tidak bisa compare")
        return

    df = yesterday_df.merge(
        today_df,
        on="kode",
        suffixes=("_old", "_new")
    )

    # hitung penurunan
    df["penurunan_subsidi"] = df["subsidi_old"] - df["subsidi_new"]
    df["penurunan_komersil"] = df["komersil_old"] - df["komersil_new"]

    # ambil yang benar-benar turun
    df = df[(df["penurunan_subsidi"] > 0) | (df["penurunan_komersil"] > 0)]

    # total penurunan
    df["total_penurunan"] = df["penurunan_subsidi"] + df["penurunan_komersil"]

    # ranking
    ranking = df.sort_values("total_penurunan", ascending=False)

    # =====================
    # STATISTIK TAMBAHAN
    # =====================

    total_terjual = df["total_penurunan"].sum()

    top_perumahan = ranking[[
        "nama_old", "developer_old", "kecamatan_old", "total_penurunan"
    ]].head(10)

    # agregasi per kecamatan
    per_kecamatan = df.groupby("kecamatan_old")["total_penurunan"].sum().reset_index()
    per_kecamatan = per_kecamatan.sort_values("total_penurunan", ascending=False)

    # =====================
    # SAVE CSV
    # =====================
    today = datetime.now().strftime("%Y-%m-%d")

    ranking.to_csv(os.path.join(SAVE_DIR, f"ranking_{today}.csv"), index=False, encoding="utf-8-sig")
    top_perumahan.to_csv(os.path.join(SAVE_DIR, f"top10_{today}.csv"), index=False, encoding="utf-8-sig")
    per_kecamatan.to_csv(os.path.join(SAVE_DIR, f"kecamatan_{today}.csv"), index=False, encoding="utf-8-sig")

    # =====================
    # PRINT SUMMARY
    # =====================
    print("\nSTATISTIK HARIAN")
    print(f"Total unit berkurang: {total_terjual}")

    print("\nTOP PERUMAHAN:")
    print(top_perumahan)

    print("\nTOP KECAMATAN:")
    print(per_kecamatan.head(5))


# =========================
# MAIN
# =========================
def main():
    print("Fetch data...")
    today_df = fetch_data()

    print("Save snapshot...")
    save_snapshot(today_df)

    print("Load yesterday...")
    yesterday_df = load_yesterday()

    print("Generate statistik...")
    generate_statistics(today_df, yesterday_df)


if __name__ == "__main__":
    main()