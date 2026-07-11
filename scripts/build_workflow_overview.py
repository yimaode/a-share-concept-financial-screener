"""Build the README overview for the concept-freezing financial screener."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "assets" / "workflow-overview.png"


def _font() -> str:
    candidates = ["PingFang SC", "Noto Sans CJK SC", "Hiragino Sans GB", "SimHei"]
    available = {item.name for item in font_manager.fontManager.ttflist}
    return next((name for name in candidates if name in available), "DejaVu Sans")


def _box(ax, x, y, width, height, title, detail, fill, edge):
    patch = FancyBboxPatch(
        (x, y), width, height,
        boxstyle="round,pad=0.012,rounding_size=0.018",
        facecolor=fill, edgecolor=edge, linewidth=1.5,
        transform=ax.transAxes,
    )
    ax.add_patch(patch)
    ax.text(x + width / 2, y + height * .66, title, ha="center", va="center",
            transform=ax.transAxes, fontsize=13, weight="bold", color="#111827")
    ax.text(x + width / 2, y + height * .35, detail, ha="center", va="center",
            transform=ax.transAxes, fontsize=9.5, color="#4B5563", linespacing=1.35)


def _arrow(ax, start, end, color="#475569"):
    arrow = FancyArrowPatch(
        start, end, arrowstyle="-|>", mutation_scale=15,
        linewidth=1.5, color=color, transform=ax.transAxes,
        connectionstyle="arc3,rad=0",
    )
    ax.add_patch(arrow)


def main() -> None:
    plt.rcParams["font.family"] = _font()
    fig, ax = plt.subplots(figsize=(16, 9), facecolor="#F8FAFC")
    ax.set_facecolor("#F8FAFC")
    ax.axis("off")

    ax.text(.05, .92, "基于投资概念固化的 A 股财报量化筛选器",
            transform=ax.transAxes, fontsize=25, weight="bold", color="#0F172A")
    ax.text(.05, .865, "把零散研究观点固化为可审核规则，再让 Agent 对公司列表执行可重复、可追溯的财报筛选",
            transform=ax.transAxes, fontsize=13, color="#475569")

    ax.text(.05, .77, "阶段一 · 概念固化（低频、私有、需人工审核）",
            transform=ax.transAxes, fontsize=14, weight="bold", color="#1D4ED8")
    top = [
        ("研究材料", "有权使用的论坛发言\n个人笔记 · 投资方法"),
        ("规则化抽取", "原文切片 · 投资洞察\n候选概念 · 可能指标"),
        ("人工审核", "定义 · 正负关键词\n硬指标 · 证据要求"),
        ("冻结概念库", "可版本化 concepts.json\n不包含原始私有语料"),
    ]
    xs = [.05, .29, .53, .77]
    for x, (title, detail) in zip(xs, top):
        _box(ax, x, .58, .18, .14, title, detail, "#DBEAFE", "#2563EB")
    for x1, x2 in zip(xs[:-1], xs[1:]):
        _arrow(ax, (x1 + .185, .65), (x2 - .008, .65), "#2563EB")

    ax.text(.05, .47, "阶段二 · 按概念筛选（高频、可批量、可恢复）",
            transform=ax.transAxes, fontsize=14, weight="bold", color="#92400E")
    bottom = [
        ("公司列表 + 概念库", "单股或 CSV 批次\n冻结规则作为输入"),
        ("财务数据 + 财报 PDF", "联网指标保持数值口径\n本地 PDF 保留原文页码"),
        ("指标与证据", "同比 · CAGR · 趋势\n正负证据 · 风险反证"),
        ("研究交付物", "概念评分 · 资料状态\nCANSLIM 辅助 · 候选清单"),
    ]
    for x, (title, detail) in zip(xs, bottom):
        _box(ax, x, .28, .18, .14, title, detail, "#FEF3C7", "#D97706")
    for x1, x2 in zip(xs[:-1], xs[1:]):
        _arrow(ax, (x1 + .185, .35), (x2 - .008, .35), "#D97706")

    footer = FancyBboxPatch(
        (.05, .08), .90, .10, boxstyle="round,pad=0.012,rounding_size=0.018",
        facecolor="#E5E7EB", edgecolor="#64748B", linewidth=1.2,
        transform=ax.transAxes,
    )
    ax.add_patch(footer)
    ax.text(.5, .14, "Agent 工具包 = 阅读说明 + 两阶段工作流 + CLI/脚本 + 质量守卫 + 测试 + 结果模板",
            transform=ax.transAxes, ha="center", va="center", fontsize=12,
            weight="bold", color="#111827")
    ax.text(.5, .105, "不是单一 Skill · 默认无需 LLM API · 输出只用于研究初筛，不构成投资建议",
            transform=ax.transAxes, ha="center", va="center", fontsize=10.5, color="#4B5563")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT, dpi=160, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
