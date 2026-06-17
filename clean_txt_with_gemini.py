from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import time
from pathlib import Path
from typing import Iterable

import requests


PROMPT_TEMPLATE = """你是一個嚴格的文字清理器。請把以下研究報告文字清理後輸出，規則如下：
1) 只保留「正文敘述內容」(段落、條列的敘述句)。
2) 移除所有表格內容與其殘留格式，包括但不限於：數字欄列、對齊空格造成的欄位、表頭、統計表、估值表、財務表、圖表座標數字、圖表資料點。
3) 移除所有免責聲明、利益衝突揭露、分析師認證、法規揭露、版權與轉載限制、聯絡資訊區塊。
4) 移除頁首頁尾、重複標題、頁碼、純版面符號。
5) 除了上述移除項目外，其餘正文盡量一字不漏保留，不要改寫、不要摘要、不要翻譯。
6) 只輸出清理後純文字，不要任何說明。

以下是原始文字：
-----
{text}
-----
"""


def split_text(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + max_chars, length)
        if end < length:
            # Prefer splitting on paragraph boundaries.
            split_at = text.rfind("\n\n", start, end)
            if split_at > start + (max_chars // 2):
                end = split_at + 2
            else:
                split_at = text.rfind("\n", start, end)
                if split_at > start + (max_chars // 2):
                    end = split_at + 1
        chunks.append(text[start:end])
        start = end
    return chunks


def iter_txt_files(root: Path) -> Iterable[Path]:
    yield from root.rglob("*.txt")


DISCLOSURE_PATTERNS = [
    r"disclosure",
    r"analyst certification",
    r"conflict of interest",
    r"does and seeks to do business",
    r"finra",
    r"not be associated persons",
    r"research as only a single factor",
    r"免責",
    r"揭露",
    r"版權",
    r"轉載",
    r"不得散布",
    r"for important disclosures",
    r"unless otherwise noted, all metrics are based on",
]


def post_filter_text(text: str) -> str:
    lines = text.splitlines()
    kept: list[str] = []
    for line in lines:
        s = line.strip()
        if not s:
            kept.append("")
            continue

        lowered = s.lower()
        if any(re.search(pat, lowered, flags=re.IGNORECASE) for pat in DISCLOSURE_PATTERNS):
            continue

        # Drop likely table residue lines composed mostly of symbols/numbers.
        alpha_count = sum(ch.isalpha() for ch in s)
        digit_count = sum(ch.isdigit() for ch in s)
        if alpha_count == 0 and digit_count >= 6:
            continue
        if re.fullmatch(r"[\s\-\+\|\.:;,()\[\]{}_/\\%$#@!~`=<>0-9]+", s):
            continue

        kept.append(s)

    # Collapse repeated blank lines.
    out: list[str] = []
    prev_blank = False
    for line in kept:
        is_blank = line == ""
        if is_blank and prev_blank:
            continue
        out.append(line)
        prev_blank = is_blank

    cleaned = "\n".join(out).strip()
    return cleaned + "\n" if cleaned else ""


def call_gemini(api_key: str, model: str, text: str, timeout: int = 120) -> str:
    model_path = model if model.startswith("models/") else f"models/{model}"
    url = f"https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": PROMPT_TEMPLATE.format(text=text)}]}],
        "generationConfig": {
            "temperature": 0,
            "topP": 0.95,
            "maxOutputTokens": 65536,
            "responseMimeType": "text/plain",
        },
    }
    headers = {"Content-Type": "application/json"}

    retry_waits = [2, 4, 8, 12]
    last_err = None
    for i, wait_s in enumerate(retry_waits, start=1):
        try:
            resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=timeout)
            if resp.status_code in (429, 500, 502, 503, 504):
                last_err = f"http {resp.status_code}: {resp.text[:500]}"
                time.sleep(wait_s)
                continue
            resp.raise_for_status()
            data = resp.json()
            candidates = data.get("candidates") or []
            if not candidates:
                raise RuntimeError(f"No candidates in response: {data}")
            parts = candidates[0].get("content", {}).get("parts", [])
            output_text = "".join(p.get("text", "") for p in parts).strip()
            # For chunks that are mostly tables/disclosures, empty output is acceptable.
            return (output_text + "\n") if output_text else ""
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)
            if i < len(retry_waits):
                time.sleep(wait_s)
                continue
            raise RuntimeError(f"Gemini API failed after retries: {last_err}") from exc

    raise RuntimeError(f"Gemini API failed: {last_err}")


