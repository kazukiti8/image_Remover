# utils/file_operations.py
import os
import time
import cv2
from PySide6.QtWidgets import QMessageBox

try:
    import send2trash
except ImportError:
    print("エラー: send2trash ライブラリが見つかりません。`pip install Send2Trash` を実行してください。")
    send2trash = None

def get_file_info(file_path):
    """
    指定されたファイルの基本情報（サイズ、更新日時、解像度）を取得する。
    解像度取得でエラーが発生した場合、エラーメッセージを返すように変更。
    """
    file_size = "N/A"
    mod_time = "N/A"
    dimensions = "N/A"
    dimension_error = None # 解像度取得エラーメッセージ用

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
        try:
            img = cv2.imread(file_path)
            if img is not None:
                h, w = img.shape[:2]
                dimensions = f"{w}x{h}"
            else:
                # 読み込みは成功したが画像データがない場合
                dimension_error = "画像読込不可(形式/破損?)"
                dimensions = "読込エラー"
                print(f"警告: 解像度取得のため画像読み込み失敗 ({os.path.basename(file_path)}) - {dimension_error}")
        except cv2.error as e:
            dimension_error = f"OpenCVエラー: {e.msg}"
            dimensions = "読込エラー"
            print(f"警告: 解像度取得中にOpenCVエラー ({os.path.basename(file_path)}): {e.msg}")
        except MemoryError:
            dimension_error = "メモリ不足"
            dimensions = "読込エラー"
            print(f"警告: 解像度取得中にメモリ不足 ({os.path.basename(file_path)})")
        except Exception as e:
            dimension_error = f"予期せぬエラー: {type(e).__name__}"
            dimensions = "読込エラー"
            print(f"警告: 解像度取得中に予期せぬエラー ({os.path.basename(file_path)}): {e}")

    except FileNotFoundError:
        print(f"警告: ファイル情報取得エラー - ファイルが見つかりません ({file_path})")
        file_size, mod_time, dimensions = "削除済?", "削除済?", "削除済?"
        dimension_error = "ファイルなし" # エラー情報として設定
    except PermissionError:
        print(f"警告: ファイル情報取得エラー - アクセス権がありません ({file_path})")
        file_size, mod_time, dimensions = "アクセス不可", "アクセス不可", "アクセス不可"
        dimension_error = "アクセス権なし" # エラー情報として設定
    except Exception as e:
        # statに関するその他のエラー
        print(f"警告: ファイル情報取得エラー ({file_path}): {e}")
        file_size, mod_time = "エラー", "エラー"
        # dimensions は try-except 内で設定されている可能性があるためそのまま
        if dimension_error is None: # 解像度取得前にエラーが起きた場合
            dimension_error = f"ファイル情報取得エラー: {type(e).__name__}"
            dimensions = "エラー"

    # dimension_error は現状返り値に含めていないが、必要ならタプルで返すなど変更可能
    return file_size, mod_time, dimensions # dimension_error は返さない

def delete_files_to_trash(file_paths, parent_widget=None):
    """
    指定されたファイルパスのリストをゴミ箱に移動する。
    確認ダイアログを表示し、結果(成功数, エラーリスト[辞書], 削除成功パスセット)を返す。
    エラーリストは {'path': file_path, 'error': error_message} の形式。
    (この関数は変更なし)
    """
    if send2trash is None:
        QMessageBox.critical(parent_widget, "エラー", "send2trash ライブラリが見つかりません。\n削除機能を使用できません。")
        return 0, [{"path": "N/A", "error": "send2trashライブラリがありません"}], set()

    unique_files_to_delete = sorted(list(set(file_paths)))

    if not unique_files_to_delete:
        QMessageBox.information(parent_widget, "情報", "削除対象のファイルが選択されていません。")
        return 0, [], set()

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
        errors = [] # エラー情報を辞書で格納
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
                    err_msg = "ファイルが見つかりません"
                    print(f"  削除スキップ: {err_msg} {normalized_path}")
                    errors.append({'path': normalized_path, 'error': err_msg})
            except PermissionError as e:
                err_msg = f"アクセス権がありません: {e}"
                print(f"  削除エラー: {file_path} - {err_msg}")
                errors.append({'path': file_path, 'error': err_msg})
            except OSError as e: # send2trash が OSError を出すことがある
                err_msg = f"OSエラー: {e}"
                print(f"  削除エラー: {file_path} - {err_msg}")
                errors.append({'path': file_path, 'error': err_msg})
            except Exception as e: # その他の予期せぬエラー
                err_msg = f"予期せぬエラー: {e}"
                print(f"  削除エラー: {file_path} - {err_msg}")
                errors.append({'path': file_path, 'error': err_msg})

        # --- 結果メッセージ表示 ---
        if errors:
             error_details = "\n".join([f"- {os.path.basename(e['path'])}: {e['error']}" for e in errors[:5]]) # 先頭5件表示
             if len(errors) > 5:
                 error_details += f"\n...他 {len(errors) - 5} 件のエラー"
             QMessageBox.warning(parent_widget, "削除エラー", f"{len(errors)} 個のファイルの削除中にエラーが発生しました:\n{error_details}")
        if deleted_count > 0:
             QMessageBox.information(parent_widget, "削除完了", f"{deleted_count} 個のファイルをゴミ箱に移動しました。")

        return deleted_count, errors, files_actually_deleted
    else:
        print("削除がキャンセルされました。")
        return 0, [], set()

def open_file_external(file_path, parent_widget=None):
    """
    指定されたファイルを外部アプリケーションで開く。
    (この関数は変更なし)
    """
    if not file_path or not os.path.exists(file_path):
        print(f"ファイルが見つかりません: {file_path}")
        QMessageBox.warning(parent_widget, "エラー", f"ファイルが見つかりません:\n{file_path}")
        return
    try:
        # Windows のみ: os.startfile を使用
        if os.name == 'nt':
            os.startfile(os.path.normpath(file_path))
        # macOS: open コマンドを使用
        elif sys.platform == 'darwin':
            subprocess.call(['open', os.path.normpath(file_path)])
        # Linux: xdg-open コマンドを使用
        else:
            subprocess.call(['xdg-open', os.path.normpath(file_path)])
        print(f"ファイルを開きました: {file_path}")
    except FileNotFoundError: # startfile や open/xdg-open が見つからない場合
         QMessageBox.critical(parent_widget, "エラー", f"ファイルを開くコマンドが見つかりません。\nOSを確認してください。")
    except Exception as e:
        print(f"ファイルを開けませんでした ({file_path}): {e}")
        QMessageBox.critical(parent_widget, "エラー", f"ファイルを開けませんでした:\n{file_path}\n\n{e}")

# open_file_external で subprocess, sys を使うためインポート
import subprocess
import sys
