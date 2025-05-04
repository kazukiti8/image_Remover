# utils/file_operations.py
import os
import time
import cv2
from PySide6.QtWidgets import QMessageBox # 確認ダイアログ用にインポート

try:
    import send2trash
except ImportError:
    print("エラー: send2trash ライブラリが見つかりません。`pip install Send2Trash` を実行してください。")
    send2trash = None

def get_file_info(file_path):
    """指定されたファイルの基本情報（サイズ、更新日時、解像度）を取得する"""
    file_size = "N/A"
    mod_time = "N/A"
    dimensions = "N/A"
    try:
        # ファイルサイズと更新日時
        stat_info = os.stat(file_path)
        file_size_bytes = stat_info.st_size
        if file_size_bytes < 1024: file_size = f"{file_size_bytes} B"
        elif file_size_bytes < 1024**2: file_size = f"{file_size_bytes/1024:.1f} KB"
        elif file_size_bytes < 1024**3: file_size = f"{file_size_bytes/(1024**2):.1f} MB"
        else: file_size = f"{file_size_bytes/(1024**3):.1f} GB"
        mod_time = time.strftime('%Y/%m/%d %H:%M', time.localtime(stat_info.st_mtime))

        # 解像度取得 (画像を開く)
        img = cv2.imread(file_path)
        if img is not None:
            h, w = img.shape[:2]
            dimensions = f"{w}x{h}"
        else:
             print(f"警告: 解像度取得のため画像読み込み失敗 ({file_path})")

    except Exception as e:
        print(f"警告: ファイル情報/解像度取得エラー ({file_path}): {e}")

    return file_size, mod_time, dimensions

def delete_files_to_trash(file_paths, parent_widget=None):
    """
    指定されたファイルパスのリストをゴミ箱に移動する。
    確認ダイアログを表示し、結果(成功数, エラーリスト)を返す。
    """
    if send2trash is None:
        QMessageBox.critical(parent_widget, "エラー", "send2trash ライブラリが見つかりません。\n削除機能を使用できません。")
        return 0, ["send2trashライブラリがありません"]

    unique_files_to_delete = sorted(list(set(file_paths))) # 重複削除

    if not unique_files_to_delete:
        QMessageBox.information(parent_widget, "情報", "削除対象のファイルが選択されていません。")
        return 0, []

    # --- 確認ダイアログを表示 ---
    num_files = len(unique_files_to_delete)
    message = f"{num_files} 個のファイルを選択しました。\n"
    message += "これらのファイルをゴミ箱に移動しますか？\n\n"
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
        deleted_count = 0
        errors = []
        files_actually_deleted = set()

        # --- 削除処理実行 ---
        for file_path in unique_files_to_delete:
            try:
                normalized_path = os.path.normpath(file_path)
                if os.path.exists(normalized_path):
                    send2trash.send2trash(normalized_path)
                    print(f"  削除成功: {normalized_path}")
                    deleted_count += 1
                    files_actually_deleted.add(normalized_path)
                else:
                    print(f"  削除スキップ: ファイルが見つかりません {normalized_path}")
                    errors.append(f"{os.path.basename(normalized_path)}: ファイルが見つかりません")
            except Exception as e:
                print(f"  削除エラー: {file_path} - {e}")
                errors.append(f"{os.path.basename(file_path)}: {e}")

        # --- 結果メッセージ表示 ---
        if errors:
             QMessageBox.warning(parent_widget, "削除エラー", f"{len(errors)} 個のファイルの削除中にエラーが発生しました:\n" + "\n".join(errors))
        if deleted_count > 0:
             QMessageBox.information(parent_widget, "削除完了", f"{deleted_count} 個のファイルをゴミ箱に移動しました。")

        return deleted_count, errors, files_actually_deleted # 実際に削除したファイルのセットも返す
    else:
        print("削除がキャンセルされました。")
        return 0, [], set() # キャンセル時は空を返す

def open_file_external(file_path, parent_widget=None):
    """指定されたファイルを関連付けられたアプリケーションで開く"""
    if not file_path or not os.path.exists(file_path):
        print(f"ファイルが見つかりません: {file_path}")
        QMessageBox.warning(parent_widget, "エラー", f"ファイルが見つかりません:\n{file_path}")
        return
    try:
        # os.startfile は Windows 専用
        os.startfile(os.path.normpath(file_path))
        print(f"ファイルを開きました: {file_path}")
    except Exception as e:
        print(f"ファイルを開けませんでした ({file_path}): {e}")
        QMessageBox.critical(parent_widget, "エラー", f"ファイルを開けませんでした:\n{file_path}\n\n{e}")

