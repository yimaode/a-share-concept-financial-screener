"""公司分析主管线（改造后）。

数据分工：
- 标准财务指标：只来自 akshare（网络），作为唯一真相源。
- PDF：只做文本抽取 → 证据句抽取，不再抽取任何数字指标。

流程：
  download(可选) → extract-pdf-text → fetch-web-metrics(akshare 序列)
  → compute-metric-trends → extract-evidence → score-concepts
  → build-deliverables(三份交付物)
"""

import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path


def _count_jsonl(path: Path) -> int:
    path = Path(path)
    if not path.exists():
        return 0
    n = 0
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                n += 1
    return n


def _guard_metrics(series_file: Path) -> int:
    """硬守卫：akshare 无任何指标数据时判失败，杜绝空壳成功。"""
    n = _count_jsonl(series_file)
    if n == 0:
        print(
            "GUARD FAILED: akshare 未返回任何标准财务指标"
            "（可能是代码错误、停牌/退市、或接口异常）。终止管线以避免产出空壳结果。",
            file=sys.stderr,
        )
        return 1
    print(f"GUARD: akshare 指标点 = {n} — OK")
    return 0


def _guard_evidence(evidence_file: Path) -> int:
    """软守卫：证据句为空只提醒不失败（可能是扫描件 PDF 或无关键词命中）。"""
    n = _count_jsonl(evidence_file)
    if n == 0:
        print(
            "GUARD WARNING: 未抽到任何证据句"
            "（可能是扫描件 PDF 或无关键词命中）。继续执行，但打分的证据维度将为空。",
            file=sys.stderr,
        )
    else:
        print(f"GUARD: 证据句 = {n} — OK")
    return 0


def _guard_pdf_extraction(manifest_file: Path) -> int:
    """Require at least one fully/partly readable PDF and reject empty inputs."""
    path = Path(manifest_file)
    if not path.exists():
        print("GUARD FAILED: PDF extraction manifest is missing", file=sys.stderr)
        return 1
    try:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, ValueError) as exc:
        print(f"GUARD FAILED: invalid PDF extraction manifest: {exc}", file=sys.stderr)
        return 1
    usable = [r for r in rows if r.get("text_page_count", 0) > 0 and r.get("extract_status") in {"success", "partial"}]
    if not rows or not usable:
        print("GUARD FAILED: no readable financial-report PDF", file=sys.stderr)
        return 1
    failed = sum(r.get("extract_status") == "failed" for r in rows)
    print(f"GUARD: readable PDFs = {len(usable)}/{len(rows)}, failed = {failed} — OK")
    return 0


def _guard_pdf_period_alignment(pdf_dir: Path, as_of_period: str | None) -> int:
    """历史运行要求 PDF 至少包含与数字截止期完全一致的一份报告。"""
    if not as_of_period:
        return 0
    mapping = {"Q1": "第一季度报告", "H1": "半年度报告", "Q3": "第三季度报告", "A": "年度报告"}
    expected = f"{as_of_period[:4]}_{mapping[as_of_period[4:]]}"
    names = [p.stem for p in Path(pdf_dir).glob("*.pdf")]
    if any(expected in name for name in names):
        print(f"GUARD: PDF coverage includes {as_of_period} — OK")
        return 0
    print(f"GUARD FAILED: PDF directory does not include a report for {as_of_period}", file=sys.stderr)
    return 1


def _run_stage(name: str, func) -> dict:
    started = datetime.now().isoformat()
    try:
        rc = func()
        if rc != 0:
            return {
                "stage": name, "status": "failed",
                "started_at": started, "finished_at": datetime.now().isoformat(),
                "error_message": "Non-zero exit",
            }
        return {
            "stage": name, "status": "success",
            "started_at": started, "finished_at": datetime.now().isoformat(),
            "error_message": "",
        }
    except Exception as e:
        return {
            "stage": name, "status": "failed",
            "started_at": started, "finished_at": datetime.now().isoformat(),
            "error_message": str(e),
        }


