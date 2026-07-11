"""akshare 网络数据源：A 股标准财务指标唯一真相源。

设计原则（见项目改造决策）：
- 所有数字/量化指标只来自 akshare（东财），不再从 PDF 抽取。
- 输出为 metric_series 形状的 dict，可直接作为 compute-metric-trends 的输入序列。
- 每条数据显式标注来源 source=akshare，selection_method=akshare。
"""

try:
    import akshare as ak
    HAS_AKSHARE = True
except ImportError:
    HAS_AKSHARE = False

import json
import time

# akshare 直接提供的基础指标（base metric_id → 中文名）。
# ``rd_expense_ratio`` 是由同报告期的研发费用/营业收入派生，仍完全来自 akshare。
METRIC_MAP = {
    "revenue": "营业总收入",
    "net_profit_attributable": "归母净利润",
    "deducted_net_profit": "扣非净利润",
    "operating_cashflow": "经营现金流量净额",
    "gross_margin": "毛利率",
    "inventory": "存货",
    "contract_liabilities": "合同负债",
    "construction_in_progress": "在建工程",
    "rd_expense": "研发费用",
    "rd_expense_ratio": "研发费用率",
}

# 从财务摘要 stock_financial_abstract 取的指标
ABSTRACT_METRICS = {
    "revenue", "net_profit_attributable", "deducted_net_profit",
    "operating_cashflow", "gross_margin",
}

# 资产负债表 stock_balance_sheet_by_report_em 列名映射
BALANCE_SHEET_COLS = {
    "inventory": "INVENTORY",
    "contract_liabilities": "CONTRACT_LIAB",
    "construction_in_progress": "CIP",
}

# 利润表 stock_profit_sheet_by_report_em 列名映射
PROFIT_SHEET_COLS = {
    "rd_expense": "RESEARCH_EXPENSE",
}

PERCENT_METRICS = {"gross_margin", "rd_expense_ratio"}

PERIOD_MAP = {"0331": "Q1", "0630": "H1", "0930": "Q3", "1231": "A"}
ORDER_MAP = {"Q1": 1, "Q2": 2, "H1": 2, "Q3": 3, "Q4": 4, "A": 4}

# 概念库 hard_metrics（含 _yoy / _ratio 后缀）→ 输出序列 metric_id。
# ``market_share`` 不是 akshare 财务报表字段，因此明确标为“不支持”，不能伪装成缺失的
# 财务数字；它只能由后续独立行业数据源补充。
CONCEPT_TO_BASE = {
    "revenue_yoy": "revenue",
    "net_profit_yoy": "net_profit_attributable",
    "non_gaap_net_profit_yoy": "deducted_net_profit",
    "operating_cashflow_yoy": "operating_cashflow",
    "gross_margin": "gross_margin",
    "inventory_yoy": "inventory",
    "contract_liabilities_yoy": "contract_liabilities",
    "rd_expense_ratio": "rd_expense_ratio",
    "construction_in_progress_yoy": "construction_in_progress",
    "market_share": "",
}

UNSUPPORTED_AKSHARE_METRICS = {"market_share"}
DERIVED_REQUIREMENTS = {"rd_expense_ratio": {"rd_expense", "revenue"}}


def _symbol(company_code: str) -> str:
    return f"SH{company_code}" if company_code.startswith("6") else f"SZ{company_code}"


def _make_point(metric_id: str, metric_name: str, period: str, year: int, value: float) -> dict:
    is_pct = metric_id in PERCENT_METRICS
    ptype = period[4:]
    return {
        "series_id": f"ms_akshare_{metric_id}_{period}",
        "metric_id": metric_id,
        "metric_name": metric_name,
        "report_period": period,
        "period_year": year,
        "period_type": ptype,
        "period_order": ORDER_MAP.get(ptype, 0),
        "value_normalized": float(value),
        "value_unit_normalized": "percent" if is_pct else "CNY",
        "is_percent": is_pct,
        "source_candidate_id": "akshare",
        "source": "akshare",
        "source_pdf": "akshare_eastmoney",
        "page_number": 0,
        "selection_method": "akshare",
        "source_snippet": f"{metric_name} 来自 akshare(东财)",
    }


