
import json
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

from src.sql_guard import validate_sql


# ==========================================
# 1. ENVIRONMENT CONFIGURATION
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent

# Environment runtime tetap diprioritaskan.
load_dotenv(BASE_DIR / ".env")


def get_database_url():
    database_url = os.getenv("GOLD_DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "GOLD_DATABASE_URL belum diatur"
        )

    return database_url


# ==========================================
# 2. DATABASE CONNECTION TEST
# ==========================================

def test_connection():
    with psycopg.connect(
        get_database_url(),
        connect_timeout=5,
        options="-c default_transaction_read_only=on",
    ) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM gold.shipment_fact"
            )

            total = cursor.fetchone()[0]

            print("Koneksi PostgreSQL berhasil!")
            print(f"Total shipment: {total}")


# ==========================================
# 3. SAFE SQL EXECUTOR
# ==========================================

def execute_safe_query(sql: str, params=None):

    # STEP 1: SQL harus lolos validasi.
    if not validate_sql(sql):
        raise ValueError("SQL tidak diizinkan")

    if params is None:
        params = ()

    # STEP 2: Gunakan koneksi read-only.
    with psycopg.connect(
        get_database_url(),
        connect_timeout=5,
        row_factory=dict_row,
        autocommit=True,
        options="-c default_transaction_read_only=on",
    ) as conn:

        # STEP 3: Eksekusi dalam transaksi read-only.
        with conn.transaction():
            conn.execute("SET TRANSACTION READ ONLY")

            # Batasi waktu query.
            conn.execute(
                "SET LOCAL statement_timeout = '3000ms'"
            )

            # STEP 4: Jalankan parameterized query.
            with conn.cursor() as cursor:
                cursor.execute(sql, params)

                # Maksimum 100 baris hasil.
                rows = cursor.fetchmany(101)

                if len(rows) > 100:
                    raise ValueError(
                        "Hasil query melebihi 100 baris"
                    )

                # STEP 5: Konversi hasil agar
                # dapat digunakan oleh FastAPI.
                result = json.loads(
                    json.dumps(rows, default=str)
                )

                result_size = len(
                    json.dumps(result).encode("utf-8")
                )

                if result_size > 100_000:
                    raise ValueError(
                        "Ukuran hasil query terlalu besar"
                    )

                return result


# ==========================================
# 4. LOCAL CONNECTION CHECK
# ==========================================

if __name__ == "__main__":
    test_connection()
