# utils/image_loader.py
import os
import cv2
import numpy as np
from PIL import Image

# pillow-heif をインポートして登録
try:
    import pillow_heif
    pillow_heif.register_heif_opener() # Pillow で HEIF/HEIC を開けるように登録
    HEIF_AVAILABLE = True
    print("pillow-heif を検出しました。HEIC/HEIF形式に対応します。")
except ImportError:
    HEIF_AVAILABLE = False
    print("警告: pillow-heif がインストールされていません。HEIC/HEIF形式は読み込めません。")

def load_image_pil(image_path):
    """
    Pillowを使用して画像を読み込む。HEIC/HEIFにも対応。

    Args:
        image_path (str): 画像ファイルのパス。

    Returns:
        tuple: (PIL.Image.Image or None, str or None)
               成功時は (Pillowイメージオブジェクト, None)。
               失敗時は (None, エラーメッセージ)。
    """
    if not os.path.exists(image_path):
        return None, f"ファイルが見つかりません: {os.path.basename(image_path)}"
    try:
        # Pillow で画像を開く (pillow-heif が登録されていれば HEIC も開ける)
        img_pil = Image.open(image_path)
        # 必要であればここで Orientation 補正を行うことも可能
        # img_pil.load() # 遅延読み込みを解決する場合
        return img_pil, None
    except FileNotFoundError: # open() でも発生しうる
        return None, f"ファイルが見つかりません(Pillow): {os.path.basename(image_path)}"
    except Exception as e:
        error_msg = f"画像読込エラー(Pillow: {type(e).__name__}): {e}"
        print(f"エラー: Pillowでの画像読み込み中にエラー ({os.path.basename(image_path)}): {e}")
        return None, error_msg

def load_image_as_numpy(image_path, mode='bgr'):
    """
    画像をNumPy配列として読み込む。HEIC/HEIFに対応。

    Args:
        image_path (str): 画像ファイルのパス。
        mode (str): 読み込みモード ('bgr', 'rgb', 'gray')。

    Returns:
        tuple: (np.ndarray or None, str or None)
               成功時は (NumPy配列, None)。
               失敗時は (None, エラーメッセージ)。
    """
    if not os.path.exists(image_path):
        return None, f"ファイルが見つかりません: {os.path.basename(image_path)}"

    img_np = None
    error_msg = None

    # HEIC/HEIF の可能性があるか拡張子で判定
    is_heif = image_path.lower().endswith(('.heic', '.heif'))

    if is_heif and HEIF_AVAILABLE:
        # HEIC/HEIF の場合は Pillow (pillow-heif経由) で読み込み、NumPy に変換
        img_pil, pil_error = load_image_pil(image_path)
        if pil_error:
            return None, pil_error
        if img_pil:
            try:
                # Pillow イメージを NumPy 配列 (RGB) に変換
                # RGBA や P モードの場合、RGB に変換
                if img_pil.mode == 'RGBA':
                    img_pil = img_pil.convert('RGB')
                elif img_pil.mode == 'P':
                    img_pil = img_pil.convert('RGB')
                elif img_pil.mode == 'LA':
                    img_pil = img_pil.convert('L') # グレースケールに

                img_rgb = np.array(img_pil)

                # 必要に応じて色空間を変換
                if mode == 'bgr':
                    if len(img_rgb.shape) == 3 and img_rgb.shape[2] == 3: # カラー画像か確認
                         img_np = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
                    elif len(img_rgb.shape) == 2: # グレースケールの場合
                         img_np = cv2.cvtColor(img_rgb, cv2.COLOR_GRAY2BGR) # BGRに変換
                    else:
                         error_msg = "未対応のチャンネル数(Pillow RGB->BGR)"
                elif mode == 'gray':
                    if len(img_rgb.shape) == 3 and img_rgb.shape[2] == 3:
                         img_np = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
                    elif len(img_rgb.shape) == 2:
                         img_np = img_rgb # そのまま
                    else:
                         error_msg = "未対応のチャンネル数(Pillow RGB->Gray)"
                elif mode == 'rgb':
                    img_np = img_rgb # そのまま
                else:
                    error_msg = f"未対応の読み込みモード: {mode}"

            except Exception as e:
                error_msg = f"NumPy変換/色空間変換エラー({type(e).__name__}): {e}"
                print(f"エラー: HEIF読み込み後のNumPy変換/色空間変換中にエラー ({os.path.basename(image_path)}): {e}")
    else:
        # HEIC/HEIF 以外、または pillow-heif が利用できない場合は OpenCV で読み込み
        try:
            read_flag = cv2.IMREAD_COLOR
            if mode == 'gray':
                read_flag = cv2.IMREAD_GRAYSCALE
            elif mode == 'ignore_orientation': # 将来用
                 read_flag = cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION

            img_cv = cv2.imread(image_path, read_flag)

            if img_cv is None:
                error_msg = f"画像を読み込めません(cv2): {os.path.basename(image_path)}"
            else:
                # 必要に応じて色空間を変換 (OpenCVはBGRで読み込む)
                if mode == 'rgb' and len(img_cv.shape) == 3:
                    img_np = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB)
                elif mode == 'gray' and len(img_cv.shape) == 3:
                     img_np = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
                else: # bgr または gray で読み込んだ場合
                    img_np = img_cv

        except cv2.error as e:
            error_msg = f"OpenCVエラー: {e.msg}"
            print(f"エラー: OpenCVでの画像読み込み中にエラー ({os.path.basename(image_path)}): {e.msg}")
        except Exception as e:
            error_msg = f"画像読込エラー(cv2: {type(e).__name__}): {e}"
            print(f"エラー: OpenCVでの画像読み込み中に予期せぬエラー ({os.path.basename(image_path)}): {e}")

    if error_msg:
        return None, error_msg
    elif img_np is None: # フォールスルーでNoneになった場合
         return None, "画像データの取得に失敗"
    else:
        return img_np, None

def get_image_dimensions(image_path):
    """
    画像の幅と高さを取得する。HEIC/HEIFに対応。

    Args:
        image_path (str): 画像ファイルのパス。

    Returns:
        tuple: (int, int) or (None, None)
               成功時は (幅, 高さ)。
               失敗時は (None, None)。
    """
    # まず Pillow (HEIF対応) で試す
    img_pil, error_msg_pil = load_image_pil(image_path)
    if img_pil:
        try:
            width, height = img_pil.size
            return width, height
        except Exception as e:
            print(f"警告: Pillowでのサイズ取得中にエラー ({os.path.basename(image_path)}): {e}")
            # Pillowでエラーが出ても OpenCV で試す

    # Pillow で読めなかった場合、OpenCV で試す
    # (HEIC以外、または pillow-heif がない場合)
    img_np, error_msg_np = load_image_as_numpy(image_path, mode='bgr') # モードは何でも良い
    if img_np is not None:
        try:
            h, w = img_np.shape[:2]
            return w, h
        except Exception as e:
             print(f"警告: NumPy配列からのサイズ取得中にエラー ({os.path.basename(image_path)}): {e}")

    # どちらでも読めなかった場合
    print(f"警告: 画像サイズの取得に失敗しました ({os.path.basename(image_path)}) - Pillow:{error_msg_pil}, CV2:{error_msg_np}")
    return None, None