def _needed_metrics(concepts_file) -> set:
    """根据冻结概念库推导 akshare 需抓取的原始字段集合。"""
    try:
        concepts = json.loads(open(concepts_file, encoding="utf-8").read()).get("concepts", [])
    except (OSError, ValueError):
        return set()
    needed = set()
    for c in concepts:
        for m in c.get("hard_metrics", []):
            output_metric = CONCEPT_TO_BASE.get(m, m)
            if output_metric in DERIVED_REQUIREMENTS:
                needed.update(DERIVED_REQUIREMENTS[output_metric])
            elif output_metric in METRIC_MAP:
                needed.add(output_metric)
    return needed


def _retry_fetch(fetcher, *args, **kwargs):
    for attempt in range(3):
        try:
            return fetcher(*args, **kwargs)
        except Exception:
            if attempt == 2:
                return None
            time.sleep(0.5 * (attempt + 1))


def _fetch_abstract_metrics(company_code: str, needed: set) -> list:
    wanted = needed & ABSTRACT_METRICS
    if not wanted:
        return []
    df = _retry_fetch(ak.stock_financial_abstract, symbol=company_code)
    if df is None or df.empty or "指标" not in df.columns:
        return []

    date_cols = [c for c in df.columns if c.startswith("20") and len(c) == 8]
    points = []
    for mid in wanted:
        cn_name = METRIC_MAP[mid]
        row = df[df["指标"] == cn_name]
        if row.empty:
            continue
        for col in date_cols:
            val = row[col].values[0]
            try:
                v = float(val)
            except (ValueError, TypeError):
                continue
            if v != v:  # NaN
                continue
            # 合法的负值和零值是财务结论的一部分：亏损、负经营现金流与归零都必须
            # 进入趋势和风险评分。这里只排除 NaN/不可转换值，绝不能按正数筛选。
            period = col[:4] + PERIOD_MAP.get(col[4:], "")
            if not period[4:]:
                continue
            points.append(_make_point(mid, cn_name, period, int(col[:4]), v))
    return points


def _fetch_report_em(fetch_fn, company_code: str, col_map: dict, needed: set) -> list:
    wanted = {mid: col for mid, col in col_map.items() if mid in needed}
    if not wanted:
        return []
    df = _retry_fetch(fetch_fn, symbol=_symbol(company_code))
    if df is None or df.empty:
        return []

    points = []
    for mid, col in wanted.items():
        if col not in df.columns:
            continue
        cn_name = METRIC_MAP[mid]
        for _, r in df.iterrows():
            val = r.get(col)
            try:
                v = float(val)
            except (ValueError, TypeError):
                continue
            if v != v:  # NaN
                continue
            dt = str(r.get("REPORT_DATE", ""))[:10]
            if len(dt) != 10:
                continue
            ptype = PERIOD_MAP.get(dt[5:7] + dt[8:10])
            if not ptype:
                continue
            period = dt[:4] + ptype
            points.append(_make_point(mid, cn_name, period, int(dt[:4]), v))
    return points


def _derive_rd_expense_ratio(series: list[dict]) -> list[dict]:
    """用同报告期研发费用/营业收入生成研发费用率（百分点）。"""
    by_key = {(p["metric_id"], p["report_period"]): p for p in series}
    derived: list[dict] = []
    for (_, period), rd in sorted(by_key.items()):
        if rd["metric_id"] != "rd_expense":
            continue
        revenue = by_key.get(("revenue", period))
        if revenue is None:
            continue
        denominator = revenue.get("value_normalized")
        if denominator is None or denominator == 0:
            continue
        value = rd["value_normalized"] / denominator * 100
        point = _make_point(
            "rd_expense_ratio", METRIC_MAP["rd_expense_ratio"], period,
            rd["period_year"], value,
        )
        point["source_snippet"] = (
            "研发费用率 = akshare研发费用 / akshare营业总收入（同报告期）"
        )
        point["source_candidate_id"] = (
            f"akshare_derived:{rd['series_id']}:{revenue['series_id']}"
        )
        point["selection_method"] = "akshare_derived"
        derived.append(point)
    return derived


