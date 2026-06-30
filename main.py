import os
import time
import logging
from pathlib import Path
from datetime import datetime

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# =====================================================
# CONFIG
# =====================================================

BASE_URL = "https://sikumbang.tapera.go.id/ajax/lokasi/search"

SAVE_DIR = Path("data")

SAVE_DIR.mkdir(exist_ok=True)

PAGE_LIMIT = 100

TIMEOUT = 30

TARGET_KABUPATEN = "KAB LUMAJANG"


HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0",
}


# =====================================================
# LOGGER
# =====================================================

LOG_FILE = SAVE_DIR / "scraper.log"

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


def log(message):

    print(message)

    logger.info(message)


# =====================================================
# REQUEST SESSION
# =====================================================

def create_session():

    retry = Retry(

        total=5,

        backoff_factor=2,

        status_forcelist=[429, 500, 502, 503, 504],

        allowed_methods=["GET"],

    )

    adapter = HTTPAdapter(max_retries=retry)

    session = requests.Session()

    session.mount("https://", adapter)

    session.mount("http://", adapter)

    session.headers.update(HEADERS)

    return session


# =====================================================
# API CLIENT
# =====================================================

class SikumbangClient:

    def __init__(self):

        self.session = create_session()

    def fetch_page(self, page):

        params = {

            "sort": "terbaru",

            "page": page,

            "limit": PAGE_LIMIT,

        }

        response = self.session.get(

            BASE_URL,

            params=params,

            timeout=TIMEOUT,

        )

        response.raise_for_status()

        return response.json()

    def fetch_all(self):

        page = 1

        data_all = []

        while True:

            log(f"Fetch page {page}")

            result = self.fetch_page(page)

            rows = result.get("data", [])

            if len(rows) == 0:

                break

            data_all.extend(rows)

            page += 1

            time.sleep(0.3)

        log(f"Total API rows : {len(data_all)}")

        return data_all


# =====================================================
# DATA PROCESSOR
# =====================================================

class DataProcessor:

    @staticmethod
    def normalize(item):

        wilayah = item.get("wilayah", {})

        developer = item.get("pengembang", {})

        return {

            "kode": item.get("idLokasi"),

            "nama": item.get("namaPerumahan"),

            "developer": developer.get("nama"),

            "asosiasi": developer.get("asosiasi"),

            "provinsi": wilayah.get("provinsi"),

            "kabupaten": wilayah.get("kabupaten"),

            "kecamatan": wilayah.get("kecamatan"),

            "kelurahan": wilayah.get("kelurahan"),

            "subsidi": item.get("jumlahUnit", 0),

            "komersil": item.get("jumlahUnitKomersil", 0),

            "jenis": item.get("jenisPerumahan"),

            "aktif": item.get("aktivasi"),

        }

    @classmethod
    def build_dataframe(cls, api_rows):

        records = []

        for item in api_rows:

            wilayah = item.get("wilayah", {})

            if wilayah.get("kabupaten", "").upper() != TARGET_KABUPATEN:

                continue

            records.append(

                cls.normalize(item)

            )

        df = pd.DataFrame(records)

        if len(df) == 0:

            return df

        df = df.sort_values(

            "nama"

        ).reset_index(drop=True)

        log(f"Total Lumajang : {len(df)}")

        return df


# =====================================================
# SNAPSHOT
# =====================================================

class SnapshotManager:

    @staticmethod
    def today():

        return datetime.now().strftime("%Y-%m-%d")

    @classmethod
    def filename(cls):

        return SAVE_DIR / f"snapshot_{cls.today()}.csv"

    @classmethod
    def save(cls, dataframe):

        file = cls.filename()

        if file.exists():

            log("Snapshot hari ini sudah ada")

            return file

        dataframe.to_csv(

            file,

            index=False,

            encoding="utf-8-sig",

        )

        log(f"Snapshot saved : {file}")

        return file


# =====================================================
# UTILITIES
# =====================================================

def load_latest_snapshot():

    files = sorted(

        SAVE_DIR.glob("snapshot_*.csv")

    )

    if len(files) == 0:

        return None

    return pd.read_csv(files[-1])


