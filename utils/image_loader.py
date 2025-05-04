# utils/image_loader.py
import os
import cv2
import numpy as np
from PIL import Image
from typing import Tuple, Optional, Any # ★ typing モジュールから必要な型をインポート ★

# pillow-heif をインポートして登録
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIF_AVAILABLE: bool = True # ★ 型ヒント追加 ★
    print("pillow-heif を検出しました。HEIC/HEIF形式に対応します。")
except ImportError:
    HEIF_AVAILABLE = False
    print("警告: pillow-heif がインストールされていません。HEIC/HEIF形式は読み込めません。")

# ★ 型エイリアスを定義 (可読性のため) ★
ImageType = Image.Image # Pillow の Image 型
NumpyImageType = np.ndarray[Any, Any] # NumPy 配列の型 (より具体的に shape を指定しても良い)
ErrorMsgType = Optional[str] # エラーメッセージ (str または None)
PilLoadResult = Tuple[Optional[ImageType], ErrorMsgType]
NumpyLoadResult = Tuple[Optional[NumpyImageType], ErrorMsgType]
DimensionResult = Tuple[Optional[int], Optional[int]]

def load_image_pil(image_path: str) -> PilLoadResult:
    """
    Pillowを使用して画像を読み込む。HEIC/HEIFにも対応。

    Args:
        image_path (str): 画像ファイルのパス。

    Returns:
        PilLoadResult: (Pillowイメージオブジェクト or None, エラーメッセージ or None)
    """
    if not os.path.exists(image_path):
        return None, f"ファイルが見つかりません: {os.path.basename(image_path)}"
    try:
        img_pil: ImageType = Image.open(image_path)
        # img_pil.load() # 必要であればコメント解除
        return img_pil, None
    except FileNotFoundError:
        return None, f"ファイルが見つかりません(Pillow): {os.path.basename(image_path)}"
    except Exception as e:
        error_msg: str = f"画像読込エラー(Pillow: {type(e).__name__}): {e}"
        print(f"エラー: Pillowでの画像読み込み中にエラー ({os.path.basename(image_path)}): {e}")
        return None, error_msg

def load_image_as_numpy(image_path: str, mode: str = 'bgr') -> NumpyLoadResult:
    """
    画像をNumPy配列として読み込む。HEIC/HEIFに対応。

    Args:
        image_path (str): 画像ファイルのパス。
        mode (str): 読み込みモード ('bgr', 'rgb', 'gray')。

    Returns:
        NumpyLoadResult: (NumPy配列 or None, エラーメッセージ or None)
    """
    if not os.path.exists(image_path):
        return None, f"ファイルが見つかりません: {os.path.basename(image_path)}"

    img_np: Optional[NumpyImageType] = None
    error_msg: ErrorMsgType = None

    is_heif: bool = image_path.lower().endswith(('.heic', '.heif'))

    if is_heif and HEIF_AVAILABLE:
        img_pil: Optional[ImageType]
        pil_error: ErrorMsgType
        img_pil, pil_error = load_image_pil(image_path)
        if pil_error:
            return None, pil_error
        if img_pil:
            try:
                if img_pil.mode == 'RGBA': img_pil = img_pil.convert('RGB')
                elif img_pil.mode == 'P': img_pil = img_pil.convert('RGB')
                elif img_pil.mode == 'LA': img_pil = img_pil.convert('L')

                img_rgb: NumpyImageType = np.array(img_pil)

                if mode == 'bgr':
                    if len(img_rgb.shape) == 3 and img_rgb.shape[2] == 3: img_np = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
                    elif len(img_rgb.shape) == 2: img_np = cv2.cvtColor(img_rgb, cv2.COLOR_GRAY2BGR)
                    else: error_msg = "未対応のチャンネル数(Pillow RGB->BGR)"
                elif mode == 'gray':
                    if len(img_rgb.shape) == 3 and img_rgb.shape[2] == 3: img_np = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
                    elif len(img_rgb.shape) == 2: img_np = img_rgb
                    else: error_msg = "未対応のチャンネル数(Pillow RGB->Gray)"
                elif mode == 'rgb':
                    img_np = img_rgb
                else:
                    error_msg = f"未対応の読み込みモード: {mode}"
            except Exception as e:
                error_msg = f"NumPy変換/色空間変換エラー({type(e).__name__}): {e}"
                print(f"エラー: HEIF読み込み後のNumPy変換/色空間変換中にエラー ({os.path.basename(image_path)}): {e}")
    else:
        try:
            read_flag: int = cv2.IMREAD_COLOR
            if mode == 'gray': read_flag = cv2.IMREAD_GRAYSCALE
            # elif mode == 'ignore_orientation': read_flag = cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION

            img_cv: Optional[NumpyImageType] = cv2.imread(image_path, read_flag)

            if img_cv is None: error_msg = f"画像を読み込めません(cv2): {os.path.basename(image_path)}"
            else:
                if mode == 'rgb' and len(img_cv.shape) == 3: img_np = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB)
                elif mode == 'gray' and len(img_cv.shape) == 3: img_np = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
                else: img_np = img_cv
        except cv2.error as e: error_msg = f"OpenCVエラー: {e.msg}"; print(f"エラー: OpenCVでの画像読み込み中にエラー ({os.path.basename(image_path)}): {e.msg}")
        except Exception as e: error_msg = f"画像読込エラー(cv2: {type(e).__name__}): {e}"; print(f"エラー: OpenCVでの画像読み込み中に予期せぬエラー ({os.path.basename(image_path)}): {e}")

    if error_msg: return None, error_msg
    elif img_np is None: return None, "画像データの取得に失敗"
    else: return img_np, None

def get_image_dimensions(image_path: str) -> DimensionResult:
    """
    画像の幅と高さを取得する。HEIC/HEIFに対応。

    Args:
        image_path (str): 画像ファイルのパス。

    Returns:
        DimensionResult: (幅: int or None, 高さ: int or None)
    """
    img_pil: Optional[ImageType]
    error_msg_pil: ErrorMsgType
    img_pil, error_msg_pil = load_image_pil(image_path)
    if img_pil:
        try:
            width: int
            height: int
            width, height = img_pil.size
            return width, height
        except Exception as e:
            print(f"警告: Pillowでのサイズ取得中にエラー ({os.path.basename(image_path)}): {e}")

    img_np: Optional[NumpyImageType]
    error_msg_np: ErrorMsgType
    img_np, error_msg_np = load_image_as_numpy(image_path, mode='bgr') # モードは何でも良い
    if img_np is not None:
        try:
            h: int
            w: int
            # shape は (height, width, [channels])
            h, w = img_np.shape[:2]
            return w, h
        except Exception as e:
             print(f"警告: NumPy配列からのサイズ取得中にエラー ({os.path.basename(image_path)}): {e}")

    print(f"警告: 画像サイズの取得に失敗しました ({os.path.basename(image_path)}) - Pillow:{error_msg_pil}, CV2:{error_msg_np}")
    return None, None