def _filter_as_of_period(series: list[dict], as_of_period: str | None) -> list[dict]:
    if not as_of_period:
        return series
    import re
    if not re.fullmatch(r"\d{4}(Q1|H1|Q3|A)", as_of_period):
        raise ValueError("as_of_period must use YYYYQ1, YYYYH1, YYYYQ3, or YYYYA")
    year = int(as_of_period[:4])
    order = ORDER_MAP[as_of_period[4:]]
    return [p for p in series if (p["period_year"], p["period_order"]) <= (year, order)]


def _derive_single_quarters(series: list[dict]) -> list[dict]:
    """把利润表/现金流累计口径拆成单季值，原始累计序列仍保留。"""
    cumulative_metrics = {
        "revenue", "net_profit_attributable", "deducted_net_profit",
        "operating_cashflow", "rd_expense",
    }
    by_key = {(p["metric_id"], p["report_period"]): p for p in series}
    result: list[dict] = []
    for metric_id in cumulative_metrics:
        for year in sorted({p["period_year"] for p in series if p["metric_id"] == metric_id}):
            q1 = by_key.get((metric_id, f"{year}Q1"))
            h1 = by_key.get((metric_id, f"{year}H1"))
            q3 = by_key.get((metric_id, f"{year}Q3"))
            annual = by_key.get((metric_id, f"{year}A"))
            for output_period, current, previous in [
                (f"{year}Q1", q1, None), (f"{year}Q2", h1, q1),
                (f"{year}Q3", q3, h1), (f"{year}Q4", annual, q3),
            ]:
                if current is None or (previous is None and not output_period.endswith("Q1")):
                    continue
                value = current["value_normalized"] if previous is None else current["value_normalized"] - previous["value_normalized"]
                point = _make_point(
                    f"single_quarter_{metric_id}", f"单季{current['metric_name']}", output_period, year, value,
                )
                point["source_candidate_id"] = current["series_id"] if previous is None else f"akshare_derived:{current['series_id']}:{previous['series_id']}"
                point["selection_method"] = "akshare_single_quarter"
                point["source_snippet"] = "akshare 单季值；Q2/Q3/Q4 由同年累计值相减得到"
                result.append(point)
    return result


def fetch_web_metrics(company_code, concepts_file, as_of_period: str | None = None):
    """抓取概念库所需的全部基础指标，返回 metric_series 形状的 dict 列表。"""
    if not HAS_AKSHARE:
        return []

    needed = _needed_metrics(concepts_file)
    if not needed:
        return []

    series: list[dict] = []
    series.extend(_fetch_abstract_metrics(company_code, needed))
    series.extend(_fetch_report_em(
        ak.stock_balance_sheet_by_report_em, company_code, BALANCE_SHEET_COLS, needed))
    series.extend(_fetch_report_em(
        ak.stock_profit_sheet_by_report_em, company_code, PROFIT_SHEET_COLS, needed))

    # 同一 (metric_id, period) 去重，保留先出现的
    seen = set()
    deduped = []
    for p in series:
        key = (p["metric_id"], p["report_period"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(p)
    # 派生指标必须在原始序列去重后计算，保证分子/分母各唯一且同报告期匹配。
    if "rd_expense" in needed and "revenue" in needed:
        deduped.extend(_derive_rd_expense_ratio(deduped))
    deduped.extend(_derive_single_quarters(deduped))
    return _filter_as_of_period(deduped, as_of_period)
