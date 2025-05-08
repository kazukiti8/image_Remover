# utils/image_loader.py
import os
import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError # ★ UnidentifiedImageError をインポート ★
from typing import Tuple, Optional, Any

# pillow-heif をインポートして登録
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIF_AVAILABLE: bool = True
    print("pillow-heif を検出しました。HEIC/HEIF形式に対応します。")
except ImportError:
    HEIF_AVAILABLE = False
    print("警告: pillow-heif がインストールされていません。HEIC/HEIF形式は読み込めません。")
except Exception as e: # pillow_heif のインポート/登録中の予期せぬエラー
    HEIF_AVAILABLE = False
    print(f"警告: pillow-heif の初期化中にエラーが発生しました: {e}")


# ★ 型エイリアス ★
ImageType = Image.Image
NumpyImageType = np.ndarray[Any, Any]
ErrorMsgType = Optional[str]
PilLoadResult = Tuple[Optional[ImageType], ErrorMsgType]
NumpyLoadResult = Tuple[Optional[NumpyImageType], ErrorMsgType]
DimensionResult = Tuple[Optional[int], Optional[int]]

def load_image_pil(image_path: str) -> PilLoadResult:
    """
    Pillowを使用して画像を読み込む。HEIC/HEIFにも対応。
    エラーハンドリングを詳細化。
    """
    filename = os.path.basename(image_path) # エラーメッセージ用
    if not os.path.exists(image_path):
        return None, f"ファイルが見つかりません: {filename}"
    try:
        # ★ with を使ってファイルハンドルを管理 ★
        with Image.open(image_path) as img_pil:
            # 必要に応じてロード (通常は属性アクセス時に行われる)
            # img_pil.load()
            # ★ copy() して返すことで、with を抜けても画像データが有効 ★
            return img_pil.copy(), None
    except FileNotFoundError:
        # Image.open 内で発生する可能性も考慮
        return None, f"ファイルが見つかりません(Pillow): {filename}"
    except UnidentifiedImageError:
        return None, f"画像形式を認識できません(Pillow): {filename}"
    except OSError as e:
        # ファイル破損、アクセス権、ディスクI/Oエラーなど
        return None, f"ファイル読込エラー(Pillow OSError: {e}): {filename}"
    except MemoryError:
        return None, f"メモリ不足(Pillow): {filename}"
    except Exception as e:
        # pillow-heif 関連のエラーなども含む可能性
        error_type = type(e).__name__
        return None, f"予期せぬ画像読込エラー(Pillow {error_type}: {e}): {filename}"

