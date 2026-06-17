from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def to_json_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export standardized JSON files to a clean single CSV.")
    parser.add_argument("--input-root", type=Path, required=True, help="Folder containing JSON files.")
    parser.add_argument("--output-csv", type=Path, required=True, help="Output CSV path.")
    args = parser.parse_args()

    input_root = args.input_root.resolve()
    output_csv = args.output_csv.resolve()
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    fields = [
        "__file__",
        "meta.source_pdf",
        "meta.model",
        "meta.processed_at_utc",
        "data.report_date",
        "data.report_source",
        "data.company_name",
        "data.ticker",
        "data.industry",
        "data.flag_1m",
        "data.rating.original",
        "data.rating.mapped",
        "data.rating.change",
        "data.price.current",
        "data.price.target",
        "data.price.expected_return",
        "data.analyst",
        "data.forecast.eps",
        "data.forecast.revenue",
        "data.revision.eps_revision",
        "data.revision.revenue_revision",
        "data.revision.margin_trend",
        "data.operation.inventory",
        "data.operation.margin_trend",
        "data.operation.product_mix",
        "data.operation.catalyst",
        "data.operation.risk",
        "data.catalyst",
        "data.risk",
        "data.esg",
        "data.operation.esg",
    ]

    rows = []
    for fp in sorted(input_root.rglob("*.json")):
        try:
            content = json.loads(fp.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            rows.append({"__file__": str(fp.relative_to(input_root)), "__parse_error__": str(exc)})
            continue

        meta = content.get("meta", {}) if isinstance(content.get("meta"), dict) else {}
        data = content.get("data", {}) if isinstance(content.get("data"), dict) else {}
        rating = data.get("rating", {}) if isinstance(data.get("rating"), dict) else {}
        price = data.get("price", {}) if isinstance(data.get("price"), dict) else {}
        forecast = data.get("forecast", {}) if isinstance(data.get("forecast"), dict) else {}
        revision = data.get("revision", {}) if isinstance(data.get("revision"), dict) else {}
        operation = data.get("operation", {}) if isinstance(data.get("operation"), dict) else {}

        row = {
            "__file__": str(fp.relative_to(input_root)),
            "meta.source_pdf": to_json_text(meta.get("source_pdf")),
            "meta.model": to_json_text(meta.get("model")),
            "meta.processed_at_utc": to_json_text(meta.get("processed_at_utc")),
            "data.report_date": to_json_text(data.get("report_date")),
            "data.report_source": to_json_text(data.get("report_source")),
            "data.company_name": to_json_text(data.get("company_name")),
            "data.ticker": to_json_text(data.get("ticker")),
            "data.industry": to_json_text(data.get("industry")),
            "data.flag_1m": to_json_text(data.get("flag_1m")),
            "data.rating.original": to_json_text(rating.get("original")),
            "data.rating.mapped": to_json_text(rating.get("mapped")),
            "data.rating.change": to_json_text(rating.get("change")),
            "data.price.current": to_json_text(price.get("current")),
            "data.price.target": to_json_text(price.get("target")),
            "data.price.expected_return": to_json_text(price.get("expected_return")),
            "data.analyst": to_json_text(data.get("analyst")),
            "data.forecast.eps": to_json_text(forecast.get("eps")),
            "data.forecast.revenue": to_json_text(forecast.get("revenue")),
            "data.revision.eps_revision": to_json_text(revision.get("eps_revision")),
            "data.revision.revenue_revision": to_json_text(revision.get("revenue_revision")),
            "data.revision.margin_trend": to_json_text(revision.get("margin_trend")),
            "data.operation.inventory": to_json_text(operation.get("inventory")),
            "data.operation.margin_trend": to_json_text(operation.get("margin_trend")),
            "data.operation.product_mix": to_json_text(operation.get("product_mix")),
            "data.operation.catalyst": to_json_text(operation.get("catalyst")),
            "data.operation.risk": to_json_text(operation.get("risk")),
            "data.catalyst": to_json_text(data.get("catalyst")),
            "data.risk": to_json_text(data.get("risk")),
            "data.esg": to_json_text(data.get("esg")),
            "data.operation.esg": to_json_text(operation.get("esg")),
        }
        rows.append(row)

    with output_csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"Done. rows={len(rows)} output={output_csv}")


if __name__ == "__main__":
    main()
