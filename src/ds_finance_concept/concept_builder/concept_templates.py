CONCEPT_TEMPLATES = [
    {
        "concept_id": "super_growth_stock",
        "name": "超级成长股",
        "definition": "公司营收和利润持续高速增长，通常年增长率超过30%，具备行业领先的成长性特征",
        "aliases": ["超级成长股", "高成长", "成长股", "业绩爆发"],
        "positive_keywords": {
            "growth": ["成长", "高增长", "业绩增长", "收入增长", "利润增长"],
            "quality": ["龙头", "领先", "市场份额", "份额提升"],
        },
        "negative_keywords": {
            "decline": ["下滑", "增速放缓", "增长放缓", "增长率下降"],
        },
        "hard_metrics": [
            "revenue_yoy",
            "net_profit_yoy",
            "non_gaap_net_profit_yoy",
            "market_share",
        ],
        "evidence_rules": {
            "min_evidence_count": 2,
            "require_financial_metric": True,
        },
        "scoring": {
            "high_confidence_weight": 3,
            "medium_confidence_weight": 2,
            "low_confidence_weight": 1,
        },
    },
    {
        "concept_id": "industry_boom",
        "name": "行业景气",
        "definition": "行业处于上行周期，下游需求旺盛，供需格局改善，景气度持续提升",
        "aliases": ["行业景气", "景气", "需求旺盛", "行业上行"],
        "positive_keywords": {
            "demand": ["景气", "需求旺盛", "行业复苏", "周期向上"],
            "supply": ["供不应求", "供需改善"],
        },
        "negative_keywords": {
            "decline": ["需求下滑", "景气下行", "周期向下"],
        },
        "hard_metrics": [
            "revenue_yoy",
            "gross_margin",
            "contract_liabilities_yoy",
            "market_share",
        ],
        "evidence_rules": {
            "min_evidence_count": 2,
            "require_financial_metric": True,
        },
        "scoring": {
            "high_confidence_weight": 3,
            "medium_confidence_weight": 2,
            "low_confidence_weight": 1,
        },
    },
    {
        "concept_id": "core_alpha_company",
        "name": "核心α公司",
        "definition": "公司具备强大竞争壁垒，通过技术、品牌或规模优势获得持续超额收益",
        "aliases": ["核心α公司", "核心公司", "龙头", "龙头股", "行业龙头", "龙头企业", "细分龙头", "核心龙头", "竞争优势", "市占率领先", "市场占有率领先"],
        "positive_keywords": {
            "moat": ["核心", "壁垒", "竞争力", "技术", "客户认证"],
            "position": ["龙头", "龙头股", "行业龙头", "龙头企业", "细分龙头", "核心龙头", "第一", "领先", "市场份额", "市占率领先", "市场占有率领先"],
        },
        "negative_keywords": {
            "erosion": ["壁垒削弱", "竞争加剧", "份额下降"],
        },
        "hard_metrics": [
            "gross_margin",
            "rd_expense_ratio",
            "market_share",
            "net_profit_yoy",
        ],
        "evidence_rules": {
            "min_evidence_count": 2,
            "require_financial_metric": True,
        },
        "scoring": {
            "high_confidence_weight": 3,
            "medium_confidence_weight": 2,
            "low_confidence_weight": 1,
        },
    },
    {
        "concept_id": "supply_shortage",
        "name": "供不应求",
        "definition": "产品需求远超供给能力，产能利用率高，价格有上涨动力，订单交付周期延长",
        "aliases": ["供不应求", "产能紧张", "订单饱满", "满产满销"],
        "positive_keywords": {
            "demand_excess": ["供不应求", "订单饱满", "产能紧张", "满产", "涨价"],
            "order": ["在手订单", "订单储备"],
        },
        "negative_keywords": {
            "excess": ["产能过剩", "订单不足"],
        },
        "hard_metrics": [
            "revenue_yoy",
            "gross_margin",
            "contract_liabilities_yoy",
            "inventory_yoy",
            "construction_in_progress_yoy",
        ],
        "evidence_rules": {
            "min_evidence_count": 2,
            "require_financial_metric": True,
        },
        "scoring": {
            "high_confidence_weight": 3,
            "medium_confidence_weight": 2,
            "low_confidence_weight": 1,
        },
    },
    {
        "concept_id": "pre_explosion_stage",
        "name": "爆发前期",
        "definition": "公司处于产能扩张或新产品放量前夕，静待催化剂触发业绩爆发",
        "aliases": ["爆发前期", "产能释放", "新产品放量", "订单储备"],
        "positive_keywords": {
            "capacity": ["产能释放", "新产线", "扩产", "投产"],
            "pipeline": ["订单储备", "新产品", "放量"],
        },
        "negative_keywords": {
            "delay": ["投产延迟", "放量不及预期"],
        },
        "hard_metrics": [
            "construction_in_progress_yoy",
            "rd_expense_ratio",
            "contract_liabilities_yoy",
            "revenue_yoy",
        ],
        "evidence_rules": {
            "min_evidence_count": 2,
            "require_financial_metric": True,
        },
        "scoring": {
            "high_confidence_weight": 3,
            "medium_confidence_weight": 2,
            "low_confidence_weight": 1,
        },
    },
    {
        "concept_id": "risk_negative_evidence",
        "name": "反证与风险",
        "definition": "存在可能导致投资逻辑失效的风险信号或负面证据，需要持续跟踪验证",
        "aliases": ["反证与风险", "风险", "下滑", "需求疲软", "库存积压", "毛利率下降"],
        "positive_keywords": {},
        "negative_keywords": {
            "risk": ["风险", "下滑", "疲软", "库存积压", "毛利率下降", "现金流恶化"],
            "demand": ["需求下滑", "需求疲软"],
        },
        "hard_metrics": [
            "gross_margin",
            "inventory_yoy",
            "operating_cashflow_yoy",
            "revenue_yoy",
        ],
        "evidence_rules": {
            "min_evidence_count": 1,
            "require_financial_metric": False,
        },
        "scoring": {
            "high_confidence_weight": 3,
            "medium_confidence_weight": 2,
            "low_confidence_weight": 1,
        },
    },
]

CANDIDATE_ID_TO_TEMPLATE_ID = {
    "super_growth_stock": "super_growth_stock",
    "industry_prosperity": "industry_boom",
    "core_alpha_company": "core_alpha_company",
    "supply_shortage": "supply_shortage",
    "pre_explosion_phase": "pre_explosion_stage",
    "risk_counterevidence": "risk_negative_evidence",
}
