import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from requests import HTTPError
from pypdf import PdfReader


DEFAULT_MODEL = "gemini-2.5-flash"
MODEL_FALLBACKS = ["gemini-2.5-flash", "gemini-2.0-flash"]
DEFAULT_API_KEY = "AIzaSyAxULZlWSxzrGyIF2SmrklEaT5wtqhEWQA"
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_PDF_PATH = BASE_DIR / "train" / "KGI" / "KGI1" / "6274_2025_11_17_C_TW.pdf"


def extract_pdf_text(pdf_path: Path, max_pages: int | None = None) -> str:
    reader = PdfReader(str(pdf_path))
    pages = []
    for idx, page in enumerate(reader.pages, start=1):
        if max_pages is not None and idx > max_pages:
            break
        text = page.extract_text() or ""
        pages.append(f"\n\n=== PAGE {idx} ===\n{text}")
    return "".join(pages).strip()


def build_prompt(pdf_text: str) -> str:
    return f"""
You are a financial research information extraction engine.
Extract structured data from the report text below.

Rules:
1) Return ONLY valid JSON (no markdown, no explanation).
2) Keep every requested key even if missing.
3) Use null when information is unavailable.
4) Keep numbers as numbers when possible.
5) Keep currency/unit hints in adjacent *_unit fields when needed.
6) If there are multiple values, use arrays.
7) Key output information MUST be in Traditional Chinese (zh-TW), not Simplified Chinese.
8) Keep proper nouns/tickers/models unchanged when needed (e.g., 6274, NVIDIA, ASIC), but explanations, summaries, status labels, and qualitative bullets should be Traditional Chinese.
9) For classification labels, prefer Traditional Chinese terms:
   - beat_or_miss: "優於預期" / "符合預期" / "低於預期"
   - cheap_or_expensive: "偏便宜" / "合理" / "偏昂貴"
   - investment rating text should use Traditional Chinese style terms (e.g., "買進", "增加持股", "中立", "減碼").
10) extraction_quality.notes MUST be written in Traditional Chinese (zh-TW).

Required JSON schema:
{{
  "report_info": {{
    "report_date": null,
    "author": null,
    "research_firm": null
  }},
  "stock_identity": {{
    "company_name": null,
    "ticker": null,
    "exchange": null
  }},
  "investment_rating": {{
    "current_rating": null,
    "previous_rating": null,
    "rating_change": null
  }},
  "valuation_metrics": {{
    "target_price": null,
    "target_price_unit": null,
    "current_price": null,
    "current_price_unit": null,
    "implied_upside_pct": null
  }},
  "bullish_arguments": [],
  "bearish_risks": [],
  "industry_outlook": null,
  "management_guidance": [],
  "financial_estimates": {{
    "years": [],
    "revenue": [],
    "revenue_unit": null,
    "gross_margin_pct": [],
    "operating_margin_pct": [],
    "net_margin_pct": []
  }},
  "eps_growth": {{
    "years": [],
    "eps": [],
    "eps_unit": null,
    "yoy_growth_pct": []
  }},
  "quarterly_performance_tracker": {{
    "recent_quarters": [],
    "actual_vs_consensus": [],
    "beat_or_miss": []
  }},
  "product_mix_changes": [],
  "capacity_utilization": {{
    "current_utilization_pct": null,
    "expansion_plan": null
  }},
  "inventory_level": {{
    "inventory_status": null,
    "days_inventory": null,
    "trend": null
  }},
  "valuation_multiples": {{
    "current_pe": null,
    "current_pb": null,
    "historical_pe_range": null,
    "historical_pb_range": null,
    "cheap_or_expensive": null
  }},
  "peer_benchmarking": [],
  "dividend_policy": {{
    "payout_ratio_pct": null,
    "dividend_yield_pct": null,
    "dividend_trend": null
  }},
  "extraction_quality": {{
    "confidence_score_0_to_1": null,
    "notes": null
  }}
}}

Report text:
\"\"\"{pdf_text}\"\"\"
""".strip()


