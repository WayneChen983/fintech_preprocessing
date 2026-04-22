# Fintech Preprocessing

此專案用於金融研究報告（PDF）前處理：下載資料、抽取文字、呼叫 Gemini LLM，並輸出結構化 JSON，供後續模型訓練使用。

## 功能

- 下載 Google Drive 資料夾內容並整理輸出（`Download_Data.py`）
- 讀取券商 PDF 報告並抽取文字
- 呼叫 Gemini API，輸出固定欄位 JSON（`pdf_to_json_gemini.py`）
- 內建重試與模型 fallback（`gemini-2.5-flash` -> `gemini-2.0-flash`）

## 專案結構

- `Download_Data.py`：下載/解壓資料腳本
- `pdf_to_json_gemini.py`：PDF -> JSON 結構化腳本
- `train/`：原始與處理後資料（本機資料夾，不上傳）

## 環境需求

- Python 3.10+
- 套件：`pypdf`、`requests`、`gdown`

安裝方式：

```bash
py -3 -m pip install pypdf requests gdown
```

## 使用方式

### 1) 下載資料（可選）

```bash
py -3 Download_Data.py --output-dir "c:\Users\bl515-pub\Downloads\Fintech_preprossing\train"
```

### 2) PDF 轉 JSON（預設路徑可直接執行）

```bash
py -3 pdf_to_json_gemini.py
```

或指定檔案：

```bash
py -3 pdf_to_json_gemini.py --pdf "你的pdf路徑" --output "你的json路徑"
```

測試前幾頁（節省配額）：

```bash
py -3 pdf_to_json_gemini.py --max-pages 8
```

## 輸出欄位

腳本會輸出以下核心欄位：

- `report_info`
- `stock_identity`
- `investment_rating`
- `valuation_metrics`
- `bullish_arguments`
- `bearish_risks`
- `industry_outlook`
- `management_guidance`
- `financial_estimates`
- `eps_growth`
- `quarterly_performance_tracker`
- `product_mix_changes`
- `capacity_utilization`
- `inventory_level`
- `valuation_multiples`
- `peer_benchmarking`
- `dividend_policy`
- `extraction_quality`

## 注意事項

- JSON 關鍵輸出資訊預設使用繁體中文（zh-TW）
- `train/` 為資料集與產出資料，已設定不納入版本控制

---

## English

This project preprocesses financial research reports (PDF): it downloads source files, extracts report text, calls Gemini LLM, and outputs structured JSON for downstream model training.

### Features

- Download and organize files from a Google Drive folder (`Download_Data.py`)
- Extract text from broker research PDFs
- Convert report content into a fixed JSON schema (`pdf_to_json_gemini.py`)
- Built-in retry and model fallback (`gemini-2.5-flash` -> `gemini-2.0-flash`)

### Quick Start

Install dependencies:

```bash
py -3 -m pip install pypdf requests gdown
```

Run with default paths:

```bash
py -3 pdf_to_json_gemini.py
```

Run with custom paths:

```bash
py -3 pdf_to_json_gemini.py --pdf "path/to/report.pdf" --output "path/to/output.json"
```

Test only first N pages to save quota:

```bash
py -3 pdf_to_json_gemini.py --max-pages 8
```

### Notes

- Key output information is expected in Traditional Chinese (zh-TW)
- `train/` is excluded from version control
