import pytest

from ds_finance_concept.concept_builder.errors import InsightValidationError
from ds_finance_concept.concept_builder.insight_extractor import (
    extract_insight_from_quote,
    extract_insights_from_quotes,
    generate_insight_id,
)


def make_quote(normalized_text, raw_text=None, **overrides):
    defaults = {
        "quote_id": "quote_test123456",
        "source_file": "001.md",
        "heading_path": ["H1"],
        "raw_text": raw_text if raw_text is not None else normalized_text,
        "normalized_text": normalized_text,
    }
    defaults.update(overrides)
    return defaults


def test_growth_revenue_profit_concept():
    quote = make_quote("公司成长性良好，收入持续增长，利润创新高")
    card = extract_insight_from_quote(quote)
    assert card is not None
    assert "超级成长股" in card.candidate_concepts
    assert "revenue_yoy" in card.possible_financial_metrics
    assert "net_profit_yoy" in card.possible_financial_metrics
    assert card.confidence == "high"


def test_supply_demand_order_capacity():
    quote = make_quote("行业供不应求，订单饱满，产能紧张")
    card = extract_insight_from_quote(quote)
    assert card is not None
    assert "供不应求" in card.candidate_concepts
    assert "订单改善" in card.observable_signals
    assert card.confidence == "high"


def test_inventory_weak_demand_margin_decline():
    quote = make_quote("库存积压严重，需求疲软，毛利率下降明显")
    card = extract_insight_from_quote(quote)
    assert card is not None
    assert "反证与风险" in card.candidate_concepts
    assert "库存压力" in card.observable_signals
    assert "需求走弱" in card.observable_signals


def test_bull_stock_not_quantifiable():
    quote = make_quote("这是一支大牛股，具有极强成长性")
    card = extract_insight_from_quote(quote)
    assert card is not None
    assert len(card.not_quantifiable_parts) > 0
    assert card.confidence in ("low", "medium")
    assert card.confidence != "high"


def test_short_text_returns_none():
    quote = make_quote("短")
    card = extract_insight_from_quote(quote)
    assert card is None


def test_insight_id_consistency():
    quote = make_quote("公司成长性良好前景光明")
    card1 = extract_insight_from_quote(quote)
    card2 = extract_insight_from_quote(quote)
    assert card1 is not None
    assert card2 is not None
    assert card1.insight_id == card2.insight_id


def test_no_investment_keyword_but_long_enough():
    quote = make_quote("这是一段足够长的但是没有任何投资判断关键词的文本内容描述")
    card = extract_insight_from_quote(quote)
    assert card is not None
    assert card.confidence == "low"


def test_no_investment_keyword_and_short():
    quote = make_quote("这是一段普通描述")
    card = extract_insight_from_quote(quote)
    assert card is None


def test_missing_required_field_raises():
    quote = {
        "quote_id": "q1",
        "source_file": "f.md",
    }
    with pytest.raises(InsightValidationError, match="missing required field"):
        extract_insight_from_quote(quote)


def test_extract_insights_from_quotes():
    quotes = [
        make_quote("公司成长性良好，收入增长快"),
        make_quote("短"),
        make_quote("库存积压风险需要关注行业景气度变化"),
    ]
    cards = extract_insights_from_quotes(quotes)
    assert len(cards) == 2


def test_generate_insight_id_is_stable():
    id1 = generate_insight_id("quote_abc", "hello world")
    id2 = generate_insight_id("quote_abc", "hello world")
    assert id1 == id2
    assert id1.startswith("insight_")
    assert len(id1) == 20


def test_generate_insight_id_different_inputs():
    id1 = generate_insight_id("quote_a", "text")
    id2 = generate_insight_id("quote_b", "text")
    assert id1 != id2


def test_report_keywords_extracted():
    quote = make_quote("公司毛利率提升，订单饱满，产能正在扩产")
    card = extract_insight_from_quote(quote)
    assert card is not None
    assert "毛利率" in card.possible_report_keywords
    assert "扩产" in card.possible_report_keywords


def test_confidence_medium_when_concept_no_metric():
    quote = make_quote("行业景气度回升明显")
    card = extract_insight_from_quote(quote)
    assert card is not None
    assert card.confidence == "medium"


def test_confidence_low_when_no_concept():
    quote = make_quote("估值" + "偏高需要谨慎评估当前的")
    card = extract_insight_from_quote(quote)
    assert card is not None
    assert card.confidence == "low"


def test_not_quantifiable_caps_confidence():
    quote = make_quote("大牛股成长性良好，收入利润双增长")
    card = extract_insight_from_quote(quote)
    assert card is not None
    assert len(card.not_quantifiable_parts) > 0
    assert card.confidence == "medium"


def test_empty_list_fields_never_none():
    quote = make_quote("估值水平处于历史低位")
    card = extract_insight_from_quote(quote)
    assert card is not None
    assert isinstance(card.candidate_concepts, list)
    assert isinstance(card.observable_signals, list)
    assert isinstance(card.possible_financial_metrics, list)
    assert isinstance(card.possible_report_keywords, list)
    assert isinstance(card.not_quantifiable_parts, list)
