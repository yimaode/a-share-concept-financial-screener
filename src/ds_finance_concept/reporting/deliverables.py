"""三份交付物生成器（改造后最终输出）。

① 概念 → 核心指标 数据表(CSV) + 各指标趋势图(PNG)   —— 你分析用的数据来源(来自 akshare)
② PDF 关键证据句(CSV, 带原文出处) + 每概念证据数量(CSV) —— 你分析用的数据来源(来自 PDF)
③ 最终量化打分 + 证据来源(CSV + MD)                    —— 系统自动输出的最终结论
"""

import csv
import json
from datetime import datetime
from pathlib import Path

from ..data_fetcher.web_api import CONCEPT_TO_BASE, METRIC_MAP


_CJK_FONT_CANDIDATES = [
    "Noto Sans SC", "PingFang SC", "Hiragino Sans GB", "Heiti SC",
    "Microsoft YaHei", "SimHei", "Arial Unicode MS",
]


def _configure_chart_font() -> None:
    """选用系统已安装的中文字体，避免图表中文变成豆腐块。"""
    import matplotlib
    from matplotlib import font_manager

    available = {f.name for f in font_manager.fontManager.ttflist}
    selected = next((n for n in _CJK_FONT_CANDIDATES if n in available), None)
    if selected:
        matplotlib.rcParams["font.family"] = "sans-serif"
        matplotlib.rcParams["font.sans-serif"] = [selected, "DejaVu Sans"]
    matplotlib.rcParams["axes.unicode_minus"] = False


def _read_json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    out: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s:
                out.append(json.loads(s))
    return out


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _latest_trend(trends: list[dict], metric_id: str) -> dict | None:
    pts = [t for t in trends if t.get("metric_id") == metric_id]
    if not pts:
        return None
    pts.sort(key=lambda t: (t.get("period_year", 0), t.get("period_order", 0)))
    return pts[-1]


def _fmt(v, pct=False):
    if v is None:
        return ""
    if pct:
        return f"{v * 100:.2f}%"
    return f"{v:.2f}"


def _fmt_metric_value(v, is_percent=False):
    if v is None:
        return ""
    return f"{v:.2f}%" if is_percent else f"{v:.2f}"


# ---------------------------------------------------------------------------
# ① 概念 → 核心指标 表 + 趋势图
# ---------------------------------------------------------------------------
def _build_concept_metrics(concepts, trends, series, out_dir) -> list[str]:
    files: list[str] = []

    # 概念↔指标快照表
    rows = []
    for c in concepts:
        cid = c.get("concept_id", "")
        cname = c.get("name", "")
        for hm in c.get("hard_metrics", []):
            base = CONCEPT_TO_BASE.get(hm, hm)
            if not base:
                rows.append({
                    "concept_id": cid, "concept_name": cname, "hard_metric": hm,
                    "base_metric_id": "", "base_metric_name": "(akshare 无此指标)",
                    "latest_period": "", "latest_value": "", "unit": "",
                    "yoy": "", "change_pp": "", "consecutive_growth": "", "cagr_3y": "",
                })
                continue
            t = _latest_trend(trends, base)
            if t is None:
                rows.append({
                    "concept_id": cid, "concept_name": cname, "hard_metric": hm,
                    "base_metric_id": base, "base_metric_name": METRIC_MAP.get(base, base),
                    "latest_period": "", "latest_value": "(无数据)", "unit": "",
                    "yoy": "", "change_pp": "", "consecutive_growth": "", "cagr_3y": "",
                })
                continue
            is_pct = t.get("is_percent", False)
            rows.append({
                "concept_id": cid, "concept_name": cname, "hard_metric": hm,
                "base_metric_id": base, "base_metric_name": t.get("metric_name", base),
                "latest_period": t.get("report_period", ""),
                "latest_value": _fmt_metric_value(t.get("value_normalized"), is_pct),
                "unit": t.get("value_unit_normalized", ""),
                "yoy": "" if is_pct else _fmt(t.get("yoy"), pct=True),
                "change_pp": _fmt(t.get("change_pp")) if is_pct else "",
                "consecutive_growth": t.get("consecutive_growth_count", 0),
                "cagr_3y": _fmt(t.get("cagr_3y"), pct=True),
            })
    p1 = out_dir / "01_concept_metrics.csv"
    _write_csv(p1, [
        "concept_id", "concept_name", "hard_metric", "base_metric_id", "base_metric_name",
        "latest_period", "latest_value", "unit", "yoy", "change_pp",
        "consecutive_growth", "cagr_3y",
    ], rows)
    files.append(str(p1))

    # 完整指标序列(长表)——原始数据来源
    srows = sorted(series, key=lambda s: (s.get("metric_id", ""), s.get("period_year", 0), s.get("period_order", 0)))
    p2 = out_dir / "01_metric_series.csv"
    _write_csv(p2, [
        "metric_id", "metric_name", "report_period", "period_year", "period_type",
        "value_normalized", "value_unit_normalized", "is_percent", "source",
    ], [{
        "metric_id": s.get("metric_id", ""), "metric_name": s.get("metric_name", ""),
        "report_period": s.get("report_period", ""), "period_year": s.get("period_year", ""),
        "period_type": s.get("period_type", ""), "value_normalized": s.get("value_normalized", ""),
        "value_unit_normalized": s.get("value_unit_normalized", ""),
        "is_percent": s.get("is_percent", False), "source": s.get("source", "akshare"),
    } for s in srows])
    files.append(str(p2))

    # 趋势图
    files.extend(_make_trend_charts(trends, out_dir / "01_charts"))
    return files


