import os
import numpy as np
from PIL import Image, ImageTk
import tkinter as tk

class ImageProcessor:
    def __init__(self, app):
        self.app = app
        self.left_photo = None
        self.right_photo = None
        self.left_idx = None
        self.right_idx = None
    
    def find_similar_images(self):
        threshold = self.app.similarity_threshold.get() / 100
        
        similar_pairs = []
        
        for i in range(len(self.app.images_data)):
            if self.app.scanning is False:
                break
                
            img1 = self.app.images_data[i]
            hash1 = np.unpackbits(img1['hash'])
            
            for j in range(i+1, len(self.app.images_data)):
                if self.app.scanning is False:
                    break
                    
                img2 = self.app.images_data[j]
                hash2 = np.unpackbits(img2['hash'])
                
                # Calculate similarity (Hamming distance)
                similarity = 1 - np.count_nonzero(hash1 != hash2) / len(hash1)
                
                if similarity >= threshold:
                    similar_pairs.append((i, j, similarity))
        
        # Sort by similarity (highest first)
        similar_pairs.sort(key=lambda x: x[2], reverse=True)
        
        # Update tree to highlight similar images
        for i, j, similarity in similar_pairs:
            # Update items in tree to show they have similar pairs
            try:
                self.app.root.after(0, self.app.ui.highlight_tree_item, i, j)
            except Exception as e:
                print(f"Error highlighting items: {e}")
        
        # Display first similar pair if exists
        if similar_pairs:
            i, j, _ = similar_pairs[0]
            self.app.root.after(0, self.display_image_pair, i, j)
    
    def display_image_pair(self, left_idx, right_idx):
        self.display_image('left', left_idx)
        self.display_image('right', right_idx)
    
    def display_image(self, side, idx):
        if idx >= len(self.app.images_data):
            return
            
        img_data = self.app.images_data[idx]
        img_path = img_data['path']
        
        try:
            # Check if file exists
            if not os.path.exists(img_path):
                print(f"ファイルが見つかりません (表示): {img_path}")
                return
                
            # Load image with PIL
            img = Image.open(img_path)
            
            # Get canvas dimensions
            canvas = self.app.ui.left_canvas if side == 'left' else self.app.ui.right_canvas
            canvas_width = canvas.winfo_width()
            canvas_height = canvas.winfo_height()
            
            # If canvas is not yet realized, use minimal dimensions
            if canvas_width <= 1:
                canvas_width = 300
            if canvas_height <= 1:
                canvas_height = 300
            
            # Resize to fit canvas while preserving aspect ratio
            img_width, img_height = img.size
            scale = min(canvas_width/img_width, canvas_height/img_height)
            
            if scale < 1:
                new_width = int(img_width * scale)
                new_height = int(img_height * scale)
                img = img.resize((new_width, new_height), Image.LANCZOS)
            
            # Convert to PhotoImage
            photo = ImageTk.PhotoImage(img)
            
            # Clear canvas and display image
            canvas.delete("all")
            canvas.create_image(canvas_width//2, canvas_height//2, image=photo, anchor=tk.CENTER)
            
            # Store reference to prevent garbage collection
            if side == 'left':
                self.left_photo = photo
                self.app.ui.left_info.config(text=f"{os.path.basename(img_path)}\n{img_width} x {img_height}, {img_data['size']:,} bytes")
                self.left_idx = idx
            else:
                self.right_photo = photo
                self.app.ui.right_info.config(text=f"{os.path.basename(img_path)}\n{img_width} x {img_height}, {img_data['size']:,} bytes")
                self.right_idx = idx
        except Exception as e:
            print(f"Error displaying {img_path}: {e}")
    
    def display_next_pair(self):
        # Simple implementation - just show first pair
        if len(self.app.images_data) >= 2:
            self.display_image_pair(0, 1)