def parse_model_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def call_gemini_once(api_key: str, model: str, prompt: str, timeout_sec: int = 240) -> dict:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "response_mime_type": "application/json",
        },
    }

    response = requests.post(url, json=payload, timeout=timeout_sec)
    response.raise_for_status()
    data = response.json()

    candidates = data.get("candidates", [])
    if not candidates:
        raise RuntimeError(f"Gemini returned no candidates: {json.dumps(data, ensure_ascii=False)}")

    parts = candidates[0].get("content", {}).get("parts", [])
    if not parts:
        raise RuntimeError(f"Gemini returned empty parts: {json.dumps(data, ensure_ascii=False)}")

    text = "".join(part.get("text", "") for part in parts).strip()
    if not text:
        raise RuntimeError(f"Gemini returned empty text: {json.dumps(data, ensure_ascii=False)}")
    return parse_model_json(text)


def call_gemini_with_retries(
    api_key: str,
    model: str,
    prompt: str,
    timeout_sec: int = 240,
    max_retries: int = 3,
) -> dict:
    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            return call_gemini_once(api_key=api_key, model=model, prompt=prompt, timeout_sec=timeout_sec)
        except HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            last_error = e
            if status not in (429, 500, 502, 503, 504):
                raise
            if attempt < max_retries:
                sleep_sec = min(2**attempt, 8)
                print(f"[{model}] temporary HTTP {status}, retrying in {sleep_sec}s...")
                time.sleep(sleep_sec)
        except Exception as e:  # noqa: BLE001
            last_error = e
            if attempt < max_retries:
                sleep_sec = min(2**attempt, 8)
                print(f"[{model}] temporary error, retrying in {sleep_sec}s...")
                time.sleep(sleep_sec)
    raise RuntimeError(f"Failed calling Gemini model '{model}' after retries: {last_error}") from last_error


def call_gemini_with_fallback(api_key: str, preferred_model: str, prompt: str) -> tuple[str, dict]:
    model_candidates = [preferred_model] + [m for m in MODEL_FALLBACKS if m != preferred_model]
    last_error: Exception | None = None
    for model in model_candidates:
        try:
            result = call_gemini_with_retries(api_key=api_key, model=model, prompt=prompt)
            return model, result
        except Exception as e:  # noqa: BLE001
            last_error = e
            print(f"Model '{model}' failed: {e}")
    raise RuntimeError(f"All candidate models failed. Last error: {last_error}") from last_error


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract financial report fields from a PDF using Gemini.")
    parser.add_argument(
        "--pdf",
        default=str(DEFAULT_PDF_PATH),
        help=f"Path to input PDF file (default: {DEFAULT_PDF_PATH}).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path to output JSON file. Default: same folder as PDF, same filename with .json",
    )
    parser.add_argument(
        "--api-key",
        default=DEFAULT_API_KEY,
        help="Gemini API key. Defaults to built-in key in this script.",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Gemini model name (default: {DEFAULT_MODEL}).")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Only read first N pages (for quick test / quota saving).",
    )
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    output_path = Path(args.output) if args.output else pdf_path.with_suffix(".json")
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    pdf_text = extract_pdf_text(pdf_path, max_pages=args.max_pages)
    if not pdf_text:
        raise RuntimeError("No extractable text found in PDF.")

    prompt = build_prompt(pdf_text)
    used_model, extracted = call_gemini_with_fallback(
        api_key=args.api_key,
        preferred_model=args.model,
        prompt=prompt,
    )

    final_payload = {
        "meta": {
            "source_pdf": str(pdf_path),
            "model": used_model,
            "processed_at_utc": datetime.now(timezone.utc).isoformat(),
        },
        "data": extracted,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(final_payload, f, ensure_ascii=False, indent=2)

    print(f"Done. JSON written to: {output_path}")


if __name__ == "__main__":
    try:
        main()
    except ModuleNotFoundError as e:
        missing = getattr(e, "name", "unknown")
        print(f"Missing dependency: {missing}")
        print("Install with: py -3 -m pip install pypdf requests")
        sys.exit(1)
