import argparse
import importlib
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


DEFAULT_FOLDER_URL = "https://drive.google.com/drive/folders/1f3i_81pFOrgZnqQonpGcRgD5-Qe34z_G?usp=drive_link"
DEFAULT_OUTPUT_DIR = r"D:\Fintech\Project\train"
TARGET_FILENAME = "train1.zip"


def ensure_gdown_installed():
	"""Install gdown automatically if it is not available."""
	try:
		importlib.import_module("gdown")
	except ImportError:
		print("gdown 尚未安裝，正在自動安裝...", flush=True)
		subprocess.check_call([sys.executable, "-m", "pip", "install", "gdown"])


def find_target_file(root: Path, file_name: str) -> Path | None:
	wanted_normalized = re.sub(r"[^a-z0-9]", "", file_name.lower())
	fallback_match = None

	for path in root.rglob(file_name):
		if path.is_file():
			return path

	for path in root.rglob("*.zip"):
		if not path.is_file():
			continue
		current_normalized = re.sub(r"[^a-z0-9]", "", path.name.lower())
		if current_normalized == wanted_normalized:
			return path
		if fallback_match is None and wanted_normalized in current_normalized:
			fallback_match = path

	if fallback_match is not None:
		print(
			f"找不到完全同名檔案 {file_name}，改用最接近的檔案: {fallback_match.name}",
			flush=True,
		)
		return fallback_match

	return None


def download_and_extract(
	folder_url: str,
	output_dir: Path,
	target_filename: str = TARGET_FILENAME,
	keep_zip: bool = False,
	clean_output: bool = True,
) -> Path:
	ensure_gdown_installed()
	gdown = importlib.import_module("gdown")

	output_dir.mkdir(parents=True, exist_ok=True)

	if clean_output:
		for item in output_dir.iterdir():
			if item.is_dir():
				shutil.rmtree(item)
			else:
				item.unlink(missing_ok=True)

	with tempfile.TemporaryDirectory() as temp_dir:
		temp_path = Path(temp_dir)
		print(f"開始下載 Google Drive 資料夾: {folder_url}")

		gdown.download_folder(
			url=folder_url,
			output=str(temp_path),
			quiet=False,
			use_cookies=False,
		)

		downloaded_zip = find_target_file(temp_path, target_filename)
		if downloaded_zip is None:
			raise FileNotFoundError(
				f"在提供的 Google Drive 資料夾中找不到 {target_filename}，請確認檔名與分享權限。"
			)

		local_zip_path = output_dir / target_filename
		shutil.copy2(downloaded_zip, local_zip_path)
		print(f"已下載至: {local_zip_path}")

	print("開始解壓縮與整理資料夾結構...")
	with tempfile.TemporaryDirectory() as extract_temp:
		extract_root = Path(extract_temp) / "extracted"
		extract_root.mkdir(parents=True, exist_ok=True)

		with zipfile.ZipFile(local_zip_path, "r") as zf:
			zf.extractall(extract_root)

		top_level_items = [p for p in extract_root.iterdir()]
		source_root = extract_root
		if len(top_level_items) == 1 and top_level_items[0].is_dir():
			source_root = top_level_items[0]

		for item in source_root.iterdir():
			destination = output_dir / item.name
			if destination.exists():
				if destination.is_dir():
					shutil.rmtree(destination)
				else:
					destination.unlink()
			shutil.move(str(item), str(destination))

	if not keep_zip:
		local_zip_path.unlink(missing_ok=True)
		print("已刪除下載的 zip 檔。")

	print(f"完成，輸出目錄只保留最底層資料: {output_dir}")
	return output_dir


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="下載 Google Drive 資料夾中的 train1.zip，並解壓縮到指定本地資料夾。"
	)
	parser.add_argument(
		"--folder-url",
		default=DEFAULT_FOLDER_URL,
		help="Google Drive 資料夾連結",
	)
	parser.add_argument(
		"--output-dir",
		default=DEFAULT_OUTPUT_DIR,
		help="本地輸出資料夾 (預設: D:\\Fintech\\Project\\train)",
	)
	parser.add_argument(
		"--file-name",
		default=TARGET_FILENAME,
		help="要下載的 zip 檔名 (預設: train1.zip)",
	)
	parser.add_argument(
		"--keep-zip",
		action="store_true",
		help="保留下載的 zip 檔 (預設不保留)",
	)
	parser.add_argument(
		"--no-clean-output",
		action="store_true",
		help="不要先清空輸出資料夾 (預設會先清空，確保只保留最新解壓內容)",
	)
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	download_and_extract(
		folder_url=args.folder_url,
		output_dir=Path(args.output_dir),
		target_filename=args.file_name,
		keep_zip=args.keep_zip,
		clean_output=not args.no_clean_output,
	)


if __name__ == "__main__":
	main()
