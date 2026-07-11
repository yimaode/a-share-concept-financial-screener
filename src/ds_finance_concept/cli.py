import argparse
import json
import sys
from pathlib import Path

from .concept_builder.concept_candidate_builder import build_concept_candidates
from .concept_builder.concept_candidate_writer import (
    write_concept_candidates_json,
    write_concept_candidates_review_md,
)
from .concept_builder.concept_draft_builder import build_draft_concepts
from .concept_builder.concept_draft_writer import (
    write_concept_review_md,
    write_concepts_draft_json,
    write_concepts_draft_yaml,
)
from .concept_builder.concept_freezer import ConceptFreezeError, run_freeze_concepts
from .concept_builder.concept_validator import ConceptValidationError, run_validate_concepts
from .concept_builder.errors import InputPathError, QuoteReaderError
from .evidence_extractor.errors import ConceptsNotFrozenError, EvidenceExtractorError
from .evidence_extractor.extractor import extract_evidence
from .evidence_extractor.writer import (
    write_concept_keyword_stats,
    write_evidence_csv,
    write_evidence_jsonl,
    write_evidence_report,
)
from .metric_extractor.errors import MetricExtractorError
from .metric_extractor.extractor import extract_metric_candidates
from .metric_extractor.writer import (
    write_metric_candidates_csv,
    write_metric_candidates_jsonl,
    write_metric_extraction_report,
    write_metric_stats_json,
    write_high_confidence_table_csv,
)
from .metric_series.builder import build_metric_series
from .metric_series.errors import MetricSeriesError
from .metric_series.writer import (
    write_metric_groups_jsonl,
    write_metric_series_jsonl,
    write_review_queue_csv,
    write_series_long_csv,
    write_series_report,
    write_series_wide_csv,
)
from .concept_scores.scorer import score_concepts
from .concept_scores.errors import ConceptScoreError
from .concept_scores.writer import (
    write_details_jsonl,
    write_score_report,
    write_scores_csv,
    write_scores_json,
)
from .reporting.report_builder import build_company_report
from .reporting.excel_exporter import export_excel
from .reporting.pipeline import run_batch_pipeline, run_company_pipeline
from .reporting.deliverables import build_deliverables
from .reporting.validator import validate_final_output
from .table_extractor.table_extractor import extract_pdf_tables
from .manual_review.review_pack import prepare_metric_review_pack, import_manual_metric_values
from .data_fetcher.web_api import fetch_web_metrics
from .data_fetcher.market_api import fetch_market_features
from .canslim.evaluator import evaluate_canslim, read_jsonl
from .data_fetcher.report_downloader import ReportDownloadError, download_financial_reports
from .metric_trends.builder import compute_trends
from .metric_trends.errors import MetricTrendsError
from .metric_trends.writer import (
    write_trend_report,
    write_trend_summary,
    write_trends_jsonl,
    write_trends_long_csv,
    write_trends_wide_csv,
)
from .pdf_extractor.errors import PdfExtractorError
from .pdf_extractor.extractor import extract_pdf_directory


def _build_metric_report_stats(candidates) -> dict:
    from collections import defaultdict

    stats: dict = {"metrics": {}}
    for c in candidates:
        mid = c.metric_id
        if mid not in stats["metrics"]:
            stats["metrics"][mid] = {
                "candidate_count": 0,
                "high_confidence_count": 0,
                "needs_review_count": 0,
                "periods": set(),
            }
        ms = stats["metrics"][mid]
        ms["candidate_count"] += 1
        if c.confidence == "high":
            ms["high_confidence_count"] += 1
        if c.needs_review:
            ms["needs_review_count"] += 1
        ms["periods"].add(c.report_period)
    for mid in stats["metrics"]:
        stats["metrics"][mid]["periods"] = sorted(stats["metrics"][mid]["periods"])
    return stats
