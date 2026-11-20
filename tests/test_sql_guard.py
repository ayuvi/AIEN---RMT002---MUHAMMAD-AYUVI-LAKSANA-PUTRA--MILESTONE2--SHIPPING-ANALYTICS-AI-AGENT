
from src.sql_guard import validate_sql


def test_safe_select():
    sql = "SELECT COUNT(*) FROM gold.shipment_fact"
    assert validate_sql(sql) is True


def test_delete_rejected():
    sql = "DELETE FROM gold.shipment_fact"
    assert validate_sql(sql) is False


def test_other_schema_rejected():
    sql = "SELECT * FROM public.users"
    assert validate_sql(sql) is False


def test_multiple_statements_rejected():
    sql = (
        "SELECT * FROM gold.shipment_fact; "
        "DELETE FROM gold.shipment_fact"
    )
    assert validate_sql(sql) is False


def test_select_without_table_rejected():
    assert validate_sql("SELECT 1") is False


def test_unknown_column_rejected():
    sql = "SELECT password FROM gold.shipment_fact"
    assert validate_sql(sql) is False


def test_join_other_schema_rejected():
    sql = (
        "SELECT * FROM gold.shipment_fact "
        "JOIN public.users ON true"
    )
    assert validate_sql(sql) is False


def test_unknown_function_rejected():
    sql = "SELECT pg_sleep(10) FROM gold.shipment_fact"
    assert validate_sql(sql) is False


def test_union_rejected():
    sql = (
        "SELECT shipment_id FROM gold.shipment_fact "
        "UNION SELECT shipment_id FROM gold.shipment_fact"
    )
    assert validate_sql(sql) is False


def test_select_into_rejected():
    sql = "SELECT * INTO TEMP TABLE copied FROM gold.shipment_fact"
    assert validate_sql(sql) is False



def test_carrier_analytics_allowed():
    sql = """
        SELECT
            carrier_id,
            SUM(delivered_count) AS total_delivered,
            SUM(on_time_delivered_count) AS on_time,
            ROUND(
                100.0 * SUM(on_time_delivered_count)
                / NULLIF(SUM(delivered_count), 0),
                2
            ) AS on_time_rate
        FROM gold.carrier_daily
        GROUP BY carrier_id
        ORDER BY on_time_rate DESC
    """

    assert validate_sql(sql) is True


def test_carrier_analytics_with_date_filter():
    sql = """
    SELECT
        carrier_id,
        SUM(delivered_count) AS total_delivered,
        SUM(on_time_delivered_count) AS on_time,
        ROUND(
            100.0 * SUM(on_time_delivered_count)
            / NULLIF(SUM(delivered_count), 0),
            2
        ) AS on_time_rate
    FROM gold.carrier_daily
    WHERE metric_date >= '2026-08-01'
      AND metric_date < '2026-09-01'
    GROUP BY carrier_id
    ORDER BY on_time_rate DESC
    """

    assert validate_sql(sql) is True


def test_weekly_trends_allowed():
    sql = """
    SELECT
        DATE_TRUNC('week', metric_date) AS week_start,
        SUM(shipment_count) AS total_shipments
    FROM gold.city_daily
    WHERE metric_date >= '2026-08-01'
      AND metric_date < '2026-09-01'
    GROUP BY DATE_TRUNC('week', metric_date)
    ORDER BY week_start
    """

    assert validate_sql(sql) is True