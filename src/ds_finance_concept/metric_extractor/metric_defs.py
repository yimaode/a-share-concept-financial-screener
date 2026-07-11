METRIC_DEFINITIONS = {
    "revenue": {
        "name": "营业收入",
        "aliases": ["营业收入合计", "营业总收入", "主营业务收入", "营业收入", "营收"],
    },
    "net_profit_attributable": {
        "name": "归母净利润",
        "aliases": [
            "归属于上市公司股东的净利润",
            "归母净利润",
            "归属于母公司所有者的净利润",
        ],
    },
    "deducted_net_profit": {
        "name": "扣非净利润",
        "aliases": [
            "扣除非经常性损益后的净利润",
            "扣非净利润",
            "归属于上市公司股东的扣除非经常性损益的净利润",
        ],
    },
    "operating_cashflow": {
        "name": "经营活动现金流量净额",
        "aliases": [
            "经营活动产生的现金流量净额",
            "经营现金流量净额",
            "经营性现金流",
            "经营活动现金流量净额",
        ],
    },
    "gross_margin": {
        "name": "毛利率",
        "aliases": ["综合毛利率", "毛利率"],
    },
    "total_assets": {
        "name": "总资产",
        "aliases": ["资产总计", "总资产", "资产总额"],
    },
    "inventory": {
        "name": "存货",
        "aliases": ["存货", "存货净额"],
    },
    "contract_liabilities": {
        "name": "合同负债",
        "aliases": ["合同负债"],
    },
    "fixed_assets": {
        "name": "固定资产",
        "aliases": ["固定资产", "固定资产净额", "固定资产账面价值"],
    },
    "construction_in_progress": {
        "name": "在建工程",
        "aliases": ["在建工程", "在建工程合计"],
    },
    "rd_expense": {
        "name": "研发费用",
        "aliases": ["研发费用", "研发投入金额", "研发费用金额", "研发投入"],
    },
}

RD_EXPENSE_RATIO_ALIASES = [
    "研发投入占营业收入比例", "研发费用率", "研发投入比例",
]

REVENUE_FALSE_POSITIVES = [
    "其他收益", "投资收益", "递延收益",
    "公允价值变动收益", "资产处置收益", "汇兑收益",
]
