"""Rebuild the README scorecard from sanitized aggregate example data."""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "examples" / "showcase"
OUTPUT = ROOT / "docs" / "assets" / "showcase-scorecard.png"


def _font() -> str:
    candidates = ["PingFang SC", "Noto Sans CJK SC", "Hiragino Sans GB", "SimHei"]
    available = {item.name for item in font_manager.fontManager.ttflist}
    return next((name for name in candidates if name in available), "DejaVu Sans")


def main() -> None:
    with (DATA / "300750_concept_scores.csv").open(encoding="utf-8") as handle:
        scores = list(csv.DictReader(handle))
    with (DATA / "300750_canslim.csv").open(encoding="utf-8") as handle:
        canslim = list(csv.DictReader(handle))

    plt.rcParams["font.family"] = _font()
    plt.rcParams["axes.unicode_minus"] = False
    fig = plt.figure(figsize=(16, 9), facecolor="#F7F8FA")
    grid = fig.add_gridspec(2, 1, height_ratios=[3.5, 1.2], hspace=.36)

    ax = fig.add_subplot(grid[0])
    names = [row["concept_name"] for row in scores][::-1]
    values = [int(row["score"]) for row in scores][::-1]
    colors = ["#D97706" if name == "反证与风险" else "#2563EB" for name in names]
    bars = ax.barh(names, values, color=colors, edgecolor="#1F2937", linewidth=.7)
    ax.set_xlim(0, 105)
    ax.set_xlabel("量化分数（0–100）")
    ax.set_title("概念量化评分示例", loc="left", fontsize=20, weight="bold", pad=28)
    ax.text(0, 1.02, "宁德时代（300750）· 2026Q1 聚合结果 · 示例不构成投资建议",
            transform=ax.transAxes, color="#4B5563", fontsize=11)
    ax.grid(axis="x", color="#D1D5DB", linewidth=.8, alpha=.7)
    ax.set_axisbelow(True)
    ax.spines[["top", "right", "left"]].set_visible(False)
    for bar, value in zip(bars, values):
        ax.text(value + 1.2, bar.get_y() + bar.get_height() / 2, str(value),
                va="center", fontsize=11, color="#111827", weight="bold")

    ax2 = fig.add_subplot(grid[1])
    ax2.axis("off")
    state_style = {
        "pass": ("通过", "#DBEAFE", "#1D4ED8"),
        "fail": ("未通过", "#FEF3C7", "#92400E"),
        "unavailable": ("资料不足", "#E5E7EB", "#374151"),
    }
    width = .125
    start = .03
    for index, row in enumerate(canslim):
        x = start + index * (width + .014)
        label, fill, ink = state_style[row["status"]]
        ax2.add_patch(plt.Rectangle((x, .2), width, .62, transform=ax2.transAxes,
                                    facecolor=fill, edgecolor=ink, linewidth=1.1))
        ax2.text(x + width / 2, .61, f"{row['dimension']} · {row['name']}",
                 transform=ax2.transAxes, ha="center", va="center",
                 fontsize=10, color="#111827", weight="bold")
        ax2.text(x + width / 2, .37, label, transform=ax2.transAxes,
                 ha="center", va="center", fontsize=10, color=ink)
    ax2.text(.03, .96, "CANSLIM 辅助评估 · 七维状态", transform=ax2.transAxes,
             fontsize=14, weight="bold", color="#111827")
    ax2.text(.03, .04, "数据源：akshare（财务/行情）与公开财报 PDF（语言证据）；外部接口缺失会明确标记为资料不足。",
             transform=ax2.transAxes, fontsize=10, color="#4B5563")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT, dpi=160, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
