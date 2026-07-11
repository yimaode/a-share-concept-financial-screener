import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .errors import PdfWriteError
from .manifest import PdfManifest, PdfPage


def write_manifest_jsonl(manifests: list[PdfManifest], output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output_file.open("w", encoding="utf-8") as f:
            for m in manifests:
                record = asdict(m)
                json.dump(record, f, ensure_ascii=False)
                f.write("\n")
    except Exception as e:
        raise PdfWriteError(f"Failed to write manifest to {output_file}: {e}") from e


def write_pages_jsonl(pages: list[PdfPage], output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output_file.open("w", encoding="utf-8") as f:
            for p in pages:
                record = asdict(p)
                json.dump(record, f, ensure_ascii=False)
                f.write("\n")
    except Exception as e:
        raise PdfWriteError(f"Failed to write pages to {output_file}: {e}") from e


def write_full_text(
    manifests: list[PdfManifest],
    pages: list[PdfPage],
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    pages_by_pdf: dict[str, list[PdfPage]] = {}
    for p in pages:
        pages_by_pdf.setdefault(p.pdf_id, []).append(p)

    for manifest in manifests:
        if manifest.extract_status == "failed":
            continue

        pdf_id = manifest.pdf_id
        pdf_pages = sorted(pages_by_pdf.get(pdf_id, []), key=lambda x: x.page_number)

        lines: list[str] = []
        for page in pdf_pages:
            lines.append(f"{'=' * 5} PAGE {page.page_number} {'=' * 5}")
            if page.text:
                lines.append(page.text)
            lines.append("")

        output_file = output_dir / f"{pdf_id}.txt"
        try:
            output_file.write_text("\n".join(lines), encoding="utf-8")
        except Exception as e:
            raise PdfWriteError(f"Failed to write full text to {output_file}: {e}") from e


def write_extraction_report(
    manifests: list[PdfManifest],
    output_file: Path,
    output_dir: Path,
) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)

    success = sum(1 for m in manifests if m.extract_status == "success")
    partial = sum(1 for m in manifests if m.extract_status == "partial")
    failed = sum(1 for m in manifests if m.extract_status == "failed")
    needs_ocr = sum(1 for m in manifests if m.needs_ocr)
    total_pages = sum(m.page_count for m in manifests)
    total_chars = sum(m.total_char_count for m in manifests)

    lines: list[str] = []
    lines.append("# PDF 文本抽取报告")
    lines.append("")
    lines.append(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append("## 总览")
    lines.append("")
    lines.append(f"| 指标 | 数值 |")
    lines.append(f"| --- | --- |")
    lines.append(f"| PDF 总数 | {len(manifests)} |")
    lines.append(f"| 成功 | {success} |")
    lines.append(f"| 部分成功 | {partial} |")
    lines.append(f"| 失败 | {failed} |")
    lines.append(f"| 需要 OCR | {needs_ocr} |")
    lines.append(f"| 总页数 | {total_pages} |")
    lines.append(f"| 总字符数 | {total_chars} |")
    lines.append("")

    if failed > 0:
        lines.append("## 失败文件")
        lines.append("")
        for m in manifests:
            if m.extract_status == "failed":
                lines.append(f"- **{m.relative_path}**: {m.error_message}")
        lines.append("")

    if needs_ocr > 0:
        lines.append("## 需要 OCR 的文件")
        lines.append("")
        for m in manifests:
            if m.needs_ocr:
                lines.append(f"- **{m.relative_path}** ({m.text_page_count}/{m.page_count} 页有文本)")
        lines.append("")

    lines.append("## 输出文件")
    lines.append("")
    lines.append(f"- Manifest: `{output_dir / 'pdf_manifest.jsonl'}`")
    lines.append(f"- Pages: `{output_dir / 'pages.jsonl'}`")
    lines.append(f"- Full text: `{output_dir / 'full_text/'}`")
    lines.append(f"- 本报告: `{output_file}`")

    try:
        output_file.write_text("\n".join(lines), encoding="utf-8")
    except Exception as e:
        raise PdfWriteError(f"Failed to write report to {output_file}: {e}") from e
