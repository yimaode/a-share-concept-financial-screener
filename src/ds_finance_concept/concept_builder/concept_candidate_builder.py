from collections import Counter

from .concept_candidate_schema import ConceptCandidate
from .errors import InsightValidationError

CONCEPT_MAPPING = {
    "super_growth_stock": {
        "canonical_name": "超级成长股",
        "keywords": ["超级成长股", "高成长", "成长股", "大牛股", "业绩爆发"],
    },
    "industry_prosperity": {
        "canonical_name": "行业景气",
        "keywords": ["行业景气", "景气", "需求旺盛", "行业上行"],
    },
    "core_alpha_company": {
        "canonical_name": "核心 α 公司",
        "keywords": [
            "核心α公司", "核心 alpha", "核心公司",
            "龙头", "龙头股", "行业龙头", "龙头企业", "细分龙头", "核心龙头",
            "竞争优势", "市占率领先", "市场占有率领先",
        ],
    },
    "supply_shortage": {
        "canonical_name": "供不应求",
        "keywords": ["供不应求", "产能紧张", "订单饱满", "满产满销"],
    },
    "pre_explosion_phase": {
        "canonical_name": "爆发前期",
        "keywords": ["爆发前期", "产能释放", "新产品放量", "订单储备"],
    },
    "risk_counterevidence": {
        "canonical_name": "反证与风险",
        "keywords": ["反证与风险", "风险", "反证", "下滑", "需求疲软", "库存积压", "毛利率下降"],
    },
}

INSIGHT_REQUIRED_FIELDS = [
    "insight_id", "quote_id", "investment_claim",
    "candidate_concepts", "observable_signals",
    "possible_financial_metrics", "possible_report_keywords",
    "not_quantifiable_parts", "confidence",
]


def _classify_concept(concept_name: str) -> str | None:
    for cid, info in CONCEPT_MAPPING.items():
        if concept_name in info["keywords"]:
            return cid
    return None


def _freq_sorted(items: list[list[str]]) -> list[str]:
    counter: Counter[str] = Counter()
    for item_list in items:
        counter.update(item_list)
    return [item for item, _ in counter.most_common()]


def _compute_review(cc: ConceptCandidate) -> None:
    reasons: list[str] = []
    if cc.candidate_concept_id == "uncategorized":
        reasons.append("未识别概念，需人工分类")
    if cc.evidence_count < 2:
        reasons.append(f"证据不足（仅{cc.evidence_count}条insight）")
    if (
        cc.confidence_summary.get("medium", 0) == 0
        and cc.confidence_summary.get("high", 0) == 0
        and cc.evidence_count > 0
    ):
        reasons.append("全部为低置信度")
    if reasons:
        cc.needs_manual_review = True
        cc.manual_review_reasons = reasons


def build_concept_candidates(insights: list[dict]) -> list[ConceptCandidate]:
    grouped: dict[str, dict] = {}

    for insight in insights:
        for field in INSIGHT_REQUIRED_FIELDS:
            if field not in insight:
                raise InsightValidationError(
                    f"Insight missing required field: {field}, "
                    f"insight_id={insight.get('insight_id', 'unknown')}"
                )

        concepts: list[str] = insight.get("candidate_concepts", [])

        if not concepts:
            continue

        for concept_name in concepts:
            cid = _classify_concept(concept_name) or "uncategorized"

            if cid not in grouped:
                canonical = (
                    CONCEPT_MAPPING[cid]["canonical_name"]
                    if cid != "uncategorized"
                    else concept_name
                )
                grouped[cid] = {
                    "canonical_name": canonical,
                    "quote_ids": [],
                    "insight_ids": [],
                    "claims": [],
                    "signals": [],
                    "metrics": [],
                    "keywords": [],
                    "not_quantifiable": [],
                    "confidence": {"high": 0, "medium": 0, "low": 0},
                }

            bucket = grouped[cid]
            bucket["quote_ids"].append(insight["quote_id"])
            bucket["insight_ids"].append(insight["insight_id"])
            bucket["claims"].append(insight["investment_claim"])
            bucket["signals"].append(insight.get("observable_signals", []))
            bucket["metrics"].append(insight.get("possible_financial_metrics", []))
            bucket["keywords"].append(insight.get("possible_report_keywords", []))
            bucket["not_quantifiable"].append(insight.get("not_quantifiable_parts", []))
            conf = insight.get("confidence", "low")
            if conf in bucket["confidence"]:
                bucket["confidence"][conf] += 1

    results: list[ConceptCandidate] = []
    for cid, bucket in sorted(grouped.items()):
        cc = ConceptCandidate(
            candidate_concept_id=cid,
            canonical_name=bucket["canonical_name"],
            source_quote_ids=sorted(set(bucket["quote_ids"])),
            source_insight_ids=sorted(set(bucket["insight_ids"])),
            summary_definition="",
            common_observable_signals=_freq_sorted(bucket["signals"]),
            common_financial_metrics=_freq_sorted(bucket["metrics"]),
            common_report_keywords=_freq_sorted(bucket["keywords"]),
            common_not_quantifiable_parts=_freq_sorted(bucket["not_quantifiable"]),
            confidence_summary=bucket["confidence"],
            evidence_count=len(set(bucket["insight_ids"])),
        )
        _compute_review(cc)
        results.append(cc)

    return results
