import csv

from ds_finance_concept.reporting import pipeline


def test_guard_metrics_fails_on_missing_file(tmp_path):
    assert pipeline._guard_metrics(tmp_path / "nope.jsonl") == 1


def test_guard_metrics_fails_on_empty_file(tmp_path):
    f = tmp_path / "series.jsonl"
    f.write_text("", encoding="utf-8")
    assert pipeline._guard_metrics(f) == 1


def test_guard_metrics_passes_with_data(tmp_path):
    f = tmp_path / "series.jsonl"
    f.write_text('{"metric_id": "revenue"}\n', encoding="utf-8")
    assert pipeline._guard_metrics(f) == 0


def test_guard_evidence_never_fails(tmp_path):
    missing = tmp_path / "nope.jsonl"
    assert pipeline._guard_evidence(missing) == 0
    empty = tmp_path / "ev.jsonl"
    empty.write_text("", encoding="utf-8")
    assert pipeline._guard_evidence(empty) == 0
    full = tmp_path / "ev2.jsonl"
    full.write_text('{"concept_id": "c"}\n', encoding="utf-8")
    assert pipeline._guard_evidence(full) == 0


def test_count_jsonl_ignores_blank_lines(tmp_path):
    f = tmp_path / "x.jsonl"
    f.write_text('{"a":1}\n\n{"b":2}\n', encoding="utf-8")
    assert pipeline._count_jsonl(f) == 2


def test_read_company_codes_and_batch_manifest(monkeypatch, tmp_path):
    companies = tmp_path / "companies.csv"
    companies.write_text("company_code,name\n000001,平安银行\n603129,春风动力\n000001,重复\n", encoding="utf-8")
    assert pipeline._read_company_codes(companies) == ["000001", "603129"]

    calls = []

    def fake_run(code, pdf_dir, concepts_file, output_dir, max_reports, as_of_period):
        calls.append((code, pdf_dir, max_reports, as_of_period))
        return 0 if code == "000001" else 1

    monkeypatch.setattr(pipeline, "run_company_pipeline", fake_run)
    out = tmp_path / "batch"
    assert pipeline.run_batch_pipeline(companies, tmp_path / "concepts.json", out,
                                       max_reports=6, as_of_period="2025A") == 1
    assert calls == [("000001", None, 6, "2025A"), ("603129", None, 6, "2025A")]
    with (out / "batch_manifest.csv").open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert [r["status"] for r in rows] == ["success", "failed"]
    assert len((out / "batch_progress.jsonl").read_text(encoding="utf-8").splitlines()) == 2


def test_batch_resume_skips_successful_company(monkeypatch, tmp_path):
    companies = tmp_path / "companies.csv"
    companies.write_text("company_code\n000001\n", encoding="utf-8")
    company_dir = tmp_path / "batch" / "000001"
    company_dir.mkdir(parents=True)
    (company_dir / "pipeline_manifest.json").write_text('{"stages":[{"status":"success"}]}', encoding="utf-8")
    monkeypatch.setattr(pipeline, "run_company_pipeline", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should skip")))
    assert pipeline.run_batch_pipeline(companies, tmp_path / "concepts.json", tmp_path / "batch", resume=True) == 0


def test_read_company_codes_rejects_invalid_code(tmp_path):
    companies = tmp_path / "companies.csv"
    companies.write_text("code\n123\n", encoding="utf-8")
    try:
        pipeline._read_company_codes(companies)
    except ValueError as e:
        assert "Invalid company code" in str(e)
    else:
        raise AssertionError("expected invalid code to fail")


def test_guard_pdf_period_alignment(tmp_path):
    (tmp_path / "2025_年度报告.pdf").write_bytes(b"%PDF-test")
    assert pipeline._guard_pdf_period_alignment(tmp_path, "2025A") == 0
    assert pipeline._guard_pdf_period_alignment(tmp_path, "2025Q3") == 1


def test_guard_pdf_extraction_rejects_empty_and_accepts_readable(tmp_path):
    manifest = tmp_path / "pdf_manifest.jsonl"
    manifest.write_text("", encoding="utf-8")
    assert pipeline._guard_pdf_extraction(manifest) == 1
    manifest.write_text('{"extract_status":"partial","text_page_count":3}\n', encoding="utf-8")
    assert pipeline._guard_pdf_extraction(manifest) == 0