def load_image_as_numpy(image_path: str, mode: str = 'bgr') -> NumpyLoadResult:
    """
    画像をNumPy配列として読み込む。HEIC/HEIFに対応。
    エラーハンドリングを詳細化。
    """
    filename = os.path.basename(image_path) # エラーメッセージ用
    if not os.path.exists(image_path):
        return None, f"ファイルが見つかりません: {filename}"

    img_np: Optional[NumpyImageType] = None
    error_msg: ErrorMsgType = None
    is_heif: bool = image_path.lower().endswith(('.heic', '.heif'))

    if is_heif and HEIF_AVAILABLE:
        img_pil: Optional[ImageType]
        pil_error: ErrorMsgType
        img_pil, pil_error = load_image_pil(image_path) # 詳細化されたエラーハンドリングを利用
        if pil_error:
            return None, f"HEIF読込失敗 ({pil_error}): {filename}"
        if img_pil:
            try:
                # 色空間/モード変換
                target_mode: Optional[str] = None
                if mode == 'gray':
                    if img_pil.mode == 'L': target_mode = 'L'
                    elif img_pil.mode in ['RGB', 'RGBA']: target_mode = 'L'
                    elif img_pil.mode == 'LA': target_mode = 'L' # アルファ捨てる
                    else: target_mode = 'L' # とりあえずグレースケールに
                elif mode in ['bgr', 'rgb']:
                    if img_pil.mode in ['RGB', 'RGBA']: target_mode = 'RGB'
                    elif img_pil.mode in ['L', 'LA']: target_mode = 'RGB' # グレースケールからRGBへ
                    elif img_pil.mode == 'P': target_mode = 'RGB' # パレットからRGBへ
                    else: target_mode = 'RGB' # とりあえずRGBに

                if target_mode and img_pil.mode != target_mode:
                    print(f"デバッグ: HEIFの色空間変換 {img_pil.mode} -> {target_mode} ({filename})")
                    img_pil_converted = img_pil.convert(target_mode)
                else:
                    img_pil_converted = img_pil

                # NumPy配列に変換
                img_converted_np: NumpyImageType = np.array(img_pil_converted)

                # OpenCVの色空間変換 (必要な場合)
                if mode == 'bgr' and len(img_converted_np.shape) == 3:
                    img_np = cv2.cvtColor(img_converted_np, cv2.COLOR_RGB2BGR)
                elif mode == 'gray' and len(img_converted_np.shape) == 3:
                     img_np = cv2.cvtColor(img_converted_np, cv2.COLOR_RGB2GRAY)
                else: # mode=='rgb' or mode=='gray' で元々グレースケールの場合
                    img_np = img_converted_np

            except MemoryError: error_msg = f"メモリ不足(HEIF->NumPy): {filename}"
            except ValueError as e: error_msg = f"値エラー(HEIF->NumPy/cvtColor: {e}): {filename}"
            except Exception as e: error_msg = f"変換エラー(HEIF->NumPy: {type(e).__name__} {e}): {filename}"
        else: error_msg = f"Pillowイメージ取得失敗(HEIF): {filename}" # load_image_pilがNoneを返した場合

    else: # HEIF以外、またはHEIF非対応の場合 -> OpenCVで読み込み
        try:
            read_flag: int = cv2.IMREAD_COLOR
            if mode == 'gray': read_flag = cv2.IMREAD_GRAYSCALE
            # elif mode == 'ignore_orientation': read_flag = cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION

            # ★ imdecode を使うことでファイルパスに日本語が含まれる場合の問題を回避 ★
            with open(image_path, 'rb') as f:
                file_bytes = np.frombuffer(f.read(), dtype=np.uint8)
            img_cv: Optional[NumpyImageType] = cv2.imdecode(file_bytes, read_flag)
            # img_cv = cv2.imread(image_path, read_flag) # 古い方法

            if img_cv is None:
                # imdecode が None を返すのは、データが不正などの場合
                error_msg = f"画像データをデコードできません(cv2): {filename}"
            else:
                # 必要な色空間変換
                if mode == 'rgb' and len(img_cv.shape) == 3:
                    img_np = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB)
                elif mode == 'gray' and len(img_cv.shape) == 3:
                    img_np = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
                else: # mode=='bgr' or mode=='gray'で元々グレースケール
                    img_np = img_cv

        except cv2.error as e: error_msg = f"OpenCVエラー(imdecode/cvtColor: {e.msg}): {filename}"
        except FileNotFoundError: error_msg = f"ファイルが見つかりません(cv2): {filename}" # open() で発生
        except OSError as e: error_msg = f"ファイル読込エラー(cv2 OSError: {e}): {filename}" # open() で発生
        except MemoryError: error_msg = f"メモリ不足(cv2): {filename}"
        except Exception as e: error_msg = f"予期せぬ画像読込エラー(cv2 {type(e).__name__}: {e}): {filename}"

    if error_msg:
        print(f"エラー: {error_msg}") # コンソールにも出力
        return None, error_msg
    elif img_np is None:
        # ここに来ることは少ないはずだが念のため
        err = f"画像データの取得に最終的に失敗: {filename}"
        print(f"エラー: {err}")
        return None, err
    else:
        return img_np, None

def get_image_dimensions(image_path: str) -> DimensionResult:
    """
    画像の幅と高さを取得する。HEIC/HEIFに対応。
    エラーハンドリングを詳細化。
    """
    filename = os.path.basename(image_path)
    # まず Pillow で試す (多くの形式に対応、Exifも読める可能性がある)
    img_pil: Optional[ImageType]
    error_msg_pil: ErrorMsgType
    img_pil, error_msg_pil = load_image_pil(image_path)
    if img_pil:
        try:
            width, height = img_pil.size
            return width, height
        except Exception as e:
            print(f"警告: Pillowでのサイズ取得中にエラー ({filename}): {e}")
            # Pillowで読めてもサイズ取得でエラーになる場合があるかもしれない
            # この場合、OpenCVで試すフォールバックは行わない

    # Pillow で読めなかった場合、OpenCV で試す
    img_np: Optional[NumpyImageType]
    error_msg_np: ErrorMsgType
    # modeは何でも良いが、メモリ消費が少ない gray を試す
    img_np, error_msg_np = load_image_as_numpy(image_path, mode='gray')
    if img_np is not None:
        try:
            # shape は (height, width, [channels])
            h, w = img_np.shape[:2]
            return w, h
        except Exception as e:
             print(f"警告: NumPy配列からのサイズ取得中にエラー ({filename}): {e}")

    # どちらでも取得できなかった場合
    combined_error = f"Pillow:({error_msg_pil or '成功?'}), OpenCV:({error_msg_np or '成功?'})"
    print(f"警告: 画像サイズの取得に失敗しました ({filename}) - {combined_error}")
    return None, None

