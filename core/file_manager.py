import os
import sys
import shutil
from tkinter import messagebox

class FileManager:
    def __init__(self, app):
        self.app = app
    
    def move_image(self, side):
        if not self.app.destination_folder.get():
            messagebox.showerror("エラー", "移動先フォルダを指定してください")
            return
            
        try:
            if side == 'left' and hasattr(self.app.processor, 'left_idx'):
                img_data = self.app.images_data[self.app.processor.left_idx]
            elif side == 'right' and hasattr(self.app.processor, 'right_idx'):
                img_data = self.app.images_data[self.app.processor.right_idx]
            else:
                return
                
            src_path = img_data['path']
            filename = os.path.basename(src_path)
            dst_path = os.path.join(self.app.destination_folder.get(), filename)
            
            # Check if source file exists
            if not os.path.exists(src_path):
                messagebox.showerror("エラー", f"ファイルが見つかりません: {src_path}")
                return
                
            # Move or copy file
            if self.app.move_to_trash.get():
                try:
                    import send2trash
                    send2trash.send2trash(src_path)
                except ImportError:
                    # Fall back to regular delete if send2trash not available
                    os.remove(src_path)
            else:
                shutil.move(src_path, dst_path)
                
            # Remove from tree and data
            if side == 'left' and hasattr(self.app.processor, 'left_idx'):
                tree_item = self.app.ui.tree.get_children()[self.app.processor.left_idx]
                self.app.ui.tree.delete(tree_item)
                del self.app.images_data[self.app.processor.left_idx]
            elif side == 'right' and hasattr(self.app.processor, 'right_idx'):
                tree_item = self.app.ui.tree.get_children()[self.app.processor.right_idx]
                self.app.ui.tree.delete(tree_item)
                del self.app.images_data[self.app.processor.right_idx]
                
            # Refresh display
            self.app.processor.display_next_pair()
        except Exception as e:
            messagebox.showerror("エラー", f"移動中にエラーが発生しました: {e}")
    
    def open_image(self, side):
        try:
            if side == 'left' and hasattr(self.app.processor, 'left_idx'):
                img_data = self.app.images_data[self.app.processor.left_idx]
            elif side == 'right' and hasattr(self.app.processor, 'right_idx'):
                img_data = self.app.images_data[self.app.processor.right_idx]
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