def run_company_pipeline(company_code, pdf_dir, concepts_file, output_dir, max_reports=12,
                         as_of_period=None):
    output_dir = Path(output_dir)
    pe = output_dir / "pdf_extract"
    se = output_dir / "series"
    tr = output_dir / "metric_trends"
    ev = output_dir / "evidence"
    sc = output_dir / "concept_scores"
    mk = output_dir / "market_features"
    dl = output_dir / "deliverables"

    import importlib
    cli = importlib.import_module("ds_finance_concept.cli")

    series_file = se / "metric_series.jsonl"
    pages_file = pe / "pages.jsonl"
    manifest_file = pe / "pdf_manifest.jsonl"
    trends_file = tr / "metric_trends.jsonl"
    evidence_file = ev / "evidence_hits.jsonl"
    scores_file = sc / "concept_scores.json"
    market_file = mk / "market_features.json"
    canslim_file = sc / "canslim_assessment.json"

    stages = []
    if pdf_dir is None:
        pdf_dir = output_dir / "raw_pdfs"
        stages.append(("download-financial-reports", lambda: cli.main([
            "download-financial-reports", "--company-code", company_code,
            "--output-dir", str(pdf_dir), "--max-reports", str(max_reports),
        ])))
    else:
        pdf_dir = Path(pdf_dir)

    stages.extend([
        ("guard-pdf-period", lambda: _guard_pdf_period_alignment(pdf_dir, as_of_period)),
        ("extract-pdf-text", lambda: cli.main([
            "extract-pdf-text", "--pdf-dir", str(pdf_dir), "--output-dir", str(pe),
        ])),
        ("guard-pdf-extraction", lambda: _guard_pdf_extraction(manifest_file)),
        ("fetch-web-metrics", lambda: cli.main(
            ["fetch-web-metrics", "--company-code", company_code,
             "--concepts-file", str(concepts_file), "--output-file", str(series_file)]
            + (["--as-of-period", as_of_period] if as_of_period else [])
        )),
        ("guard-metrics", lambda: _guard_metrics(series_file)),
        ("compute-metric-trends", lambda: cli.main([
            "compute-metric-trends", "--series-file", str(series_file), "--output-dir", str(tr),
        ])),
        ("fetch-market-features", lambda: cli.main(
            ["fetch-market-features", "--company-code", company_code,
             "--output-file", str(market_file)]
            + (["--as-of-period", as_of_period] if as_of_period else [])
        )),
        ("extract-evidence", lambda: cli.main([
            "extract-evidence", "--concepts-file", str(concepts_file),
            "--pages-file", str(pages_file), "--manifest-file", str(manifest_file),
            "--output-dir", str(ev),
        ])),
        ("guard-evidence", lambda: _guard_evidence(evidence_file)),
        ("score-concepts", lambda: cli.main([
            "score-concepts", "--concepts-file", str(concepts_file),
            "--metric-trends-file", str(trends_file), "--evidence-file", str(evidence_file),
            "--output-dir", str(sc),
        ])),
        ("evaluate-canslim", lambda: cli.main([
            "evaluate-canslim", "--trends-file", str(trends_file),
            "--concept-scores-file", str(scores_file), "--market-features-file", str(market_file),
            "--output-file", str(canslim_file),
        ])),
        ("build-deliverables", lambda: cli.main([
            "build-deliverables", "--company-code", company_code,
            "--concepts-file", str(concepts_file), "--series-file", str(series_file),
            "--metric-trends-file", str(trends_file), "--evidence-file", str(evidence_file),
            "--evidence-stats-file", str(ev / "concept_keyword_stats.json"),
            "--concept-scores-file", str(scores_file),
            "--score-details-file", str(sc / "concept_score_details.jsonl"),
            "--canslim-file", str(canslim_file),
            "--output-dir", str(dl),
        ])),
    ])

    results = []
    for name, func in stages:
        s = _run_stage(name, func)
        results.append(s)
        if s["status"] == "failed":
            break

    manifest = {
        "company_code": company_code,
        "as_of_period": as_of_period or "latest_available",
        "pipeline_run_at": datetime.now().isoformat(),
        "stages": results,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "pipeline_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if all(s["status"] == "success" for s in results) else 1


def _read_company_codes(companies_file: Path) -> list[str]:
    """读取含 company_code/code/stock_code 列的 UTF-8 CSV，去重并保留顺序。"""
    path = Path(companies_file)
    if not path.exists():
        raise ValueError(f"Companies CSV not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("Companies CSV must have a header row")
        key = next((k for k in ("company_code", "code", "stock_code") if k in reader.fieldnames), None)
        if key is None:
            raise ValueError("Companies CSV must contain company_code, code, or stock_code")
        codes: list[str] = []
        for row_num, row in enumerate(reader, 2):
            raw = (row.get(key) or "").strip()
            if not re.fullmatch(r"\d{6}", raw):
                raise ValueError(f"Invalid company code at CSV row {row_num}: {raw!r}")
            if raw not in codes:
                codes.append(raw)
    if not codes:
        raise ValueError("Companies CSV contains no company codes")
    return codes


def _company_pipeline_succeeded(company_dir: Path) -> bool:
    manifest = company_dir / "pipeline_manifest.json"
    if not manifest.exists():
        return False
    try:
        stages = json.loads(manifest.read_text(encoding="utf-8")).get("stages", [])
    except (OSError, ValueError):
        return False
    return bool(stages) and all(s.get("status") == "success" for s in stages)


def run_batch_pipeline(companies_file, concepts_file, output_dir, max_reports=12,
                       as_of_period=None, resume=False):
    """逐公司运行新主管线，并写出可审计的批量清单。

    每家公司拥有独立的 raw_pdfs / deliverables 目录；单家公司失败不会遮蔽其他公司的
    结果，但批量命令最终会返回非零，提醒操作者处理失败项。
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    codes = _read_company_codes(Path(companies_file))
    progress_file = output_dir / "batch_progress.jsonl"
    rows: list[dict] = []
    for code in codes:
        company_dir = output_dir / code
        skipped = resume and _company_pipeline_succeeded(company_dir)
        rc = 0 if skipped else run_company_pipeline(
            code, None, concepts_file, company_dir, max_reports=max_reports,
            as_of_period=as_of_period,
        )
        row = {
            "company_code": code,
            "status": "skipped_success" if skipped else ("success" if rc == 0 else "failed"),
            "output_dir": str(company_dir),
            "pipeline_manifest": str(company_dir / "pipeline_manifest.json"),
        }
        rows.append(row)
        with progress_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"updated_at": datetime.now().isoformat(), **row}, ensure_ascii=False) + "\n")

    with (output_dir / "batch_manifest.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["company_code", "status", "output_dir", "pipeline_manifest"])
        writer.writeheader()
        writer.writerows(rows)
    (output_dir / "batch_manifest.json").write_text(json.dumps({
        "company_count": len(rows),
        "success_count": sum(r["status"] in {"success", "skipped_success"} for r in rows),
        "failed_count": sum(r["status"] == "failed" for r in rows),
        "as_of_period": as_of_period or "latest_available",
        "companies": rows,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if all(r["status"] in {"success", "skipped_success"} for r in rows) else 1