def get_snapshot_files():

    return sorted(

        SAVE_DIR.glob("snapshot_*.csv")

    )


# =====================================================
# MAIN FETCH
# =====================================================

def fetch_latest_data():

    client = SikumbangClient()

    api_rows = client.fetch_all()

    df = DataProcessor.build_dataframe(api_rows)

    if df.empty:
        log("Data kosong.")
        return df

    SnapshotManager.save(df)

    InventoryManager.update(df)

    HistoryManager.append_snapshot(df)

    SalesGenerator.generate()

    SummaryGenerator.update(df)

    DailyRanking.generate()

    MonthlyRanking.generate()

    DeveloperRanking.generate()

    KecamatanRanking.generate()

    TopSales.generate()

    WeeklyGrowth.generate()

    Statistics.generate()

    SnapshotChecker.check()

    return df

# =====================================================
# HISTORY MANAGER
# =====================================================


class HistoryManager:

    FILE = SAVE_DIR / "history.csv"

    COLUMNS = [
        "tanggal",
        "kode",
        "nama",
        "developer",
        "asosiasi",
        "provinsi",
        "kabupaten",
        "kecamatan",
        "kelurahan",
        "subsidi",
        "komersil",
        "jenis",
        "aktif"
    ]

    @classmethod
    def append_snapshot(cls, df):

        if df.empty:
            return

        snapshot = df.copy()

        snapshot["tanggal"] = pd.to_datetime(
            SnapshotManager.today()
        )

        snapshot = snapshot[cls.COLUMNS]

        if cls.FILE.exists():

            history = pd.read_csv(cls.FILE, parse_dates=["tanggal"])

            # Hapus data hari ini agar tidak duplikat
            history = history[
                history["tanggal"] != SnapshotManager.today()
            ]

            history = pd.concat(
                [history, snapshot],
                ignore_index=True
            )

        else:

            history = snapshot

        history.sort_values(
            ["tanggal", "kode"],
            inplace=True
        )

        history.to_csv(
            cls.FILE,
            index=False,
            encoding="utf-8-sig"
        )

        log(f"History updated ({len(snapshot)} rows)")


# =====================================================
# INVENTORY MANAGER
# =====================================================

class InventoryManager:

    FILE = SAVE_DIR / "inventory.csv"

    @classmethod
    def update(cls, df):

        if df.empty:
            return

        inventory = df.copy()

        inventory["tanggal_update"] = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        inventory = inventory.sort_values(
            "nama"
        ).reset_index(drop=True)

        inventory.to_csv(

            cls.FILE,

            index=False,

            encoding="utf-8-sig"

        )

        log(f"Inventory updated ({len(inventory)} rows)")

# =====================================================
# SNAPSHOT COMPARISON
# =====================================================


class SnapshotComparator:

    @staticmethod
    def latest_two():

        files = get_snapshot_files()

        if len(files) < 2:
            return None, None

        return files[-2], files[-1]

    @classmethod
    def compare(cls):

        old_file, new_file = cls.latest_two()

        if old_file is None:
            return pd.DataFrame()

        old = pd.read_csv(old_file)

        new = pd.read_csv(new_file)

        merged = old.merge(
            new,
            on="kode",
            suffixes=("_old", "_new")
        )

        merged["terjual_subsidi"] = (
            merged["subsidi_old"]
            -
            merged["subsidi_new"]
        )

        merged["terjual_komersil"] = (
            merged["komersil_old"]
            -
            merged["komersil_new"]
        )

        merged["total_terjual"] = (
            merged["terjual_subsidi"]
            +
            merged["terjual_komersil"]
        )

        return merged


# =====================================================
# SALES GENERATOR
# =====================================================

