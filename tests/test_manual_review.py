import json, csv
from pathlib import Path
from ds_finance_concept.manual_review.review_pack import prepare_metric_review_pack, import_manual_metric_values


def _w(path, data):
    if isinstance(data, list):
        path.write_text("\n".join(json.dumps(d, ensure_ascii=False) for d in data) + "\n", encoding="utf-8")
    else:
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def test_review_pack_generates_xlsx(tmp_path):
    cf = tmp_path / "c.jsonl"
    _w(cf, [{"candidate_id": "mc_1", "metric_id": "revenue", "report_period": "2024A",
             "value_normalized": 5e9, "value_unit_normalized": "CNY", "confidence": "high",
             "needs_review": False, "source_pdf": "r.pdf", "page_number": 5,
             "source_snippet": "revenue", "section_type": "income_statement"}])
    tf = tmp_path / "t.jsonl"; tf.write_text("", encoding="utf-8")
    prepare_metric_review_pack("603486", cf, tf, tmp_path / "out")
    assert (tmp_path / "out/metric_review_pack.xlsx").exists()
    assert (tmp_path / "out/manual_metric_values.template.csv").exists()


def test_template_csv_header(tmp_path):
    cf = tmp_path / "c.jsonl"
    _w(cf, [{"candidate_id": "mc_1", "metric_id": "revenue", "report_period": "2024A",
             "value_normalized": 5e9, "value_unit_normalized": "CNY", "confidence": "high",
             "needs_review": False, "source_pdf": "r.pdf", "page_number": 5,
             "source_snippet": "test", "section_type": "income_statement"}])
    tf = tmp_path / "t.jsonl"; tf.write_text("", encoding="utf-8")
    prepare_metric_review_pack("603486", cf, tf, tmp_path / "out")
    with open(tmp_path / "out/manual_metric_values.template.csv") as f:
        r = csv.DictReader(f)
        assert "company_code" in r.fieldnames
        assert "review_status" in r.fieldnames


def test_import_approved_only(tmp_path):
    mv = tmp_path / "mv.csv"
    with open(mv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["company_code","metric_id","report_period","value","unit","source_pdf","page_number",
                     "source_type","source_table_id","source_row_index","source_column_index",
                     "evidence_text","reviewer","review_status","review_note"])
        w.writerow(["603486","revenue","2024A","153.2","亿元","2024A.pdf","5","table","","","","rev up","u","approved",""])
        w.writerow(["603486","revenue","2024H1","100","亿元","2024H1.pdf","3","table","","","","rev","u","rejected",""])
    a, r, e = import_manual_metric_values(mv, tmp_path / "out.jsonl", tmp_path / "rpt.md")
    assert a == 1
    assert r == 1
    assert e == 0


def test_import_rejects_invalid(tmp_path):
    mv = tmp_path / "mv.csv"
    with open(mv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["company_code","metric_id","report_period","value","unit","source_pdf","page_number",
                     "source_type","source_table_id","source_row_index","source_column_index",
                     "evidence_text","reviewer","review_status","review_note"])
        w.writerow(["603486","bad_metric","bad_period","abc","bad_unit","","x","","","","","","u","bad_status",""])
    a, r, e = import_manual_metric_values(mv, tmp_path / "out.jsonl", tmp_path / "rpt.md")
    assert a == 0
    assert e > 0


def test_import_wan_conversion(tmp_path):
    mv = tmp_path / "mv.csv"
    with open(mv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["company_code","metric_id","report_period","value","unit","source_pdf","page_number",
                     "source_type","source_table_id","source_row_index","source_column_index",
                     "evidence_text","reviewer","review_status","review_note"])
        w.writerow(["603486","revenue","2024A","1234.56","万元","r.pdf","5","","","","","test","u","approved",""])
    a, _, _ = import_manual_metric_values(mv, tmp_path / "out.jsonl", tmp_path / "rpt.md")
    assert a == 1
    with open(tmp_path / "out.jsonl") as f:
        out = json.loads(f.readline())
    assert out["value_normalized"] == 12345600.0


def test_import_yi_conversion(tmp_path):
    mv = tmp_path / "mv.csv"
    with open(mv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["company_code","metric_id","report_period","value","unit","source_pdf","page_number",
                     "source_type","source_table_id","source_row_index","source_column_index",
                     "evidence_text","reviewer","review_status","review_note"])
        w.writerow(["603486","revenue","2024A","5.6","亿元","r.pdf","5","","","","","test","u","approved",""])
    a, _, _ = import_manual_metric_values(mv, tmp_path / "out.jsonl", tmp_path / "rpt.md")
    assert a == 1
    with open(tmp_path / "out.jsonl") as f:
        out = json.loads(f.readline())
    assert out["value_normalized"] == 560000000.0


def test_import_percent(tmp_path):
    mv = tmp_path / "mv.csv"
    with open(mv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["company_code","metric_id","report_period","value","unit","source_pdf","page_number",
                     "source_type","source_table_id","source_row_index","source_column_index",
                     "evidence_text","reviewer","review_status","review_note"])
        w.writerow(["603486","gross_margin","2024A","35.8","%","r.pdf","5","","","","","test","u","approved",""])
    a, _, _ = import_manual_metric_values(mv, tmp_path / "out.jsonl", tmp_path / "rpt.md")
    assert a == 1
    with open(tmp_path / "out.jsonl") as f:
        out = json.loads(f.readline())
    assert out["is_percent"] is True


def test_import_duplicate_same_merged(tmp_path):
    mv = tmp_path / "mv.csv"
    with open(mv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["company_code","metric_id","report_period","value","unit","source_pdf","page_number",
                     "source_type","source_table_id","source_row_index","source_column_index",
                     "evidence_text","reviewer","review_status","review_note"])
        w.writerow(["603486","revenue","2024A","100","亿元","r.pdf","5","","","","","same text","u","approved",""])
        w.writerow(["603486","revenue","2024A","100","亿元","r.pdf","5","","","","","same text","u","approved",""])
    a, _, _ = import_manual_metric_values(mv, tmp_path / "out.jsonl", tmp_path / "rpt.md")
    assert a == 1
