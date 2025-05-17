# utils/config_handler.py
import os
import json
from typing import Dict, Any, Union, Optional

SETTINGS_FILE: str = os.path.join(os.path.expanduser("~"), ".image_cleaner_settings.json")

# デフォルト設定値
DEFAULT_SETTINGS: Dict[str, Any] = {
    # スキャン設定
    'scan_subdirectories': False,
    'use_cache': True,  # デフォルトではキャッシュを使用する
    # スキャン状態の自動保存と復元
    'auto_save_state': True,  # スキャン中に定期的に状態を自動保存
    'auto_restore_on_start': True,  # 起動時に前回の中断状態を自動チェック
    'auto_save_interval': 100,  # 何ファイル処理するごとに状態を保存するか
    # ブレ検出設定
    'blur_algorithm': 'fft',
    'blur_threshold': 0.80,
    'blur_laplacian_threshold': 100,
    # 類似ペア検出設定
    'similarity_mode': 'phash_orb',
    'hash_threshold': 5,
    'orb_nfeatures': 1500,
    'orb_ratio_threshold': 0.70,
    'min_good_matches': 40,
    # アプリケーション状態
    'last_directory': os.path.expanduser("~"),
    'last_save_load_dir': os.path.expanduser("~"),
    'presets': {},
    # テーマ設定
    'theme': 'light', # 'light' or 'dark'
    # フィルター設定
    'filters': {
        'blurry': {
            'min_score': 0.0,
            'max_score': 1.0,
            'filename': ''
        },
        'similarity': {
            'min_similarity': 0,
            'max_similarity': 100,
            'duplicates_only': False,
            'filename': ''
        }
    }
}
# 型エイリアス
SettingsDict = Dict[str, Any]

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

                        if key == 'presets':
                            if isinstance(loaded_value, dict):
                                valid_presets = { name: preset_dict for name, preset_dict in loaded_value.items() if isinstance(preset_dict, dict) }
                                current_settings[key] = valid_presets
                            else:
                                print(f"警告: 設定 'presets' の型不正 (dict期待)。デフォルト値使用。")
                                current_settings[key] = {}
                        # ★★★ テーマ設定の読み込み ★★★
                        elif key == 'theme':
                            if isinstance(loaded_value, str) and loaded_value in ['light', 'dark']:
                                current_settings[key] = loaded_value
                            else:
                                print(f"警告: 設定 'theme' の値が無効 ('{loaded_value}')。デフォルト値 'light' を使用。")
                                current_settings[key] = 'light' # 無効な値ならデフォルトに
                        # ★★★★★★★★★★★★★★★★★★★
                        elif isinstance(default_value, bool):
                            if isinstance(loaded_value, bool): current_settings[key] = loaded_value
                            else: print(f"警告: 設定 '{key}' の型不正 (bool期待)。デフォルト値使用。")
                        elif isinstance(default_value, int):
                            try: current_settings[key] = int(loaded_value)
                            except (ValueError, TypeError): print(f"警告: 設定 '{key}' の型不正 (int期待)。デフォルト値使用。")
                        elif isinstance(default_value, float):
                            try: current_settings[key] = float(loaded_value)
                            except (ValueError, TypeError): print(f"警告: 設定 '{key}' の型不正 (float期待)。デフォルト値使用。")
                        elif isinstance(default_value, str):
                             current_settings[key] = str(loaded_value)
                        else:
                            if isinstance(loaded_value, expected_type): current_settings[key] = loaded_value
                            else: print(f"警告: 設定 '{key}' の型不正 ({expected_type.__name__}期待)。デフォルト値使用。")

                print(f"設定ファイルを読み込みました: {SETTINGS_FILE}")
        except (json.JSONDecodeError, TypeError, ValueError, OSError) as e:
            print(f"警告: 設定ファイルの読み込み失敗 ({e})。デフォルト設定使用。")
            current_settings = DEFAULT_SETTINGS.copy()
        except Exception as e:
             print(f"警告: 設定ファイル読み込み中に予期せぬエラー ({type(e).__name__}: {e})。デフォルト設定使用。")
             current_settings = DEFAULT_SETTINGS.copy()
    else:
        print("設定ファイルが見つかりません。デフォルト設定を使用します。")

    # 互換性維持とデフォルト値設定
    if 'last_save_load_dir' not in current_settings:
        current_settings['last_save_load_dir'] = current_settings.get('last_directory', os.path.expanduser("~"))
    if 'presets' not in current_settings: current_settings['presets'] = {}
    if 'theme' not in current_settings: current_settings['theme'] = 'light' # theme がなければ light

    return current_settings

def save_settings(settings_to_save: SettingsDict) -> bool:
    """現在の設定をファイルに保存する"""
    valid_settings: SettingsDict = {}
    for key, default_value in DEFAULT_SETTINGS.items():
        value_to_save: Any = settings_to_save.get(key)

        if key == 'presets':
            if isinstance(value_to_save, dict):
                valid_presets = { name: preset_dict for name, preset_dict in value_to_save.items() if isinstance(preset_dict, dict) }
                valid_settings[key] = valid_presets
            else:
                print(f"警告: 保存する設定 'presets' の型が不正です。空の辞書を保存します。")
                valid_settings[key] = {}
            continue
        # ★★★ テーマ設定の検証 ★★★
        elif key == 'theme':
            if isinstance(value_to_save, str) and value_to_save in ['light', 'dark']:
                valid_settings[key] = value_to_save
            else:
                print(f"警告: 保存する設定 'theme' の値が無効 ('{value_to_save}')。デフォルト値 'light' を保存します。")
                valid_settings[key] = 'light' # 不正な値ならデフォルトに
            continue
        # ★★★★★★★★★★★★★★★★★

        if value_to_save is None:
            value_to_save = default_value
            print(f"情報: 設定 '{key}' が見つからないため、デフォルト値 ({default_value}) を保存します。")

        expected_type: type = type(default_value)
        try:
            if isinstance(default_value, bool): valid_settings[key] = bool(value_to_save)
            elif isinstance(default_value, int): valid_settings[key] = int(value_to_save)
            elif isinstance(default_value, float): valid_settings[key] = float(value_to_save)
            elif isinstance(default_value, str): valid_settings[key] = str(value_to_save)
            else:
                 if isinstance(value_to_save, expected_type): valid_settings[key] = value_to_save
                 else: raise TypeError("予期しない型")
        except (ValueError, TypeError):
             print(f"警告: 設定 '{key}' の値を正しい型 ({expected_type.__name__}) に変換できません。デフォルト値 ({default_value}) を保存します。")
             valid_settings[key] = default_value

    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(valid_settings, f, ensure_ascii=False, indent=4)
        print(f"設定を保存しました: {SETTINGS_FILE}")
        return True
    except OSError as e: print(f"警告: 設定ファイルの保存失敗 (OSError: {e})。"); return False
    except TypeError as e: print(f"警告: 設定データのJSONシリアライズ失敗 (TypeError: {e})。"); return False
    except Exception as e: print(f"警告: 設定ファイル保存中に予期せぬエラー ({type(e).__name__}: {e})。"); return False

