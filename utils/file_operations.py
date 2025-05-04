# utils/file_operations.py
import os
import sys
import time
import subprocess
from typing import Tuple, List, Dict, Set, Optional, Any # ★ typing をインポート ★
from PySide6.QtWidgets import QMessageBox, QWidget # ★ QWidget をインポート ★

# 画像ローダー関数をインポート
try:
    from .image_loader import get_image_dimensions
except ImportError:
     print("エラー: utils.image_loader のインポートに失敗しました。")
     def get_image_dimensions(path: str) -> Tuple[Optional[int], Optional[int]]: return None, None

try:
    import send2trash
except ImportError:
    print("エラー: send2trash ライブラリが見つかりません。`pip install Send2Trash` を実行してください。")
    send2trash = None

# ★ 型エイリアス ★
FileInfoResult = Tuple[str, str, str] # (size_str, mod_time_str, dimensions_str)
ErrorDict = Dict[str, str] # {'path': str, 'error': str}
DeleteResult = Tuple[int, List[ErrorDict], Set[str]] # (deleted_count, errors, deleted_paths_set)

def get_file_info(file_path: str) -> FileInfoResult:
    """
    指定されたファイルの基本情報（サイズ、更新日時、解像度）を取得する。
    """
    file_size: str = "N/A"
    mod_time: str = "N/A"
    dimensions: str = "N/A"

    try:
        stat_info: os.stat_result = os.stat(file_path)
        file_size_bytes: int = stat_info.st_size
        if file_size_bytes < 1024: file_size = f"{file_size_bytes} B"
        elif file_size_bytes < 1024**2: file_size = f"{file_size_bytes/1024:.1f} KB"
        elif file_size_bytes < 1024**3: file_size = f"{file_size_bytes/(1024**2):.1f} MB"
        else: file_size = f"{file_size_bytes/(1024**3):.1f} GB"
        mod_time = time.strftime('%Y/%m/%d %H:%M', time.localtime(stat_info.st_mtime))

        width: Optional[int]
        height: Optional[int]
        width, height = get_image_dimensions(file_path)
        if width is not None and height is not None:
            dimensions = f"{width}x{height}"
        else:
            dimensions = "読込エラー"

    except FileNotFoundError:
        print(f"警告: ファイル情報取得エラー - ファイルが見つかりません ({file_path})")
        file_size, mod_time, dimensions = "削除済?", "削除済?", "削除済?"
    except PermissionError:
        print(f"警告: ファイル情報取得エラー - アクセス権がありません ({file_path})")
        file_size, mod_time, dimensions = "アクセス不可", "アクセス不可", "アクセス不可"
    except Exception as e:
        print(f"警告: ファイル情報取得エラー ({file_path}): {e}")
        file_size, mod_time = "エラー", "エラー"
        if dimensions == "N/A": dimensions = "エラー"

    return file_size, mod_time, dimensions

def delete_files_to_trash(file_paths: List[str], parent_widget: Optional[QWidget] = None) -> DeleteResult:
    """指定されたファイルパスのリストをゴミ箱に移動する。"""
    if send2trash is None:
        QMessageBox.critical(parent_widget, "エラー", "send2trash ライブラリが見つかりません。\n削除機能を使用できません。")
        return 0, [{"path": "N/A", "error": "send2trashライブラリがありません"}], set()

    # 重複を除外しソート
    unique_files_to_delete: List[str] = sorted(list(set(file_paths)))
    if not unique_files_to_delete:
        QMessageBox.information(parent_widget, "情報", "削除対象のファイルが選択されていません。")
        return 0, [], set()

    num_files: int = len(unique_files_to_delete)
    message: str = f"{num_files} 個のファイルを選択しました。\nこれらのファイルをゴミ箱に移動しますか？\n\n"
    display_limit: int = 10
    if num_files <= display_limit:
        message += "\n".join([os.path.basename(f) for f in unique_files_to_delete])
    else:
        message += "\n".join([os.path.basename(f) for f in unique_files_to_delete[:display_limit]])
        message += f"\n...他 {num_files - display_limit} 個"

    reply = QMessageBox.question(parent_widget, "削除の確認", message,
                                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                 QMessageBox.StandardButton.No)

    if reply == QMessageBox.StandardButton.Yes:
        print(f"{num_files} 個のファイルをゴミ箱へ移動します...")
        deleted_count: int = 0
        errors: List[ErrorDict] = []
        files_actually_deleted: Set[str] = set()
        for file_path in unique_files_to_delete:
            try:
                normalized_path: str = os.path.normpath(file_path)
                if os.path.exists(normalized_path):
                    send2trash.send2trash(normalized_path)
                    print(f"  削除成功: {normalized_path}")
                    deleted_count += 1
                    files_actually_deleted.add(normalized_path)
                else:
                    err_msg: str = "ファイルが見つかりません"
                    print(f"  削除スキップ: {err_msg} {normalized_path}")
                    errors.append({'path': normalized_path, 'error': err_msg})
            except PermissionError as e: err_msg = f"アクセス権がありません: {e}"; print(f"  削除エラー: {file_path} - {err_msg}"); errors.append({'path': file_path, 'error': err_msg})
            except OSError as e: err_msg = f"OSエラー: {e}"; print(f"  削除エラー: {file_path} - {err_msg}"); errors.append({'path': file_path, 'error': err_msg})
            except Exception as e: err_msg = f"予期せぬエラー: {e}"; print(f"  削除エラー: {file_path} - {err_msg}"); errors.append({'path': file_path, 'error': err_msg})

        if errors:
            error_details: str = "\n".join([f"- {os.path.basename(e['path'])}: {e['error']}" for e in errors[:5]])
            if len(errors) > 5:
                error_details += f"\n...他 {len(errors) - 5} 件のエラー"
            QMessageBox.warning(parent_widget, "削除エラー",
                                f"{len(errors)} 個のファイルの削除中にエラーが発生しました:\n{error_details}")
        if deleted_count > 0:
            QMessageBox.information(parent_widget, "削除完了", f"{deleted_count} 個のファイルをゴミ箱に移動しました。")

        return deleted_count, errors, files_actually_deleted
    else:
        print("削除がキャンセルされました.")
        return 0, [], set()

def open_file_external(file_path: str, parent_widget: Optional[QWidget] = None) -> None:
    """指定されたファイルを外部アプリケーションで開く。"""
    if not file_path or not os.path.exists(file_path):
        print(f"ファイルが見つかりません: {file_path}")
        QMessageBox.warning(parent_widget, "エラー", f"ファイルが見つかりません:\n{file_path}")
        return
    try:
        normalized_path: str = os.path.normpath(file_path)
        if os.name == 'nt': os.startfile(normalized_path)
        elif sys.platform == 'darwin': subprocess.call(['open', normalized_path])
        else: subprocess.call(['xdg-open', normalized_path])
        print(f"ファイルを開きました: {file_path}")
    except FileNotFoundError:
        QMessageBox.critical(parent_widget, "エラー", f"ファイルを開くコマンドが見つかりません。\nOSを確認してください。")
    except Exception as e:
        print(f"ファイルを開けませんでした ({file_path}): {e}")
        QMessageBox.critical(parent_widget, "エラー", f"ファイルを開けませんでした:\n{file_path}\n\n{e}")
