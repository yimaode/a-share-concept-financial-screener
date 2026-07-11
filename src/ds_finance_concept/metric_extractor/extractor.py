import json
import re
from collections import defaultdict
from pathlib import Path

from .errors import ConceptsNotFrozenError, MetricExtractorError
from .metric_defs import METRIC_DEFINITIONS, RD_EXPENSE_RATIO_ALIASES, REVENUE_FALSE_POSITIVES
from .schema import MetricCandidate, generate_candidate_id

NUMBER_PATTERN = re.compile(
    r"(?:人民币\s*)?"
    r"[（(]?\s*"
    r"(-?\d[\d,]*\.?\d*)"
    r"\s*[）)]?"
    r"\s*(万元|亿元|亿|元|%)?"
)

PERIOD_PATTERNS = [
    (r"(\d{4})\s*Q\s*([1-4])", lambda m: f"{m.group(1)}Q{m.group(2)}"),
    (r"(\d{4})\s*H\s*([1-2])", lambda m: f"{m.group(1)}H{m.group(2)}"),
    (r"(\d{4})\s*[Aa](?![\u4e00-\u9fff])", lambda m: f"{m.group(1)}A"),
    (r"(\d{4})[\s_\-]*年\s*第\s*一\s*季\s*度\s*报告", lambda m: f"{m.group(1)}Q1"),
    (r"(\d{4})[\s_\-]*年\s*一\s*季\s*度\s*报告", lambda m: f"{m.group(1)}Q1"),
    (r"(\d{4})[\s_\-]*一\s*季\s*报", lambda m: f"{m.group(1)}Q1"),
    (r"(\d{4})[\s_\-]*年\s*第\s*一\s*季\s*度", lambda m: f"{m.group(1)}Q1"),
    (r"(\d{4})[\s_\-]*年\s*第\s*[三3]\s*季\s*度\s*报告", lambda m: f"{m.group(1)}Q3"),
    (r"(\d{4})[\s_\-]*年\s*[三3]\s*季\s*度\s*报告", lambda m: f"{m.group(1)}Q3"),
    (r"(\d{4})[\s_\-]*[三3]\s*季\s*报", lambda m: f"{m.group(1)}Q3"),
    (r"(\d{4})[\s_\-]*年\s*第\s*[三3]\s*季\s*度", lambda m: f"{m.group(1)}Q3"),
    (r"(\d{4})[\s_\-]*年\s*半\s*年\s*度\s*报告", lambda m: f"{m.group(1)}H1"),
    (r"(\d{4})[\s_\-]*年\s*中\s*期\s*报告", lambda m: f"{m.group(1)}H1"),
    (r"(\d{4})[\s_\-]*半\s*年\s*度\s*报告", lambda m: f"{m.group(1)}H1"),
    (r"(\d{4})[\s_\-]*半\s*年\s*报", lambda m: f"{m.group(1)}H1"),
    (r"(\d{4})[\s_\-]*H1", lambda m: f"{m.group(1)}H1"),
    (r"(\d{4})[\s_\-]*Q3", lambda m: f"{m.group(1)}Q3"),
    (r"(\d{4})[\s_\-]*年\s*年\s*度\s*报告", lambda m: f"{m.group(1)}A"),
    (r"(\d{4})[\s_\-]*年\s*度\s*报告", lambda m: f"{m.group(1)}A"),
    (r"(\d{4})[\s_\-]*年\s*度\s*报", lambda m: f"{m.group(1)}A"),
    (r"(\d{4})[\s_\-]*年\s*年\s*报", lambda m: f"{m.group(1)}A"),
]



def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise MetricExtractorError(f"File not found: {path}")
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                records.append(json.loads(stripped))
            except json.JSONDecodeError as e:
                raise MetricExtractorError(
                    f"Invalid JSON at line {line_num} in {path}: {e}"
                ) from e
    return records