class SalesGenerator:

    @classmethod
    def generate(cls):

        merged = SnapshotComparator.compare()

        if merged.empty:

            log("Belum ada snapshot pembanding.")

            return

        sold = merged[
            merged["total_terjual"] > 0
        ].copy()

        if sold.empty:

            log("Tidak ada penjualan.")

            return

        sold["tanggal"] = SnapshotManager.today()

        sold = sold[[
            "tanggal",
            "kode",
            "nama_old",
            "developer_old",
            "kecamatan_old",
            "terjual_subsidi",
            "terjual_komersil",
            "total_terjual",
        ]]

        sold.columns = [

            "tanggal",

            "kode",

            "nama",

            "developer",

            "kecamatan",

            "terjual_subsidi",

            "terjual_komersil",

            "total_terjual",

        ]

        filename = (
            SAVE_DIR
            /
            f"sales_{SnapshotManager.today()}.csv"
        )

        sold.to_csv(

            filename,

            index=False,

            encoding="utf-8-sig"

        )

        log(f"Sales file : {filename}")


# =====================================================
# SUMMARY
# =====================================================

class SummaryGenerator:

    FILE = SAVE_DIR / "summary.csv"

    @classmethod
    def update(cls, dataframe):

        sales_today = 0

        sales_file = (
            SAVE_DIR
            /
            f"sales_{SnapshotManager.today()}.csv"
        )

        if sales_file.exists():

            sales = pd.read_csv(sales_file)

            if not sales.empty:

                sales_today = sales[
                    "total_terjual"
                ].sum()

        summary = pd.DataFrame([{

            "tanggal": SnapshotManager.today(),

            "total_perumahan": len(dataframe),

            "total_unit_subsidi": dataframe["subsidi"].sum(),

            "total_unit_komersil": dataframe["komersil"].sum(),

            "total_penjualan": sales_today,

        }])

        if cls.FILE.exists():

            old = pd.read_csv(cls.FILE)

            old = old[
                old["tanggal"] != SnapshotManager.today()
            ]

            summary = pd.concat(
                [old, summary],
                ignore_index=True
            )

        summary.to_csv(

            cls.FILE,

            index=False,

            encoding="utf-8-sig"

        )

        log("Summary updated.")


# =====================================================
# MISSING SNAPSHOT
# =====================================================

class SnapshotChecker:

    @staticmethod
    def check():

        files = get_snapshot_files()

        if len(files) < 2:
            return

        dates = []

        for file in files:

            name = file.stem.replace(
                "snapshot_",
                ""
            )

            dates.append(

                datetime.strptime(
                    name,
                    "%Y-%m-%d"
                )

            )

        for i in range(1, len(dates)):

            gap = (
                dates[i]
                -
                dates[i - 1]
            ).days

            if gap > 1:

                log(
                    f"WARNING : Snapshot hilang {gap-1} hari "
                    f"({dates[i-1].date()} -> {dates[i].date()})"
                )

# =====================================================
# ANALYTICS ENGINE
# =====================================================


class AnalyticsEngine:

    @staticmethod
    def load_all_sales():

        files = sorted(
            SAVE_DIR.glob("sales_*.csv")
        )

        if len(files) == 0:
            return pd.DataFrame()

        dfs = []

        for file in files:

            try:

                df = pd.read_csv(file)

                dfs.append(df)

            except:

                pass

        if len(dfs) == 0:
            return pd.DataFrame()

        return pd.concat(
            dfs,
            ignore_index=True
        )

    @staticmethod
    def load_history():

        history = SAVE_DIR / "history.csv"

        if not history.exists():
            return pd.DataFrame()

        return pd.read_csv(history)


class DailyRanking:

    FILE = SAVE_DIR / "ranking_harian.csv"

    @classmethod
    def generate(cls):

        sales = AnalyticsEngine.load_all_sales()

        if sales.empty:
            return

        latest = sales["tanggal"].max()

        today = sales[
            sales["tanggal"] == latest
        ]

        today = today.sort_values(
            "total_terjual",
            ascending=False
        )

        today.to_csv(
            cls.FILE,
            index=False,
            encoding="utf-8-sig"
        )

        log("Ranking harian updated.")


class MonthlyRanking:

    FILE = SAVE_DIR / "ranking_bulanan.csv"

    @classmethod
    def generate(cls):

        sales = AnalyticsEngine.load_all_sales()

        if sales.empty:
            return

        sales["tanggal"] = pd.to_datetime(
            sales["tanggal"]
        )

        sales["bulan"] = sales[
            "tanggal"
        ].dt.to_period("M").astype(str)

        ranking = (

            sales.groupby(

                [
                    "bulan",
                    "kode",
                    "nama",
                    "developer",
                    "kecamatan",
                ]

            )["total_terjual"]

            .sum()

            .reset_index()

            .sort_values(

                [
                    "bulan",
                    "total_terjual"
                ],

                ascending=[False, False]

            )

        )

        ranking.to_csv(

            cls.FILE,

            index=False,

            encoding="utf-8-sig"

        )

        log("Ranking bulanan updated.")