from .pdf_extractor.writer import (
    write_extraction_report,
    write_full_text,
    write_manifest_jsonl,
    write_pages_jsonl,
)
from .concept_builder.insight_extractor import extract_insights_from_quotes
from .concept_builder.insight_writer import write_insight_cards_jsonl
from .concept_builder.jsonl_writer import write_quote_cards_jsonl
from .concept_builder.markdown_parser import parse_markdown_dir
from .concept_builder.quote_reader import read_quote_cards_jsonl
from .concept_builder.workflow import prepare_concept_workspace


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="concept-screener")
    subparsers = parser.add_subparsers(dest="command")

    build_parser = subparsers.add_parser("build-quotes")
    build_parser.add_argument("--input-dir", required=True, type=Path)
    build_parser.add_argument("--output-file", required=True, type=Path)

    prepare_parser = subparsers.add_parser(
        "prepare-concepts",
        help="Stage 1: private Markdown notes -> reviewable concept draft workspace",
    )
    prepare_parser.add_argument("--input-dir", required=True, type=Path)
    prepare_parser.add_argument("--workspace-dir", required=True, type=Path)

    insight_parser = subparsers.add_parser("build-insights")
    insight_parser.add_argument("--quote-file", required=True, type=Path)
    insight_parser.add_argument("--output-file", required=True, type=Path)

    concept_parser = subparsers.add_parser("build-concept-candidates")
    concept_parser.add_argument("--insight-file", required=True, type=Path)
    concept_parser.add_argument("--output-json", required=True, type=Path)
    concept_parser.add_argument("--output-review", required=True, type=Path)

    draft_parser = subparsers.add_parser("build-concepts-draft")
    draft_parser.add_argument("--candidates-file", required=True, type=Path)
    draft_parser.add_argument("--output-yaml", required=True, type=Path)
    draft_parser.add_argument("--output-json", type=Path, default=None)
    draft_parser.add_argument("--output-review", required=True, type=Path)

    validate_parser = subparsers.add_parser("validate-concepts")
    validate_parser.add_argument("--concepts-json", required=True, type=Path)
    validate_parser.add_argument("--output-report", required=True, type=Path)

    freeze_parser = subparsers.add_parser("freeze-concepts")
    freeze_parser.add_argument("--concepts-json", required=True, type=Path)
    freeze_parser.add_argument("--output-json", required=True, type=Path)
    freeze_parser.add_argument("--output-yaml", required=True, type=Path)

    pdf_parser = subparsers.add_parser("extract-pdf-text")
    pdf_parser.add_argument("--pdf-dir", required=True, type=Path)
    pdf_parser.add_argument("--output-dir", required=True, type=Path)

    evidence_parser = subparsers.add_parser("extract-evidence")
    evidence_parser.add_argument("--concepts-file", required=True, type=Path)
    evidence_parser.add_argument("--pages-file", required=True, type=Path)
    evidence_parser.add_argument("--manifest-file", required=True, type=Path)
    evidence_parser.add_argument("--output-dir", required=True, type=Path)

    metric_parser = subparsers.add_parser("extract-metric-candidates")
    metric_parser.add_argument("--pages-file", required=True, type=Path)
    metric_parser.add_argument("--manifest-file", required=True, type=Path)
    metric_parser.add_argument("--concepts-file", required=True, type=Path)
    metric_parser.add_argument("--tables-file", type=Path, default=None)
    metric_parser.add_argument("--output-dir", required=True, type=Path)

    tables_parser = subparsers.add_parser("extract-pdf-tables")
    tables_parser.add_argument("--pdf-dir", required=True, type=Path)
    tables_parser.add_argument("--output-dir", required=True, type=Path)

    review_parser = subparsers.add_parser("prepare-metric-review-pack")
    review_parser.add_argument("--company-code", required=True)
    review_parser.add_argument("--metric-candidates-file", required=True, type=Path)
    review_parser.add_argument("--tables-file", required=True, type=Path)
    review_parser.add_argument("--output-dir", required=True, type=Path)

    import_parser = subparsers.add_parser("import-manual-metric-values")
    import_parser.add_argument("--manual-values-file", required=True, type=Path)
    import_parser.add_argument("--output-file", required=True, type=Path)
    import_parser.add_argument("--output-report", required=True, type=Path)

    web_parser = subparsers.add_parser("fetch-web-metrics")
    web_parser.add_argument("--company-code", required=True)
    web_parser.add_argument("--concepts-file", required=True, type=Path)
    web_parser.add_argument("--output-file", required=True, type=Path)
    web_parser.add_argument("--as-of-period", default=None,
                            help="Optional cutoff: YYYYQ1, YYYYH1, YYYYQ3, or YYYYA")

    download_parser = subparsers.add_parser("download-financial-reports")
    download_parser.add_argument("--company-code", required=True)
    download_parser.add_argument("--output-dir", required=True, type=Path)
    download_parser.add_argument("--max-reports", type=int, default=12)

    series_parser = subparsers.add_parser("build-metric-series")
    series_parser.add_argument("--candidates-file", required=True, type=Path)
    series_parser.add_argument("--review-decisions", type=Path, default=None)
    series_parser.add_argument("--manual-series-file", type=Path, default=None)
    series_parser.add_argument("--output-dir", required=True, type=Path)

    trends_parser = subparsers.add_parser("compute-metric-trends")
    trends_parser.add_argument("--series-file", required=True, type=Path)
    trends_parser.add_argument("--output-dir", required=True, type=Path)

    score_parser = subparsers.add_parser("score-concepts")
    score_parser.add_argument("--concepts-file", required=True, type=Path)
    score_parser.add_argument("--metric-trends-file", required=True, type=Path)
    score_parser.add_argument("--evidence-file", required=True, type=Path)
    score_parser.add_argument("--output-dir", required=True, type=Path)

    pipeline_parser = subparsers.add_parser("run-company-pipeline")
    pipeline_parser.add_argument("--company-code", required=True)
    pipeline_parser.add_argument("--pdf-dir", type=Path, default=None,
                                 help="Existing PDF directory; omit to download reports automatically")
    pipeline_parser.add_argument("--concepts-file", required=True, type=Path)
    pipeline_parser.add_argument("--output-dir", required=True, type=Path)
    pipeline_parser.add_argument("--max-reports", type=int, default=12)
    pipeline_parser.add_argument("--as-of-period", default=None,
                                 help="Optional financial-data cutoff: YYYYQ1, YYYYH1, YYYYQ3, or YYYYA")

    screen_parser = subparsers.add_parser(
        "screen-company",
        help="Stage 2: screen one A-share company with a frozen concept library",
    )
    screen_parser.add_argument("--company-code", required=True)
    screen_parser.add_argument("--pdf-dir", type=Path, default=None)
    screen_parser.add_argument("--concepts-file", required=True, type=Path)
    screen_parser.add_argument("--output-dir", required=True, type=Path)
    screen_parser.add_argument("--max-reports", type=int, default=12)
    screen_parser.add_argument("--as-of-period", default=None)

    batch_pipeline_parser = subparsers.add_parser("run-batch-pipeline")
    batch_pipeline_parser.add_argument("--companies-file", required=True, type=Path,
                                       help="UTF-8 CSV with company_code/code/stock_code column")
    batch_pipeline_parser.add_argument("--concepts-file", required=True, type=Path)
    batch_pipeline_parser.add_argument("--output-dir", required=True, type=Path)
    batch_pipeline_parser.add_argument("--max-reports", type=int, default=12)
    batch_pipeline_parser.add_argument("--as-of-period", default=None,
                                       help="Optional financial-data cutoff: YYYYQ1, YYYYH1, YYYYQ3, or YYYYA")
    batch_pipeline_parser.add_argument("--resume", action="store_true",
                                       help="Skip companies with an already successful pipeline manifest")

    screen_batch_parser = subparsers.add_parser(
        "screen-batch",
        help="Stage 2: screen an A-share CSV with a frozen concept library",
    )
    screen_batch_parser.add_argument("--companies-file", required=True, type=Path)
    screen_batch_parser.add_argument("--concepts-file", required=True, type=Path)
    screen_batch_parser.add_argument("--output-dir", required=True, type=Path)
    screen_batch_parser.add_argument("--max-reports", type=int, default=12)
    screen_batch_parser.add_argument("--as-of-period", default=None)
    screen_batch_parser.add_argument("--resume", action="store_true")

    market_parser = subparsers.add_parser("fetch-market-features")
    market_parser.add_argument("--company-code", required=True)
    market_parser.add_argument("--output-file", required=True, type=Path)
    market_parser.add_argument("--as-of-period", default=None)

    canslim_parser = subparsers.add_parser("evaluate-canslim")
    canslim_parser.add_argument("--trends-file", required=True, type=Path)
    canslim_parser.add_argument("--concept-scores-file", required=True, type=Path)
    canslim_parser.add_argument("--market-features-file", required=True, type=Path)
    canslim_parser.add_argument("--output-file", required=True, type=Path)

    report_parser = subparsers.add_parser("build-company-report")
    report_parser.add_argument("--company-code", required=True)
    report_parser.add_argument("--concepts-file", required=True, type=Path)
    report_parser.add_argument("--metric-trends-file", required=True, type=Path)
    report_parser.add_argument("--metric-series-file", required=True, type=Path)
    report_parser.add_argument("--evidence-file", required=True, type=Path)
    report_parser.add_argument("--concept-scores-file", required=True, type=Path)
    report_parser.add_argument("--output-dir", required=True, type=Path)

    excel_parser = subparsers.add_parser("export-excel")
    excel_parser.add_argument("--company-code", required=True)
    excel_parser.add_argument("--metric-candidates-file", required=True, type=Path)
    excel_parser.add_argument("--metric-series-file", required=True, type=Path)
    excel_parser.add_argument("--metric-trends-file", required=True, type=Path)
    excel_parser.add_argument("--evidence-file", required=True, type=Path)
    excel_parser.add_argument("--concept-scores-file", required=True, type=Path)
    excel_parser.add_argument("--output-file", required=True, type=Path)

    validate_parser = subparsers.add_parser("validate-final-output")
    validate_parser.add_argument("--company-code", required=True)
    validate_parser.add_argument("--output-dir", required=True, type=Path)
    validate_parser.add_argument("--report-file", required=True, type=Path)

    deliver_parser = subparsers.add_parser("build-deliverables")
    deliver_parser.add_argument("--company-code", required=True)
    deliver_parser.add_argument("--concepts-file", required=True, type=Path)
    deliver_parser.add_argument("--series-file", required=True, type=Path)
    deliver_parser.add_argument("--metric-trends-file", required=True, type=Path)
    deliver_parser.add_argument("--evidence-file", required=True, type=Path)
    deliver_parser.add_argument("--evidence-stats-file", required=True, type=Path)
    deliver_parser.add_argument("--concept-scores-file", required=True, type=Path)
    deliver_parser.add_argument("--score-details-file", required=True, type=Path)
    deliver_parser.add_argument("--canslim-file", required=True, type=Path)
    deliver_parser.add_argument("--output-dir", required=True, type=Path)

    args = parser.parse_args(argv)

    if args.command == "prepare-concepts":
        try:
            counts = prepare_concept_workspace(args.input_dir, args.workspace_dir)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        print("Stage 1 concept workspace prepared (not frozen)")
        print(f"Counts: {counts}")
        print(f"Review: {args.workspace_dir / '04_concepts_review.md'}")
        return 0

    if args.command == "build-quotes":
        try:
            cards = parse_markdown_dir(args.input_dir)
            write_quote_cards_jsonl(cards, args.output_file)
        except InputPathError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        print(f"Generated {len(cards)} quote cards to {args.output_file}")
        return 0

    if args.command == "build-insights":
        try:
            quotes = read_quote_cards_jsonl(args.quote_file)
            print(f"Read quote cards: {len(quotes)}")
        except QuoteReaderError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        try:
            cards = extract_insights_from_quotes(quotes)
            write_insight_cards_jsonl(cards, args.output_file)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        print(f"Generated insight cards: {len(cards)}")
        print(f"Output file: {args.output_file}")
        return 0

    if args.command == "build-concept-candidates":
        try:
            insights = read_quote_cards_jsonl(args.insight_file)
            print(f"Read insight cards: {len(insights)}")
        except QuoteReaderError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        try:
            candidates = build_concept_candidates(insights)
            write_concept_candidates_json(
                candidates,
                args.output_json,
                str(args.insight_file),
            )
            write_concept_candidates_review_md(
                candidates,
                args.output_review,
            )
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        print(f"Generated {len(candidates)} concept candidates")
        print(f"Output JSON: {args.output_json}")
        print(f"Output Review: {args.output_review}")
        return 0

    if args.command == "build-concepts-draft":
        if not args.candidates_file.exists():
            print(f"Error: Candidates file not found: {args.candidates_file}", file=sys.stderr)
            return 1

        try:
            concepts_data = json.loads(
                args.candidates_file.read_text(encoding="utf-8")
            )
        except Exception as e:
            print(f"Error: failed to parse candidates JSON: {e}", file=sys.stderr)
            return 1

        candidates_list = concepts_data.get("concepts", [])

        try:
            draft_concepts = build_draft_concepts(candidates_list)
            write_concepts_draft_yaml(
                draft_concepts,
                args.output_yaml,
                str(args.candidates_file),
            )
            write_concept_review_md(draft_concepts, args.output_review)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        if args.output_json:
            try:
                write_concepts_draft_json(
                    draft_concepts,
                    args.output_json,
                    str(args.candidates_file),
                )
            except Exception as e:
                print(f"Error: {e}", file=sys.stderr)
                return 1

        evidence_total = sum(c.get("evidence_count", 0) for c in draft_concepts)
        print(f"Generated {len(draft_concepts)} draft concepts (total evidence: {evidence_total})")
        print(f"Output YAML: {args.output_yaml}")
        if args.output_json:
            print(f"Output JSON: {args.output_json}")
        print(f"Output Review: {args.output_review}")
        return 0

    if args.command == "validate-concepts":
        try:
            passed, report = run_validate_concepts(
                args.concepts_json,
                args.output_report,
            )
        except ConceptValidationError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        print(f"Validation {'PASSED' if passed else 'FAILED'}")
        print(f"Report: {args.output_report}")
        return 0 if passed else 1

    if args.command == "freeze-concepts":
        try:
            run_freeze_concepts(
                args.concepts_json,
                args.output_json,
                args.output_yaml,
            )
        except ConceptFreezeError as e:
            print(f"Freeze failed: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        print(f"Concepts frozen successfully")
        print(f"Output JSON: {args.output_json}")
        print(f"Output YAML: {args.output_yaml}")
        return 0

    if args.command == "extract-pdf-text":
        if not args.pdf_dir.exists():
            print(f"Error: PDF directory not found: {args.pdf_dir}", file=sys.stderr)
            return 1
        if not args.pdf_dir.is_dir():
            print(f"Error: PDF path is not a directory: {args.pdf_dir}", file=sys.stderr)
            return 1

        try:
            manifests, pages = extract_pdf_directory(args.pdf_dir)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        try:
            write_manifest_jsonl(manifests, args.output_dir / "pdf_manifest.jsonl")
            write_pages_jsonl(pages, args.output_dir / "pages.jsonl")
            write_full_text(manifests, pages, args.output_dir / "full_text")
            write_extraction_report(manifests, args.output_dir / "extraction_report.md", args.output_dir)
        except PdfExtractorError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        success = sum(1 for m in manifests if m.extract_status == "success")
        partial = sum(1 for m in manifests if m.extract_status == "partial")
        failed = sum(1 for m in manifests if m.extract_status == "failed")
        print(f"PDFs processed: {len(manifests)} (success={success}, partial={partial}, failed={failed})")
        print(f"Total pages: {sum(m.page_count for m in manifests)}")
        print(f"Output: {args.output_dir}")
        return 0

    if args.command == "extract-evidence":
        try:
            hits, warnings, manifest_pdfs, stats = extract_evidence(
                args.concepts_file,
                args.pages_file,
                args.manifest_file,
            )
        except ConceptsNotFrozenError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except EvidenceExtractorError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        concepts_data = json.loads(args.concepts_file.read_text(encoding="utf-8"))

        try:
            write_evidence_jsonl(hits, args.output_dir / "evidence_hits.jsonl")
            write_evidence_csv(hits, args.output_dir / "evidence_hits.csv")
            write_concept_keyword_stats(stats, args.output_dir / "concept_keyword_stats.json")
            write_evidence_report(
                hits, stats, warnings, manifest_pdfs,
                args.output_dir / "evidence_report.md",
                str(args.concepts_file),
                str(args.pages_file),
                str(args.manifest_file),
                concepts_data.get("version", "0.1.0"),
            )
        except EvidenceExtractorError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        print(f"Evidence hits: {len(hits)} (positive={sum(1 for h in hits if h.polarity=='positive')}, negative={sum(1 for h in hits if h.polarity=='negative')})")
        if warnings:
            print(f"Warnings: {len(warnings)}")
        print(f"Output: {args.output_dir}")
        return 0

    if args.command == "extract-metric-candidates":
        try:
            candidates, warnings, manifest_pdfs = extract_metric_candidates(
                args.pages_file,
                args.manifest_file,
                args.concepts_file,
                args.tables_file,
            )
        except ConceptsNotFrozenError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except MetricExtractorError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        concepts_data = json.loads(args.concepts_file.read_text(encoding="utf-8"))

        try:
            write_metric_candidates_jsonl(candidates, args.output_dir / "metric_candidates.jsonl")
            write_metric_candidates_csv(candidates, args.output_dir / "metric_candidates.csv")
            write_high_confidence_table_csv(candidates, args.output_dir / "high_confidence_table_candidates.csv")
            write_metric_stats_json(candidates, manifest_pdfs, warnings, args.output_dir / "metric_stats.json")

            stats_for_report = _build_metric_report_stats(candidates)
            write_metric_extraction_report(
                candidates, stats_for_report, warnings, manifest_pdfs,
                args.output_dir / "metric_extraction_report.md",
                str(args.concepts_file),
                str(args.pages_file),
                str(args.manifest_file),
                concepts_data.get("version", "0.1.0"),
            )
        except MetricExtractorError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        needs_review = sum(1 for c in candidates if c.needs_review)
        print(f"Metric candidates: {len(candidates)} (needs_review={needs_review})")
        if warnings:
            print(f"Warnings: {len(warnings)}")
        print(f"Output: {args.output_dir}")
        return 0

    if args.command == "build-metric-series":
        try:
            groups, series, warnings = build_metric_series(
                args.candidates_file,
                args.review_decisions,
                args.manual_series_file,
            )
        except MetricSeriesError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        try:
            write_metric_groups_jsonl(groups, args.output_dir / "metric_groups.jsonl")
            write_metric_series_jsonl(series, args.output_dir / "metric_series.jsonl")
            write_series_long_csv(series, args.output_dir / "metric_series_long.csv")
            write_series_wide_csv(series, args.output_dir / "metric_series_wide.csv")
            write_review_queue_csv(groups, args.output_dir / "metric_review_queue.csv")
            write_series_report(
                groups, series, 0, warnings,
                args.output_dir / "metric_series_report.md",
                str(args.candidates_file),
            )
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        sel = sum(1 for g in groups if g.status == "selected")
        rev = sum(1 for g in groups if g.status == "needs_review")
        con = sum(1 for g in groups if g.status == "conflict")
        print(f"Groups: {len(groups)} (selected={sel}, needs_review={rev}, conflict={con})")
        print(f"Series points: {len(series)}")
        if warnings:
            print(f"Warnings: {len(warnings)}")
        print(f"Output: {args.output_dir}")
        return 0

    if args.command == "compute-metric-trends":
        try:
            trends, warnings = compute_trends(args.series_file)
        except MetricTrendsError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        try:
            write_trends_jsonl(trends, args.output_dir / "metric_trends.jsonl")
            write_trends_long_csv(trends, args.output_dir / "metric_trends_long.csv")
            write_trends_wide_csv(trends, args.output_dir / "metric_trends_wide.csv")
            write_trend_summary(trends, warnings, args.output_dir / "metric_trend_summary.json")
            write_trend_report(trends, warnings, args.output_dir / "metric_trend_report.md", str(args.series_file))
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        print(f"Trend points: {len(trends)}")
        if warnings:
            print(f"Warnings: {len(warnings)}")
        print(f"Output: {args.output_dir}")
        return 0

    if args.command == "score-concepts":
        try:
            scores_data, details, warnings = score_concepts(
                args.concepts_file,
                args.metric_trends_file,
                args.evidence_file,
            )
        except ConceptScoreError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        try:
            write_scores_json(scores_data, args.output_dir / "concept_scores.json")
            write_scores_csv(scores_data["concepts"], args.output_dir / "concept_scores.csv")
            write_details_jsonl(details, args.output_dir / "concept_score_details.jsonl")
            write_score_report(
                scores_data, warnings,
                args.output_dir / "concept_score_report.md",
                str(args.concepts_file),
                str(args.metric_trends_file),
                str(args.evidence_file),
            )
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        for c in scores_data["concepts"]:
            print(f"  {c['concept_id']}: {c['score']} ({c['level']})")
        print(f"Concepts scored: {len(scores_data['concepts'])}")
        if warnings:
            print(f"Warnings: {len(warnings)}")
        print(f"Output: {args.output_dir}")
        return 0

    if args.command in {"run-company-pipeline", "screen-company"}:
        ret = run_company_pipeline(
            args.company_code,
            args.pdf_dir,
            args.concepts_file,
            args.output_dir,
            args.max_reports,
            args.as_of_period,
        )
        manifest_file = args.output_dir / "pipeline_manifest.json"
        if manifest_file.exists():
            m = json.loads(manifest_file.read_text(encoding="utf-8"))
            for s in m["stages"]:
                status = "✓" if s["status"] == "success" else "✗"
                print(f"  {status} {s['stage']}")
                if s["error_message"]:
                    print(f"    Error: {s['error_message']}")
        return ret

    if args.command in {"run-batch-pipeline", "screen-batch"}:
        try:
            ret = run_batch_pipeline(
                args.companies_file, args.concepts_file, args.output_dir,
                args.max_reports, args.as_of_period, args.resume,
            )
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        print(f"Batch manifest: {args.output_dir / 'batch_manifest.csv'}")
        return ret

    if args.command == "fetch-market-features":
        try:
            data = fetch_market_features(args.company_code, args.as_of_period)
            args.output_file.parent.mkdir(parents=True, exist_ok=True)
            args.output_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        print(f"Market features: {args.output_file}")
        return 0

    if args.command == "evaluate-canslim":
        try:
            result = evaluate_canslim(
                read_jsonl(args.trends_file),
                json.loads(args.concept_scores_file.read_text(encoding="utf-8")),
                json.loads(args.market_features_file.read_text(encoding="utf-8")),
            )
            args.output_file.parent.mkdir(parents=True, exist_ok=True)
            args.output_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        print(f"CANSLIM: {result['result']}")
        print(f"Output: {args.output_file}")
        return 0

    if args.command == "build-company-report":
        try:
            md, files, warnings = build_company_report(
                args.company_code,
                args.concepts_file,
                args.metric_trends_file,
                args.metric_series_file,
                args.evidence_file,
                args.concept_scores_file,
                args.output_dir,
            )
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        print(f"Report: {args.output_dir / 'company_report.md'}")
        print(f"Assets: {len(files)} files")
        if warnings:
            print(f"Warnings: {len(warnings)}")
        return 0

    if args.command == "export-excel":
        try:
            export_excel(
                args.company_code,
                args.metric_candidates_file,
                args.metric_series_file,
                args.metric_trends_file,
                args.evidence_file,
                args.concept_scores_file,
                args.output_file,
            )
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        print(f"Excel: {args.output_file}")
        return 0

    if args.command == "validate-final-output":
        passed, report = validate_final_output(args.company_code, args.output_dir)
        args.report_file.parent.mkdir(parents=True, exist_ok=True)
        args.report_file.write_text(report, encoding="utf-8")
        print(f"Validation: {'PASS' if passed else 'FAIL'}")
        print(f"Report: {args.report_file}")
        return 0 if passed else 1

    if args.command == "extract-pdf-tables":
        try:
            count = extract_pdf_tables(args.pdf_dir, args.output_dir)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        print(f"Tables extracted: {count}")
        print(f"Output: {args.output_dir}")
        return 0

    if args.command == "prepare-metric-review-pack":
        try:
            prepare_metric_review_pack(args.company_code, args.metric_candidates_file,
                                       args.tables_file, args.output_dir)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        print(f"Review pack: {args.output_dir}/metric_review_pack.xlsx")
        print(f"Template: {args.output_dir}/manual_metric_values.template.csv")
        return 0

    if args.command == "import-manual-metric-values":
        a, r, e = import_manual_metric_values(args.manual_values_file, args.output_file, args.output_report)
        print(f"Imported: {a} approved, {r} rejected, {e} errors")
        print(f"Output: {args.output_file}")
        return 0 if e == 0 else 1

    if args.command == "fetch-web-metrics":
        try:
            series = fetch_web_metrics(
                args.company_code, str(args.concepts_file), args.as_of_period,
            )
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        args.output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output_file, "w", encoding="utf-8") as f:
            for s in series:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")
        args.output_file.with_name("web_fetch_manifest.json").write_text(json.dumps({
            "company_code": args.company_code, "source": "akshare", "as_of_period": args.as_of_period or "latest_available",
            "point_count": len(series), "fetched_at": __import__("datetime").datetime.now().isoformat(),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Web metrics: {len(series)} points")
        return 0

    if args.command == "download-financial-reports":
        try:
            reports = download_financial_reports(
                args.company_code, args.output_dir, max_reports=args.max_reports
            )
        except ReportDownloadError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        print(f"Downloaded financial reports: {len(reports)}")
        print(f"Output: {args.output_dir}")
        return 0

    if args.command == "build-deliverables":
        try:
            files = build_deliverables(
                args.company_code,
                args.concepts_file,
                args.series_file,
                args.metric_trends_file,
                args.evidence_file,
                args.evidence_stats_file,
                args.concept_scores_file,
                args.score_details_file,
                args.canslim_file,
                args.output_dir,
            )
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        print(f"Deliverables: {len(files)} files")
        print(f"Output: {args.output_dir}")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