def _read_concepts(path: Path) -> dict:
    if not path.exists():
        raise MetricExtractorError(f"Concepts file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("status") != "frozen":
        raise ConceptsNotFrozenError(
            f"Concepts file status is {data.get('status', 'unknown')!r}, must be 'frozen'"
        )
    return data


def _detect_report_period(source_pdf: str, text: str) -> str:
    search_name = source_pdf.replace(".PDF", ".pdf").replace(".Pdf", ".pdf")
    search_name = search_name.replace("_", " ").replace("-", " ")

    for pattern, formatter in PERIOD_PATTERNS:
        m = re.search(pattern, search_name)
        if m:
            return formatter(m)

    for pattern, formatter in PERIOD_PATTERNS:
        m = re.search(pattern, text)
        if m:
            return formatter(m)

    return "unknown"


PAGE_UNIT_PATTERN = re.compile(
    r"(?:除特别注明外[,，]?\s*)?"
    r"(?:金额)?单位[：:为]\s*"
    r"(?:人民币\s*)?"
    r"(万元|亿元|亿|元)",
    re.IGNORECASE,
)


def _detect_page_unit(text: str) -> str | None:
    matches = list(PAGE_UNIT_PATTERN.finditer(text))
    units = {m.group(1) for m in matches if m.group(1)}
    if len(units) == 1:
        return units.pop()
    return None


SECTION_HEADERS = [
    ("key_financial_data", ["主要会计数据和财务指标", "主要会计数据", "主要财务指标", "公司主要会计数据和财务指标"]),
    ("income_statement", ["合并及母公司利润表", "母公司利润表", "合并利润表", "利润表", "合并及公司利润表"]),
    ("balance_sheet", ["合并及母公司资产负债表", "母公司资产负债表", "合并资产负债表", "资产负债表", "合并及公司资产负债表"]),
    ("cashflow_statement", ["合并及母公司现金流量表", "母公司现金流量表", "合并现金流量表", "现金流量表", "合并及公司现金流量表"]),
]

TABLE_UNIT_HINT_MARGIN = 15

COLUMN_CURRENT_PATTERNS = [
    "本报告期", "本期金额", "本期发生额", "本期数", "本期",
    "本年金额", "本年度", "本年",
    "本期末", "期末余额",
]

COLUMN_PREVIOUS_PATTERNS = [
    "上年同期", "上期金额", "上期发生额", "上期数", "上期",
    "上年金额", "上年度", "上年",
    "上年末", "期初余额",
]

PERCENT_COLUMN_PATTERNS = [
    "本年比上年增减", "比上年同期增减", "增减比例", "同比增减",
]

YEAR_COLUMN_PATTERN = re.compile(r"(20\d{2})\s*年")

AMOUNT_METRICS_SET = {
    "revenue", "net_profit_attributable", "deducted_net_profit",
    "operating_cashflow", "fixed_assets", "inventory",
    "contract_liabilities", "total_assets", "construction_in_progress",
    "rd_expense",
}

MIN_PLAUSIBLE_CNY_TABLE = 1_000_000


def _detect_section_regions(text: str) -> list[dict]:
    lines = text.split("\n")
    regions: list[dict] = []
    for i, line in enumerate(lines):
        for section_type, patterns in SECTION_HEADERS:
            for pat in patterns:
                if pat in line and len(line.strip()) < 80:
                    regions.append({
                        "section_type": section_type,
                        "section_name": section_type,
                        "start_line": i,
                        "end_line": min(len(lines), i + 150),
                    })
                    break
    return regions


def _detect_column_roles(text: str, section_start: int, section_end: int) -> list[dict]:
    lines = text.split("\n")
    roles: list[dict] = []
    header_zone = lines[max(0, section_start - 3):min(len(lines), section_start + 10)]
    header_text = "\n".join(header_zone)

    for pat in COLUMN_CURRENT_PATTERNS:
        for m in re.finditer(pat, header_text):
            roles.append({"label": m.group(0), "role": "current_period", "position": m.start()})

    for pat in COLUMN_PREVIOUS_PATTERNS:
        for m in re.finditer(pat, header_text):
            roles.append({"label": m.group(0), "role": "previous_period", "position": m.start()})

    roles.sort(key=lambda r: r["position"])
    return roles


def _detect_table_unit(text: str, hint_line: int) -> str | None:
    lines = text.split("\n")
    start = max(0, hint_line - TABLE_UNIT_HINT_MARGIN)
    end = min(len(lines), hint_line + 3)
    for i in range(start, end):
        if i >= len(lines):
            break
        m = PAGE_UNIT_PATTERN.search(lines[i])
        if m:
            return m.group(1)
    return None


def _extract_snippet_lines(
    lines: list[str],
    alias_start: int,
    alias_end: int,
    num_start: int,
    num_end: int,
) -> list[str]:
    current_pos = 0
    involved: set[int] = set()
    for i, line in enumerate(lines):
        line_end = current_pos + len(line)
        if (alias_start < line_end and alias_end > current_pos):
            involved.add(i)
        if (num_start < line_end and num_end > current_pos):
            involved.add(i)
        current_pos += len(line) + 1

    if not involved:
        return [""]

    min_idx = min(involved)
    max_idx = max(involved)
    result_idxs = set()
    for idx in range(max(0, min_idx - 1), min(len(lines), max_idx + 3)):
        result_idxs.add(idx)

    return [lines[i].strip() for i in sorted(result_idxs)]


def _parse_number(raw: str, unit: str) -> tuple[float, float, str, bool]:
    clean = raw.replace(",", "").replace(" ", "")
    is_neg = False
    if clean.startswith("-"):
        is_neg = True
        clean = clean[1:]
    try:
        val = float(clean)
    except ValueError:
        val = 0.0
    if is_neg:
        val = -val

    is_percent = False
    normalized = val
    norm_unit = "unknown"

    if unit in ("%",):
        is_percent = True
        normalized = val
        norm_unit = "percent"
    elif unit in ("万元",):
        normalized = val * 10000
        norm_unit = "CNY"
    elif unit in ("亿元", "亿"):
        normalized = val * 100000000
        norm_unit = "CNY"
    elif unit in ("元",):
        normalized = val
        norm_unit = "CNY"
    elif unit:
        normalized = val
        norm_unit = "unknown"

    return val, normalized, norm_unit, is_percent


def _is_standalone_year(text: str, pos: int, end: int) -> bool:
    num_str = text[pos:end]
    if len(num_str) == 4 and num_str.startswith(("19", "20")):
        before = text[max(0, pos - 1):pos]
        after = text[end:end + 1]
        if before in ("", " ", "\n", "（", "(", "。", "，", ",") and after in ("", " ", "\n", "）", ")", "。", "，", ",", "年"):
            return True
    return False


def _build_alias_map(concepts: list[dict]) -> dict[str, list[tuple[str, str, str]]]:
    alias_map: dict[str, list[tuple[str, str, str]]] = {}

    for metric_id, defn in METRIC_DEFINITIONS.items():
        name = defn["name"]
        for alias in defn["aliases"]:
            alias_map.setdefault(alias, []).append((metric_id, name, alias))

    for c in concepts:
        cid = c.get("concept_id", "")
        metrics = c.get("hard_metrics", [])
        for m in metrics:
            if m in METRIC_DEFINITIONS:
                name = METRIC_DEFINITIONS[m]["name"]
                for alias in METRIC_DEFINITIONS[m]["aliases"]:
                    entry = (m, name, alias)
                    existing = alias_map.get(alias, [])
                    if entry not in existing:
                        existing.append(entry)
                    alias_map[alias] = existing

    return alias_map


def _compute_confidence(
    snippet: str,
    metric_alias: str,
    num_matches: int,
    has_unit: bool,
    norm_unit: str,
    report_period: str,
    is_percent: bool,
    metric_id: str,
) -> str:
    if norm_unit == "unknown":
        return "low"
    if metric_id == "gross_margin" and not is_percent:
        return "low"
    if not has_unit:
        return "low"
    if num_matches > 1:
        return "low"
    if report_period == "unknown":
        return "low"

    snippet_clean = snippet.replace(" ", "")
    if metric_alias.replace(" ", "") in snippet_clean:
        return "high"
    return "medium"


def extract_metric_candidates(
    pages_file: Path,
    manifest_file: Path,
    concepts_file: Path,
    tables_file: Path | None = None,
) -> tuple[list[MetricCandidate], list[str], list[dict]]:
    concepts_data = _read_concepts(concepts_file)
    concepts = concepts_data.get("concepts", [])
    alias_map = _build_alias_map(concepts)

    pages = _read_jsonl(pages_file)

    manifest_ids: set[str] = set()
    manifest_pdfs: list[dict] = []
    if manifest_file.exists():
        manifest_records = _read_jsonl(manifest_file)
        for m in manifest_records:
            mid = m.get("pdf_id", "")
            if mid:
                manifest_ids.add(mid)
            manifest_pdfs.append(m)

    candidates: list[MetricCandidate] = []
    warnings: list[str] = []
    seen: set[tuple] = set()

    if tables_file and tables_file.exists():
        _extract_from_tables(
            tables_file, alias_map, candidates, seen, manifest_ids, warnings
        )
    else:
        # A structured table preserves the row/column relationship needed for
        # quantitative time series.  Do not mix it with fuzzy whole-page
        # number scanning, which mainly creates unreviewable narrative hits.
        # The latter remains available for legacy callers without tables.
        _extract_from_pages(pages, alias_map, candidates, seen, manifest_ids, warnings)

    candidates.sort(key=lambda c: (
        c.relative_path, c.page_number, c.metric_id, c.source_snippet,
    ))

    return candidates, warnings, manifest_pdfs


def _extract_from_tables(
    tables_file: Path,
    alias_map: dict,
    candidates: list,
    seen: set,
    manifest_ids: set,
    warnings: list,
) -> set[tuple[str, int]]:
    import json

    covered_pages: set[tuple[str, int]] = set()
    with tables_file.open("r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            tbl = json.loads(s)
            rows = tbl.get("rows", [])
            if len(rows) < 2:
                continue

            section_type = tbl.get("section_type", "unknown")
            report_period = tbl.get("report_period", "unknown")
            table_unit = tbl.get("unit_raw", "")
            unit_source = tbl.get("unit_source", "table_nearby_text")
            pdf_id = tbl.get("pdf_id", "")
            source_pdf = tbl.get("source_pdf", "")
            rel_path = tbl.get("relative_path", "")
            page_number = tbl.get("page_number", 0)

            column_roles = _parse_table_columns(rows, report_period)

            for ri, row in enumerate(rows):
                combined = "".join(str(c) for c in row)
                for alias_str in sorted(alias_map.keys(), key=len, reverse=True):
                    if alias_str not in combined:
                        continue

                    if alias_str in ("营业收入", "营收", "营业收入合计", "营业总收入", "主营业务收入"):
                        if any(fp in combined for fp in REVENUE_FALSE_POSITIVES):
                            continue

                    for entry in alias_map[alias_str]:
                        metric_id, metric_name, matched_alias = entry

                        for ci, col_val in enumerate(row):
                            if ci == 0:
                                continue
                            cr = column_roles[ci] if ci < len(column_roles) else {"role": "unknown", "label": "", "report_period": report_period}

                            if cr["role"] == "change_column":
                                continue

                            num_m = NUMBER_PATTERN.search(str(col_val))
                            if not num_m:
                                continue

                            raw_num = num_m.group(1)
                            unit = num_m.group(2) or ""
                            has_local_unit = bool(unit)
                            if not has_local_unit and table_unit:
                                unit = table_unit

                            is_percent = unit == "%" or "%" in str(col_val)
                            val, normalized, norm_unit, is_pct = _parse_number(raw_num, unit)

                            if not has_local_unit and table_unit and not is_pct:
                                val, normalized, norm_unit, is_pct = _parse_number(raw_num, table_unit)

                            if metric_id == "revenue" and any(fp in str(col_val) for fp in REVENUE_FALSE_POSITIVES):
                                continue
                            if metric_id == "rd_expense" and (is_percent or is_pct):
                                continue
                            if metric_id in AMOUNT_METRICS_SET and is_pct:
                                continue

                            confidence = "high"
                            review_reasons: list[str] = []

                            if norm_unit == "unknown":
                                confidence = "medium"
                                review_reasons.append("单位无法识别")
                            if not has_local_unit and table_unit and unit_source not in ("page_text", "table_header"):
                                review_reasons.append(f"unit_inferred_from_{unit_source}")
                            if metric_id == "gross_margin" and not is_pct:
                                review_reasons.append("毛利率指标未检测到百分号")
                            if cr["role"] == "unknown":
                                review_reasons.append("column_role=unknown")

                            needs_review = len(review_reasons) > 0
                            snippet = f"{combined[:200]} | col={ci}"

                            cid = generate_candidate_id(metric_id, raw_num + (unit or ""), pdf_id, page_number, snippet)
                            key = (metric_id, raw_num, unit, pdf_id, page_number, snippet[:80])
                            if key in seen:
                                continue
                            seen.add(key)

                            candidates.append(MetricCandidate(
                                candidate_id=cid, metric_id=metric_id,
                                metric_name=metric_name, matched_alias=matched_alias,
                                raw_value=raw_num + (" " + unit if unit else ""),
                                value=val, value_unit_raw=unit,
                                value_normalized=normalized,
                                value_unit_normalized=norm_unit,
                                is_percent=is_pct,
                                report_period=cr.get("report_period", report_period),
                                source_pdf=source_pdf, relative_path=rel_path,
                                pdf_id=pdf_id, page_number=page_number,
                                source_snippet=snippet,
                                confidence=confidence,
                                needs_review=needs_review,
                                review_reasons=review_reasons,
                                section_type=section_type,
                                section_name=section_type,
                                column_role=cr["role"],
                                column_label=cr["label"],
                                unit_source=unit_source,
                            ))
                            covered_pages.add((pdf_id, page_number))
    return covered_pages


def _parse_table_columns(rows: list[list], report_period: str) -> list[dict]:
    roles: list[dict] = [
        {"role": "header", "label": str(rows[0][c]) if c < len(rows[0]) else "", "report_period": report_period}
        for c in range(max(len(r) for r in rows[:1]))
    ]

    if len(roles) <= 1:
        return roles

    current_keywords = ["本期", "本年", "本年度", "本报告期", "本期金额", "本年金额", "期末余额", "本期末"]
    prev_keywords = ["上期", "上年", "上年度", "上年同期", "上期金额", "上年金额", "期初余额", "上年末"]
    change_keywords = ["增减", "增长率", "变动比例"]

    for i, role in enumerate(roles):
        label = str(role.get("label", ""))
        col_text = " ".join(str(rows[r][i]) if i < len(rows[r]) else "" for r in range(min(3, len(rows))))
        year_match = re.search(r"(?<!\d)(20\d{2})\s*年?", label)

        # Annual-report summary tables commonly use explicit years instead of
        # “本期/上期”.  Each year is an independently usable annual point, not
        # merely a comparison value, so retain the source year in report_period.
        if year_match:
            role["role"] = "current_period"
            year = year_match.group(1)
            if "第一季度" in label or "一季度" in label:
                role["report_period"] = f"{year}Q1"
            elif "半年度" in label or "半年" in label:
                role["report_period"] = f"{year}H1"
            elif "第三季度" in label or "三季度" in label:
                role["report_period"] = f"{year}Q3"
            elif report_period.endswith("Q1") and "3月31日" in label:
                role["report_period"] = f"{year}Q1"
            elif report_period.endswith("H1") and "6月30日" in label:
                role["report_period"] = f"{year}H1"
            elif report_period.endswith("Q3") and "9月30日" in label:
                role["report_period"] = f"{year}Q3"
            else:
                role["report_period"] = f"{year}A"
            continue

        if any(kw in col_text or kw in label for kw in change_keywords) or "%" in col_text:
            role["role"] = "change_column"
        elif any(kw in label or kw in col_text for kw in current_keywords):
            role["role"] = "current_period"
        elif any(kw in label or kw in col_text for kw in prev_keywords):
            role["role"] = "previous_period"
        if role["role"] == "header" and i > 0:
            role["role"] = "unknown"

    return roles


def _extract_from_pages(
    pages: list[dict],
    alias_map: dict,
    candidates: list,
    seen: set,
    manifest_ids: set,
    warnings: list,
    skip_pages: set[tuple[str, int]] | None = None,
) -> None:
    for page in pages:
        pdf_id = page.get("pdf_id", "")
        source_pdf = page.get("source_pdf", "")
        relative_path = page.get("relative_path", "")
        page_number = page.get("page_number", 0)
        text = page.get("text", "")

        if skip_pages and (pdf_id, page_number) in skip_pages:
            continue

        if manifest_ids and pdf_id and pdf_id not in manifest_ids:
            warnings.append(f"pdf_id {pdf_id} not found in manifest")

        if not text:
            continue

        report_period = _detect_report_period(source_pdf, text)
        page_unit = _detect_page_unit(text)
        lines = text.split("\n")
        regions = _detect_section_regions(text)

        for region in regions:
            section_type = region["section_type"]
            table_unit = _detect_table_unit(text, region["start_line"])
            column_roles = _detect_column_roles(text, region["start_line"], region["end_line"])

            for line_idx in range(region["start_line"], min(region["end_line"], len(lines))):
                line = lines[line_idx]
                line_nums = list(NUMBER_PATTERN.finditer(line))
                if not line_nums:
                    continue

                for alias_str in sorted(alias_map.keys(), key=len, reverse=True):
                    if alias_str not in line:
                        continue

                    if alias_str in ("营业收入", "营收", "营业收入合计", "营业总收入", "主营业务收入"):
                        if any(fp in line for fp in REVENUE_FALSE_POSITIVES):
                            continue

                    unit = ""
                    unit_source = ""
                    use_unit = table_unit or page_unit

                    for num_idx, num_m in enumerate(line_nums):
                        num_full = num_m.group(0)
                        raw_num = num_m.group(1)
                        unit = num_m.group(2) or ""

                        if _is_standalone_year(line, num_m.start(1), num_m.end(1)):
                            continue

                        is_parenthesis_neg = bool(re.search(
                            r'[(（]\s*' + re.escape(raw_num) + r'\s*[）)]', num_full))
                        if is_parenthesis_neg and not raw_num.startswith("-"):
                            raw_num = "-" + raw_num

                        has_local_unit = bool(unit)
                        if not has_local_unit and use_unit:
                            unit = use_unit
                            unit_source = "table_header" if table_unit else "page_header"
                        else:
                            unit_source = "inline"

                        column_role = "unknown"
                        column_label = ""
                        if column_roles and len(line_nums) >= len(column_roles):
                            if num_idx < len(column_roles):
                                column_role = column_roles[num_idx]["role"]
                                column_label = column_roles[num_idx]["label"]
                        elif column_roles and len(line_nums) > 1:
                            for cr in column_roles:
                                pos_ratio = cr["position"]
                                if num_idx == 0:
                                    column_role = "current_period" if column_roles[0]["role"] == "current_period" else column_role
                                    column_label = column_roles[0]["label"]
                                    column_role = column_roles[0]["role"]

                        value, normalized, norm_unit, is_percent = _parse_number(raw_num, unit)

                        sniplines = lines[max(0, line_idx - 2):min(len(lines), line_idx + 3)]
                        snippet = " | ".join(s.strip() for s in sniplines)[:800]

                        for entry in alias_map[alias_str]:
                            metric_id, metric_name, matched_alias = entry

                            if metric_id == "revenue" and any(fp in snippet for fp in REVENUE_FALSE_POSITIVES):
                                continue

                            is_amount = metric_id in AMOUNT_METRICS_SET
                            if is_amount and is_percent:
                                continue

                            if is_amount and norm_unit == "CNY" and abs(normalized) > 0 and abs(normalized) < MIN_PLAUSIBLE_CNY_TABLE:
                                if "亿元" not in line and "亿元" not in unit:
                                    continue

                            confidence = "high"
                            review_reasons: list[str] = []
                            found_unit = unit or use_unit or ""
                            if found_unit:
                                pass

                            if norm_unit == "unknown":
                                confidence = "medium"
                                review_reasons.append("单位无法识别")
                            if unit_source in ("table_header", "page_header"):
                                review_reasons.append(f"unit_inferred_from_{unit_source}")
                                if confidence == "high":
                                    confidence = "medium"
                            if metric_id == "gross_margin" and not is_percent:
                                review_reasons.append("毛利率指标未检测到百分号")
                            if len(line_nums) > 1 and column_role == "unknown":
                                review_reasons.append("行内多数值但无法识别本期列")

                            needs_review = len(review_reasons) > 0

                            cid = generate_candidate_id(
                                metric_id, raw_num + (unit or ""), pdf_id, page_number, snippet)

                            key = (metric_id, raw_num, unit, pdf_id, page_number, snippet[:80])
                            if key in seen:
                                continue
                            seen.add(key)

                            candidates.append(MetricCandidate(
                                candidate_id=cid, metric_id=metric_id,
                                metric_name=metric_name, matched_alias=matched_alias,
                                raw_value=raw_num + (" " + unit if unit else ""),
                                value=value, value_unit_raw=unit,
                                value_normalized=normalized,
                                value_unit_normalized=norm_unit,
                                is_percent=is_percent,
                                report_period=report_period,
                                source_pdf=source_pdf, relative_path=relative_path,
                                pdf_id=pdf_id, page_number=page_number,
                                source_snippet=snippet,
                                confidence=confidence,
                                needs_review=needs_review,
                                review_reasons=review_reasons,
                                section_type=section_type,
                                section_name=section_type,
                                column_role=column_role,
                                column_label=column_label,
                                unit_source=unit_source,
                            ))

        for alias_str in sorted(alias_map.keys(), key=len, reverse=True):
            for alias_m in re.finditer(re.escape(alias_str), text):
                alias_start = alias_m.start()
                alias_end = alias_m.end()
                alias_line_idx = text[:alias_start].count("\n")

                in_region = False
                for region in regions:
                    if region["start_line"] <= alias_line_idx <= region["end_line"]:
                        in_region = True
                        break
                if in_region:
                    continue

                if alias_str in ("营业收入", "营收"):
                    line_check = lines[alias_line_idx] if alias_line_idx < len(lines) else ""
                    if any(fp in line_check for fp in REVENUE_FALSE_POSITIVES):
                        continue

                window_start = max(0, alias_start - 80)
                window_end = min(len(text), alias_end + 80)
                window = text[window_start:window_end]

                numbers = list(NUMBER_PATTERN.finditer(window))
                if not numbers:
                    continue

                for num_m in numbers:
                    num_full = num_m.group(0)
                    num_start = window_start + num_m.start()
                    num_end = window_start + num_m.end()

                    if _is_standalone_year(window, num_m.start(1), num_m.end(1)):
                        continue

                    raw_num = num_m.group(1)
                    unit = num_m.group(2) or ""

                    is_parenthesis_neg = bool(re.search(
                        r'[(（]\s*' + re.escape(raw_num) + r'\s*[）)]', num_full))
                    if is_parenthesis_neg and not raw_num.startswith("-"):
                        raw_num = "-" + raw_num

                    sniplines = _extract_snippet_lines(lines, alias_start, alias_end, num_start, num_end)
                    snippet = " | ".join(sniplines)[:500]

                    value, normalized, norm_unit, is_percent = _parse_number(raw_num, unit)

                    has_unit = bool(unit)
                    unit_inferred = False
                    if not has_unit and page_unit and not is_percent:
                        unit = page_unit
                        value, normalized, norm_unit, is_percent = _parse_number(raw_num, page_unit)
                        has_unit = True
                        unit_inferred = True

                    for entry in alias_map[alias_str]:
                        metric_id, metric_name, matched_alias = entry

                        if metric_id == "revenue" and any(fp in snippet for fp in REVENUE_FALSE_POSITIVES):
                            continue

                        confidence = _compute_confidence(
                            snippet, matched_alias, len(numbers),
                            has_unit, norm_unit, report_period,
                            is_percent, metric_id,
                        )
                        if unit_inferred and confidence == "high":
                            confidence = "medium"

                        review_reasons: list[str] = []
                        if confidence == "low":
                            review_reasons.append("置信度为 low")
                        if report_period == "unknown":
                            review_reasons.append("报告期无法识别")
                        if norm_unit == "unknown":
                            review_reasons.append("单位无法识别")
                        if unit_inferred:
                            review_reasons.append(f"unit_inferred_from_page: {page_unit}")
                        if len(numbers) > 1:
                            review_reasons.append(f"同一片段出现 {len(numbers)} 个数值")
                        if metric_id == "gross_margin" and not is_percent:
                            review_reasons.append("毛利率指标未检测到百分号")
                        needs_review = len(review_reasons) > 0

                        cid = generate_candidate_id(
                            metric_id, raw_num + (unit or ""), pdf_id, page_number, snippet,
                        )

                        key = (metric_id, raw_num, unit, pdf_id, page_number, snippet[:80])
                        if key in seen:
                            continue
                        seen.add(key)

                        candidates.append(MetricCandidate(
                            candidate_id=cid, metric_id=metric_id,
                            metric_name=metric_name, matched_alias=matched_alias,
                            raw_value=raw_num + (" " + unit if unit else ""),
                            value=value, value_unit_raw=unit,
                            value_normalized=normalized,
                            value_unit_normalized=norm_unit,
                            is_percent=is_percent,
                            report_period=report_period,
                            source_pdf=source_pdf, relative_path=relative_path,
                            pdf_id=pdf_id, page_number=page_number,
                            source_snippet=snippet,
                            confidence=confidence,
                            needs_review=needs_review,
                            review_reasons=review_reasons,
                        ))

    candidates.sort(key=lambda c: (
        c.relative_path,
        c.page_number,
        c.metric_id,
        c.source_snippet,
    ))
