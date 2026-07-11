import json
import pytest

from ds_finance_concept.data_fetcher import report_downloader
from ds_finance_concept.data_fetcher.report_downloader import (
    PDF_URL_TEMPLATE,
    ReportDownloadError,
    download_financial_reports,
)


def test_http_get_retries_transient_transport_error(monkeypatch):
    monkeypatch.setattr(report_downloader.time, "sleep", lambda _: None)
    calls = []

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return b"ok"

    def flaky(*args, **kwargs):
        calls.append(1)
        if len(calls) < 3:
            raise OSError("temporary")
        return Response()

    monkeypatch.setattr(report_downloader, "urlopen", flaky)
    assert report_downloader._http_get("https://example.com") == b"ok"
    assert len(calls) == 3


def _catalogue() -> bytes:
    return json.dumps({"data": {"list": [
        {"art_code": "AN2026Q1", "notice_date": "2026-04-28", "title": "鸣志电器:鸣志电器2026年第一季度报告", "codes": [{"stock_code": "603728"}]},
        {"art_code": "AN2025A", "notice_date": "2026-04-25", "title": "鸣志电器:鸣志电器2025年年度报告", "codes": [{"stock_code": "603728"}]},
        {"art_code": "AN2025AS", "notice_date": "2026-04-25", "title": "鸣志电器:鸣志电器2025年年度报告摘要", "codes": [{"stock_code": "603728"}]},
        {"art_code": "AN2025EN", "notice_date": "2026-04-26", "title": "鸣志电器:鸣志电器2025年年度报告（英文版）", "codes": [{"stock_code": "603728"}]},
        {"art_code": "OTHER", "notice_date": "2026-04-25", "title": "其他公司:2025年年度报告", "codes": [{"stock_code": "600000"}]},
    ]}}).encode("utf-8")


def test_download_financial_reports_filters_summary_and_validates_pdf(tmp_path):
    pdf = b"%PDF-1.7\n" + b"x" * 2_000

    def fake_get(url):
        if "np-anotice-stock" in url:
            return _catalogue()
        assert url in {PDF_URL_TEMPLATE.format(art_code="AN2026Q1"), PDF_URL_TEMPLATE.format(art_code="AN2025A")}
        return pdf

    reports = download_financial_reports("603728", tmp_path, http_get=fake_get)

    assert [(r.report_year, r.report_kind) for r in reports] == [
        (2026, "第一季度报告"), (2025, "年度报告"),
    ]
    assert all((tmp_path / f"{r.report_year}_{r.report_kind}.pdf").exists() for r in reports)
    manifest = json.loads((tmp_path / "download_manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["reports"]) == 2


def test_download_financial_reports_rejects_non_pdf(tmp_path):
    def fake_get(url):
        return _catalogue() if "np-anotice-stock" in url else b"<html>challenge</html>"

    with pytest.raises(ReportDownloadError, match="not a PDF"):
        download_financial_reports("603728", tmp_path, http_get=fake_get)


def test_download_financial_reports_reads_later_catalogue_pages(tmp_path):
    page_one = json.dumps({"data": {"list": [
        {"art_code": f"NOTICE{i}", "notice_date": "2026-05-01", "title": "普通公告", "codes": [{"stock_code": "600933"}]}
        for i in range(100)
    ]}}).encode("utf-8")
    page_two = json.dumps({"data": {"list": [
        {"art_code": "AN2025Q3", "notice_date": "2025-10-30", "title": "爱柯迪:2025年第三季度报告", "codes": [{"stock_code": "600933"}]}
    ]}}).encode("utf-8")

    def fake_get(url):
        if "page_index=1" in url:
            return page_one
        if "page_index=2" in url:
            return page_two
        return b"%PDF-1.7\n" + b"x" * 2_000

    reports = download_financial_reports("600933", tmp_path, http_get=fake_get)
    assert [(r.report_year, r.report_kind) for r in reports] == [(2025, "第三季度报告")]
