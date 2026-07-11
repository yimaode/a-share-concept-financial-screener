"""将 akshare 趋势、概念证据与 akshare 市场特征组合为 CANSLIM 初筛。"""

from __future__ import annotations

import json
from pathlib import Path


def _latest(trends: list[dict], metric_id: str, annual: bool = False) -> dict | None:
    rows = [t for t in trends if t.get("metric_id") == metric_id and (not annual or t.get("period_type") == "A")]
    return max(rows, key=lambda t: (t.get("period_year", 0), t.get("period_order", 0)), default=None)


def _growth_pass(trend: dict | None, threshold: float) -> str:
    if not trend or trend.get("yoy_status") != "computed" or trend.get("yoy") is None:
        return "unavailable"
    return "pass" if trend["yoy"] >= threshold else "fail"


def _annual_growth_status(trends: tuple[dict | None, dict | None], threshold: float) -> str:
    values = [t.get("cagr_3y") if t else None for t in trends]
    if any(value is None for value in values):
        return "unavailable"
    return "pass" if all(value >= threshold for value in values) else "fail"


def evaluate_canslim(trends: list[dict], concept_scores: dict, market: dict) -> dict:
    concepts = {c.get("concept_id"): c for c in concept_scores.get("concepts", [])}
    revenue, profit = _latest(trends, "revenue"), _latest(trends, "net_profit_attributable")
    annual_revenue, annual_profit = _latest(trends, "revenue", annual=True), _latest(trends, "net_profit_attributable", annual=True)
    supply = [_latest(trends, x) for x in ("contract_liabilities", "construction_in_progress")]

    current_growth = (_growth_pass(revenue, .20), _growth_pass(profit, .20))
    dimensions = {
        "C": {"name": "当前季度增长", "status": "unavailable" if "unavailable" in current_growth else ("pass" if current_growth == ("pass", "pass") else "fail"), "reason": "营收与归母净利润最新同比均至少20%"},
        "A": {"name": "年度增长", "status": _annual_growth_status((annual_revenue, annual_profit), .15), "reason": "年报营收和归母净利润三年 CAGR 至少15%"},
        "N": {"name": "新变化", "status": "pass" if concepts.get("pre_explosion_stage", {}).get("positive_signals", 0) >= 2 else "fail", "reason": "爆发前期概念至少两个正向证据关键词信号"},
        "S": {"name": "供需", "status": "pass" if any(t and t.get("yoy_status") == "computed" and (t.get("yoy") or 0) > 0 for t in supply) else "fail", "reason": "合同负债或在建工程同比改善"},
        "L": {"name": "领先性", "status": "unavailable" if market.get("leader_relative_strength_6m") is None else ("pass" if market["leader_relative_strength_6m"] > 0 else "fail"), "reason": "个股六个月收益率高于沪深300"},
        "I": {"name": "机构认同", "status": "unavailable" if market.get("institution_holder_count") is None else ("pass" if market["institution_holder_count"] > 0 else "fail"), "reason": "最近报告期存在机构持仓记录"},
        "M": {"name": "市场方向", "status": "unavailable" if market.get("market_above_ma50") is None or market.get("market_above_ma200") is None else ("pass" if market["market_above_ma50"] and market["market_above_ma200"] else "fail"), "reason": "沪深300位于50日和200日均线之上"},
    }
    unavailable = [k for k, v in dimensions.items() if v["status"] == "unavailable"]
    passed = [k for k, v in dimensions.items() if v["status"] == "pass"]
    if unavailable:
        result = "资料不足"
    elif all(dimensions[k]["status"] == "pass" for k in ("C", "A", "L", "M")) and len(passed) >= 5:
        result = "符合 CANSLIM 初筛"
    else:
        result = "暂不符合 CANSLIM 初筛"
    return {"framework": "CANSLIM", "result": result, "passed_dimensions": passed,
            "unavailable_dimensions": unavailable, "dimensions": dimensions, "market_features": market,
            "disclaimer": "用于量化初筛，不构成投资建议。"}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
