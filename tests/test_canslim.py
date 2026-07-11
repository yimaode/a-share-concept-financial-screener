from ds_finance_concept.canslim.evaluator import evaluate_canslim
from datetime import date

from ds_finance_concept.data_fetcher import market_api
from ds_finance_concept.data_fetcher.market_api import _close_values, _retry_call


def _trend(metric_id, year=2025, period="Q1", yoy=.3, cagr=.2):
    return {"metric_id": metric_id, "period_year": year, "period_type": period,
            "period_order": {"Q1": 1, "A": 4}[period], "yoy": yoy,
            "yoy_status": "computed", "cagr_3y": cagr}


def test_canslim_passes_when_all_dimensions_available_and_positive():
    trends = [_trend("revenue"), _trend("net_profit_attributable"),
              _trend("revenue", period="A"), _trend("net_profit_attributable", period="A"),
              _trend("contract_liabilities")]
    scores = {"concepts": [{"concept_id": "pre_explosion_stage", "positive_signals": 2}]}
    market = {"leader_relative_strength_6m": .2, "institution_holder_count": 3,
              "market_above_ma50": True, "market_above_ma200": True}
    result = evaluate_canslim(trends, scores, market)
    assert result["result"] == "符合 CANSLIM 初筛"
    assert len(result["passed_dimensions"]) == 7


def test_canslim_reports_insufficient_data_when_market_unavailable():
    result = evaluate_canslim([], {"concepts": []}, {
        "leader_relative_strength_6m": None, "institution_holder_count": None,
        "market_above_ma50": None, "market_above_ma200": None,
    })
    assert result["result"] == "资料不足"
    assert {"L", "I", "M"} <= set(result["unavailable_dimensions"])


def test_canslim_annual_growth_below_threshold_is_fail_not_unavailable():
    trends = [_trend("revenue", period="A", cagr=.10),
              _trend("net_profit_attributable", period="A", cagr=.20)]
    result = evaluate_canslim(trends, {"concepts": []}, {
        "leader_relative_strength_6m": 0, "institution_holder_count": 0,
        "market_above_ma50": False, "market_above_ma200": False,
    })
    assert result["dimensions"]["A"]["status"] == "fail"
    assert "A" not in result["unavailable_dimensions"]


def test_market_close_values_supports_english_index_columns():
    class Frame:
        empty = False
        columns = ["date", "close"]
        def __getitem__(self, key):
            assert key == "close"
            return type("Column", (), {"tolist": lambda self: [1, 2, 3]})()
    assert _close_values(Frame()) == [1.0, 2.0, 3.0]


def test_market_retry_recovers_from_transient_failure(monkeypatch):
    monkeypatch.setattr("ds_finance_concept.data_fetcher.market_api.time.sleep", lambda _: None)
    calls = []
    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("temporary")
        return "ok"
    assert _retry_call(flaky) == "ok"
    assert len(calls) == 3


def test_stock_history_uses_akshare_fallback(monkeypatch):
    monkeypatch.setattr("ds_finance_concept.data_fetcher.market_api.time.sleep", lambda _: None)
    monkeypatch.setattr(market_api.ak, "stock_zh_a_hist", lambda **_: (_ for _ in ()).throw(RuntimeError("down")))
    monkeypatch.setattr(market_api.ak, "stock_zh_a_daily", lambda **kwargs: kwargs["symbol"])
    assert market_api._stock_history("300750", date(2025, 1, 1), date(2025, 12, 31)) == "sz300750"


def test_market_features_keeps_index_direction_when_stock_fetch_fails(monkeypatch):
    class Column:
        def tolist(self): return list(range(1, 251))
    class Frame:
        empty = False
        columns = ["close"]
        def __getitem__(self, key): return Column()

    monkeypatch.setattr(market_api, "_stock_history", lambda *args: (_ for _ in ()).throw(RuntimeError("stock down")))
    monkeypatch.setattr(market_api, "_index_history", lambda *args: Frame())
    monkeypatch.setattr(market_api.ak, "stock_institute_hold_detail", lambda **kwargs: [])
    result = market_api.fetch_market_features("300750", "2025A")
    assert result["leader_relative_strength_6m"] is None
    assert result["market_above_ma50"] is True
    assert result["market_above_ma200"] is True
    assert any("stock market data unavailable" in warning for warning in result["warnings"])
