# utils/results_handler.py
import json
import os
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any, Union, Set # ★ Set をインポート ★

# 結果データのバージョン
RESULTS_FORMAT_VERSION: str = "1.0"
# ★ 状態データのバージョン ★
STATE_FORMAT_VERSION: str = "1.0"
# ★ 状態ファイル名 ★
STATE_FILENAME: str = ".image_cleaner_scan_state.json"

# --- 型エイリアス ---
BlurResultItem = Dict[str, Union[str, float]]
SimilarResultItem = List[Union[str, int]]
DuplicateResultDict = Dict[str, List[str]]
ErrorResultItem = Dict[str, str]
ResultsData = Dict[str, Union[List[BlurResultItem], List[SimilarResultItem], DuplicateResultDict, List[ErrorResultItem]]]
SettingsData = Dict[str, Any]
LoadResult = Tuple[Optional[ResultsData], Optional[str], Optional[SettingsData], Optional[str]]

# ★ スキャン状態データの型エイリアス ★
ScanStateData = Dict[str, Any]
# ScanStateData の具体的なキーの例 (ScanWorker で定義・使用):
# {
#     "format_version": str,
#     "save_timestamp": str,
#     "target_directory": str,
#     "settings_used": SettingsData,
#     "all_image_paths": List[str],
#     "processed_paths_blur": List[str], # JSON互換のためSetではなくListで保存
#     "processed_hashes": Dict[str, str], # path -> hash
#     "compared_pairs_similar": List[List[str]], # JSON互換のためSet[Tuple[str,str]]ではなくList[List[str]]
#     "blurry_results": List[BlurResultItem],
#     "duplicate_results": DuplicateResultDict,
#     "similar_pair_results": List[SimilarResultItem],
#     "processing_errors": List[ErrorResultItem]
# }
LoadStateResult = Tuple[Optional[ScanStateData], Optional[str]] # (state_data, error_message)

# --- 結果ファイルの保存・読み込み (変更なし) ---
def save_results_to_file(filepath: str,
                         results_data: ResultsData,
                         scanned_directory: str,
                         settings_used: Optional[SettingsData] = None) -> bool:
    """スキャン結果を指定されたJSONファイルに保存します。"""
    try:
        data_to_save: Dict[str, Any] = {
            "format_version": RESULTS_FORMAT_VERSION,
            "save_timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "scanned_directory": scanned_directory,
            "settings_used": settings_used if settings_used else {},
            "results": results_data
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=4)
        print(f"結果を保存しました: {filepath}")
        return True
    except OSError as e: print(f"エラー: 結果ファイルの保存失敗 (OSError: {e}) - {filepath}"); return False
    except TypeError as e: print(f"エラー: 結果データのJSONシリアライズ失敗 (TypeError: {e})"); return False
    except Exception as e: print(f"エラー: 結果ファイル保存中に予期せぬエラー ({type(e).__name__}: {e}) - {filepath}"); return False

def load_results_from_file(filepath: str) -> LoadResult:
    """JSONファイルからスキャン結果を読み込みます。"""
    if not os.path.exists(filepath):
        return None, None, None, "指定されたファイルが見つかりません。"
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            loaded_data: Dict[str, Any] = json.load(f)

        if not isinstance(loaded_data, dict): return None, None, None, "無効なファイル形式 (トップレベル非オブジェクト)。"
        if "format_version" not in loaded_data: print("警告: 結果ファイルにバージョン情報がありません。")
        elif loaded_data["format_version"] != RESULTS_FORMAT_VERSION: print(f"警告: 結果ファイルのバージョン不一致 (ファイル: {loaded_data['format_version']}, アプリ: {RESULTS_FORMAT_VERSION})。")

        scanned_directory: Optional[str] = loaded_data.get("scanned_directory")
        results_container: Optional[Dict[str, Any]] = loaded_data.get("results")
        settings_used: SettingsData = loaded_data.get("settings_used", {})

        if not isinstance(scanned_directory, str): return None, None, None, "無効なファイル形式 (スキャンディレクトリ情報なし)。"
        if not isinstance(results_container, dict): return None, None, None, "無効なファイル形式 (結果データなし)。"

        results_data: ResultsData = {}
        expected_keys: Dict[str, type] = {'blurry': list, 'similar': list, 'duplicates': dict, 'errors': list}
        for key, expected_type in expected_keys.items():
            data_item: Any = results_container.get(key)
            if data_item is None:
                print(f"警告: 結果データにキー '{key}' がありません。空として扱います。")
                results_data[key] = expected_type()
            elif isinstance(data_item, expected_type):
                 results_data[key] = data_item
            else:
                 return None, None, None, f"無効なファイル形式 (結果データ '{key}' の型不正)。"

        print(f"結果を読み込みました: {filepath}")
        return results_data, scanned_directory, settings_used, None

    except json.JSONDecodeError as e: return None, None, None, f"JSONファイルの解析失敗: {e}"
    except OSError as e: return None, None, None, f"結果ファイルの読み込み失敗 (OSError: {e})"
    except Exception as e: return None, None, None, f"結果ファイル読み込み中に予期せぬエラー ({type(e).__name__}: {e})"

