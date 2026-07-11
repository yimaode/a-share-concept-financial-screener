import hashlib, json, re
from collections import Counter
from datetime import datetime
from pathlib import Path
from ..metric_extractor.extractor import _detect_report_period as period_fn

SECTION_PATTERNS = {
    "key_financial_data": ["主要会计数据和财务指标","主要会计数据","主要财务指标","公司主要会计数据和财务指标"],
    "income_statement": ["合并及母公司利润表","母公司利润表","合并利润表","利润表"],
    "balance_sheet": ["合并及母公司资产负债表","母公司资产负债表","合并资产负债表","资产负债表"],
    "cashflow_statement": ["合并及母公司现金流量表","母公司现金流量表","合并现金流量表","现金流量表"],
}
UNIT_PATTERN = re.compile(r"(?:除特别注明外[,，]?\s*)?(?:金额)?单位[：:为]\s*(?:人民币\s*)?(万元|亿元|亿|元)", re.IGNORECASE)

def _classify_section(text): 
    for st, pats in SECTION_PATTERNS.items():
        for p in pats:
            if p in text: return st
    return "unknown"

def _find_unit_nearby(page_text, _):
    """Return the page-level accounting unit used by an extracted table.

    Financial-report summary tables normally declare their unit immediately
    above the table (for example, ``单位：元 币种：人民币``).  pdfplumber
    extracts that declaration as page text rather than a table cell, so keep
    it as table metadata for the metric extractor.
    """
    matches = list(UNIT_PATTERN.finditer(page_text or ""))
    if not matches:
        return ("", "")
    return (matches[-1].group(1), "page_text")

def extract_pdf_tables(pdf_dir, output_dir):
    import pdfplumber
    pdf_files = sorted(p for p in pdf_dir.rglob("*") if p.is_file() and p.suffix.lower() == ".pdf")
    output_dir = Path(output_dir); output_dir.mkdir(parents=True, exist_ok=True)
    tables, pages_out, manifests, failed = [], [], [], []
    
    for pdf_path in pdf_files:
        try:
            with pdfplumber.open(str(pdf_path)) as pdf:
                file_bytes = pdf_path.read_bytes()
                pdf_id = f"pdf_{hashlib.sha256(file_bytes).hexdigest()[:12]}"
                rel = str(pdf_path.relative_to(pdf_dir))
                manifests.append({"pdf_id": pdf_id, "source_pdf": pdf_path.name,
                                  "relative_path": rel, "page_count": len(pdf.pages),
                                  "extract_status": "success", "error_message": ""})
                for pi, page in enumerate(pdf.pages):
                    page_text = page.extract_text() or ""
                    report_period = period_fn(pdf_path.name, page_text)
                    pages_out.append({"pdf_id":pdf_id,"source_pdf":pdf_path.name,"relative_path":rel,"page_number":pi+1,"text":page_text.strip(),"char_count":len(page_text),"extraction_method":"pdfplumber_text"})
                    pts = page.extract_tables()
                    if not pts: continue
                    for ti, pt in enumerate(pts):
                        if not pt or len(pt) < 2: continue
                        rows = [[str(c or "") for c in r] for r in pt]
                        st = _classify_section(page_text)
                        unit_raw, unit_source = _find_unit_nearby(page_text, rows)
                        tables.append({"table_id":f"tbl_{hashlib.sha256(f'{pdf_id}|{pi}|{ti}'.encode()).hexdigest()[:12]}","pdf_id":pdf_id,"source_pdf":pdf_path.name,"relative_path":rel,"report_period":report_period,"page_number":pi+1,"table_index":ti,"extraction_method":"pdfplumber_extract_table","row_count":len(rows),"column_count":len(rows[0]) if rows else 0,"rows":rows,"section_type":st,"section_name":st,"unit_raw":unit_raw,"unit_source":unit_source,"warnings":[]})
        except Exception as e:
            failed.append(f"{pdf_path.name}: {e}")
            manifests.append({"pdf_id": "", "source_pdf": pdf_path.name,
                              "relative_path": str(pdf_path.relative_to(pdf_dir)), "page_count": 0,
                              "extract_status": "failed", "error_message": str(e)})
    
    with (output_dir/"tables.jsonl").open("w",encoding="utf-8") as f:
        for t in tables: json.dump(t,f,ensure_ascii=False); f.write("\n")
    with (output_dir/"pages.jsonl").open("w",encoding="utf-8") as f:
        for p in pages_out: json.dump(p,f,ensure_ascii=False); f.write("\n")
    with (output_dir/"pdf_manifest.jsonl").open("w",encoding="utf-8") as f:
        for manifest in manifests: json.dump(manifest,f,ensure_ascii=False); f.write("\n")
    
    rpt = [f"# Table Extraction",f"PDF: {len(pdf_files)}",f"Tables: {len(tables)}",f"Pages: {len(pages_out)}"]
    if failed: rpt += [f"Failed: {len(failed)}"] + [f"- {x}" for x in failed]
    (output_dir/"table_extraction_report.md").write_text("\n".join(rpt),encoding="utf-8")
    return len(tables)
