
import sqlglot
from sqlglot import exp


# Daftar tabel dan kolom sesuai Gold Contract
ALLOWED_COLUMNS = {
    "gold.shipment_fact": {
        "shipment_id", "order_date", "carrier_id",
        "origin_hub", "destination_city", "service_level",
        "promised_delivery_at_utc", "delivered_at_utc",
        "delivery_status", "shipping_fee_idr",
        "refund_amount_idr", "exception_note",
    },
    "gold.carrier_daily": {
        "metric_date", "carrier_id", "shipment_count",
        "delivered_count", "on_time_delivered_count",
        "late_delivered_count", "in_transit_count",
        "shipping_fee_idr", "refund_amount_idr",
    },
    "gold.city_daily": {
        "metric_date", "destination_city", "shipment_count",
        "delivered_count", "on_time_delivered_count",
        "late_delivered_count", "in_transit_count",
        "shipping_fee_idr", "refund_amount_idr",
    },
}

# Fungsi yang dibutuhkan untuk analitik
ALLOWED_FUNCTIONS = {
    "COUNT", "SUM", "AVG", "MIN", "MAX",
    "ROUND", "NULLIF", "COALESCE",
    "DATE_TRUNC",
    "TIMESTAMP_TRUNC",
}

# Struktur yang belum kita izinkan
BLOCKED_NODES = (
    exp.Join,
    exp.Subquery,
    exp.Union,
    exp.Intersect,
    exp.Except,
    exp.With,
    exp.CTE,
    exp.Into,
    exp.Lateral,
    exp.Window,
)


def validate_sql(sql: str) -> bool:
    try:
        if not isinstance(sql, str) or not sql.strip():
            return False

        statements = sqlglot.parse(sql, read="postgres")

        if len(statements) != 1:
            return False

        statement = statements[0]

        # Hanya SELECT biasa
        if not isinstance(statement, exp.Select):
            return False

        # Tolak struktur kompleks yang belum diaudit
        if any(
            isinstance(node, BLOCKED_NODES)
            for node in statement.walk()
        ):
            return False

        # Wajib tepat satu tabel
        tables = list(statement.find_all(exp.Table))

        if len(tables) != 1:
            return False

        table = tables[0]

        # Tidak boleh mengakses catalog/database lain
        if table.catalog:
            return False

        full_name = f"{table.db}.{table.name}"

        if full_name not in ALLOWED_COLUMNS:
            return False

        allowed_columns = ALLOWED_COLUMNS[full_name]

        # Alias output untuk ORDER BY / HAVING
        output_aliases = {
            alias.alias.lower()
            for alias in statement.expressions
            if isinstance(alias, exp.Alias)
        }

        # Validasi semua kolom
        for column in statement.find_all(exp.Column):
            name = column.name.lower()

            if name not in allowed_columns:
                if name not in output_aliases:
                    return False

            if column.table:
                valid_qualifiers = {
                    table.name.lower(),
                    table.alias_or_name.lower(),
                }
                if column.table.lower() not in valid_qualifiers:
                    return False

        # Tolak SELECT *; COUNT(*) tetap diperbolehkan
        for star in statement.find_all(exp.Star):
            if not isinstance(star.parent, exp.Count):
                return False

        # Validasi fungsi
        for func in statement.find_all(exp.Func):

            if isinstance(func, exp.And):
                continue

            func_name = func.sql_name().upper()

            if isinstance(func, exp.Anonymous):
                func_name = func.name.upper()

            if func_name not in ALLOWED_FUNCTIONS:
                return False

        return True

    except Exception:
        return False
