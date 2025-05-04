# utils/file_operations.py
import os
import sys
import time
import subprocess
from typing import Tuple, List, Dict, Set, Optional, Any
from PySide6.QtWidgets import QMessageBox, QWidget
from PIL import Image, UnidentifiedImageError # ★ Pillow と UnidentifiedImageError をインポート ★
from PIL.ExifTags import TAGS

# image_loader は直接使わない

try:
    import send2trash
except ImportError:
    print("エラー: send2trash ライブラリが見つかりません。`pip install Send2Trash` を実行してください。")
    send2trash = None

# 型エイリアス (変更なし)
FileInfoResult = Tuple[str, str, str, str] # (size_str, mod_time_str, dimensions_str, exif_date_str)
ErrorDict = Dict[str, str]
DeleteResult = Tuple[int, List[ErrorDict], Set[str]]

# --- Exif 読み取りヘルパー関数 (変更なし) ---
def get_exif_data(img: Image.Image) -> Optional[Dict[str, Any]]:
    """Pillow ImageオブジェクトからExifデータを辞書として取得する"""
    try:
        exif_raw = img._getexif()
        if exif_raw is None:
            return None
        exif_data: Dict[str, Any] = {}
        for tag_id, value in exif_raw.items():
            tag_name = TAGS.get(tag_id, tag_id)
            exif_data[tag_name] = value
        return exif_data
    except AttributeError:
        return None # Exif非対応フォーマットなど
    except Exception as e:
        # print(f"警告: Exifデータの読み取り中にエラー: {e}") # デバッグ用
        return None

def get_exif_datetime_original(exif_data: Optional[Dict[str, Any]]) -> Optional[str]:
    """Exifデータ辞書から DateTimeOriginal (撮影日時) を取得する"""
    if exif_data is None:
        return None
    datetime_original = exif_data.get('DateTimeOriginal')
    if isinstance(datetime_original, str):
        if len(datetime_original) == 19 and datetime_original[4] == ':' and datetime_original[7] == ':':
             return datetime_original
    return None

# --- ファイル情報取得関数 ---
def get_file_info(file_path: str) -> FileInfoResult:
    """
    指定されたファイルの基本情報（サイズ、更新日時、解像度、撮影日時）を取得する。
    ファイルハンドルが確実に閉じられるように with を使用。
    """
    file_size_str: str = "N/A"
    mod_time_str: str = "N/A"
    dimensions_str: str = "N/A"
    exif_date_str: str = "N/A"

    try:
        # --- ファイル基本情報 (os.stat) ---
        stat_info: os.stat_result = os.stat(file_path)
        file_size_bytes: int = stat_info.st_size
        if file_size_bytes < 1024: file_size_str = f"{file_size_bytes} B"
        elif file_size_bytes < 1024**2: file_size_str = f"{file_size_bytes/1024:.1f} KB"
        elif file_size_bytes < 1024**3: file_size_str = f"{file_size_bytes/(1024**2):.1f} MB"
        else: file_size_str = f"{file_size_bytes/(1024**3):.1f} GB"
        mod_time_str = time.strftime('%Y/%m/%d %H:%M', time.localtime(stat_info.st_mtime))

        # --- 解像度と撮影日時 (Pillowで取得) ---
        try:
            # ★★★ with ステートメントを使用してファイルを開く ★★★
            with Image.open(file_path) as img:
                # 画像フォーマットによってはロードが必要な場合がある
                # img.load() # 必要であれば呼び出すが、通常は属性アクセス時にロードされる
                width, height = img.size
                dimensions_str = f"{width}x{height}"

                # Exifデータの取得と撮影日時の抽出
                exif_data = get_exif_data(img) # 開いた Image オブジェクトを渡す
                dt_original = get_exif_datetime_original(exif_data)
                if dt_original:
                    exif_date_str = dt_original
            # ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★

        except FileNotFoundError:
             # os.stat は成功したが、Image.open で失敗 (タイミングの問題)
             dimensions_str = "読込エラー"
             exif_date_str = "読込エラー"
             print(f"警告: Pillowでの画像オープン中にファイルが見つかりません ({os.path.basename(file_path)})")
        except UnidentifiedImageError:
             # Pillow が認識できない画像形式
             dimensions_str = "形式不明"
             exif_date_str = "形式不明"
             print(f"情報: Pillowが画像形式を認識できません ({os.path.basename(file_path)})")
        except Exception as img_err:
            # その他のPillow関連エラー (破損ファイルなど)
            dimensions_str = "読込エラー"
            exif_date_str = "読込エラー"
            print(f"警告: Pillowでの画像情報取得エラー ({os.path.basename(file_path)}): {img_err}")

    except FileNotFoundError:
        # os.stat 自体が失敗
        print(f"警告: ファイル情報取得エラー - ファイルが見つかりません ({os.path.basename(file_path)})")
        file_size_str, mod_time_str, dimensions_str, exif_date_str = "削除済?", "削除済?", "削除済?", "削除済?"
    except PermissionError:
        print(f"警告: ファイル情報取得エラー - アクセス権がありません ({os.path.basename(file_path)})")
        file_size_str, mod_time_str, dimensions_str, exif_date_str = "アクセス不可", "アクセス不可", "アクセス不可", "アクセス不可"
    except Exception as e:
        # os.stat での予期せぬエラー
        print(f"警告: ファイル情報取得エラー (os.stat) ({os.path.basename(file_path)}): {e}")
        file_size_str, mod_time_str = "エラー", "エラー"
        # dimensions_str, exif_date_str は N/A のままか、Pillowエラーで上書きされる

    return file_size_str, mod_time_str, dimensions_str, exif_date_str