# ★★★ スキャン状態の保存・読み込み関数 ★★★

def get_state_filepath(directory_path: str) -> str:
    """指定されたディレクトリに対応する状態ファイルのパスを返す"""
    return os.path.join(directory_path, STATE_FILENAME)

def save_scan_state(directory_path: str, state_data: ScanStateData) -> bool:
    """現在のスキャン状態を指定されたディレクトリの状態ファイルに保存する"""
    filepath = get_state_filepath(directory_path)
    try:
        # state_data に必須の情報が含まれているか基本的なチェック (任意)
        required_keys = ["target_directory", "settings_used", "all_image_paths"]
        if not all(key in state_data for key in required_keys):
            print("エラー: 保存する状態データに必要なキーが不足しています。")
            return False

        # バージョンとタイムスタンプを追加
        state_data["format_version"] = STATE_FORMAT_VERSION
        state_data["save_timestamp"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # JSON互換性のためにSetをListに変換 (呼び出し元で行う方が良い場合もある)
        if "processed_paths_blur" in state_data and isinstance(state_data["processed_paths_blur"], set):
            state_data["processed_paths_blur"] = sorted(list(state_data["processed_paths_blur"]))
        if "compared_pairs_similar" in state_data and isinstance(state_data["compared_pairs_similar"], set):
             # Set[Tuple[str, str]] -> List[List[str]]
             state_data["compared_pairs_similar"] = sorted([list(pair) for pair in state_data["compared_pairs_similar"]])

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(state_data, f, ensure_ascii=False, indent=4)
        print(f"スキャン状態を保存しました: {filepath}")
        return True
    except OSError as e:
        print(f"エラー: 状態ファイルの保存失敗 (OSError: {e}) - {filepath}")
        return False
    except TypeError as e:
        print(f"エラー: 状態データのJSONシリアライズ失敗 (TypeError: {e})")
        # 問題のあるキーと値を特定するデバッグコードを追加すると役立つ
        # for k, v in state_data.items():
        #     try: json.dumps({k: v})
        #     except TypeError: print(f"  シリアライズ不可: key='{k}', type={type(v)}")
        return False
    except Exception as e:
        print(f"エラー: 状態ファイル保存中に予期せぬエラー ({type(e).__name__}: {e}) - {filepath}")
        return False

def load_scan_state(directory_path: str) -> LoadStateResult:
    """指定されたディレクトリの状態ファイルを読み込む"""
    filepath = get_state_filepath(directory_path)
    if not os.path.exists(filepath):
        return None, "状態ファイルが見つかりません。"

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            loaded_data: ScanStateData = json.load(f)

        # 簡単な検証
        if not isinstance(loaded_data, dict):
            return None, "無効な状態ファイル形式 (トップレベル非オブジェクト)。"
        if loaded_data.get("target_directory") != directory_path:
            # ディレクトリが一致しない場合は無効な状態とみなす
            return None, "状態ファイルの対象ディレクトリが一致しません。"
        if loaded_data.get("format_version") != STATE_FORMAT_VERSION:
            print(f"警告: 状態ファイルのバージョン不一致 (ファイル: {loaded_data.get('format_version')}, アプリ: {STATE_FORMAT_VERSION})。互換性がない可能性があります。")
            # ここでエラーにするか、続行するかは要件次第

        # JSONから読み込んだListをSetに変換 (必要に応じて)
        if "processed_paths_blur" in loaded_data and isinstance(loaded_data["processed_paths_blur"], list):
            loaded_data["processed_paths_blur"] = set(loaded_data["processed_paths_blur"])
        if "compared_pairs_similar" in loaded_data and isinstance(loaded_data["compared_pairs_similar"], list):
            # List[List[str]] -> Set[Tuple[str, str]]
             try:
                 # frozenset にしないと set の要素にできない
                 loaded_data["compared_pairs_similar"] = set(tuple(sorted(pair)) for pair in loaded_data["compared_pairs_similar"] if len(pair)==2)
             except TypeError:
                 print("警告: compared_pairs_similar の形式が不正です。")
                 loaded_data["compared_pairs_similar"] = set() # 空にする

        print(f"スキャン状態を読み込みました: {filepath}")
        return loaded_data, None

    except json.JSONDecodeError as e:
        return None, f"状態ファイルのJSON解析失敗: {e}"
    except OSError as e:
        return None, f"状態ファイルの読み込み失敗 (OSError: {e})"
    except Exception as e:
        return None, f"状態ファイル読み込み中に予期せぬエラー ({type(e).__name__}: {e})"

def delete_scan_state(directory_path: str) -> bool:
    """指定されたディレクトリの状態ファイルを削除する"""
    filepath = get_state_filepath(directory_path)
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            print(f"状態ファイルを削除しました: {filepath}")
            return True
        except OSError as e:
            print(f"エラー: 状態ファイルの削除失敗 (OSError: {e}) - {filepath}")
            return False
        except Exception as e:
            print(f"エラー: 状態ファイル削除中に予期せぬエラー ({type(e).__name__}: {e}) - {filepath}")
            return False
    else:
        # ファイルが存在しない場合は削除成功とみなす
        # print(f"状態ファイルは存在しませんでした: {filepath}")
        return True

# ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★

