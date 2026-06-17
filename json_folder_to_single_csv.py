from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def flatten_json(obj: Any, prefix: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}

    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, (dict, list)):
                flat.update(flatten_json(v, key))
            else:
                flat[key] = v
    elif isinstance(obj, list):
        # Keep list order by storing each element as indexed field.
        for i, v in enumerate(obj):
            key = f"{prefix}[{i}]"
            if isinstance(v, (dict, list)):
                flat.update(flatten_json(v, key))
            else:
                flat[key] = v
        if not obj:
            flat[prefix] = "[]"
    else:
        flat[prefix] = obj

    return flat


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert all JSON files under a folder into one CSV.")
    parser.add_argument("--input-root", type=Path, required=True, help="Folder containing JSON files.")
    parser.add_argument("--output-csv", type=Path, required=True, help="Output CSV file path.")
    args = parser.parse_args()

    input_root = args.input_root.resolve()
    output_csv = args.output_csv.resolve()
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    json_files = sorted(input_root.rglob("*.json"))
    rows: list[dict[str, Any]] = []
    all_fields: set[str] = set()

    for fp in json_files:
        try:
            content = json.loads(fp.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            rows.append(
                {
                    "__file__": str(fp.relative_to(input_root)),
                    "__parse_error__": str(exc),
                }
            )
            all_fields.update(rows[-1].keys())
            continue

        flat = flatten_json(content)
        flat["__file__"] = str(fp.relative_to(input_root))
        rows.append(flat)
        all_fields.update(flat.keys())

    fieldnames = sorted(all_fields)
    with output_csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"Done. files={len(json_files)} rows={len(rows)} output={output_csv}")


if __name__ == "__main__":
    main()
