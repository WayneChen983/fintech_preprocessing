import argparse
import importlib
import re
import subprocess
import sys
from pathlib import Path


DEFAULT_FILE_URL = "https://drive.google.com/file/d/1hF0ORomDSi3YcmvJX3QZPNYiue1Lt_q4/view?usp=drive_link"
DEFAULT_OUTPUT = "train_3.zip"


def ensure_gdown_installed() -> None:
    try:
        importlib.import_module("gdown")
    except ImportError:
        print("gdown 未安裝，正在自動安裝...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "gdown"])


def extract_file_id(file_url: str) -> str | None:
    match = re.search(r"/d/([a-zA-Z0-9_-]+)", file_url)
    if match:
        return match.group(1)
    return None


def download_file(file_url: str, output_path: Path) -> Path:
    ensure_gdown_installed()
    gdown = importlib.import_module("gdown")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    file_id = extract_file_id(file_url)

    print(f"開始下載: {file_url}")
    if file_id:
        result = gdown.download(
            id=file_id,
            output=str(output_path),
            quiet=False,
            fuzzy=True,
            use_cookies=False,
        )
    else:
        result = gdown.download(
            url=file_url,
            output=str(output_path),
            quiet=False,
            fuzzy=True,
            use_cookies=False,
        )

    if not result:
        raise RuntimeError("下載失敗，請確認連結權限是否為可存取。")

    final_path = Path(result).resolve()
    print(f"下載完成: {final_path}")
    return final_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="下載指定的 Google Drive 檔案。")
    parser.add_argument(
        "--url",
        default=DEFAULT_FILE_URL,
        help="Google Drive 檔案連結",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help="輸出檔案路徑（預設: train_3.zip）",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    download_file(args.url, Path(args.output))


if __name__ == "__main__":
    main()
