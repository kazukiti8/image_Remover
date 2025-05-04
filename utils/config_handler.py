# utils/config_handler.py
import os
import json
# QMessageBox はここでは不要になったので削除

# 設定ファイルのパス (ユーザーのホームディレクトリに隠しファイルとして)
SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".image_cleaner_settings.json")

# デフォルト設定値 (pHash関連を追加)
DEFAULT_SETTINGS = {
    'blur_threshold': 0.80,
    'use_phash': True,         # pHashを使用するかどうか
    'hash_threshold': 5,       # pHashのハミング距離閾値
    'orb_nfeatures': 1500,
    'orb_ratio_threshold': 0.70,
    'min_good_matches': 40,
    'last_directory': os.path.expanduser("~") # 最後に開いたディレクトリ
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
                        # 型が一致するかチェック (bool, int, float, str)
                        # isinstance(True, int) は True になるため、boolは特別扱い
                        if isinstance(default_value, bool):
                            if isinstance(loaded_settings[key], bool):
                                current_settings[key] = loaded_settings[key]
                            else:
                                print(f"警告: 設定ファイルの値の型が不正です ({key}: bool期待)。デフォルト値を使用します。")
                        elif isinstance(loaded_settings[key], type(default_value)):
                             # 数値型(int, float) または 文字列型(str) の場合
                             current_settings[key] = loaded_settings[key]
                        # int設定にfloat値が入っている場合などは許容しない (厳密に)
                        # elif isinstance(default_value, int) and isinstance(loaded_settings[key], float):
                        #     current_settings[key] = int(loaded_settings[key]) # 丸める場合
                        else:
                            print(f"警告: 設定ファイルの値の型が不正です ({key}: {type(default_value).__name__}期待)。デフォルト値を使用します。")
                    # else:
                        # 設定ファイルにキーが存在しない場合はデフォルト値が使われる
                        # print(f"情報: 設定ファイルにキー '{key}' がありません。デフォルト値を使用します。")

                print(f"設定ファイルを読み込みました: {SETTINGS_FILE}")
        except (json.JSONDecodeError, TypeError, ValueError, OSError) as e:
            print(f"警告: 設定ファイルの読み込みに失敗しました ({e})。デフォルト設定を使用します。")
            # エラーが発生した場合もデフォルト設定を返す
            current_settings = DEFAULT_SETTINGS.copy()
        except Exception as e:
             print(f"警告: 設定ファイルの読み込み中に予期せぬエラーが発生しました ({e})。デフォルト設定を使用します。")
             current_settings = DEFAULT_SETTINGS.copy()
    else:
        print("設定ファイルが見つかりません。デフォルト設定を使用します。")
        # 初回起動時など、設定ファイルがない場合はデフォルト設定でファイルを作成する
        save_settings(current_settings) # ここで保存を試みる

    return current_settings

def save_settings(settings_to_save):
    """現在の設定をファイルに保存する"""
    # 保存する前に、デフォルトに含まれないキーを削除する（オプション）
    valid_settings = {k: settings_to_save.get(k, v) for k, v in DEFAULT_SETTINGS.items()}

    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            # indent=4 で整形して保存
            json.dump(valid_settings, f, ensure_ascii=False, indent=4)
        print(f"設定を保存しました: {SETTINGS_FILE}")
        return True # 保存成功
    except OSError as e:
        print(f"警告: 設定ファイルの保存に失敗しました ({e})。")
        # GUIコンテキストがないため、ここではエラーメッセージ表示はしない
        # 必要であれば呼び出し元で表示する
        return False # 保存失敗
    except Exception as e:
        print(f"警告: 設定ファイルの保存中に予期せぬエラーが発生しました ({e})。")
        return False
