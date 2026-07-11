import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook

CORE_METRICS = ["revenue","net_profit_attributable","deducted_net_profit","operating_cashflow",
    "gross_margin","total_assets","inventory","contract_liabilities","fixed_assets",
    "construction_in_progress","rd_expense"]

TEMPLATE_HEADER = ["company_code","metric_id","report_period","value","unit","source_pdf",
    "page_number","source_type","source_table_id","source_row_index","source_column_index",
    "evidence_text","reviewer","review_status","review_note"]

VALID_UNITS = {"CNY","yuan","元","万元","亿元","%","percent"}
VALID_PERIOD = re.compile(r'^\d{4}(Q[1-4]|H[1-2]|A)$')
VALID_STATUS = {"approved","rejected","pending"}


def prepare_metric_review_pack(company_code, candidates_file, tables_file, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cands = _read_jsonl(candidates_file)
    tables = _read_jsonl(tables_file) if tables_file and Path(tables_file).exists() else []

    wb = Workbook()
    _write_sheet(wb, "README", ["公司代码","说明"], [[company_code,"财务指标人工复核包-不构成投资建议"]])

    core_summary = defaultdict(lambda: {"candidates":0,"selected":0,"review":0,"periods":set()})
    for c in cands:
        mid = c.get("metric_id","")
        if mid in CORE_METRICS:
            core_summary[mid]["candidates"] += 1
            core_summary[mid]["periods"].add(c.get("report_period",""))
            if c.get("needs_review"): core_summary[mid]["review"] += 1
    _write_sheet(wb, "Core Metric Summary", ["metric_id","candidates","periods","needs_review"],
        [[m,core_summary[m]["candidates"],len(core_summary[m]["periods"]),core_summary[m]["review"]] for m in CORE_METRICS])

    near = [c for c in cands if c.get("confidence") in ("high","medium") and c.get("metric_id") in CORE_METRICS
            and c.get("value_unit_normalized") != "unknown" and c.get("report_period") != "unknown"][:100]
    _write_sheet(wb, "Near Selected", ["metric_id","report_period","value_normalized","unit","confidence","needs_review","source_pdf","page_number","review_reasons"],
        [[c.get(k,"") for k in ["metric_id","report_period","value_normalized","value_unit_normalized","confidence","needs_review","source_pdf","page_number"]] + ["; ".join(c.get("review_reasons",[]))] for c in near])

    tc = [c for c in cands if c.get("section_type")][:200]
    _write_sheet(wb, "Table Candidates", ["metric_id","report_period","value_normalized","unit","section_type","column_role","confidence","source_pdf","page_number"],
        [[c.get(k,"") for k in ["metric_id","report_period","value_normalized","value_unit_normalized","section_type","column_role","confidence","source_pdf","page_number"]] for c in tc])

    hc = [c for c in cands if c.get("section_type") and c.get("confidence") in ("high","medium")
          and c.get("value_unit_normalized") != "unknown" and c.get("report_period") != "unknown"][:100]
    _write_sheet(wb, "High Confidence", ["metric_id","report_period","value_normalized","unit","section_type","column_role","source_pdf","page_number"],
        [[c.get(k,"") for k in ["metric_id","report_period","value_normalized","value_unit_normalized","section_type","column_role","source_pdf","page_number"]] for c in hc])

    template_rows = []
    best = _pick_best_candidates(cands)
    for (mid, period), c in sorted(best.items()):
        template_rows.append([company_code, mid, period,
            c.get("value_normalized",""), c.get("value_unit_normalized",""),
            c.get("source_pdf",""), c.get("page_number",""),
            "table" if c.get("section_type") else "text", "","","",
            (c.get("source_snippet","") or "")[:200],
            "", "pending", ""])
    _write_sheet(wb, "Manual Values Template", TEMPLATE_HEADER, template_rows)
    _write_sheet(wb, "Warnings", ["message"], [
        "模板已自动填入每个metric+period的最优候选，请确认后改review_status为approved",
        "不确认的行请删除或保持pending，自动候选不等于最终财务值",
    ])

    wb.save(str(output_dir / "metric_review_pack.xlsx"))

    tmp_file = output_dir / "manual_metric_values.template.csv"
    with tmp_file.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(TEMPLATE_HEADER)
        for r in template_rows:
            w.writerow(r)

    report = f"""# 人工复核报告
公司: {company_code}
生成时间: {datetime.now().isoformat()}
候选总数: {len(cands)}
核心指标候选: {sum(core_summary[m]['candidates'] for m in CORE_METRICS)}
Near Selected: {len(near)}
Table Candidates: {len(tc)}
HC Candidates: {len(hc)}
模板行数: {len(template_rows)}
"""
    (output_dir / "manual_review_report.md").write_text(report, encoding="utf-8")


def _read_jsonl(path):
    if not Path(path).exists(): return []
    recs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                recs.append(json.loads(line))
    return recs


def _write_sheet(wb, name, headers, rows):
    ws = wb.create_sheet(title=name[:31])
    ws.append(headers)
    for r in rows:
        ws.append([str(v) for v in r])
    ws.freeze_panes = "A2"


def _pick_best_candidates(candidates: list) -> dict:
    CONF_ORDER = {"high": 0, "medium": 1, "low": 2}

    groups = defaultdict(list)
    for c in candidates:
        mid = c.get("metric_id", "")
        period = c.get("report_period", "")
        if mid in CORE_METRICS and period and period != "unknown":
            groups[(mid, period)].append(c)

    best = {}
    for key, items in groups.items():
        mid, period = key

        items = [c for c in items if c.get("value_unit_normalized") not in ("unknown", "", None)]
        if not items:
            continue

        if mid in {"revenue","deducted_net_profit","operating_cashflow",
                    "total_assets","inventory","contract_liabilities","fixed_assets","construction_in_progress"}:
            items = [c for c in items if c.get("value_unit_normalized") == "CNY" and abs(c.get("value_normalized") or 0) > 1e6]
        if mid == "net_profit_attributable":
            items = [c for c in items if c.get("value_unit_normalized") == "CNY" and abs(c.get("value_normalized") or 0) > 1e8
                     and abs(c.get("value_normalized") or 0) < 2e10
                     and "实现营业收入" not in (c.get("source_snippet") or "")]
            if not items:
                continue
        if mid == "gross_margin":
            items = [c for c in items if c.get("is_percent") or c.get("value_unit_raw") == "%"]
        if mid == "rd_expense":
            items = [c for c in items if not c.get("is_percent")]

        if not items:
            continue

        items.sort(key=lambda c: (
            CONF_ORDER.get(c.get("confidence", "low"), 2),
            0 if c.get("section_type") else 1,
            -abs(c.get("value_normalized") or 0),
        ))
        best[key] = items[0]
    return best


def import_manual_metric_values(manual_file, output_file, output_report):
    errors = []
    approved = []
    rejected = []
    seen = {}

    with open(manual_file, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, 2):
            cc = row.get("company_code","").strip()
            mid = row.get("metric_id","").strip()
            period = row.get("report_period","").strip()
            val_str = row.get("value","").strip()
            unit = row.get("unit","").strip()
            pdf = row.get("source_pdf","").strip()
            pg = row.get("page_number","").strip()
            ev = row.get("evidence_text","").strip()
            status = row.get("review_status","").strip()

            errs = []
            if not cc: errs.append("empty company_code")
            if mid not in CORE_METRICS: errs.append(f"invalid metric_id: {mid}")
            if not VALID_PERIOD.match(period): errs.append(f"invalid period: {period}")
            try: val = float(val_str)
            except (ValueError, TypeError): errs.append(f"non-numeric value: {val_str}")
            if unit and unit not in VALID_UNITS: errs.append(f"invalid unit: {unit}")
            if not pdf: errs.append("empty source_pdf")
            try: pgn = int(pg)
            except (ValueError, TypeError): errs.append(f"invalid page_number: {pg}")
            if not ev: errs.append("empty evidence_text")
            if status not in VALID_STATUS: errs.append(f"invalid status: {status}")

            if errs:
                for e in errs: errors.append(f"Row {i}: {e}")
                continue

            if status == "rejected":
                rejected.append(row)
                continue
            if status == "pending":
                continue

            norm_val = val
            norm_unit = "CNY"
            is_pct = False
            if unit == "万元": norm_val = val * 10000
            elif unit == "亿元": norm_val = val * 100000000
            elif unit in ("元","yuan"): norm_val = val
            elif unit in ("%","percent"): norm_unit = "percent"; is_pct = True; norm_val = val

            key = (cc, mid, period, norm_val, norm_unit)
            if key in seen:
                existing = seen[key]
                snip = row.get("evidence_text","")[:50]
                if existing.get("evidence_text","")[:50] != snip:
                    errors.append(f"Row {i}: conflicting duplicate for {mid}/{period}")
                continue

            seen[key] = {"evidence_text": row.get("evidence_text","")[:50]}
            approved.append({
                "series_id": f"ms_manual_{mid}_{period}",
                "metric_id": mid, "metric_name": mid, "report_period": period,
                "period_year": int(period[:4]) if period[:4].isdigit() else 0,
                "period_type": period[4:] if len(period)>4 else "",
                "period_order": {"Q1":1,"H1":2,"Q3":3,"A":4}.get(period[4:],0) if len(period)>4 else 0,
                "value_normalized": norm_val, "value_unit_normalized": norm_unit,
                "is_percent": is_pct, "source_candidate_id": "manual",
                "source_pdf": pdf, "page_number": pgn,
                "selection_method": "manual_review", "source_snippet": ev[:200],
            })

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        for a in approved:
            json.dump(a, f, ensure_ascii=False); f.write("\n")

    rpt = f"# Manual Import Report\nApproved: {len(approved)}\nRejected: {len(rejected)}\nErrors: {len(errors)}\n"
    if errors:
        rpt += "\n## Errors\n" + "\n".join(f"- {e}" for e in errors[:20])
    Path(output_report).write_text(rpt, encoding="utf-8")
    return len(approved), len(rejected), len(errors)
