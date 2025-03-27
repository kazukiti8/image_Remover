import os
import sys
import cv2
import numpy as np
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import shutil
import hashlib
from datetime import datetime
import pickle
import threading

class SimiPix:
    def __init__(self, root):
        self.root = root
        self.root.title("SimiPix")
        self.root.geometry("1400x800")
        
        # Variables
        self.source_folder = tk.StringVar()
        self.destination_folder = tk.StringVar()
        self.similarity_threshold = tk.DoubleVar(value=90.0)
        self.use_cache = tk.BooleanVar(value=True)
        self.move_to_trash = tk.BooleanVar(value=False)
        self.left_priority_extensions = tk.StringVar(value="jpg,png,jpeg")
        
        self.images_data = []
        self.current_index = 0
        self.cache = {}
        self.cache_file = None
        self.scanning = False
        
        # Create UI
        self.create_ui()
        
        # Bind keyboard shortcuts
        self.root.bind('<q>', lambda e: self.move_image('left'))
        self.root.bind('<w>', lambda e: self.move_image('right'))
        self.root.bind('<a>', lambda e: self.open_image('left'))
        self.root.bind('<s>', lambda e: self.open_image('right'))
        
    def create_ui(self):
        # Top frame for folder selection
        top_frame = ttk.Frame(self.root, padding=5)
        top_frame.pack(fill=tk.X)
        
        ttk.Label(top_frame, text="検索フォルダ:").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(top_frame, textvariable=self.source_folder, width=70).grid(row=0, column=1, padx=5)
        ttk.Button(top_frame, text="...", width=3, command=self.browse_source).grid(row=0, column=2)
        
        ttk.Label(top_frame, text="移動先フォルダ:").grid(row=1, column=0, sticky=tk.W)
        ttk.Entry(top_frame, textvariable=self.destination_folder, width=70).grid(row=1, column=1, padx=5)
        ttk.Button(top_frame, text="...", width=3, command=self.browse_destination).grid(row=1, column=2)
        
        # Image list frame
        list_frame = ttk.Frame(self.root, padding=5)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create treeview for image list
        columns = ('filename', 'size', 'date', 'width', 'height', 'path')
        self.tree = ttk.Treeview(list_frame, columns=columns, show='headings')
        
        # Set column headings
        self.tree.heading('filename', text='画像名')
        self.tree.heading('size', text='サイズ')
        self.tree.heading('date', text='日付')
        self.tree.heading('width', text='幅')
        self.tree.heading('height', text='高さ')
        self.tree.heading('path', text='画像名')
        
        # Configure columns
        self.tree.column('filename', width=200)
        self.tree.column('size', width=80)
        self.tree.column('date', width=150)
        self.tree.column('width', width=50)
        self.tree.column('height', width=50)
        self.tree.column('path', width=400)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        
        # Pack treeview and scrollbar
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.tree.bind('<<TreeviewSelect>>', self.on_tree_select)
        
        # Image display frame
        display_frame = ttk.Frame(self.root, padding=5)
        display_frame.pack(fill=tk.BOTH, expand=True)
        
        # Left image frame
        left_frame = ttk.LabelFrame(display_frame, text="左画像", padding=5)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.left_info = ttk.Label(left_frame, text="")
        self.left_info.pack(fill=tk.X)
        
        self.left_canvas = tk.Canvas(left_frame, bg='white')
        self.left_canvas.pack(fill=tk.BOTH, expand=True)
        
        # Right image frame
        right_frame = ttk.LabelFrame(display_frame, text="右画像", padding=5)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self.right_info = ttk.Label(right_frame, text="")
        self.right_info.pack(fill=tk.X)
        
        self.right_canvas = tk.Canvas(right_frame, bg='white')
        self.right_canvas.pack(fill=tk.BOTH, expand=True)
        
        # Bottom control frame
        control_frame = ttk.Frame(self.root, padding=5)
        control_frame.pack(fill=tk.X)
        
        # Left side controls
        left_controls = ttk.Frame(control_frame)
        left_controls.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Label(left_controls, text="類似しきい値:").grid(row=0, column=0, sticky=tk.W)
        ttk.Scale(left_controls, from_=0, to=100, variable=self.similarity_threshold, 
                 length=200).grid(row=0, column=1, padx=5)
        ttk.Label(left_controls, textvariable=self.similarity_threshold).grid(row=0, column=2)
        
        ttk.Checkbutton(left_controls, text="キャッシュ有効", variable=self.use_cache).grid(row=1, column=0, sticky=tk.W)
        ttk.Checkbutton(left_controls, text="ごみ箱に移動する", variable=self.move_to_trash).grid(row=1, column=1, sticky=tk.W)
        
        ttk.Label(left_controls, text="左側優先拡張子:").grid(row=2, column=0, sticky=tk.W)
        ttk.Entry(left_controls, textvariable=self.left_priority_extensions, width=30).grid(row=2, column=1, padx=5, sticky=tk.W)
        
        # Right side controls
        right_controls = ttk.Frame(control_frame)
        right_controls.pack(side=tk.RIGHT)
        
        ttk.Button(right_controls, text="検索", command=self.start_scan).grid(row=0, column=0, padx=5)
        ttk.Button(right_controls, text="中止", command=self.stop_scan).grid(row=0, column=1, padx=5)
        ttk.Button(right_controls, text="まとめて移動", command=self.batch_move).grid(row=0, column=2, padx=5)
    
    def browse_source(self):
        folder = filedialog.askdirectory()
        if folder:
            self.source_folder.set(folder)
    
    def browse_destination(self):
        folder = filedialog.askdirectory()
        if folder:
            self.destination_folder.set(folder)
    
    def start_scan(self):
        if not self.source_folder.get():
            messagebox.showerror("エラー", "検索フォルダを指定してください")
            return
            
        if self.scanning:
            return
            
        # Clear previous results
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        self.images_data = []
        self.current_index = 0
        
        # Start scanning in a separate thread
        self.scanning = True
        threading.Thread(target=self.scan_images, daemon=True).start()
    
    def stop_scan(self):
        self.scanning = False
    
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
    
    def scan_images(self):
        source_dir = self.source_folder.get()
        
        # Load or create cache
        self.cache_file = os.path.join(source_dir, "_cache.spx")
        if self.use_cache.get() and os.path.exists(self.cache_file):
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
                if self.scanning is False:
                    break
                    
                ext = os.path.splitext(file)[1].lower()
                if ext in ['.jpg', '.jpeg', '.png', '.bmp', '.gif']:
                    image_files.append(os.path.join(root, file))
        
        # Process images
        for i, img_path in enumerate(image_files):
            if self.scanning is False:
                break
                
            # Update status
            self.root.title(f"SimiPix - 検索中... {i+1}/{len(image_files)} - {os.path.basename(img_path)}")
            
            # Get image data
            try:
                # Check if in cache
                file_stats = os.stat(img_path)
                file_modified = file_stats.st_mtime
                file_size = file_stats.st_size
                
                cache_key = f"{img_path}:{file_size}:{file_modified}"
                
                if self.use_cache.get() and cache_key in self.cache:
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
                self.images_data.append(img_data)
                
                # Add to UI (in main thread)
                self.root.after(0, self.add_to_tree, img_data)
            except Exception as e:
                print(f"Error processing {img_path}: {e}")
        
        # Find similar images
        if self.scanning and len(self.images_data) > 0:
            self.find_similar_images()
        
        # Save cache
        if self.use_cache.get():
            try:
                with open(self.cache_file, 'wb') as f:
                    pickle.dump(self.cache, f)
            except Exception as e:
                print(f"Error saving cache: {e}")
        
        self.scanning = False
        self.root.after(0, lambda: self.root.title("SimiPix"))
    
    def add_to_tree(self, img_data):
        """Add image to tree (called from main thread)"""
        self.tree.insert('', tk.END, values=(
            img_data['filename'],
            f"{img_data['size']:,}",
            img_data['date'],
            img_data['width'],
            img_data['height'],
            img_data['path']
        ))
    
    def find_similar_images(self):
        threshold = self.similarity_threshold.get() / 100
        
        similar_pairs = []
        
        for i in range(len(self.images_data)):
            if self.scanning is False:
                break
                
            img1 = self.images_data[i]
            hash1 = np.unpackbits(img1['hash'])
            
            for j in range(i+1, len(self.images_data)):
                if self.scanning is False:
                    break
                    
                img2 = self.images_data[j]
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
                self.root.after(0, self.highlight_tree_item, i, j)
            except Exception as e:
                print(f"Error highlighting items: {e}")
        
        # Display first similar pair if exists
        if similar_pairs:
            i, j, _ = similar_pairs[0]
            self.root.after(0, self.display_image_pair, i, j)
    
    def highlight_tree_item(self, i, j):
        """Highlight tree items (called from main thread)"""
        try:
            children = self.tree.get_children()
            if i < len(children) and j < len(children):
                self.tree.item(children[i], tags=('similar',))
                self.tree.item(children[j], tags=('similar',))
                self.tree.tag_configure('similar', background='#FFEEEE')
        except Exception as e:
            print(f"Error in highlight_tree_item: {e}")
    
    def on_tree_select(self, event):
        selected = self.tree.selection()
        if selected:
            idx = self.tree.index(selected[0])
            self.display_image('left', idx)
    
    def display_image_pair(self, left_idx, right_idx):
        self.display_image('left', left_idx)
        self.display_image('right', right_idx)
    
    def display_image(self, side, idx):
        if idx >= len(self.images_data):
            return
            
        img_data = self.images_data[idx]
        img_path = img_data['path']
        
        try:
            # Check if file exists
            if not os.path.exists(img_path):
                print(f"ファイルが見つかりません (表示): {img_path}")
                return
                
            # Load image with PIL
            img = Image.open(img_path)
            
            # Get canvas dimensions
            canvas = self.left_canvas if side == 'left' else self.right_canvas
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
                self.left_info.config(text=f"{os.path.basename(img_path)}\n{img_width} x {img_height}, {img_data['size']:,} bytes")
                self.left_idx = idx
            else:
                self.right_photo = photo
                self.right_info.config(text=f"{os.path.basename(img_path)}\n{img_width} x {img_height}, {img_data['size']:,} bytes")
                self.right_idx = idx
        except Exception as e:
            print(f"Error displaying {img_path}: {e}")
    
    def move_image(self, side):
        if not self.destination_folder.get():
            messagebox.showerror("エラー", "移動先フォルダを指定してください")
            return
            
        try:
            if side == 'left' and hasattr(self, 'left_idx'):
                img_data = self.images_data[self.left_idx]
            elif side == 'right' and hasattr(self, 'right_idx'):
                img_data = self.images_data[self.right_idx]
            else:
                return
                
            src_path = img_data['path']
            filename = os.path.basename(src_path)
            dst_path = os.path.join(self.destination_folder.get(), filename)
            
            # Check if source file exists
            if not os.path.exists(src_path):
                messagebox.showerror("エラー", f"ファイルが見つかりません: {src_path}")
                return
                
            # Move or copy file
            if self.move_to_trash.get():
                try:
                    import send2trash
                    send2trash.send2trash(src_path)
                except ImportError:
                    # Fall back to regular delete if send2trash not available
                    os.remove(src_path)
            else:
                shutil.move(src_path, dst_path)
                
            # Remove from tree and data
            if side == 'left' and hasattr(self, 'left_idx'):
                tree_item = self.tree.get_children()[self.left_idx]
                self.tree.delete(tree_item)
                del self.images_data[self.left_idx]
            elif side == 'right' and hasattr(self, 'right_idx'):
                tree_item = self.tree.get_children()[self.right_idx]
                self.tree.delete(tree_item)
                del self.images_data[self.right_idx]
                
            # Refresh display
            self.display_next_pair()
        except Exception as e:
            messagebox.showerror("エラー", f"移動中にエラーが発生しました: {e}")
    
    def display_next_pair(self):
        # Simple implementation - just show first pair
        if len(self.images_data) >= 2:
            self.display_image_pair(0, 1)
    
    def open_image(self, side):
        try:
            if side == 'left' and hasattr(self, 'left_idx'):
                img_data = self.images_data[self.left_idx]
            elif side == 'right' and hasattr(self, 'right_idx'):
                img_data = self.images_data[self.right_idx]
            else:
                return
                
            # Check if file exists
            if not os.path.exists(img_data['path']):
                messagebox.showerror("エラー", f"ファイルが見つかりません: {img_data['path']}")
                return
                
            # Open with default application
            if sys.platform == 'win32':
                os.startfile(img_data['path'])
            elif sys.platform == 'darwin':  # macOS
                import subprocess
                subprocess.call(('open', img_data['path']))
            else:  # Linux
                import subprocess
                subprocess.call(('xdg-open', img_data['path']))
        except Exception as e:
            messagebox.showerror("エラー", f"画像を開く際にエラーが発生しました: {e}")
    
    def batch_move(self):
        # Not implemented
        messagebox.showinfo("情報", "この機能はまだ実装されていません")

if __name__ == "__main__":
    root = tk.Tk()
    app = SimiPix(root)
    root.mainloop()