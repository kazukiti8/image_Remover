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

# --- 画像ファイルの連番リネーム関数 ---
def rename_images_to_sequence(directory_path: str, parent_widget: Optional[QWidget] = None) -> Tuple[int, List[ErrorDict]]:
    """
    指定されたディレクトリ内の画像ファイルをすべて連番(1, 2, 3...)にリネームする。
    サブディレクトリは含めない。
    
    戻り値:
    - 成功したリネーム数
    - エラーのリスト（ファイルパスとエラーメッセージの辞書）
    """
    # 対象となる画像ファイル拡張子
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
    
    # ディレクトリ内のファイル一覧を取得（サブディレクトリは含めない）
    files_in_dir = [f for f in os.listdir(directory_path) 
                   if os.path.isfile(os.path.join(directory_path, f)) and 
                   os.path.splitext(f.lower())[1] in image_extensions]
    
    # 画像ファイルが存在しない場合
    if not files_in_dir:
        if parent_widget:
            QMessageBox.information(parent_widget, "情報", "リネーム対象の画像ファイルが見つかりませんでした。")
        return 0, []
    
    # リネーム前に確認ダイアログを表示
    num_files = len(files_in_dir)
    message = f"{num_files} 個の画像ファイルを連番にリネームします。\nこの操作は元に戻せません。続行しますか？\n\n"
    display_limit = 10
    if num_files <= display_limit:
        message += "\n".join(files_in_dir)
    else:
        message += "\n".join(files_in_dir[:display_limit]) + f"\n...他 {num_files - display_limit} 個"
    
    if parent_widget:
        reply = QMessageBox.question(parent_widget, "リネームの確認", message, 
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                    QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            print("リネームがキャンセルされました。")
            return 0, []
    
    # リネーム処理
    renamed_count = 0
    errors = []
    
    # 一時的に拡張子を保存してリネーム後に元の拡張子を使用
    file_extensions = {file: os.path.splitext(file)[1] for file in files_in_dir}
    
    # 桁数を決定（例: 100個のファイルなら3桁）
    digits = len(str(num_files))
    
    # リネーム用の一時ディレクトリ（衝突を避けるため）
    temp_dir = os.path.join(directory_path, "__temp_rename__")
    try:
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
        
        # 1. まず一時ディレクトリにリネームして移動（ファイル名の衝突を避けるため）
        for i, file in enumerate(sorted(files_in_dir), 1):
            original_path = os.path.join(directory_path, file)
            temp_path = os.path.join(temp_dir, f"_temp_{i:0{digits}d}{file_extensions[file]}")
            try:
                os.rename(original_path, temp_path)
            except Exception as e:
                errors.append({'path': original_path, 'error': str(e)})
                print(f"エラー（一時移動）: {file} - {e}")
        
        # 2. 一時ディレクトリから元のディレクトリに連番でリネームして戻す
        for i, file in enumerate(sorted([f for f in os.listdir(temp_dir) if f.startswith('_temp_')]), 1):
            temp_path = os.path.join(temp_dir, file)
            ext = os.path.splitext(file)[1]
            new_path = os.path.join(directory_path, f"{i:0{digits}d}{ext}")
            try:
                os.rename(temp_path, new_path)
                renamed_count += 1
                print(f"リネーム成功: {i:0{digits}d}{ext}")
            except Exception as e:
                errors.append({'path': temp_path, 'error': str(e)})
                print(f"エラー（リネーム）: {file} - {e}")
        
    except Exception as e:
        if parent_widget:
            QMessageBox.critical(parent_widget, "エラー", f"リネーム処理中にエラーが発生しました: {e}")
        errors.append({'path': directory_path, 'error': str(e)})
        print(f"致命的なエラー: {e}")
    finally:
        # 一時ディレクトリの削除（残っているファイルがあれば元のディレクトリに戻す）
        if os.path.exists(temp_dir):
            for file in os.listdir(temp_dir):
                try:
                    temp_path = os.path.join(temp_dir, file)
                    # 元の名前が分からないのでランダムな名前で戻す
                    recovery_name = f"recovered_{int(time.time())}_{file}"
                    os.rename(temp_path, os.path.join(directory_path, recovery_name))
                    print(f"復旧: {file} -> {recovery_name}")
                except Exception as e:
                    print(f"一時ファイル移動エラー: {file} - {e}")
            try:
                os.rmdir(temp_dir)  # 空になったディレクトリを削除
            except Exception as e:
                print(f"一時ディレクトリ削除エラー: {e}")
    
    # 結果表示
    if parent_widget:
        if errors:
            error_details = "\n".join([f"- {os.path.basename(e['path'])}: {e['error']}" for e in errors[:5]])
            if len(errors) > 5:
                error_details += f"\n...他 {len(errors) - 5} 件のエラー"
            QMessageBox.warning(parent_widget, "リネームエラー", 
                              f"{len(errors)} 個のファイルのリネーム中にエラーが発生しました:\n{error_details}")
        
        if renamed_count > 0:
            QMessageBox.information(parent_widget, "リネーム完了", 
                                   f"{renamed_count} 個のファイルを連番にリネームしました。")
    
    return renamed_count, errors

# --- 削除・ファイルを開く関数 ---
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