def _make_trend_charts(trends, charts_dir) -> list[str]:
    files: list[str] = []
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        _configure_chart_font()
    except Exception:
        return files

    from collections import defaultdict
    by_metric = defaultdict(list)
    for t in trends:
        by_metric[t.get("metric_id", "?")].append(t)

    charts_dir.mkdir(parents=True, exist_ok=True)
    for mid, pts in sorted(by_metric.items()):
        pts = sorted(pts, key=lambda t: (t.get("period_year", 0), t.get("period_order", 0)))
        if len(pts) < 2:
            continue
        try:
            labels = [p.get("report_period", "") for p in pts]
            values = [p.get("value_normalized", 0) for p in pts]
            name = pts[-1].get("metric_name", mid)
            fig, ax = plt.subplots(figsize=(7, 2.6))
            ax.plot(labels, values, "o-", linewidth=1.4, markersize=3)
            ax.set_title(f"{name} ({mid})", fontsize=9)
            ax.tick_params(labelsize=6)
            step = max(1, len(labels) // 16)
            ax.set_xticks(range(0, len(labels), step))
            ax.set_xticklabels([labels[i] for i in range(0, len(labels), step)], rotation=45, ha="right")
            path = charts_dir / f"metric_{mid}.png"
            fig.savefig(path, dpi=100, bbox_inches="tight")
            plt.close(fig)
            files.append(str(path))
        except Exception:
            plt.close("all")
            continue
    return files


# ---------------------------------------------------------------------------
# ② 证据句 + 每概念计数
# ---------------------------------------------------------------------------
def _build_evidence(concepts, evidence, stats, out_dir) -> list[str]:
    files: list[str] = []

    erows = sorted(evidence, key=lambda h: (
        h.get("concept_id", ""), h.get("polarity", ""),
        h.get("source_pdf", ""), h.get("page_number", 0)))
    p1 = out_dir / "02_evidence_sentences.csv"
    _write_csv(p1, [
        "concept_id", "concept_name", "polarity", "keyword", "sentence",
        "negation_detected", "source_pdf", "page_number", "relative_path",
    ], erows)
    files.append(str(p1))

    # 每概念计数
    cname_map = {c.get("concept_id", ""): c.get("name", "") for c in concepts}
    counts: dict[str, dict] = {}
    for c in concepts:
        cid = c.get("concept_id", "")
        counts[cid] = {"concept_id": cid, "concept_name": c.get("name", ""),
                       "positive": 0, "negative": 0, "total": 0}
    for h in evidence:
        cid = h.get("concept_id", "")
        if cid not in counts:
            counts[cid] = {"concept_id": cid, "concept_name": cname_map.get(cid, cid),
                           "positive": 0, "negative": 0, "total": 0}
        if h.get("polarity") == "positive":
            counts[cid]["positive"] += 1
        elif h.get("polarity") == "negative":
            counts[cid]["negative"] += 1
        counts[cid]["total"] += 1

    p2 = out_dir / "02_evidence_concept_counts.csv"
    _write_csv(p2, ["concept_id", "concept_name", "positive", "negative", "total"],
               sorted(counts.values(), key=lambda r: -r["total"]))
    files.append(str(p2))
    return files


# ---------------------------------------------------------------------------
# ③ 最终打分 + 证据来源
# ---------------------------------------------------------------------------
def _build_final_scores(company_code, scores_data, details, evidence, out_dir, canslim=None) -> list[str]:
    files: list[str] = []
    concepts = scores_data.get("concepts", [])

    rows = []
    for c in concepts:
        coverage = c.get("metric_coverage", {})
        rows.append({
            "concept_id": c.get("concept_id", ""),
            "concept_name": c.get("concept_name", ""),
            "score": c.get("score", 0),
            "level": c.get("level", ""),
            "positive_hits": c.get("positive_hits", 0),
            "negative_hits": c.get("negative_hits", 0),
            "positive_signals": c.get("positive_signals", 0),
            "negative_signals": c.get("negative_signals", 0),
            "status": c.get("status", ""),
            "metric_coverage": f"{coverage.get('available', 0)}/{coverage.get('required', 0)}",
            "missing_metrics": " | ".join(coverage.get("missing", [])),
            "unsupported_metrics": " | ".join(coverage.get("unsupported", [])),
            "quality_warnings": " | ".join(c.get("warnings", [])),
            "top_reasons": " | ".join(c.get("top_reasons", [])),
        })
    p1 = out_dir / "03_final_scores.csv"
    _write_csv(p1, ["concept_id", "concept_name", "score", "level",
                    "positive_hits", "negative_hits", "positive_signals", "negative_signals",
                    "status", "metric_coverage",
                    "missing_metrics", "unsupported_metrics", "quality_warnings",
                    "top_reasons"], rows)
    files.append(str(p1))

    # 打分明细(证据来源)
    p2 = out_dir / "03_score_details.csv"
    _write_csv(p2, ["concept_id", "component", "source_type", "source_id", "evidence_id",
                    "metric_id", "report_period", "points", "raw_value", "reason"],
               [{
                   "concept_id": d.get("concept_id", ""),
                   "component": d.get("component", ""),
                   "source_type": d.get("source_type", ""),
                   "source_id": d.get("source_id", ""),
                   "evidence_id": d.get("evidence_id", ""),
                   "metric_id": d.get("metric_id", ""),
                   "report_period": d.get("report_period", ""),
                   "points": d.get("points", 0),
                   "raw_value": d.get("raw_value", ""),
                   "reason": d.get("reason", ""),
               } for d in details])
    files.append(str(p2))

    # 最终结论 MD
    ev_by_concept: dict[str, list] = {}
    for h in evidence:
        ev_by_concept.setdefault(h.get("concept_id", ""), []).append(h)

    quality_statuses = {c.get("status", "") for c in concepts}
    if not concepts:
        screening_status = "无可评分概念"
    elif quality_statuses == {"ready"}:
        screening_status = "资料齐全，可进入人工研究"
    else:
        screening_status = "资料未齐全，量化分数仅供初筛"

    assessment = {
        "company_code": company_code,
        "screening_status": screening_status,
        "quantitative_scores_generated": bool(concepts),
        "evidence_hit_count": len(evidence),
        "evidence_signal_count": sum(
            c.get("positive_signals", 0) + c.get("negative_signals", 0)
            for c in concepts
        ),
        "concept_status_counts": {
            status: sum(1 for c in concepts if c.get("status", "") == status)
            for status in sorted(quality_statuses)
        },
        "disclaimer": "不构成投资建议；分数用于固定概念库的量化初筛。",
    }
    p_assessment = out_dir / "03_final_assessment.json"
    p_assessment.write_text(json.dumps(assessment, ensure_ascii=False, indent=2), encoding="utf-8")
    files.append(str(p_assessment))

    if canslim is not None:
        p_canslim = out_dir / "03_canslim_assessment.csv"
        _write_csv(p_canslim, ["dimension", "name", "status", "reason"], [
            {"dimension": key, "name": value.get("name", ""),
             "status": value.get("status", ""), "reason": value.get("reason", "")}
            for key, value in canslim.get("dimensions", {}).items()
        ])
        files.append(str(p_canslim))

    lines = [
        f"# 最终量化打分 — {company_code}",
        "",
        "> 本结果由系统自动生成，不构成投资建议。数字指标来自 akshare(东财)，证据句来自财报 PDF。",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"**系统初筛状态：{screening_status}**",
        f"**CANSLIM 初筛：{canslim.get('result', '未运行') if canslim else '未运行'}**",
        "",
        "| 概念 | 分数 | Level | 资料状态 | 指标覆盖 | 正向证据/信号 | 负向证据/信号 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for c in concepts:
        lines.append(
            f"| {c.get('concept_name','')} | {c.get('score',0)} | {c.get('level','')} | "
            f"{c.get('status','')} | {c.get('metric_coverage', {}).get('available', 0)}/"
            f"{c.get('metric_coverage', {}).get('required', 0)} | "
            f"{c.get('positive_hits',0)}/{c.get('positive_signals',0)} | "
            f"{c.get('negative_hits',0)}/{c.get('negative_signals',0)} |")
    lines.append("")

    for c in concepts:
        cid = c.get("concept_id", "")
        lines.append(f"## {c.get('concept_name','')} — {c.get('score',0)} ({c.get('level','')})")
        lines.append("")
        lines.append("**打分依据：**")
        for r in c.get("top_reasons", []):
            lines.append(f"- {r}")
        c_ev = ev_by_concept.get(cid, [])
        if c_ev:
            lines.append("")
            lines.append("**证据来源示例：**")
            for h in c_ev[:3]:
                lines.append(f"- `[{h.get('polarity','')}]` {h.get('source_pdf','')} p.{h.get('page_number','')}：{h.get('sentence','')}")
        if c.get("warnings"):
            lines.append("")
            lines.append("**资料限制：**")
            for warning in c["warnings"]:
                lines.append(f"- {warning}")
        lines.append("")

    p3 = out_dir / "03_final_report.md"
    p3.write_text("\n".join(lines), encoding="utf-8")
    files.append(str(p3))
    return files


def build_deliverables(
    company_code: str,
    concepts_file: Path,
    series_file: Path,
    metric_trends_file: Path,
    evidence_file: Path,
    evidence_stats_file: Path,
    concept_scores_file: Path,
    score_details_file: Path,
    canslim_file: Path,
    output_dir: Path,
) -> list[str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    concepts = _read_json(concepts_file).get("concepts", [])
    series = _read_jsonl(series_file)
    trends = _read_jsonl(metric_trends_file)
    evidence = _read_jsonl(evidence_file)
    stats = _read_json(evidence_stats_file) if Path(evidence_stats_file).exists() else {}
    scores_data = _read_json(concept_scores_file) if Path(concept_scores_file).exists() else {"concepts": []}
    details = _read_jsonl(score_details_file)
    canslim = _read_json(canslim_file) if Path(canslim_file).exists() else None

    files: list[str] = []
    files += _build_concept_metrics(concepts, trends, series, output_dir)
    files += _build_evidence(concepts, evidence, stats, output_dir)
    files += _build_final_scores(company_code, scores_data, details, evidence, output_dir, canslim)
    return files
