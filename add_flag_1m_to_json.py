from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


def load_flag_map(csv_path: Path) -> dict[tuple[str, str], int]:
    encodings = ("utf-8-sig", "utf-8", "cp950", "big5")
    last_error: Exception | None = None

    for enc in encodings:
        try:
            mapping: dict[tuple[str, str], int] = {}
            with csv_path.open("r", encoding=enc, newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    month = (row.get("Month") or "").strip()
                    ticker = (row.get("ticker") or "").strip()
                    flag_raw = (row.get("Flag_1m") or "").strip()
                    if not month or not ticker or flag_raw == "":
                        continue
                    try:
                        flag_val = int(float(flag_raw))
                    except ValueError:
                        continue
                    mapping[(month, ticker)] = flag_val
            return mapping
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            continue

    raise RuntimeError(f"Failed to read CSV with known encodings: {last_error}")


def extract_month(text: str) -> str | None:
    if not text:
        return None
    text = text.strip()

    # ISO-like: 2025-11-13 / 2025/11/13 / 2025.11.13
    m = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", text)
    if m:
        return f"{m.group(1)}{int(m.group(2)):02d}"

    # Fallback if day is absent but year-month exists.
    m = re.search(r"(\d{4})\D+(\d{1,2})", text)
    if m:
        return f"{m.group(1)}{int(m.group(2)):02d}"

    # Compact date token: 20260129 -> 202601
    m = re.search(r"(20\d{2})(\d{2})\d{2}", text)
    if m:
        return f"{m.group(1)}{m.group(2)}"

    # Two-digit year token: 251210 -> assume 20YYMMDD
    m = re.search(r"(?<!\d)(\d{2})(\d{2})\d{2}(?!\d)", text)
    if m:
        return f"20{m.group(1)}{m.group(2)}"

    return None


def extract_ticker(text: str) -> str | None:
    if not text:
        return None
    m = re.search(r"(\d{4,6})", text)
    if not m:
        return None
    return m.group(1)


def process_json_file(src: Path, dst: Path, flag_map: dict[tuple[str, str], int]) -> tuple[str, str]:
    try:
        content = json.loads(src.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return ("ERR", f"read/parse failed: {exc}")

    data = content.get("data")
    if not isinstance(data, dict):
        return ("ERR", "missing object field: data")

    report_date = str(data.get("report_date", "")).strip()
    raw_ticker = str(data.get("ticker", "")).strip()
    month = extract_month(report_date) or extract_month(src.name)
    ticker = extract_ticker(raw_ticker) or extract_ticker(src.name)

    if not month or not ticker:
        data["flag_1m"] = None
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
        return ("MISS", "cannot derive month/ticker")

    data["flag_1m"] = flag_map.get((month, ticker))

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
    if data["flag_1m"] is None:
        return ("MISS", f"no CSV row for ({month}, {ticker})")
    return ("OK", "")


def main() -> None:
    parser = argparse.ArgumentParser(description="Add flag_1m into JSON files by Month+ticker lookup.")
    parser.add_argument("--input-root", type=Path, required=True, help="Root folder containing source JSON files.")
    parser.add_argument("--csv-path", type=Path, required=True, help="CSV containing Month,ticker,Flag_1m.")
    parser.add_argument("--output-root", type=Path, required=True, help="Root folder for new JSON files.")
    args = parser.parse_args()

    input_root = args.input_root.resolve()
    csv_path = args.csv_path.resolve()
    output_root = args.output_root.resolve()

    output_root.mkdir(parents=True, exist_ok=True)
    flag_map = load_flag_map(csv_path)

    json_files = sorted(
        p for p in input_root.rglob("*.json") if output_root not in p.parents and p != output_root
    )

    total = len(json_files)
    ok = 0
    miss = 0
    err = 0

    print(f"Found {total} JSON files.")
    for idx, src in enumerate(json_files, start=1):
        rel = src.relative_to(input_root)
        dst = output_root / rel
        status, info = process_json_file(src, dst, flag_map)
        if status == "OK":
            ok += 1
            print(f"[{idx}/{total}] OK   {rel}")
        elif status == "MISS":
            miss += 1
            print(f"[{idx}/{total}] MISS {rel} -> {info}")
        else:
            err += 1
            print(f"[{idx}/{total}] ERR  {rel} -> {info}")

    print(f"Done. output={output_root} total={total} ok={ok} miss={miss} err={err}")


if __name__ == "__main__":
    main()