# --- 削除・ファイルを開く関数 (変更なし) ---
def delete_files_to_trash(file_paths: List[str], parent_widget: Optional[QWidget] = None) -> DeleteResult:
    if send2trash is None:
        QMessageBox.critical(parent_widget, "エラー", "send2trash ライブラリが見つかりません。\n削除機能を使用できません。")
        return 0, [{"path": "N/A", "error": "send2trashライブラリがありません"}], set()
    unique_files_to_delete: List[str] = sorted(list(set(file_paths)))
    if not unique_files_to_delete:
        QMessageBox.information(parent_widget, "情報", "削除対象のファイルが選択されていません。")
        return 0, [], set()
    num_files: int = len(unique_files_to_delete)
    message: str = f"{num_files} 個のファイルを選択しました。\nこれらのファイルをゴミ箱に移動しますか？\n\n"
    display_limit: int = 10
    if num_files <= display_limit: message += "\n".join([os.path.basename(f) for f in unique_files_to_delete])
    else: message += "\n".join([os.path.basename(f) for f in unique_files_to_delete[:display_limit]]) + f"\n...他 {num_files - display_limit} 個"
    reply = QMessageBox.question(parent_widget, "削除の確認", message, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
    if reply == QMessageBox.StandardButton.Yes:
        print(f"{num_files} 個のファイルをゴミ箱へ移動します...")
        deleted_count: int = 0; errors: List[ErrorDict] = []; files_actually_deleted: Set[str] = set()
        for file_path in unique_files_to_delete:
            try:
                normalized_path: str = os.path.normpath(file_path)
                if os.path.exists(normalized_path):
                    send2trash.send2trash(normalized_path); print(f"  削除成功: {normalized_path}"); deleted_count += 1; files_actually_deleted.add(normalized_path)
                else: err_msg: str = "ファイルが見つかりません"; print(f"  削除スキップ: {err_msg} {normalized_path}"); errors.append({'path': normalized_path, 'error': err_msg})
            except PermissionError as e: err_msg = f"アクセス権がありません: {e}"; print(f"  削除エラー: {file_path} - {err_msg}"); errors.append({'path': file_path, 'error': err_msg})
            except OSError as e: err_msg = f"OSエラー: {e}"; print(f"  削除エラー: {file_path} - {err_msg}"); errors.append({'path': file_path, 'error': err_msg})
            except Exception as e: err_msg = f"予期せぬエラー: {e}"; print(f"  削除エラー: {file_path} - {err_msg}"); errors.append({'path': file_path, 'error': err_msg})
        if errors:
            error_details: str = "\n".join([f"- {os.path.basename(e['path'])}: {e['error']}" for e in errors[:5]]);
            if len(errors) > 5: error_details += f"\n...他 {len(errors) - 5} 件のエラー"
            QMessageBox.warning(parent_widget, "削除エラー", f"{len(errors)} 個のファイルの削除中にエラーが発生しました:\n{error_details}")
        if deleted_count > 0: QMessageBox.information(parent_widget, "削除完了", f"{deleted_count} 個のファイルをゴミ箱に移動しました。")
        return deleted_count, errors, files_actually_deleted
    else: print("削除がキャンセルされました."); return 0, [], set()

def open_file_external(file_path: str, parent_widget: Optional[QWidget] = None) -> None:
    if not file_path or not os.path.exists(file_path): print(f"ファイルが見つかりません: {file_path}"); QMessageBox.warning(parent_widget, "エラー", f"ファイルが見つかりません:\n{file_path}"); return
    try:
        normalized_path: str = os.path.normpath(file_path)
        if os.name == 'nt': os.startfile(normalized_path)
        elif sys.platform == 'darwin': subprocess.call(['open', normalized_path])
        else: subprocess.call(['xdg-open', normalized_path])
        print(f"ファイルを開きました: {file_path}")
    except FileNotFoundError: QMessageBox.critical(parent_widget, "エラー", f"ファイルを開くコマンドが見つかりません。\nOSを確認してください。")
    except Exception as e: print(f"ファイルを開けませんでした ({file_path}): {e}"); QMessageBox.critical(parent_widget, "エラー", f"ファイルを開けませんでした:\n{file_path}\n\n{e}")
