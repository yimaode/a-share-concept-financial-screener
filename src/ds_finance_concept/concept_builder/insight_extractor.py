import hashlib

from .errors import InsightValidationError
from .insight_schema import InsightCard

INVESTMENT_KEYWORDS = [
    "成长", "景气", "龙头", "核心", "供不应求", "订单", "需求", "产能",
    "利润", "收入", "毛利率", "现金流", "估值", "周期", "行业",
    "α", "alpha", "爆发",
]

CONCEPT_KEYWORD_MAP = [
    (["成长", "高增长", "业绩增长", "收入增长", "利润增长"], "超级成长股"),
    (["景气", "需求旺盛", "行业复苏", "周期向上"], "行业景气"),
    (["龙头", "第一", "领先", "市场份额", "份额提升"], "龙头股"),
    (["核心", "壁垒", "竞争力", "技术", "客户认证"], "核心α公司"),
    (["供不应求", "订单饱满", "产能紧张", "满产", "涨价"], "供不应求"),
    (["产能释放", "新产线", "扩产", "投产", "订单储备"], "爆发前期"),
    (["风险", "下滑", "疲软", "库存积压", "毛利率下降", "现金流恶化"], "反证与风险"),
]

SIGNAL_KEYWORD_MAP = [
    (["收入增长", "营收增长"], "营业收入增长"),
    (["利润增长", "净利润增长"], "利润增长"),
    (["毛利率提升"], "盈利能力改善"),
    (["现金流改善"], "经营质量改善"),
    (["订单", "订单饱满", "在手订单"], "订单改善"),
    (["需求旺盛", "需求提升"], "下游需求改善"),
    (["扩产", "新产线", "产能释放", "投产"], "产能扩张或释放"),
    (["涨价", "价格上涨"], "产品价格改善"),
    (["库存积压"], "库存压力"),
    (["需求疲软"], "需求走弱"),
]

METRIC_KEYWORD_MAP = [
    (["收入", "营收"], "revenue_yoy"),
    (["利润", "净利润", "归母"], "net_profit_yoy"),
    (["扣非"], "non_gaap_net_profit_yoy"),
    (["毛利率"], "gross_margin"),
    (["现金流"], "operating_cashflow_yoy"),
    (["订单", "预收", "合同负债"], "contract_liabilities_yoy"),
    (["存货", "库存"], "inventory_yoy"),
    (["产能", "扩产", "投产", "在建工程"], "construction_in_progress_yoy"),
    (["研发"], "rd_expense_ratio"),
    (["市场份额", "份额"], "market_share"),
]

NOT_QUANTIFIABLE_MAP = {
    "大牛股": "大牛股属于结果性描述，不能直接量化",
    "好公司": "好公司属于主观描述，不能直接量化",
    "格局": "格局属于抽象判断，需要拆解为竞争优势指标",
    "认知": "认知属于主观能力描述，不能从财报直接验证",
    "情绪": "市场情绪不能仅从财报直接验证",
}

ALL_REPORT_KEYWORDS: list[str] = []
for _keywords, _ in CONCEPT_KEYWORD_MAP:
    ALL_REPORT_KEYWORDS.extend(_keywords)
for _keywords, _ in SIGNAL_KEYWORD_MAP:
    ALL_REPORT_KEYWORDS.extend(_keywords)
for _keywords, _ in METRIC_KEYWORD_MAP:
    ALL_REPORT_KEYWORDS.extend(_keywords)
ALL_REPORT_KEYWORDS = sorted(set(ALL_REPORT_KEYWORDS), key=len, reverse=True)


def generate_insight_id(quote_id: str, original_text: str) -> str:
    key = f"{quote_id}:{original_text}"
    sha1_hash = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
    return f"insight_{sha1_hash}"


def _match_map_values(text: str, keyword_map: list[tuple[list[str], str]]) -> list[str]:
    results: list[str] = []
    seen: set[str] = set()
    for keywords, value in keyword_map:
        for kw in keywords:
            if kw in text and value not in seen:
                results.append(value)
                seen.add(value)
                break
    return results


def _extract_report_keywords(text: str) -> list[str]:
    results: list[str] = []
    seen: set[str] = set()
    for kw in ALL_REPORT_KEYWORDS:
        if kw in text and kw not in seen:
            results.append(kw)
            seen.add(kw)
    return results


def _compute_confidence(
    concepts: list[str],
    metrics: list[str],
    not_quantifiable: list[str],
    has_investment_kw: bool,
) -> str:
    if concepts and metrics:
        confidence = "high"
    elif concepts:
        confidence = "medium"
    else:
        confidence = "low"

    if not_quantifiable and confidence == "high":
        confidence = "medium"

    return confidence


def extract_insight_from_quote(quote: dict) -> InsightCard | None:
    required_fields = [
        "quote_id", "source_file", "heading_path",
        "raw_text", "normalized_text",
    ]
    for field in required_fields:
        if field not in quote:
            raise InsightValidationError(f"Quote missing required field: {field}")

    normalized_text: str = quote["normalized_text"]

    if len(normalized_text) < 8:
        return None

    has_investment_kw = any(kw in normalized_text for kw in INVESTMENT_KEYWORDS)

    if not has_investment_kw and len(normalized_text) < 20:
        return None

    candidate_concepts = _match_map_values(normalized_text, CONCEPT_KEYWORD_MAP)
    observable_signals = _match_map_values(normalized_text, SIGNAL_KEYWORD_MAP)
    possible_financial_metrics = _match_map_values(normalized_text, METRIC_KEYWORD_MAP)
    possible_report_keywords = _extract_report_keywords(normalized_text)

    not_quantifiable_parts: list[str] = []
    for kw, description in NOT_QUANTIFIABLE_MAP.items():
        if kw in normalized_text:
            not_quantifiable_parts.append(description)

    confidence = _compute_confidence(
        candidate_concepts, possible_financial_metrics,
        not_quantifiable_parts, has_investment_kw,
    )

    if not has_investment_kw:
        confidence = "low"

    insight_id = generate_insight_id(quote["quote_id"], quote["raw_text"])

    return InsightCard(
        insight_id=insight_id,
        quote_id=quote["quote_id"],
        source_file=quote["source_file"],
        heading_path=quote["heading_path"],
        original_text=quote["raw_text"],
        investment_claim=normalized_text,
        candidate_concepts=candidate_concepts,
        observable_signals=observable_signals,
        possible_financial_metrics=possible_financial_metrics,
        possible_report_keywords=possible_report_keywords,
        not_quantifiable_parts=not_quantifiable_parts,
        confidence=confidence,
        extraction_method="rule_based_v1",
    )


def extract_insights_from_quotes(quotes: list[dict]) -> list[InsightCard]:
    cards: list[InsightCard] = []
    for quote in quotes:
        card = extract_insight_from_quote(quote)
        if card is not None:
            cards.append(card)
    return cards
