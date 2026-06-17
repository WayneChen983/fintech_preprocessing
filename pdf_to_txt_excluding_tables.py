from __future__ import annotations

import argparse
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable

import pdfplumber
from pdfplumber.utils import extract_text


def overlaps(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return max(ax0, bx0) < min(ax1, bx1) and max(ay0, by0) < min(ay1, by1)


def filter_table_chars(page: pdfplumber.page.Page) -> list[dict]:
    tables = page.find_tables()
    if not tables:
        return list(page.chars)

    table_bboxes = [table.bbox for table in tables]
    kept_chars: list[dict] = []
    for ch in page.chars:
        char_bbox = (ch["x0"], ch["top"], ch["x1"], ch["bottom"])
        if any(overlaps(char_bbox, tbox) for tbox in table_bboxes):
            continue
        kept_chars.append(ch)
    return kept_chars


def pdf_to_text_without_tables(pdf_path: Path) -> str:
    page_texts: list[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            filtered_chars = filter_table_chars(page)
            page_text = extract_text(filtered_chars, layout=True) or ""
            page_texts.append(page_text.rstrip())
    return "\n\n".join(page_texts).strip() + "\n"


def iter_pdfs(root: Path) -> Iterable[Path]:
    yield from root.rglob("*.pdf")
    yield from root.rglob("*.PDF")


def process_one(input_root: str, output_root: str, pdf_path_str: str) -> tuple[str, str, str]:
    input_root_path = Path(input_root)
    output_root_path = Path(output_root)
    pdf_path = Path(pdf_path_str)
    rel = pdf_path.relative_to(input_root_path)
    txt_path = (output_root_path / rel).with_suffix(".txt")
    txt_path.parent.mkdir(parents=True, exist_ok=True)

    # Resume-friendly: skip files that already have output.
    if txt_path.exists() and txt_path.stat().st_size > 0:
        return ("SKIP", str(rel), "")

    try:
        text = pdf_to_text_without_tables(pdf_path)
        txt_path.write_text(text, encoding="utf-8")
        return ("OK", str(rel), "")
    except Exception as exc:
        return ("ERR", str(rel), str(exc))


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert PDFs to TXT while removing table content.")
    parser.add_argument("--input-root", type=Path, default=Path.cwd(), help="Root folder containing PDFs.")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path.cwd() / "txt_without_tables",
        help="Root folder for generated TXT files.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=max((os.cpu_count() or 2) - 1, 1),
        help="Number of worker processes for parallel conversion.",
    )
    args = parser.parse_args()

    input_root = args.input_root.resolve()
    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    pdf_files = sorted(set(iter_pdfs(input_root)))
    if not pdf_files:
        print(f"No PDF files found in: {input_root}")
        return

    print(f"Found {len(pdf_files)} PDF files. Using {args.workers} workers.")
    completed = 0
    ok_count = 0
    skip_count = 0
    err_count = 0

    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = [
            executor.submit(process_one, str(input_root), str(output_root), str(pdf_path))
            for pdf_path in pdf_files
        ]
        for fut in as_completed(futures):
            status, rel, err = fut.result()
            completed += 1
            if status == "OK":
                ok_count += 1
                print(f"[{completed}/{len(pdf_files)}] OK   {rel}")
            elif status == "SKIP":
                skip_count += 1
                print(f"[{completed}/{len(pdf_files)}] SKIP {rel}")
            else:
                err_count += 1
                print(f"[{completed}/{len(pdf_files)}] ERR  {rel} -> {err}")

    print(
        f"Done. output={output_root} total={len(pdf_files)} ok={ok_count} skip={skip_count} err={err_count}"
    )


if __name__ == "__main__":
    main()
