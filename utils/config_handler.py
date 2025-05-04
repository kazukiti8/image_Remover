# utils/config_handler.py
import os
import json
from typing import Dict, Any, Union, Optional

SETTINGS_FILE: str = os.path.join(os.path.expanduser("~"), ".image_cleaner_settings.json")

# デフォルト設定値 (scan_subdirectories を追加)
DEFAULT_SETTINGS: Dict[str, Union[float, bool, int, str]] = {
    'scan_subdirectories': False, # ★ 追加: デフォルトはサブディレクトリをスキャンしない ★
    'blur_threshold': 0.80,
    'use_phash': True,
    'hash_threshold': 5,
    'orb_nfeatures': 1500,
    'orb_ratio_threshold': 0.70,
    'min_good_matches': 40,
    'last_directory': os.path.expanduser("~"),
    'last_save_load_dir': os.path.expanduser("~") # 保存/読み込みディレクトリも追加
}
SettingsDict = Dict[str, Union[float, bool, int, str]]

def load_settings() -> SettingsDict:
    """設定ファイルを読み込み、設定辞書を返す"""
    current_settings: SettingsDict = DEFAULT_SETTINGS.copy()
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                loaded_settings: Dict[str, Any] = json.load(f)
                for key, default_value in DEFAULT_SETTINGS.items():
                    if key in loaded_settings:
                        loaded_value: Any = loaded_settings[key]
                        expected_type: type = type(default_value)
                        if isinstance(default_value, bool):
                            if isinstance(loaded_value, bool): current_settings[key] = loaded_value
                            else: print(f"警告: 設定 '{key}' の型不正 (bool期待)。デフォルト値使用。")
                        elif isinstance(loaded_value, expected_type): current_settings[key] = loaded_value
                        else: print(f"警告: 設定 '{key}' の型不正 ({expected_type.__name__}期待)。デフォルト値使用。")
                print(f"設定ファイルを読み込みました: {SETTINGS_FILE}")
        except (json.JSONDecodeError, TypeError, ValueError, OSError) as e:
            print(f"警告: 設定ファイルの読み込み失敗 ({e})。デフォルト設定使用。")
            current_settings = DEFAULT_SETTINGS.copy()
        except Exception as e:
             print(f"警告: 設定ファイル読み込み中に予期せぬエラー ({e})。デフォルト設定使用。")
             current_settings = DEFAULT_SETTINGS.copy()
    else:
        print("設定ファイルが見つかりません。デフォルト設定を使用します。")
        save_settings(current_settings) # 初回起動時に作成試行

    # last_save_load_dir がなければ last_directory で初期化 (互換性のため)
    if 'last_save_load_dir' not in current_settings:
        current_settings['last_save_load_dir'] = current_settings.get('last_directory', os.path.expanduser("~"))


    return current_settings

def save_settings(settings_to_save: SettingsDict) -> bool:
    """現在の設定をファイルに保存する"""
    valid_settings: SettingsDict = {}
    for key, default_value in DEFAULT_SETTINGS.items():
        value_to_save: Any = settings_to_save.get(key, default_value)
        expected_type: type = type(default_value)
        try:
            if isinstance(default_value, bool): valid_settings[key] = bool(value_to_save)
            elif isinstance(default_value, int): valid_settings[key] = int(value_to_save)
            elif isinstance(default_value, float): valid_settings[key] = float(value_to_save)
            else: valid_settings[key] = expected_type(value_to_save)
        except (ValueError, TypeError):
             print(f"警告: 設定 '{key}' の値を正しい型に変換できません。デフォルト値 ({default_value}) を保存します。")
             valid_settings[key] = default_value

    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(valid_settings, f, ensure_ascii=False, indent=4)
        print(f"設定を保存しました: {SETTINGS_FILE}")
        return True
    except OSError as e: print(f"警告: 設定ファイルの保存失敗 (OSError: {e})。"); return False
    except Exception as e: print(f"警告: 設定ファイル保存中に予期せぬエラー ({e})。"); return False
