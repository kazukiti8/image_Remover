import tkinter as tk
from tkinter import ttk

class AppUI:
    def __init__(self, app):
        self.app = app
        self.tree = None
        self.left_canvas = None
        self.right_canvas = None
        self.left_info = None
        self.right_info = None
    
    def create_ui(self):
        # Top frame for folder selection
        top_frame = ttk.Frame(self.app.root, padding=5)
        top_frame.pack(fill=tk.X)
        
        ttk.Label(top_frame, text="検索フォルダ:").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(top_frame, textvariable=self.app.source_folder, width=70).grid(row=0, column=1, padx=5)
        ttk.Button(top_frame, text="...", width=3, command=self.app.browse_source).grid(row=0, column=2)
        
        ttk.Label(top_frame, text="移動先フォルダ:").grid(row=1, column=0, sticky=tk.W)
        ttk.Entry(top_frame, textvariable=self.app.destination_folder, width=70).grid(row=1, column=1, padx=5)
        ttk.Button(top_frame, text="...", width=3, command=self.app.browse_destination).grid(row=1, column=2)
        
        # Image list frame
        list_frame = ttk.Frame(self.app.root, padding=5)
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
        display_frame = ttk.Frame(self.app.root, padding=5)
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
        control_frame = ttk.Frame(self.app.root, padding=5)
        control_frame.pack(fill=tk.X)
        
        # Left side controls
        left_controls = ttk.Frame(control_frame)
        left_controls.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Label(left_controls, text="類似しきい値:").grid(row=0, column=0, sticky=tk.W)
        ttk.Scale(left_controls, from_=0, to=100, variable=self.app.similarity_threshold, 
                 length=200).grid(row=0, column=1, padx=5)
        ttk.Label(left_controls, textvariable=self.app.similarity_threshold).grid(row=0, column=2)
        
        ttk.Checkbutton(left_controls, text="キャッシュ有効", variable=self.app.use_cache).grid(row=1, column=0, sticky=tk.W)
        ttk.Checkbutton(left_controls, text="ごみ箱に移動する", variable=self.app.move_to_trash).grid(row=1, column=1, sticky=tk.W)
        
        ttk.Label(left_controls, text="左側優先拡張子:").grid(row=2, column=0, sticky=tk.W)
        ttk.Entry(left_controls, textvariable=self.app.left_priority_extensions, width=30).grid(row=2, column=1, padx=5, sticky=tk.W)
        
        # Right side controls
        right_controls = ttk.Frame(control_frame)
        right_controls.pack(side=tk.RIGHT)
        
        ttk.Button(right_controls, text="検索", command=self.app.start_scan).grid(row=0, column=0, padx=5)
        ttk.Button(right_controls, text="中止", command=self.app.stop_scan).grid(row=0, column=1, padx=5)
        ttk.Button(right_controls, text="まとめて移動", command=self.app.batch_move).grid(row=0, column=2, padx=5)
    
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
            self.app.processor.display_image('left', idx)