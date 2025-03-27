import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os

from ui.app_ui import AppUI
from core.image_scanner import ImageScanner
from core.image_processor import ImageProcessor
from core.file_manager import FileManager

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
        self.scanning = False
        
        # Initialize components
        self.ui = AppUI(self)
        self.scanner = ImageScanner(self)
        self.processor = ImageProcessor(self)
        self.file_manager = FileManager(self)
        
        # Create UI
        self.ui.create_ui()
        
        # Bind keyboard shortcuts
        self.root.bind('<q>', lambda e: self.file_manager.move_image('left'))
        self.root.bind('<w>', lambda e: self.file_manager.move_image('right'))
        self.root.bind('<a>', lambda e: self.file_manager.open_image('left'))
        self.root.bind('<s>', lambda e: self.file_manager.open_image('right'))
    
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
        for item in self.ui.tree.get_children():
            self.ui.tree.delete(item)
        
        self.images_data = []
        self.current_index = 0
        
        # Start scanning in a separate thread
        self.scanning = True
        threading.Thread(target=self.scanner.scan_images, daemon=True).start()
    
    def stop_scan(self):
        self.scanning = False
    
    def batch_move(self):
        # Not implemented
        messagebox.showinfo("情報", "この機能はまだ実装されていません")