import json
from collections import defaultdict
from pathlib import Path

from .errors import ConceptScoreError
from .schema import generate_detail_id, score_to_level

BUILT_IN_CONCEPTS = {
    "super_growth_stock", "industry_boom", "core_alpha_company",
    "supply_shortage", "pre_explosion_stage", "risk_negative_evidence",
}


def _read_json(path: Path) -> dict:
    if not path.exists():
        raise ConceptScoreError(f"File not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise ConceptScoreError(f"File not found: {path}")
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            s = line.strip()
            if not s:
                continue
            try:
                records.append(json.loads(s))
            except json.JSONDecodeError as e:
                raise ConceptScoreError(f"Invalid JSON at line {line_num} in {path}: {e}") from e
    return records


def _latest_trend(trends: list[dict], metric_id: str) -> dict | None:
    candidates = [t for t in trends if t.get("metric_id") == metric_id]
    if not candidates:
        return None
    candidates.sort(key=lambda t: (t.get("period_year", 0), t.get("period_order", 0)))
    return candidates[-1]


def _hard_metric_is_usable(trends: list[dict], hard_metric: str) -> bool:
    """判断概念库声明的指标是否真的可用于其声明的统计含义。

    仅“存在一条原始值”不能代表 ``*_yoy`` 已可计算；至少要有同口径同比基期。
    """
    from ..data_fetcher.web_api import CONCEPT_TO_BASE

    metric_id = CONCEPT_TO_BASE.get(hard_metric, hard_metric)
    if not metric_id:
        return False
    candidates = [t for t in trends if t.get("metric_id") == metric_id]
    if hard_metric.endswith("_yoy"):
        return any(
            t.get("yoy_status") == "computed" and t.get("yoy") is not None
            for t in candidates
        )
    return bool(candidates)


def _evidence_signal_count(hits: list[dict]) -> int:
    """一类关键词在同一概念中只算一个评分信号。

    原始命中次数仍完整保留在交付物中，但不能让报告模板里重复出现的“技术/风险”等
    通用词反复累加分数。
    """
    return len({
        (h.get("keyword_group", ""), h.get("keyword", ""))
        for h in hits
        if h.get("keyword", "")
    })


def _evidence_references(hits: list[dict], limit: int = 5) -> str:
    """为每个关键词信号选择一个最早出现的可回溯原文出处。"""
    selected: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for hit in sorted(hits, key=lambda h: (
        h.get("relative_path", ""), h.get("page_number", 0), h.get("evidence_id", ""),
    )):
        key = (hit.get("keyword_group", ""), hit.get("keyword", ""))
        if not hit.get("evidence_id") or key in seen:
            continue
        seen.add(key)
        selected.append(hit)
        if len(selected) >= limit:
            break
    return "; ".join(
        f"{h['evidence_id']} [{h.get('source_pdf', '')} p.{h.get('page_number', '')}]"
        for h in selected
    )


def _score_super_growth(trends: list[dict], pos_hits: int, neg_hits: int) -> tuple[int, list[dict]]:
    score = 50
    details: list[dict] = []

    def _add(component: str, pts: int, reason: str, source_type: str = "metric_trend",
             source_id: str = "", metric_id: str = "", raw_value=None, period: str = ""):
        nonlocal score
        details.append({
            "detail_id": generate_detail_id("super_growth_stock", component, reason),
            "concept_id": "super_growth_stock", "component": component,
            "source_type": source_type, "source_id": source_id,
            "metric_id": metric_id, "evidence_id": "",
            "points": pts, "reason": reason, "raw_value": raw_value, "report_period": period,
        })
        score += pts

    for mid in ["revenue", "net_profit_attributable", "deducted_net_profit"]:
        t = _latest_trend(trends, mid)
        if t and t.get("yoy_status") == "computed" and t.get("yoy") is not None:
            yoy = t["yoy"]
            if yoy >= 0.3: _add(f"{mid}_yoy", 20 if mid != "deducted_net_profit" else 15, f"{mid} yoy >= 30%", metric_id=mid, source_id=t.get("trend_id", ""), raw_value=yoy, period=t.get("report_period", ""))
            elif yoy >= 0.15: _add(f"{mid}_yoy", 12 if mid != "deducted_net_profit" else 8, f"{mid} yoy >= 15%", metric_id=mid, source_id=t.get("trend_id", ""), raw_value=yoy, period=t.get("report_period", ""))
            elif yoy >= 0: _add(f"{mid}_yoy", 5 if mid != "deducted_net_profit" else 3, f"{mid} yoy >= 0%", metric_id=mid, source_id=t.get("trend_id", ""), raw_value=yoy, period=t.get("report_period", ""))
            else: _add(f"{mid}_yoy", -10 if mid != "deducted_net_profit" else -8, f"{mid} yoy < 0", metric_id=mid, source_id=t.get("trend_id", ""), raw_value=yoy, period=t.get("report_period", ""))

    t = _latest_trend(trends, "operating_cashflow")
    if t and t.get("yoy_status") == "computed" and t.get("yoy") is not None:
        yoy = t["yoy"]
        _add("ocf_yoy", 10 if yoy > 0 else -8, f"ocf yoy {'>' if yoy > 0 else '<='} 0", metric_id="operating_cashflow", source_id=t.get("trend_id", ""), raw_value=yoy, period=t.get("report_period", ""))

    t = _latest_trend(trends, "gross_margin")
    if t and t.get("yoy_status") == "computed" and t.get("change_pp") is not None:
        pp = t["change_pp"]
        if pp > 0: _add("gm_change", 10, "gross_margin change_pp > 0", metric_id="gross_margin", source_id=t.get("trend_id", ""), raw_value=pp, period=t.get("report_period", ""))
        elif pp == 0: _add("gm_change", 3, "gross_margin change_pp = 0", metric_id="gross_margin", source_id=t.get("trend_id", ""), raw_value=pp, period=t.get("report_period", ""))
        else: _add("gm_change", -8, "gross_margin change_pp < 0", metric_id="gross_margin", source_id=t.get("trend_id", ""), raw_value=pp, period=t.get("report_period", ""))

    pt = min(pos_hits * 2, 10)
    if pt > 0:
        _add("positive_evidence", pt, f"positive evidence signals = {pos_hits}", source_type="evidence")
    nt = min(neg_hits * 3, 15)
    if nt > 0:
        _add("negative_evidence", -nt, f"negative evidence signals = {neg_hits}", source_type="evidence")

    return max(0, min(100, score)), details


def _score_industry_boom(trends: list[dict], pos_hits: int, neg_hits: int) -> tuple[int, list[dict]]:
    score = 50
    details: list[dict] = []

    def _add(component: str, pts: int, reason: str, source_type: str = "metric_trend",
             source_id: str = "", metric_id: str = "", raw_value=None, period: str = ""):
        nonlocal score
        details.append({
            "detail_id": generate_detail_id("industry_boom", component, reason),
            "concept_id": "industry_boom", "component": component,
            "source_type": source_type, "source_id": source_id,
            "metric_id": metric_id, "evidence_id": "",
            "points": pts, "reason": reason, "raw_value": raw_value, "report_period": period,
        })
        score += pts

    pt = min(pos_hits * 4, 30)
    if pt > 0:
        _add("positive_evidence", pt, f"positive evidence signals = {pos_hits}", source_type="evidence")
    nt = min(neg_hits * 5, 25)
    if nt > 0:
        _add("negative_evidence", -nt, f"negative evidence signals = {neg_hits}", source_type="evidence")

    t = _latest_trend(trends, "revenue")
    if t and t.get("yoy_status") == "computed" and t.get("yoy") is not None:
        yoy = t["yoy"]
        if yoy >= 0.2: _add("revenue_yoy", 20, "revenue yoy >= 20%", metric_id="revenue", source_id=t.get("trend_id", ""), raw_value=yoy, period=t.get("report_period", ""))
        elif yoy >= 0: _add("revenue_yoy", 8, "revenue yoy >= 0%", metric_id="revenue", source_id=t.get("trend_id", ""), raw_value=yoy, period=t.get("report_period", ""))
        else: _add("revenue_yoy", -10, "revenue yoy < 0", metric_id="revenue", source_id=t.get("trend_id", ""), raw_value=yoy, period=t.get("report_period", ""))

    t = _latest_trend(trends, "gross_margin")
    if t and t.get("change_pp") is not None:
        pp = t["change_pp"]
        if pp > 0: _add("gm_change", 15, "gross_margin change_pp > 0", metric_id="gross_margin", source_id=t.get("trend_id", ""), raw_value=pp, period=t.get("report_period", ""))
        elif pp < 0: _add("gm_change", -10, "gross_margin change_pp < 0", metric_id="gross_margin", source_id=t.get("trend_id", ""), raw_value=pp, period=t.get("report_period", ""))

    latest_any = max(trends, key=lambda t: (t.get("period_year", 0), t.get("period_order", 0)), default=None)
    if latest_any and latest_any.get("consecutive_growth_count", 0) >= 2:
        _add("growth_count", 10, "consecutive_growth_count >= 2")

    return max(0, min(100, score)), details


def _score_core_alpha(trends: list[dict], pos_hits: int, neg_hits: int) -> tuple[int, list[dict]]:
    score = 50
    details: list[dict] = []

    def _add(component: str, pts: int, reason: str, source_type: str = "metric_trend",
             source_id: str = "", metric_id: str = "", raw_value=None, period: str = ""):
        nonlocal score
        details.append({
            "detail_id": generate_detail_id("core_alpha_company", component, reason),
            "concept_id": "core_alpha_company", "component": component,
            "source_type": source_type, "source_id": source_id,
            "metric_id": metric_id, "evidence_id": "",
            "points": pts, "reason": reason, "raw_value": raw_value, "report_period": period,
        })
        score += pts

    t = _latest_trend(trends, "gross_margin")
    if t:
        _add("gm_exists", 10, "gross_margin value exists", metric_id="gross_margin", source_id=t.get("trend_id", ""))
        if t.get("change_pp") is not None:
            pp = t["change_pp"]
            if pp > 0: _add("gm_change", 15, "gross_margin change_pp > 0", metric_id="gross_margin", source_id=t.get("trend_id", ""), raw_value=pp, period=t.get("report_period", ""))
            else: _add("gm_change", -10, "gross_margin change_pp < 0", metric_id="gross_margin", source_id=t.get("trend_id", ""), raw_value=pp, period=t.get("report_period", ""))

    t = _latest_trend(trends, "rd_expense_ratio")
    if t:
        _add("rd_ratio_exists", 5, "rd_expense_ratio value exists", metric_id="rd_expense_ratio", source_id=t.get("trend_id", ""), raw_value=t.get("value_normalized"), period=t.get("report_period", ""))
        if t.get("change_pp") is not None and t["change_pp"] > 0:
            _add("rd_ratio_change", 5, "rd_expense_ratio change_pp > 0", metric_id="rd_expense_ratio", source_id=t.get("trend_id", ""), raw_value=t["change_pp"], period=t.get("report_period", ""))

    t = _latest_trend(trends, "revenue")
    if t and t.get("yoy_status") == "computed" and t.get("yoy") is not None and t["yoy"] > 0:
        _add("revenue_yoy", 10, "revenue yoy > 0", metric_id="revenue", source_id=t.get("trend_id", ""), raw_value=t["yoy"], period=t.get("report_period", ""))

    pt = min(pos_hits * 4, 30)
    if pt > 0:
        _add("positive_evidence", pt, f"positive evidence signals = {pos_hits}", source_type="evidence")
    nt = min(neg_hits * 5, 25)
    if nt > 0:
        _add("negative_evidence", -nt, f"negative evidence signals = {neg_hits}", source_type="evidence")

    return max(0, min(100, score)), details


def _score_supply_shortage(trends: list[dict], pos_hits: int, neg_hits: int) -> tuple[int, list[dict]]:
    score = 50
    details: list[dict] = []

    def _add(component: str, pts: int, reason: str, source_type: str = "metric_trend",
             source_id: str = "", metric_id: str = "", raw_value=None, period: str = ""):
        nonlocal score
        details.append({
            "detail_id": generate_detail_id("supply_shortage", component, reason),
            "concept_id": "supply_shortage", "component": component,
            "source_type": source_type, "source_id": source_id,
            "metric_id": metric_id, "evidence_id": "",
            "points": pts, "reason": reason, "raw_value": raw_value, "report_period": period,
        })
        score += pts

    t = _latest_trend(trends, "contract_liabilities")
    if t and t.get("yoy_status") == "computed" and t.get("yoy") is not None:
        yoy = t["yoy"]
        if yoy > 0.3: _add("cl_yoy", 20, "contract_liabilities yoy > 30%", metric_id="contract_liabilities", source_id=t.get("trend_id", ""), raw_value=yoy, period=t.get("report_period", ""))
        elif yoy >= 0: _add("cl_yoy", 10, "contract_liabilities yoy >= 0%", metric_id="contract_liabilities", source_id=t.get("trend_id", ""), raw_value=yoy, period=t.get("report_period", ""))
        else: _add("cl_yoy", -8, "contract_liabilities yoy < 0", metric_id="contract_liabilities", source_id=t.get("trend_id", ""), raw_value=yoy, period=t.get("report_period", ""))

    t = _latest_trend(trends, "revenue")
    if t and t.get("yoy_status") == "computed" and t.get("yoy") is not None:
        yoy = t["yoy"]
        if yoy > 0.2: _add("revenue_yoy", 15, "revenue yoy > 20%", metric_id="revenue", source_id=t.get("trend_id", ""), raw_value=yoy, period=t.get("report_period", ""))
        elif yoy >= 0: _add("revenue_yoy", 8, "revenue yoy >= 0%", metric_id="revenue", source_id=t.get("trend_id", ""), raw_value=yoy, period=t.get("report_period", ""))
        else: _add("revenue_yoy", -8, "revenue yoy < 0", metric_id="revenue", source_id=t.get("trend_id", ""), raw_value=yoy, period=t.get("report_period", ""))

    t = _latest_trend(trends, "gross_margin")
    if t and t.get("change_pp") is not None:
        pp = t["change_pp"]
        if pp > 0: _add("gm_change", 15, "gross_margin change_pp > 0", metric_id="gross_margin", source_id=t.get("trend_id", ""), raw_value=pp, period=t.get("report_period", ""))
        elif pp < 0: _add("gm_change", -10, "gross_margin change_pp < 0", metric_id="gross_margin", source_id=t.get("trend_id", ""), raw_value=pp, period=t.get("report_period", ""))

    pt = min(pos_hits * 4, 30)
    if pt > 0:
        _add("positive_evidence", pt, f"positive evidence signals = {pos_hits}", source_type="evidence")
    nt = min(neg_hits * 5, 25)
    if nt > 0:
        _add("negative_evidence", -nt, f"negative evidence signals = {neg_hits}", source_type="evidence")

    return max(0, min(100, score)), details


def _score_pre_explosion(trends: list[dict], pos_hits: int, neg_hits: int) -> tuple[int, list[dict]]:
    score = 50
    details: list[dict] = []

    def _add(component: str, pts: int, reason: str, source_type: str = "metric_trend",
             source_id: str = "", metric_id: str = "", raw_value=None, period: str = ""):
        nonlocal score
        details.append({
            "detail_id": generate_detail_id("pre_explosion_stage", component, reason),
            "concept_id": "pre_explosion_stage", "component": component,
            "source_type": source_type, "source_id": source_id,
            "metric_id": metric_id, "evidence_id": "",
            "points": pts, "reason": reason, "raw_value": raw_value, "report_period": period,
        })
        score += pts

    t = _latest_trend(trends, "contract_liabilities")
    if t and t.get("yoy_status") == "computed" and t.get("yoy") is not None and t["yoy"] > 0.3:
        _add("cl_yoy", 20, "contract_liabilities yoy > 30%", metric_id="contract_liabilities", source_id=t.get("trend_id", ""), raw_value=t["yoy"], period=t.get("report_period", ""))

    t = _latest_trend(trends, "construction_in_progress")
    if t and t.get("yoy_status") == "computed" and t.get("yoy") is not None and t["yoy"] > 0.3:
        _add("cip_yoy", 15, "construction_in_progress yoy > 30%", metric_id="construction_in_progress", source_id=t.get("trend_id", ""), raw_value=t["yoy"], period=t.get("report_period", ""))

    t = _latest_trend(trends, "rd_expense_ratio")
    if t and t.get("value_normalized") is not None and t["value_normalized"] > 0:
        _add("rd_ratio_exists", 5, "rd_expense_ratio value exists", metric_id="rd_expense_ratio", source_id=t.get("trend_id", ""), raw_value=t["value_normalized"], period=t.get("report_period", ""))

    t = _latest_trend(trends, "inventory")
    if t and t.get("yoy_status") == "computed" and t.get("yoy") is not None and t["yoy"] > 0.2:
        _add("inv_yoy", 10, "inventory yoy > 20%", metric_id="inventory", source_id=t.get("trend_id", ""), raw_value=t["yoy"], period=t.get("report_period", ""))

    t = _latest_trend(trends, "revenue")
    if t and t.get("yoy_status") == "computed" and t.get("yoy") is not None and t["yoy"] > -0.1:
        _add("revenue_yoy", 10, "revenue yoy > -10%", metric_id="revenue", source_id=t.get("trend_id", ""), raw_value=t["yoy"], period=t.get("report_period", ""))

    pt = min(pos_hits * 4, 30)
    if pt > 0:
        _add("positive_evidence", pt, f"positive evidence signals = {pos_hits}", source_type="evidence")
    nt = min(neg_hits * 5, 20)
    if nt > 0:
        _add("negative_evidence", -nt, f"negative evidence signals = {neg_hits}", source_type="evidence")

    return max(0, min(100, score)), details


def _score_risk(trends: list[dict], pos_hits: int, neg_hits: int) -> tuple[int, list[dict]]:
    score = 0
    details: list[dict] = []

    def _add(component: str, pts: int, reason: str, source_type: str = "metric_trend",
             source_id: str = "", metric_id: str = "", raw_value=None, period: str = ""):
        nonlocal score
        details.append({
            "detail_id": generate_detail_id("risk_negative_evidence", component, reason),
            "concept_id": "risk_negative_evidence", "component": component,
            "source_type": source_type, "source_id": source_id,
            "metric_id": metric_id, "evidence_id": "",
            "points": pts, "reason": reason, "raw_value": raw_value, "report_period": period,
        })
        score += pts

    nt = min(neg_hits * 5, 40)
    if nt > 0:
        _add("negative_evidence", nt, f"negative evidence signals = {neg_hits}", source_type="evidence")

    for mid in [("revenue", 15), ("net_profit_attributable", 15), ("operating_cashflow", 10)]:
        t = _latest_trend(trends, mid[0])
        if t and t.get("yoy_status") == "computed" and t.get("yoy") is not None and t["yoy"] < 0:
            _add(f"{mid[0]}_yoy", mid[1], f"{mid[0]} yoy < 0", metric_id=mid[0], source_id=t.get("trend_id", ""), raw_value=t["yoy"], period=t.get("report_period", ""))

    t = _latest_trend(trends, "gross_margin")
    if t and t.get("change_pp") is not None and t["change_pp"] < 0:
        _add("gm_change", 10, "gross_margin change_pp < 0", metric_id="gross_margin", source_id=t.get("trend_id", ""), raw_value=t["change_pp"], period=t.get("report_period", ""))

    pd = min(pos_hits * 2, 10)
    if pd > 0:
        _add("positive_evidence", -pd, f"positive evidence signal deduction = {pos_hits}", source_type="evidence")

    return max(0, min(100, score)), details


def _score_generic(trends: list[dict], pos_hits: int, neg_hits: int, hard_metrics: list[str]) -> tuple[int, list[dict]]:
    score = 20
    details: list[dict] = []
    cid = "generic"

    def _add(concept_id: str, component: str, pts: int, reason: str, source_type: str = "metric_trend",
             source_id: str = "", metric_id: str = "", raw_value=None, period: str = ""):
        nonlocal score
        details.append({
            "detail_id": generate_detail_id(concept_id, component, reason),
            "concept_id": concept_id, "component": component,
            "source_type": source_type, "source_id": source_id,
            "metric_id": metric_id, "evidence_id": "",
            "points": pts, "reason": reason, "raw_value": raw_value, "report_period": period,
        })
        score += pts

    pt = min(pos_hits * 5, 40)
    if pt > 0:
        _add(cid, "positive_evidence", pt, f"positive evidence signals = {pos_hits}", source_type="evidence")
    nt = min(neg_hits * 5, 40)
    if nt > 0:
        _add(cid, "negative_evidence", -nt, f"negative evidence signals = {neg_hits}", source_type="evidence")

    metric_pts = 0
    for m in hard_metrics:
        t = _latest_trend(trends, m)
        if t and t.get("yoy_status") == "computed" and t.get("yoy") is not None and t["yoy"] > 0:
            pts = 10
            _add(cid, f"{m}_yoy", pts, f"{m} yoy > 0", metric_id=m, source_id=t.get("trend_id", ""), raw_value=t["yoy"], period=t.get("report_period", ""))
            metric_pts += pts
            if metric_pts >= 40:
                break

    return max(0, min(100, score)), details


def score_concepts(
    concepts_file: Path,
    trends_file: Path,
    evidence_file: Path,
) -> tuple[dict, list[dict], list[str]]:
    concepts_data = _read_json(concepts_file)
    if concepts_data.get("status") != "frozen":
        raise ConceptScoreError("Concepts file must be frozen")

    concepts = concepts_data.get("concepts", [])
    trends = _read_jsonl(trends_file)
    evidence = _read_jsonl(evidence_file)

    ev_by_concept: dict[str, dict] = defaultdict(lambda: {"positive": [], "negative": []})
    seen_ev: dict[str, dict] = {}
    warnings: list[str] = []

    for ev in evidence:
        eid = ev.get("evidence_id", "")
        cid = ev.get("concept_id", "")
        if eid in seen_ev:
            if json.dumps(ev, sort_keys=True, ensure_ascii=False) != json.dumps(seen_ev[eid], sort_keys=True, ensure_ascii=False):
                raise ConceptScoreError(f"Duplicate evidence_id {eid} with different content")
            warnings.append(f"Duplicate evidence_id {eid} (deduplicated)")
        seen_ev[eid] = ev
        pol = ev.get("polarity", "")
        if pol == "positive":
            ev_by_concept[cid]["positive"].append(ev)
        elif pol == "negative":
            ev_by_concept[cid]["negative"].append(ev)

    concept_results: list[dict] = []
    all_details: list[dict] = []
    all_warnings: list[str] = list(warnings)

    for c in concepts:
        cid = c.get("concept_id", "")
        cname = c.get("name", "")
        hard_metrics = c.get("hard_metrics", [])

        pos_evidence = ev_by_concept.get(cid, {}).get("positive", [])
        neg_evidence = ev_by_concept.get(cid, {}).get("negative", [])
        pos_hits = len(pos_evidence)
        neg_hits = len(neg_evidence)
        pos_signals = _evidence_signal_count(pos_evidence)
        neg_signals = _evidence_signal_count(neg_evidence)

        if cid in BUILT_IN_CONCEPTS:
            if cid == "super_growth_stock":
                score, details = _score_super_growth(trends, pos_signals, neg_signals)
            elif cid == "industry_boom":
                score, details = _score_industry_boom(trends, pos_signals, neg_signals)
            elif cid == "core_alpha_company":
                score, details = _score_core_alpha(trends, pos_signals, neg_signals)
            elif cid == "supply_shortage":
                score, details = _score_supply_shortage(trends, pos_signals, neg_signals)
            elif cid == "pre_explosion_stage":
                score, details = _score_pre_explosion(trends, pos_signals, neg_signals)
            elif cid == "risk_negative_evidence":
                score, details = _score_risk(trends, pos_signals, neg_signals)
            else:
                score, details = _score_generic(trends, pos_signals, neg_signals, hard_metrics)
                cid_for_details = cid
                for d in details:
                    d["concept_id"] = cid_for_details
        else:
            score, details = _score_generic(trends, pos_signals, neg_signals, hard_metrics)
            for d in details:
                d["concept_id"] = cid
            all_warnings.append(f"Generic scoring used for {cid}")

        # 数字评分的 source_id 是趋势 ID；证据评分必须落到实际 evidence_id/PDF/page，
        # 这样 03_score_details.csv 可以直接回查 02_evidence_sentences.csv。
        evidence_refs = {
            "positive_evidence": _evidence_references(pos_evidence),
            "negative_evidence": _evidence_references(neg_evidence),
        }
        for detail in details:
            ref = evidence_refs.get(detail.get("component"), "")
            if detail.get("source_type") == "evidence" and ref:
                detail["source_id"] = ref
                detail["evidence_id"] = "; ".join(
                    part.split(" ", 1)[0] for part in ref.split("; ")
                )

        level = score_to_level(score)
        from ..data_fetcher.web_api import UNSUPPORTED_AKSHARE_METRICS

        metric_unsupported = [m for m in hard_metrics if m in UNSUPPORTED_AKSHARE_METRICS]
        metric_missing = [
            m for m in hard_metrics
            if m not in metric_unsupported and not _hard_metric_is_usable(trends, m)
        ]
        n_available = len(hard_metrics) - len(metric_missing) - len(metric_unsupported)
        min_evidence = int(c.get("evidence_rules", {}).get("min_evidence_count", 0) or 0)
        evidence_count = pos_signals + neg_signals
        quality_warnings: list[str] = []
        if metric_missing:
            quality_warnings.append("缺少可用于评分的指标: " + ", ".join(metric_missing))
        if metric_unsupported:
            quality_warnings.append("akshare 不提供: " + ", ".join(metric_unsupported))
        if evidence_count < min_evidence:
            quality_warnings.append(f"证据句不足: {evidence_count}/{min_evidence}")

        if metric_missing:
            status = "data_incomplete"
        elif metric_unsupported:
            status = "partial_data"
        elif evidence_count < min_evidence:
            status = "evidence_limited"
        else:
            status = "ready"

        top_reasons = [
            f"{d['component']}: {d['reason']} ({d['points']:+d})"
            for d in sorted(details, key=lambda x: -abs(x["points"]))[:5]
        ]

        concept_results.append({
            "concept_id": cid, "concept_name": cname,
            "score": score, "level": level, "status": status,
            "positive_hits": pos_hits, "negative_hits": neg_hits,
            "positive_signals": pos_signals, "negative_signals": neg_signals,
            "metric_coverage": {
                "required": len(hard_metrics),
                "available": n_available,
                "missing": metric_missing,
                "unsupported": metric_unsupported,
            },
            "top_reasons": top_reasons,
            "warnings": quality_warnings,
        })
        all_details.extend(details)

    return {
        "version": "0.1.0",
        "score_type": "concept_fit",
        "total_concepts": len(concept_results),
        "concepts": concept_results,
        "warnings": all_warnings,
    }, all_details, all_warnings
