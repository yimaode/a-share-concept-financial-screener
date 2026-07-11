import json
from pathlib import Path

from ds_finance_concept.reporting.deliverables import build_deliverables


def _json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")


def test_deliverables_expose_data_quality_and_percent_values(tmp_path):
    concepts = tmp_path / "concepts.json"
    _json(concepts, {"status": "frozen", "concepts": [{
        "concept_id": "c1", "name": "概念", "hard_metrics": ["gross_margin"],
    }]})
    series = tmp_path / "series.jsonl"
    _jsonl(series, [])
    trends = tmp_path / "trends.jsonl"
    _jsonl(trends, [{
        "metric_id": "gross_margin", "metric_name": "毛利率", "report_period": "2024Q1",
        "period_year": 2024, "period_order": 1, "value_normalized": 35.5,
        "value_unit_normalized": "percent", "is_percent": True, "change_pp": 1.2,
        "consecutive_growth_count": 1,
    }])
    evidence = tmp_path / "evidence.jsonl"
    _jsonl(evidence, [])
    stats = tmp_path / "stats.json"
    _json(stats, {})
    scores = tmp_path / "scores.json"
    _json(scores, {"concepts": [{
        "concept_id": "c1", "concept_name": "概念", "score": 60, "level": "medium",
        "positive_hits": 0, "negative_hits": 0, "status": "evidence_limited",
        "metric_coverage": {"available": 1, "required": 1, "missing": [], "unsupported": []},
        "warnings": ["证据句不足: 0/2"], "top_reasons": [],
    }]})
    details = tmp_path / "details.jsonl"
    _jsonl(details, [])
    canslim = tmp_path / "canslim.json"
    _json(canslim, {"result": "资料不足", "dimensions": {"C": {
        "name": "当前季度增长", "status": "pass", "reason": "test",
    }}})

    out = tmp_path / "deliverables"
    build_deliverables("000001", concepts, series, trends, evidence, stats, scores, details, canslim, out)
    assert "35.50%" in (out / "01_concept_metrics.csv").read_text(encoding="utf-8-sig")
    assert "evidence_limited" in (out / "03_final_scores.csv").read_text(encoding="utf-8-sig")
    assert "evidence_id" in (out / "03_score_details.csv").read_text(encoding="utf-8-sig")
    report = (out / "03_final_report.md").read_text(encoding="utf-8")
    assert "资料未齐全" in report
    assert "证据句不足" in report
    assessment = json.loads((out / "03_final_assessment.json").read_text(encoding="utf-8"))
    assert assessment["screening_status"] == "资料未齐全，量化分数仅供初筛"
    assert (out / "03_canslim_assessment.csv").exists()
