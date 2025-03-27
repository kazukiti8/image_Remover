import os
import pickle
from datetime import datetime
from PIL import Image
import numpy as np

class ImageScanner:
    def __init__(self, app):
        self.app = app
        self.cache = {}
        self.cache_file = None
    
    def scan_images(self):
        source_dir = self.app.source_folder.get()
        
        # Load or create cache
        self.cache_file = os.path.join(source_dir, "_cache.spx")
        if self.app.use_cache.get() and os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'rb') as f:
                    self.cache = pickle.load(f)
            except:
                self.cache = {}
        else:
            self.cache = {}
        
        # Get all image files
        image_files = []
        for root, _, files in os.walk(source_dir):
            for file in files:
                if self.app.scanning is False:
                    break
                    
                ext = os.path.splitext(file)[1].lower()
                if ext in ['.jpg', '.jpeg', '.png', '.bmp', '.gif']:
                    image_files.append(os.path.join(root, file))
        
        # Process images
        for i, img_path in enumerate(image_files):
            if self.app.scanning is False:
                break
                
            # Update status
            self.app.root.title(f"SimiPix - 検索中... {i+1}/{len(image_files)} - {os.path.basename(img_path)}")
            
            # Get image data
            try:
                # Check if in cache
                file_stats = os.stat(img_path)
                file_modified = file_stats.st_mtime
                file_size = file_stats.st_size
                
                cache_key = f"{img_path}:{file_size}:{file_modified}"
                
                if self.app.use_cache.get() and cache_key in self.cache:
                    img_data = self.cache[cache_key]
                else:
                    # Check file existence
                    if not os.path.exists(img_path):
                        print(f"ファイルが見つかりません: {img_path}")
                        continue
                        
                    # Open image with PIL for width/height
                    try:
                        pil_img = Image.open(img_path)
                        width, height = pil_img.size
                    except Exception as e:
                        print(f"画像を開けませんでした {img_path}: {e}")
                        continue
                    
                    # Compute hash
                    hash_bytes = self.compute_image_hash(img_path)
                    if hash_bytes is None:
                        continue
                    
                    # Get file date
                    date_str = datetime.fromtimestamp(file_modified).strftime('%Y/%m/%d %H:%M:%S')
                    
                    img_data = {
                        'path': img_path,
                        'filename': os.path.basename(img_path),
                        'size': file_size,
                        'date': date_str,
                        'width': width,
                        'height': height,
                        'hash': hash_bytes
                    }
                    
                    # Save to cache
                    self.cache[cache_key] = img_data
                
                # Add to images data
                self.app.images_data.append(img_data)
                
                # Add to UI (in main thread)
                self.app.root.after(0, self.app.ui.add_to_tree, img_data)
            except Exception as e:
                print(f"Error processing {img_path}: {e}")
        
        # Find similar images
        if self.app.scanning and len(self.app.images_data) > 0:
            self.app.processor.find_similar_images()
        
        # Save cache
        if self.app.use_cache.get():
            try:
                with open(self.cache_file, 'wb') as f:
                    pickle.dump(self.cache, f)
            except Exception as e:
                print(f"Error saving cache: {e}")
        
        self.app.scanning = False
        self.app.root.after(0, lambda: self.app.root.title("SimiPix"))
    
    def compute_image_hash(self, img_path):
        """計算画像ハッシュ (日本語パス対応)"""
        try:
            # Use PIL to open image (better Unicode support)
            pil_img = Image.open(img_path)
            
            # Resize for feature computation
            pil_img_resized = pil_img.resize((64, 64))
            
            # Convert to grayscale
            if pil_img_resized.mode != 'L':
                pil_img_resized = pil_img_resized.convert('L')
                
            # Convert to numpy array
            gray = np.array(pil_img_resized)
            
            # Compute average hash
            avg = gray.mean()
            hash_img = (gray >= avg).flatten()
            
            # Convert to bytes for storage
            hash_bytes = np.packbits(hash_img)
            
            return hash_bytes
        except Exception as e:
            print(f"ハッシュ計算エラー {img_path}: {e}")
            return None