import json

from ds_finance_concept.data_fetcher import web_api


def test_needed_metrics_from_frozen_concepts(tmp_path):
    concepts = {
        "status": "frozen",
        "concepts": [
            {"concept_id": "c1", "hard_metrics": ["revenue_yoy", "rd_expense_ratio", "market_share"]},
            {"concept_id": "c2", "hard_metrics": ["construction_in_progress_yoy", "gross_margin"]},
        ],
    }
    f = tmp_path / "concepts.json"
    f.write_text(json.dumps(concepts, ensure_ascii=False), encoding="utf-8")

    needed = web_api._needed_metrics(str(f))
    assert needed == {"revenue", "rd_expense", "construction_in_progress", "gross_margin"}
    assert "market_share" not in needed


def test_make_point_amount_shape():
    p = web_api._make_point("revenue", "营业总收入", "2023A", 2023, 1000.0)
    assert p["metric_id"] == "revenue"
    assert p["report_period"] == "2023A"
    assert p["period_year"] == 2023
    assert p["period_type"] == "A"
    assert p["period_order"] == 4
    assert p["value_normalized"] == 1000.0
    assert p["value_unit_normalized"] == "CNY"
    assert p["is_percent"] is False
    assert p["source"] == "akshare"
    assert p["selection_method"] == "akshare"


def test_make_point_percent_metric():
    p = web_api._make_point("gross_margin", "毛利率", "2023Q1", 2023, 28.7)
    assert p["is_percent"] is True
    assert p["value_unit_normalized"] == "percent"
    assert p["period_type"] == "Q1"
    assert p["period_order"] == 1


def test_symbol_prefix():
    assert web_api._symbol("603129") == "SH603129"
    assert web_api._symbol("000001") == "SZ000001"


def test_fetch_web_metrics_empty_when_no_akshare(monkeypatch, tmp_path):
    monkeypatch.setattr(web_api, "HAS_AKSHARE", False)
    concepts = {"status": "frozen", "concepts": [{"concept_id": "c", "hard_metrics": ["revenue_yoy"]}]}
    f = tmp_path / "concepts.json"
    f.write_text(json.dumps(concepts, ensure_ascii=False), encoding="utf-8")
    assert web_api.fetch_web_metrics("603129", str(f)) == []


def test_all_scorer_base_metrics_are_fetchable():
    # 打分器消费的基础指标必须都在 METRIC_MAP 中（脱离 PDF 的前提）
    scorer_base_metrics = {
        "revenue", "net_profit_attributable", "deducted_net_profit",
        "operating_cashflow", "gross_margin", "inventory",
        "contract_liabilities", "construction_in_progress", "rd_expense",
    }
    assert scorer_base_metrics <= set(web_api.METRIC_MAP)


def test_negative_and_zero_financial_values_are_kept(monkeypatch):
    class FakeFrame:
        empty = False
        columns = ["指标", "20240131", "20240331", "20230331"]

        def __getitem__(self, key):
            if key == "指标":
                return FakeColumn(["经营现金流量净额"])
            if isinstance(key, bool):
                return self
            raise KeyError(key)

    # 使用一个更接近 pandas 的最小桩，验证抽取逻辑而非网络。
    import pandas as pd
    df = pd.DataFrame([{
        "指标": "经营现金流量净额", "20240331": -100.0, "20230331": 0.0,
    }])
    monkeypatch.setattr(web_api.ak, "stock_financial_abstract", lambda symbol: df)
    points = web_api._fetch_abstract_metrics("603129", {"operating_cashflow"})
    assert {(p["report_period"], p["value_normalized"]) for p in points} == {
        ("2024Q1", -100.0), ("2023Q1", 0.0)
    }


def test_rd_expense_ratio_is_derived_from_same_period():
    revenue = web_api._make_point("revenue", "营业总收入", "2024Q1", 2024, 200.0)
    rd = web_api._make_point("rd_expense", "研发费用", "2024Q1", 2024, 10.0)
    ratio = web_api._derive_rd_expense_ratio([revenue, rd])
    assert len(ratio) == 1
    assert ratio[0]["metric_id"] == "rd_expense_ratio"
    assert ratio[0]["value_normalized"] == 5.0
    assert ratio[0]["is_percent"] is True
    assert ratio[0]["selection_method"] == "akshare_derived"


def test_filter_as_of_period():
    q1 = web_api._make_point("revenue", "营业总收入", "2024Q1", 2024, 1)
    annual = web_api._make_point("revenue", "营业总收入", "2024A", 2024, 2)
    assert web_api._filter_as_of_period([q1, annual], "2024Q1") == [q1]


def test_single_quarter_derivation_keeps_negative_values():
    q1 = web_api._make_point("operating_cashflow", "经营现金流量净额", "2024Q1", 2024, -3.0)
    h1 = web_api._make_point("operating_cashflow", "经营现金流量净额", "2024H1", 2024, 5.0)
    q3 = web_api._make_point("operating_cashflow", "经营现金流量净额", "2024Q3", 2024, 2.0)
    annual = web_api._make_point("operating_cashflow", "经营现金流量净额", "2024A", 2024, 10.0)
    points = web_api._derive_single_quarters([q1, h1, q3, annual])
    values = {p["report_period"]: p["value_normalized"] for p in points}
    assert values == {"2024Q1": -3.0, "2024Q2": 8.0, "2024Q3": -3.0, "2024Q4": 8.0}
