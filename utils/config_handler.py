# utils/config_handler.py
import os
import json
from PySide6.QtWidgets import QMessageBox # エラー表示用にインポート

# 設定ファイルのパス (ユーザーのホームディレクトリに隠しファイルとして)
SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".image_cleaner_settings.json")

# デフォルト設定値
DEFAULT_SETTINGS = {
    'blur_threshold': 0.80,
    'orb_nfeatures': 1500,
    'orb_ratio_threshold': 0.70,
    'min_good_matches': 40,
    # 将来的に追加する可能性のある設定
    # 'last_directory': os.path.expanduser("~") # 最後に開いたディレクトリなど
}

def load_settings():
    """設定ファイルを読み込み、設定辞書を返す"""
    current_settings = DEFAULT_SETTINGS.copy() # まずデフォルト値で初期化
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                loaded_settings = json.load(f)
                # デフォルト設定に含まれるキーのみを読み込み、型もチェック
                for key, default_value in DEFAULT_SETTINGS.items():
                    if key in loaded_settings:
                        # 型が一致するか、または数値型の場合はint/float間の変換を許容するかなど、
                        # より厳密なチェックが必要な場合もある
                        if isinstance(loaded_settings[key], type(default_value)):
                            current_settings[key] = loaded_settings[key]
                        else:
                            print(f"警告: 設定ファイルの値の型が不正です ({key})。デフォルト値を使用します。")
                print(f"設定ファイルを読み込みました: {SETTINGS_FILE}")
        except (json.JSONDecodeError, TypeError, ValueError, OSError) as e:
            print(f"警告: 設定ファイルの読み込みに失敗しました ({e})。デフォルト設定を使用します。")
            # エラーが発生した場合もデフォルト設定を返す
            current_settings = DEFAULT_SETTINGS.copy()
    else:
        print("設定ファイルが見つかりません。デフォルト設定を使用します。")
    return current_settings

def save_settings(settings_to_save):
    """現在の設定をファイルに保存する"""
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            # indent=4 で整形して保存
            json.dump(settings_to_save, f, ensure_ascii=False, indent=4)
        print(f"設定を保存しました: {SETTINGS_FILE}")
        return True # 保存成功
    except OSError as e:
        print(f"警告: 設定ファイルの保存に失敗しました ({e})。")
        # GUIコンテキストがないため、ここではエラーメッセージ表示はしない
        # 必要であれば呼び出し元で表示する
        return False # 保存失敗