def process_one_file(
    src_path: Path,
    input_root: Path,
    output_root: Path,
    api_key: str,
    model: str,
    chunk_chars: int,
    overwrite: bool,
) -> tuple[str, str, str]:
    rel = src_path.relative_to(input_root)
    dst_path = output_root / rel
    dst_path.parent.mkdir(parents=True, exist_ok=True)

    if dst_path.exists() and dst_path.stat().st_size > 0 and not overwrite:
        return ("SKIP", str(rel), "")

    try:
        raw_text = src_path.read_text(encoding="utf-8", errors="ignore")
        parts = split_text(raw_text, chunk_chars)
        cleaned_parts = [call_gemini(api_key, model, part) for part in parts]
        cleaned = "\n".join(p.strip() for p in cleaned_parts if p.strip()) + "\n"
        cleaned = post_filter_text(cleaned)
        dst_path.write_text(cleaned, encoding="utf-8")
        return ("OK", str(rel), "")
    except Exception as exc:  # noqa: BLE001
        return ("ERR", str(rel), str(exc))


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean TXT files with Gemini (remove tables/disclosures).")
    parser.add_argument("--input-root", type=Path, required=True, help="Root folder containing source TXT files.")
    parser.add_argument("--output-root", type=Path, required=True, help="Root folder for cleaned TXT files.")
    parser.add_argument("--api-key", type=str, default=os.getenv("GEMINI_API_KEY", ""), help="Gemini API key.")
    parser.add_argument("--model", type=str, default="gemini-2.0-flash", help="Gemini model id.")
    parser.add_argument("--limit", type=int, default=0, help="Optional max number of files to process (0=all).")
    parser.add_argument("--name-contains", type=str, default="", help="Only process files whose path contains text.")
    parser.add_argument("--chunk-chars", type=int, default=30000, help="Max chars sent per Gemini request.")
    parser.add_argument("--sleep-ms", type=int, default=0, help="Sleep milliseconds between processed files.")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel workers.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing output files.")
    args = parser.parse_args()

    if not args.api_key:
        raise ValueError("Missing API key. Pass --api-key or set GEMINI_API_KEY.")

    input_root = args.input_root.resolve()
    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    files = sorted(iter_txt_files(input_root))
    if args.name_contains:
        key = args.name_contains.lower()
        files = [p for p in files if key in str(p).lower()]
    if args.limit > 0:
        files = files[: args.limit]
    total = len(files)
    if total == 0:
        print(f"No TXT files found under: {input_root}")
        return

    ok_count = 0
    skip_count = 0
    err_count = 0
    print(f"Found {total} TXT files to clean. workers={args.workers}")

    completed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = [
            executor.submit(
                process_one_file,
                src_path,
                input_root,
                output_root,
                args.api_key,
                args.model,
                args.chunk_chars,
                args.overwrite,
            )
            for src_path in files
        ]

        for fut in concurrent.futures.as_completed(futures):
            status, rel, err = fut.result()
            completed += 1
            if status == "OK":
                ok_count += 1
                print(f"[{completed}/{total}] OK   {rel}")
            elif status == "SKIP":
                skip_count += 1
                print(f"[{completed}/{total}] SKIP {rel}")
            else:
                err_count += 1
                print(f"[{completed}/{total}] ERR  {rel} -> {err}")

            if args.sleep_ms > 0:
                time.sleep(args.sleep_ms / 1000.0)

    print(f"Done. output={output_root} total={total} ok={ok_count} skip={skip_count} err={err_count}")


if __name__ == "__main__":
    main()
