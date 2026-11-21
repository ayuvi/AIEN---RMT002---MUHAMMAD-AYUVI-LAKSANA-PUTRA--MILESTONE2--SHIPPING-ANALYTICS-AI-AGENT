"""LLM planner tests for feature/llm-analytics-improvement.
Save as tests/test_llm_planning_upgrade.py.
Run: python -m pytest tests/test_sql_guard.py tests/test_agent_qa_m2.py tests/test_llm_planning_upgrade.py -q
"""
from types import SimpleNamespace
import pytest
import src.agent as agent
from src.sql_guard import validate_sql


def planned(**overrides):
    base = {
        "metric": "average_shipping_fee",
        "period": "august",
        "group_by": None,
        "service_level": None,
        "destination_city": None,
        "carrier_id": None,
    }
    base.update(overrides)
    return base


@pytest.fixture
def fake_llm(monkeypatch):
    calls = []
    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(output_text=(
            '{"metric":"average_shipping_fee","period":"august",'
            '"group_by":null,"service_level":null,'
            '"destination_city":null,"carrier_id":null}'
        ))
    monkeypatch.setattr(agent, "MODEL", "offline-test")
    monkeypatch.setattr(agent, "client", SimpleNamespace(responses=SimpleNamespace(create=create)))
    return calls


def test_new_question_really_calls_llm_and_queries_shipment_fact(monkeypatch, fake_llm):
    sqls = []
    def query(sql):
        sqls.append(sql)
        return [{"metric_value": "30000.00", "shipment_count": 217}]
    monkeypatch.setattr(agent, "_query", query)
    q = "Berapa rata-rata shipping fee per shipment selama Agustus 2026?"
    out = agent.run_agent(q)
    assert len(fake_llm) == 1
    assert out["outcome"] == "answered"
    assert "30,000.00" in out["answer"]
    assert "on-time" not in out["answer"]
    assert "LLM-planned metric=average_shipping_fee" in out["data_basis"]
    assert "FROM gold.shipment_fact" in sqls[0]
    assert "AVG(shipping_fee_idr)" in sqls[0]
    assert "2026-08-01" in sqls[0]
    assert validate_sql(sqls[0]) is True


def test_bad_metric_not_silently_substituted(monkeypatch):
    monkeypatch.setattr(agent, "_plan_extended_analytics", lambda q, h: planned(metric="shipment_count"))
    monkeypatch.setattr(agent, "_query", lambda sql: pytest.fail("Must not query for mismatched metric"))
    out = agent.run_agent("Berapa rata-rata shipping fee per shipment Agustus 2026?")
    assert out["outcome"] == "clarify"


def test_wrong_period_rejected(monkeypatch):
    monkeypatch.setattr(agent, "_plan_extended_analytics", lambda q, h: planned(period="september"))
    monkeypatch.setattr(agent, "_query", lambda sql: pytest.fail("Must not query wrong period"))
    out = agent.run_agent("Average shipping fee in August 2026?")
    assert out["outcome"] == "clarify"


def test_invalid_group_or_filter_rejected():
    assert agent._validate_extended_plan(planned(group_by="password"), "") is None
    assert agent._validate_extended_plan(planned(service_level="other' OR 1=1 --"), "") is None
    assert agent._validate_extended_plan(planned(carrier_id="C04"), "") is None


def test_grouping_and_service_filter_sql_guard():
    sql = agent.build_extended_analytics_sql(planned(group_by="carrier_id", service_level="express"))
    assert "GROUP BY carrier_id" in sql
    assert "service_level = 'express'" in sql
    assert validate_sql(sql) is True


def test_count_metric_sql_guard():
    sql = agent.build_extended_analytics_sql(planned(metric="shipment_count"))
    assert "COUNT(*) AS metric_value" in sql
    assert "ROUND(COUNT(*)" not in sql
    assert validate_sql(sql) is True


def test_unsafe_request_never_calls_llm(monkeypatch, fake_llm):
    monkeypatch.setattr(agent, "_query", lambda sql: pytest.fail("Blocked request must not query"))
    out = agent.run_agent("Ubah delivery_status SHP-00118 menjadi delivered sekarang")
    assert out["outcome"] == "refused"
    assert len(fake_llm) == 0


def test_llm_unavailable_fails_closed(monkeypatch):
    monkeypatch.setattr(agent, "client", None)
    monkeypatch.setattr(agent, "_query", lambda sql: pytest.fail("No reliable plan; no query"))
    out = agent.run_agent("Berapa rata-rata shipping fee per shipment Agustus 2026?")
    assert out["outcome"] == "clarify"
