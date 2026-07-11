import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path


_CJK_FONT_CANDIDATES = [
    "Noto Sans SC", "PingFang SC", "Hiragino Sans GB", "Heiti SC",
    "Microsoft YaHei", "SimHei", "Arial Unicode MS",
]


def _configure_chart_font() -> str | None:
    """Use an installed CJK-capable font so Chinese labels do not become tofu."""
    import matplotlib
    from matplotlib import font_manager

    available = {font.name for font in font_manager.fontManager.ttflist}
    selected = next((name for name in _CJK_FONT_CANDIDATES if name in available), None)
    if selected:
        matplotlib.rcParams["font.family"] = "sans-serif"
        matplotlib.rcParams["font.sans-serif"] = [selected, "DejaVu Sans"]
    matplotlib.rcParams["axes.unicode_minus"] = False
    return selected


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s:
                records.append(json.loads(s))
    return records


def build_company_report(
    company_code: str,
    concepts_file: Path,
    metric_trends_file: Path,
    metric_series_file: Path,
    evidence_file: Path,
    concept_scores_file: Path,
    output_dir: Path,
) -> tuple[str, list[str], list[str]]:
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    generated_files: list[str] = []
    skipped_assets: list[dict] = []
    warnings: list[str] = []

    concepts = _read_json(concepts_file).get("concepts", [])
    trends = _read_jsonl(metric_trends_file)
    series = _read_jsonl(metric_series_file)
    evidence = _read_jsonl(evidence_file)
    scores_data = _read_json(concept_scores_file) if concept_scores_file.exists() else {"concepts": []}

    has_manual = any(s.get("selection_method") == "manual_review" for s in series)

    pipeline_root = output_dir.parent
    manifest_file = pipeline_root / "pdf_tables" / "pdf_manifest.jsonl"
    if not manifest_file.exists():
        manifest_file = pipeline_root / "pdf_extract" / "pdf_manifest.jsonl"
    manifest = _read_jsonl(manifest_file) if manifest_file.exists() else []

    lines: list[str] = []
    lines.append(f"# 公司财务分析报告 — {company_code}")
    lines.append("")
    lines.append(f"> 本报告不构成投资建议。报告中的任何信息不应被视为对证券的推荐。")
    lines.append("")
    lines.append(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    lines.append("## 1. 报告范围")
    lines.append("")
    pdf_count = len(manifest)
    page_count = sum(m.get("page_count", 0) for m in manifest)
    lines.append(f"- 公司代码: {company_code}")
    lines.append(f"- 分析 PDF: {pdf_count} 份")
    lines.append(f"- 总页数: {page_count}")
    lines.append(f"- 概念数量: {len(scores_data.get('concepts', []))}")
    lines.append(f"- 趋势指标: {len(trends)} 点")
    lines.append(f"- 证据句: {len(evidence)} 条")
    lines.append("")

    lines.append("## 2. 数据完整性")
    lines.append("")
    lines.append(f"| 数据源 | 数量 |")
    lines.append(f"| --- | --- |")
    lines.append(f"| 指标趋势点 | {len(trends)} |")
    lines.append(f"| 证据句 | {len(evidence)} |")
    lines.append(f"| 时间序列点 | {len(series)} |")
    lines.append(f"| 概念评分 | {len(scores_data.get('concepts', []))} |")
    lines.append("")

    lines.append("## 3. 概念评分总览")
    lines.append("")
    sc = scores_data.get("concepts", [])
    if sc:
        lines.append("| 概念 | 分数 | Level | 正向证据 | 负向证据 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for c in sc:
            lines.append(f"| {c.get('concept_name', c.get('concept_id', ''))} | {c.get('score', 0)} | {c.get('level', '')} | {c.get('positive_hits', 0)} | {c.get('negative_hits', 0)} |")
        lines.append("")
    else:
        lines.append("无概念评分数据")
        lines.append("")

    chart_path = _make_bar_chart(sc, assets_dir)
    if chart_path:
        generated_files.append(str(chart_path))
        lines.append(f"![概念评分](assets/{chart_path.name})")
        lines.append("")

    _make_table_chart(sc, assets_dir, generated_files)

    _make_metric_latest_table(trends, assets_dir, generated_files, skipped_assets)

    lines.append("## 4. 财务趋势摘要")
    lines.append("")
    if trends:
        by_metric = defaultdict(list)
        for t in trends:
            by_metric[t["metric_id"]].append(t)
        for mid, pts in sorted(by_metric.items()):
            latest = pts[-1]
            lines.append(f"### {latest.get('metric_name', mid)}")
            lines.append(f"- 最新值: {latest.get('value_normalized', 'N/A')} ({latest.get('report_period', '')})")
            if latest.get("yoy") is not None:
                lines.append(f"- 同比: {latest['yoy']:.1%}")
            lines.append("")
            img = _make_trend_chart(pts, mid, assets_dir)
            if img:
                generated_files.append(str(img))
                lines.append(f"![{mid}趋势](assets/{img.name})")
                lines.append("")
            else:
                skipped_assets.append({
                    "type": "metric_trends",
                    "metric_id": mid,
                    "reason": "less than 2 trend points",
                })
    else:
        lines.append("无财务趋势数据")
        lines.append("")

    lines.append("## 5. 证据句摘要")
    lines.append("")
    if evidence:
        pos_ev = [e for e in evidence if e.get("polarity") == "positive"]
        neg_ev = [e for e in evidence if e.get("polarity") == "negative"]
        lines.append(f"- 正向证据: {len(pos_ev)} 条")
        lines.append(f"- 负向证据: {len(neg_ev)} 条")
        for e in pos_ev[:3]:
            lines.append(f"> {e.get('sentence', '')[:200]}")
            lines.append("")
    else:
        lines.append("无证据句数据")
        lines.append("")

    lines.append("## 6. 风险反证")
    lines.append("")
    risk = [c for c in sc if c.get("concept_id") == "risk_negative_evidence"]
    if risk:
        r = risk[0]
        lines.append(f"风险反证评分: {r['score']} ({r['level']}) — 分数越高代表风险越强")
    else:
        lines.append("无风险反证数据")
    lines.append("")

    lines.append("## 7. 需要人工复核")
    lines.append("")
    lines.append("- 所有概念评分结果需人工确认")
    lines.append("- 财务指标候选值需人工复核后进入正式数据")
    lines.append("- 证据句分类需人工验证")
    lines.append("")

    lines.append("## 8. 输入文件与生成资产")
    lines.append("")
    lines.append(f"- 概念库: `{concepts_file}`")
    lines.append(f"- 趋势文件: `{metric_trends_file}`")
    lines.append(f"- 时间序列: `{metric_series_file}`")
    lines.append(f"- 证据文件: `{evidence_file}`")
    lines.append(f"- 概念评分: `{concept_scores_file}`")
    for gf in generated_files:
        lines.append(f"- 生成: `{gf}`")
    lines.append("")

    lines.append("## 9. 免责声明")
    lines.append("")
    lines.append("本报告由自动化系统生成，不构成投资建议。")
    lines.append("")

    if has_manual:
        lines.append("## 10. 数据来源说明")
        lines.append("")
        lines.append("部分财务指标来自人工复核确认值 (source_type=manual_review)。")
        lines.append("自动抽取候选不等于最终财务值，所有数据使用前请人工确认。")
        lines.append("")

    md_content = "\n".join(lines)
    md_path = output_dir / "company_report.md"
    md_path.write_text(md_content, encoding="utf-8")
    generated_files.append(str(md_path))

    manifest_record = {
        "company_code": company_code,
        "generated_at": datetime.now().isoformat(),
        "generated_files": generated_files,
        "skipped_assets": skipped_assets,
        "warnings": warnings,
    }
    manifest_path = output_dir / "report_manifest.json"
    manifest_path.write_text(json.dumps(manifest_record, ensure_ascii=False, indent=2), encoding="utf-8")

    return md_content, generated_files, warnings


def _make_bar_chart(concepts: list[dict], assets_dir: Path) -> Path | None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        _configure_chart_font()

        if not concepts:
            return None

        names = [c.get("concept_name", c.get("concept_id", ""))[:6] for c in concepts]
        scores = [c.get("score", 0) for c in concepts]

        fig, ax = plt.subplots(figsize=(8, 3))
        colors = ["#2ca02c" if s >= 60 else "#ff7f0e" if s >= 40 else "#d62728" for s in scores]
        ax.bar(names, scores, color=colors)
        ax.set_ylim(0, 100)
        ax.set_ylabel("Score")
        ax.set_title("Concept Fit Scores")
        for i, (n, s) in enumerate(zip(names, scores)):
            ax.text(i, s + 1, str(s), ha="center", fontsize=8)

        path = assets_dir / "concept_scores_bar.png"
        fig.savefig(path, dpi=100, bbox_inches="tight")
        plt.close(fig)
        return path
    except Exception:
        return None


def _make_table_chart(concepts: list[dict], assets_dir: Path, generated_files: list[str]) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        _configure_chart_font()

        if not concepts:
            return

        fig, ax = plt.subplots(figsize=(10, len(concepts) * 0.4 + 0.5))
        ax.axis("off")
        headers = ["Concept", "Score", "Level", "+Hits", "-Hits"]
        rows = [[c.get("concept_name", c.get("concept_id", "")),
                 str(c.get("score", 0)), c.get("level", ""),
                 str(c.get("positive_hits", 0)), str(c.get("negative_hits", 0))]
                for c in concepts]
        table = ax.table(cellText=rows, colLabels=headers, cellLoc="center", loc="center")
        table.auto_set_font_size(False)
        table.set_fontsize(8)
        table.scale(1, 1.3)

        path = assets_dir / "concept_scores_table.png"
        fig.savefig(path, dpi=100, bbox_inches="tight")
        plt.close(fig)
        generated_files.append(str(path))
    except Exception:
        pass


def _make_metric_latest_table(trends: list[dict], assets_dir: Path, generated_files: list[str], skipped_assets: list[dict]) -> None:
    path = assets_dir / "metric_latest_table.png"
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        _configure_chart_font()

        fig, ax = plt.subplots(figsize=(8, 2))
        ax.axis("off")

        if not trends:
            ax.text(0.5, 0.5, "No metric trend data available", ha="center", va="center", fontsize=10)
            fig.savefig(path, dpi=100, bbox_inches="tight")
            plt.close(fig)
            generated_files.append(str(path))
            return

        by_metric = defaultdict(list)
        for t in trends:
            by_metric[t.get("metric_id", "?")].append(t)

        headers = ["Metric", "Latest Period", "Value", "YoY", "Growth"]
        rows = []
        for mid, pts in sorted(by_metric.items()):
            latest = pts[-1]
            rows.append([
                latest.get("metric_name", mid),
                latest.get("report_period", ""),
                f"{latest.get('value_normalized', 0):.1f}",
                f"{latest.get('yoy', 0):.1%}" if latest.get("yoy") is not None else "N/A",
                str(latest.get("consecutive_growth_count", 0)),
            ])

        table = ax.table(cellText=rows, colLabels=headers, cellLoc="center", loc="center")
        table.auto_set_font_size(False)
        table.set_fontsize(8)
        table.scale(1, 1.3)

        fig.savefig(path, dpi=100, bbox_inches="tight")
        plt.close(fig)
        generated_files.append(str(path))
    except Exception:
        skipped_assets.append({"type": "metric_latest_table", "reason": "chart generation failed"})


def _make_trend_chart(points: list[dict], metric_id: str, assets_dir: Path) -> Path | None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        _configure_chart_font()

        if len(points) < 2:
            return None

        labels = [p["report_period"] for p in points]
        values = [p["value_normalized"] for p in points]

        fig, ax = plt.subplots(figsize=(6, 2.5))
        ax.plot(labels, values, "o-", linewidth=1.5, markersize=4)
        ax.set_title(metric_id, fontsize=9)
        ax.tick_params(labelsize=7)
        fig.autofmt_xdate()

        path = assets_dir / f"metric_trends_{metric_id}.png"
        fig.savefig(path, dpi=100, bbox_inches="tight")
        plt.close(fig)
        return path
    except Exception:
        return None