class DeveloperRanking:

    FILE = SAVE_DIR / "developer_rank.csv"

    @classmethod
    def generate(cls):

        sales = AnalyticsEngine.load_all_sales()

        if sales.empty:
            return

        ranking = (

            sales.groupby("developer")

            ["total_terjual"]

            .sum()

            .reset_index()

            .sort_values(

                "total_terjual",

                ascending=False

            )

        )

        ranking.to_csv(

            cls.FILE,

            index=False,

            encoding="utf-8-sig"

        )

        log("Developer ranking updated.")


class KecamatanRanking:

    FILE = SAVE_DIR / "kecamatan_rank.csv"

    @classmethod
    def generate(cls):

        sales = AnalyticsEngine.load_all_sales()

        if sales.empty:
            return

        ranking = (

            sales.groupby("kecamatan")

            ["total_terjual"]

            .sum()

            .reset_index()

            .sort_values(

                "total_terjual",

                ascending=False

            )

        )

        ranking.to_csv(

            cls.FILE,

            index=False,

            encoding="utf-8-sig"

        )

        log("Kecamatan ranking updated.")


class TopSales:

    FILE = SAVE_DIR / "top_sales.csv"

    @classmethod
    def generate(cls):

        sales = AnalyticsEngine.load_all_sales()

        if sales.empty:
            return

        ranking = (

            sales.groupby(

                [

                    "kode",

                    "nama",

                    "developer",

                    "kecamatan",

                ]

            )["total_terjual"]

            .sum()

            .reset_index()

            .sort_values(

                "total_terjual",

                ascending=False

            )

        )

        ranking.to_csv(

            cls.FILE,

            index=False,

            encoding="utf-8-sig"

        )

        log("Top Sales updated.")


class WeeklyGrowth:

    FILE = SAVE_DIR / "weekly_growth.csv"

    @classmethod
    def generate(cls):

        history = AnalyticsEngine.load_history()

        if history.empty:
            return

        history["tanggal"] = pd.to_datetime(
            history["tanggal"]
        )

        latest = history["tanggal"].max()

        week = latest - pd.Timedelta(days=7)

        latest_df = history[
            history["tanggal"] == latest
        ]

        old_df = history[
            history["tanggal"] <= week
        ]

        if old_df.empty:
            return

        old = (

            old_df.sort_values("tanggal")

            .groupby("kode")

            .last()

            .reset_index()

        )

        merged = old.merge(

            latest_df,

            on="kode",

            suffixes=("_old", "_new")

        )

        merged["growth"] = (

            merged["subsidi_old"]

            -

            merged["subsidi_new"]

        )

        merged = merged.sort_values(

            "growth",

            ascending=False

        )

        merged.to_csv(

            cls.FILE,

            index=False,

            encoding="utf-8-sig"

        )

        log("Weekly Growth updated.")


class Statistics:

    FILE = SAVE_DIR / "statistics.csv"

    @classmethod
    def generate(cls):

        sales = AnalyticsEngine.load_all_sales()

        history = AnalyticsEngine.load_history()

        if history.empty:

            return

        total_sales = 0

        if not sales.empty:

            total_sales = sales[
                "total_terjual"
            ].sum()

        stats = pd.DataFrame([{

            "tanggal": SnapshotManager.today(),

            "jumlah_perumahan":

                history["kode"].nunique(),

            "developer":

                history["developer"].nunique(),

            "kecamatan":

                history["kecamatan"].nunique(),

            "total_penjualan":

                total_sales,

            "unit_subsidi":

                history["subsidi"].iloc[-1],

            "unit_komersil":

                history["komersil"].iloc[-1],

        }])

        stats.to_csv(

            cls.FILE,

            index=False,

            encoding="utf-8-sig"

        )

        log("Statistics updated.")
