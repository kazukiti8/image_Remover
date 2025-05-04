# utils/file_operations.py
import os
import sys
import time
import subprocess
# cv2 は get_file_info では使わなくなったので削除してもOK
# import cv2
from PySide6.QtWidgets import QMessageBox

# ★ 画像ローダー関数 (次元取得用) をインポート ★
try:
    # 同じ utils パッケージ内の image_loader をインポート
    from .image_loader import get_image_dimensions
except ImportError:
     print("エラー: utils.image_loader のインポートに失敗しました。")
     # ダミー関数
     def get_image_dimensions(path): return None, None

try:
    import send2trash
except ImportError:
    print("エラー: send2trash ライブラリが見つかりません。`pip install Send2Trash` を実行してください。")
    send2trash = None

def get_file_info(file_path):
    """
    指定されたファイルの基本情報（サイズ、更新日時、解像度）を取得する。
    解像度取得に image_loader を使用。
    """
    file_size = "N/A"; mod_time = "N/A"; dimensions = "N/A"

    try:
        # ファイルサイズと更新日時
        stat_info = os.stat(file_path)
        file_size_bytes = stat_info.st_size
        if file_size_bytes < 1024: file_size = f"{file_size_bytes} B"
        elif file_size_bytes < 1024**2: file_size = f"{file_size_bytes/1024:.1f} KB"
        elif file_size_bytes < 1024**3: file_size = f"{file_size_bytes/(1024**2):.1f} MB"
        else: file_size = f"{file_size_bytes/(1024**3):.1f} GB"
        mod_time = time.strftime('%Y/%m/%d %H:%M', time.localtime(stat_info.st_mtime))

        # ★ 解像度取得 (image_loader を使用) ★
        width, height = get_image_dimensions(file_path)
        if width is not None and height is not None:
            dimensions = f"{width}x{height}"
        else:
            # get_image_dimensions 内でエラーが出力されるのでここでは警告不要
            dimensions = "読込エラー"

    except FileNotFoundError:
        print(f"警告: ファイル情報取得エラー - ファイルが見つかりません ({file_path})")
        file_size, mod_time, dimensions = "削除済?", "削除済?", "削除済?"
    except PermissionError:
        print(f"警告: ファイル情報取得エラー - アクセス権がありません ({file_path})")
        file_size, mod_time, dimensions = "アクセス不可", "アクセス不可", "アクセス不可"
    except Exception as e:
        # statに関するその他のエラー
        print(f"警告: ファイル情報取得エラー ({file_path}): {e}")
        file_size, mod_time = "エラー", "エラー"
        if dimensions == "N/A": # まだN/Aなら一般的なエラー表示
             dimensions = "エラー"

    return file_size, mod_time, dimensions

def delete_files_to_trash(file_paths, parent_widget=None):
    """指定されたファイルパスのリストをゴミ箱に移動する。"""
    if send2trash is None:
        QMessageBox.critical(parent_widget, "エラー", "send2trash ライブラリが見つかりません。\n削除機能を使用できません。")
        return 0, [{"path": "N/A", "error": "send2trashライブラリがありません"}], set()

    unique_files_to_delete = sorted(list(set(file_paths)))
    if not unique_files_to_delete:
        QMessageBox.information(parent_widget, "情報", "削除対象のファイルが選択されていません。")
        return 0, [], set()

    num_files = len(unique_files_to_delete)
    message = f"{num_files} 個のファイルを選択しました。\nこれらのファイルをゴミ箱に移動しますか？\n\n"
    display_limit = 10
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
        deleted_count = 0; errors = []; files_actually_deleted = set()
        for file_path in unique_files_to_delete:
            try:
                normalized_path = os.path.normpath(file_path)
                if os.path.exists(normalized_path):
                    send2trash.send2trash(normalized_path)
                    print(f"  削除成功: {normalized_path}")
                    deleted_count += 1
                    files_actually_deleted.add(normalized_path)
                else:
                    err_msg = "ファイルが見つかりません"
                    print(f"  削除スキップ: {err_msg} {normalized_path}")
                    errors.append({'path': normalized_path, 'error': err_msg})
            except PermissionError as e: err_msg = f"アクセス権がありません: {e}"; print(f"  削除エラー: {file_path} - {err_msg}"); errors.append({'path': file_path, 'error': err_msg})
            except OSError as e: err_msg = f"OSエラー: {e}"; print(f"  削除エラー: {file_path} - {err_msg}"); errors.append({'path': file_path, 'error': err_msg})
            except Exception as e: err_msg = f"予期せぬエラー: {e}"; print(f"  削除エラー: {file_path} - {err_msg}"); errors.append({'path': file_path, 'error': err_msg})

        # --- ★★★ 修正箇所 ★★★ ---
        # エラーメッセージ表示部分を複数行に分割
        if errors:
            error_details = "\n".join([f"- {os.path.basename(e['path'])}: {e['error']}" for e in errors[:5]])
            # エラーが5件より多い場合に追記
            if len(errors) > 5:
                error_details += f"\n...他 {len(errors) - 5} 件のエラー"
            # メッセージボックスで警告表示
            QMessageBox.warning(parent_widget, "削除エラー",
                                f"{len(errors)} 個のファイルの削除中にエラーが発生しました:\n{error_details}")
        # --- ★★★★★★★★★★★★★ ---

        if deleted_count > 0:
            QMessageBox.information(parent_widget, "削除完了", f"{deleted_count} 個のファイルをゴミ箱に移動しました。")

        return deleted_count, errors, files_actually_deleted
    else:
        print("削除がキャンセルされました.")
        return 0, [], set()

def open_file_external(file_path, parent_widget=None):
    """指定されたファイルを外部アプリケーションで開く。"""
    if not file_path or not os.path.exists(file_path):
        print(f"ファイルが見つかりません: {file_path}")
        QMessageBox.warning(parent_widget, "エラー", f"ファイルが見つかりません:\n{file_path}")
        return
    try:
        normalized_path = os.path.normpath(file_path)
        if os.name == 'nt': # Windows
            os.startfile(normalized_path)
        elif sys.platform == 'darwin': # macOS
            subprocess.call(['open', normalized_path])
        else: # Linux and other Unix-like
            subprocess.call(['xdg-open', normalized_path])
        print(f"ファイルを開きました: {file_path}")
    except FileNotFoundError:
        QMessageBox.critical(parent_widget, "エラー", f"ファイルを開くコマンドが見つかりません。\nOSを確認してください。")
    except Exception as e:
        print(f"ファイルを開けませんでした ({file_path}): {e}")
        QMessageBox.critical(parent_widget, "エラー", f"ファイルを開けませんでした:\n{file_path}\n\n{e}")

