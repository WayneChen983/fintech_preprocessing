# Fintech Preprocessing

此專案用於金融研究報告前處理，重點放在只保留程式碼版本控制，不上傳大型資料檔。

## 功能

- PDF 轉 TXT（排除表格內容）
- 使用 Gemini 進一步清理文字（移除表格殘留、免責聲明等）
- 將 `MonthlyRet_Project.csv` 的 `Flag_1m` 回填到 JSON
- 將 JSON 匯出成單一 CSV（完整版與乾淨版）

## 主要腳本

- `pdf_to_txt_excluding_tables.py`
- `clean_txt_with_gemini.py`
- `add_flag_1m_to_json.py`
- `json_folder_to_single_csv.py`
- `json_with_flag_1m_clean_export.py`

## 環境需求

- Python 3.10+
- 套件：`pdfplumber`、`requests`

安裝：

```bash
pip install pdfplumber requests
```

## 快速使用

### 1) PDF 轉 TXT（排除表格）

```bash
python pdf_to_txt_excluding_tables.py --input-root . --output-root txt_without_tables
```

### 2) Gemini 清理 TXT

```bash
python clean_txt_with_gemini.py ^
  --input-root txt_without_tables ^
  --output-root txt_cleaned_gemini ^
  --api-key YOUR_GEMINI_API_KEY ^
  --model gemini-2.5-flash ^
  --workers 4
```

### 3) JSON 新增 `flag_1m`

```bash
python add_flag_1m_to_json.py ^
  --input-root . ^
  --csv-path MonthlyRet_Project.csv ^
  --output-root json_with_flag_1m
```

### 4) 匯出單一 CSV（乾淨版）

```bash
python json_with_flag_1m_clean_export.py ^
  --input-root json_with_flag_1m ^
  --output-csv json_with_flag_1m_clean.csv
```

## 版本控制注意事項

`.gitignore` 已排除 PDF/JSON/TXT/CSV/ZIP 與資料資料夾，只會追蹤程式碼與必要文件。
