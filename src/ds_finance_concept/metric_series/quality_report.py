def write_metric_quality_report(
    candidates: list[dict],
    groups: list[dict],
    series: list[dict],
    output_file: str,
) -> None:
    import json
    from collections import Counter, defaultdict
    from datetime import datetime
    from pathlib import Path

    mc = candidates
    nr_total = sum(1 for c in mc if c.get("needs_review"))
    unit_unk = sum(1 for c in mc if c.get("value_unit_normalized") == "unknown")
    rp_unk = sum(1 for c in mc if c.get("report_period") == "unknown")

    by_metric = defaultdict(lambda: {"candidates": 0, "selected": set(), "review": 0})
    for c in mc:
        mid = c.get("metric_id", "?")
        by_metric[mid]["candidates"] += 1
        if c.get("needs_review"):
            by_metric[mid]["review"] += 1

    for s in series:
        mid = s.get("metric_id", "?")
        by_metric[mid]["selected"].add(s.get("report_period", "?"))

    sel_count = len(series)
    groups_selected = [g for g in groups if g.get("status") == "selected"]
    groups_review = [g for g in groups if g.get("status") != "selected"]

    reason_counter = Counter()
    for c in mc:
        for r in c.get("review_reasons", []):
            reason_counter[r] += 1

    lines = []
    lines.append("# 指标质量诊断报告")
    lines.append("")
    lines.append(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append("## 总览")
    lines.append("")
    lines.append(f"| 指标 | 数值 |")
    lines.append(f"| --- | --- |")
    lines.append(f"| candidates 总数 | {len(mc)} |")
    lines.append(f"| selected 总数 | {sel_count} |")
    lines.append(f"| review queue 总数 | {len(groups_review)} |")
    lines.append(f"| unit unknown | {unit_unk} |")
    lines.append(f"| report_period unknown | {rp_unk} |")
    lines.append("")

    lines.append("## 按 metric_id 统计")
    lines.append("")
    lines.append("| metric_id | candidates | selected 期数 | review |")
    lines.append("| --- | --- | --- | --- |")
    for mid in sorted(by_metric):
        bm = by_metric[mid]
        lines.append(f"| {mid} | {bm['candidates']} | {len(bm['selected'])} | {bm['review']} |")
    lines.append("")

    if groups_selected:
        lines.append("## Selected 值列表")
        lines.append("")
        lines.append("| metric_id | report_period | value_normalized | value_unit |")
        lines.append("| --- | --- | --- | --- |")
        for g in groups_selected:
            lines.append(f"| {g.get('metric_id','')} | {g.get('report_period','')} | {g.get('value_normalized',0)} | {g.get('value_unit_normalized','')} |")
        lines.append("")

    lines.append("## 被拒绝 selected 的主要原因 Top 10")
    lines.append("")
    for reason, count in reason_counter.most_common(10):
        lines.append(f"- {reason}: {count}")
    lines.append("")

    cs = sum(1 for mid in ["revenue","net_profit_attributable","operating_cashflow"] if len(by_metric.get(mid,{}).get("selected",set())) >= 3)
    lines.append("## 数据充分性评估")
    lines.append("")
    if cs < 3:
        lines.append(f"**核心指标 3 年数据覆盖率不足 ({cs}/3)**，概念评分不可信。")
    else:
        lines.append(f"核心指标覆盖率 {cs}/3，财务数据可支撑评分。")
    lines.append("")

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    
    lines.append("## Near Selected Candidates")
    lines.append("")
    for mid in ["net_profit_attributable", "operating_cashflow", "inventory", "fixed_assets", "contract_liabilities"]:
        lines.append(f"### {mid}")
        lines.append("")
        mid_cands = [c for c in candidates if c.get("metric_id") == mid and c.get("confidence") in ("high", "medium")]
        for c in mid_cands[:5]:
            reasons = "; ".join(c.get("review_reasons", [])[:3])
            lines.append(f"- **{c.get('report_period','?')}** p.{c.get('page_number','?')}: {c.get('raw_value','?')} "
                        f"→ {c.get('value_normalized',0)} {c.get('value_unit_normalized','?')}")
            lines.append(f"  reasons: {reasons}")
            lines.append(f"  > {c.get('source_snippet','')[:120]}")
            lines.append("")
        if not mid_cands:
            lines.append("无 high/medium 候选")
        lines.append("")
    
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    Path(output_file).write_text("\n".join(lines), encoding="utf-8")
