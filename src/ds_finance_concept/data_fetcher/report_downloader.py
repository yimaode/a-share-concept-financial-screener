"""Scripted acquisition of public financial-report PDFs.

The SSE static-file host can return a JavaScript anti-bot page to simple HTTP
clients.  This downloader instead queries Eastmoney's public announcement
catalogue and fetches the PDF URL returned by that catalogue.  It deliberately
validates every response as a PDF before accepting it as pipeline input.
"""

from __future__ import annotations

import json
import re
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.parse import urlencode
from urllib.error import URLError
from urllib.request import Request, urlopen


CATALOG_URL = "https://np-anotice-stock.eastmoney.com/api/security/ann"
PDF_URL_TEMPLATE = "https://pdf.dfcfw.com/pdf/H2_{art_code}_1.pdf"
USER_AGENT = "Mozilla/5.0 (compatible; ds-finance-concept/0.1)"

_TITLE_RE = re.compile(
    r"(?P<year>20\d{2})年(?P<kind>年度报告|半年度报告|第一季度报告|第三季度报告)"
)
_KIND_ORDER = {"年度报告": 4, "第三季度报告": 3, "半年度报告": 2, "第一季度报告": 1}
_NON_PRIMARY_TITLE_MARKERS = ("摘要", "英文版", "外文版", "取消", "更正公告")


class ReportDownloadError(RuntimeError):
    pass


@dataclass(frozen=True)
class DownloadedReport:
    company_code: str
    title: str
    report_year: int
    report_kind: str
    announcement_date: str
    art_code: str
    source_url: str
    local_path: str
    byte_count: int


def _http_get(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json,application/pdf,*/*"})
    last_error = None
    for attempt in range(3):
        try:
            with urlopen(request, timeout=30) as response:  # nosec B310: public, fixed HTTPS hosts
                return response.read()
        except (URLError, OSError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(.5 * (attempt + 1))
    raise ReportDownloadError(f"Public report request failed after 3 attempts: {last_error}")


def _catalog_url(company_code: str, page_index: int) -> str:
    query = urlencode({
        "sr": "-1", "page_size": "100", "page_index": str(page_index),
        "ann_type": "A", "client_source": "web", "stock_list": company_code,
    })
    return f"{CATALOG_URL}?{query}"


def _parse_financial_reports(company_code: str, payload: bytes) -> list[dict]:
    try:
        body = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReportDownloadError("Announcement catalogue returned invalid JSON") from exc

    rows = body.get("data", {}).get("list", [])
    if not isinstance(rows, list):
        raise ReportDownloadError("Announcement catalogue has no list payload")

    reports: list[dict] = []
    for row in rows:
        title = str(row.get("title", ""))
        match = _TITLE_RE.search(title)
        # Evidence extraction uses the Chinese primary report.  English/summary
        # variants often share the same period and must not win deduplication.
        if not match or any(marker in title for marker in _NON_PRIMARY_TITLE_MARKERS):
            continue
        codes = row.get("codes", [])
        if not any(str(c.get("stock_code", "")) == company_code for c in codes if isinstance(c, dict)):
            continue
        art_code = str(row.get("art_code", ""))
        if not art_code:
            continue
        reports.append({
            "title": title,
            "year": int(match.group("year")),
            "kind": match.group("kind"),
            "date": str(row.get("notice_date", ""))[:10],
            "art_code": art_code,
        })

    reports.sort(key=lambda r: (r["year"], _KIND_ORDER[r["kind"]], r["date"], r["art_code"]), reverse=True)
    deduplicated: list[dict] = []
    seen: set[tuple[int, str]] = set()
    for report in reports:
        key = (report["year"], report["kind"])
        if key not in seen:
            seen.add(key)
            deduplicated.append(report)
    return deduplicated


def _catalogue_row_count(payload: bytes) -> int:
    """Return the raw row count so the caller can safely paginate."""
    try:
        body = json.loads(payload.decode("utf-8"))
        rows = body.get("data", {}).get("list", [])
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReportDownloadError("Announcement catalogue returned invalid JSON") from exc
    if not isinstance(rows, list):
        raise ReportDownloadError("Announcement catalogue has no list payload")
    return len(rows)


def _write_pdf(destination: Path, data: bytes) -> None:
    if not data.startswith(b"%PDF-"):
        raise ReportDownloadError("Downloaded response is not a PDF")
    if len(data) < 1_000:
        raise ReportDownloadError("Downloaded PDF is implausibly small")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    tmp_path.replace(destination)


def download_financial_reports(
    company_code: str,
    output_dir: Path,
    *,
    max_reports: int = 12,
    http_get: Callable[[str], bytes] = _http_get,
) -> list[DownloadedReport]:
    """Download the latest annual/interim/quarterly reports for one stock."""
    if not re.fullmatch(r"\d{6}", company_code):
        raise ReportDownloadError("company_code must be a six-digit A-share code")
    if max_reports < 1:
        raise ReportDownloadError("max_reports must be positive")

    # The catalogue is ordered by all announcements, not by periodic reports.
    # Large issuers can have a full first page containing only recent routine
    # notices, so continue until enough reports are found or the catalogue ends.
    reports: list[dict] = []
    for page_index in range(1, 51):
        payload = http_get(_catalog_url(company_code, page_index))
        reports.extend(_parse_financial_reports(company_code, payload))
        reports = _deduplicate_reports(reports)
        if len(reports) >= max_reports or _catalogue_row_count(payload) < 100:
            break
    if not reports:
        raise ReportDownloadError(f"No financial reports found for {company_code}")

    downloaded: list[DownloadedReport] = []
    for report in reports[:max_reports]:
        source_url = PDF_URL_TEMPLATE.format(art_code=report["art_code"])
        local_path = output_dir / f"{report['year']}_{report['kind']}.pdf"
        data = http_get(source_url)
        _write_pdf(local_path, data)
        downloaded.append(DownloadedReport(
            company_code=company_code,
            title=report["title"],
            report_year=report["year"],
            report_kind=report["kind"],
            announcement_date=report["date"],
            art_code=report["art_code"],
            source_url=source_url,
            local_path=str(local_path),
            byte_count=len(data),
        ))

    manifest = {
        "company_code": company_code,
        "downloaded_at": datetime.now().isoformat(),
        "source": "eastmoney_public_announcement_catalogue",
        "reports": [asdict(report) for report in downloaded],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "download_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return downloaded


def _deduplicate_reports(reports: list[dict]) -> list[dict]:
    reports.sort(key=lambda r: (r["year"], _KIND_ORDER[r["kind"]], r["date"], r["art_code"]), reverse=True)
    result: list[dict] = []
    seen: set[tuple[int, str]] = set()
    for report in reports:
        key = (report["year"], report["kind"])
        if key not in seen:
            seen.add(key)
            result.append(report)
    return result
