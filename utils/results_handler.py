# utils/results_handler.py
import json
import os
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any, Union # ★ typing をインポート ★

# 結果データのバージョン
RESULTS_FORMAT_VERSION: str = "1.0"

# ★ 型エイリアス ★
BlurResultItem = Dict[str, Union[str, float]] # {'path': str, 'score': float}
SimilarResultItem = List[Union[str, int]] # [path1: str, path2: str, score: int]
DuplicateResultDict = Dict[str, List[str]] # {hash: [path1, path2, ...]}
ErrorResultItem = Dict[str, str] # {'type': str, 'path': str, 'error': str, ...} # path1/path2 も含む可能性

ResultsData = Dict[
    str,
    Union[List[BlurResultItem], List[SimilarResultItem], DuplicateResultDict, List[ErrorResultItem]]
]
SettingsData = Dict[str, Any] # 設定データは型が混在するので Any
LoadResult = Tuple[Optional[ResultsData], Optional[str], Optional[SettingsData], Optional[str]] # (results, dir, settings, error_msg)

def save_results_to_file(filepath: str,
                         results_data: ResultsData,
                         scanned_directory: str,
                         settings_used: Optional[SettingsData] = None) -> bool:
    """
    スキャン結果を指定されたJSONファイルに保存します。
    """
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
    """
    JSONファイルからスキャン結果を読み込みます。
    """
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

        # 結果データの型チェックと補完
        results_data: ResultsData = {}
        expected_keys: Dict[str, type] = {'blurry': list, 'similar': list, 'duplicates': dict, 'errors': list}
        for key, expected_type in expected_keys.items():
            data_item: Any = results_container.get(key)
            if data_item is None:
                print(f"警告: 結果データにキー '{key}' がありません。空として扱います。")
                results_data[key] = expected_type() # 空データで補完
            elif isinstance(data_item, expected_type):
                 results_data[key] = data_item # 型が一致すればそのまま格納
            else:
                 return None, None, None, f"無効なファイル形式 (結果データ '{key}' の型不正)。"

        print(f"結果を読み込みました: {filepath}")
        return results_data, scanned_directory, settings_used, None # 成功

    except json.JSONDecodeError as e: return None, None, None, f"JSONファイルの解析失敗: {e}"
    except OSError as e: return None, None, None, f"結果ファイルの読み込み失敗 (OSError: {e})"
    except Exception as e: return None, None, None, f"結果ファイル読み込み中に予期せぬエラー ({type(e).__name__}: {e})"

