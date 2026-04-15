import os
import cv2
import numpy as np
from PIL import Image, ImageFilter
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QLabel, QSlider, QWidget, QMessageBox)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap

from captions_engine import render_caption_frame, group_words

class PreviewLabel(QLabel):
    dragged = Signal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.last_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.last_pos = event.pos()

    def mouseMoveEvent(self, event):
        if self.last_pos is not None and event.buttons() & Qt.LeftButton:
            delta = event.pos() - self.last_pos
            nx = delta.x() / self.width()
            ny = delta.y() / self.height()
            self.dragged.emit(nx, ny)
            self.last_pos = event.pos()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.last_pos = None


class CaptionPreviewDialog(QDialog):
    def __init__(self, media_path, text, c_x, c_y, c_s, c_r, parent=None, is_vertical=False):
        super().__init__(parent)
        self.parent_editor = parent
        self.setWindowTitle("Caption Preview & Layout")
        self.is_vertical = is_vertical
        
        # FIX: Adjusted minimum sizes so it fits perfectly on 1366x720 laptops
        if self.is_vertical:
            self.setMinimumSize(450, 620)
        else:
            self.setMinimumSize(800, 550)
        
        if hasattr(parent, "styleSheet"):
            self.setStyleSheet(parent.styleSheet())
            
        self.media_path = media_path
        self.text = text
        self.c_x = c_x
        self.c_y = c_y
        self.c_s = c_s
        self.c_r = c_r
        
        self.base_pil_image = self.load_base_frame(self.media_path)
        self.base_pil_image = self.simulate_canvas(self.base_pil_image)
        
        self.setup_ui()
        self.refresh_preview()

    def load_base_frame(self, path):
        tw, th = (1080, 1920) if self.is_vertical else (1920, 1080)
        fallback_img = Image.new('RGB', (tw, th), (0, 0, 0))
        
        if not path or path == "BLANK_IMAGE" or not os.path.exists(path):
            return fallback_img
            
        ext = path.lower().split('.')[-1]
        if ext in ['mp4', 'mov', 'avi', 'mkv', 'ts']:
            cap = cv2.VideoCapture(path)
            ret, frame = cap.read()
            cap.release()
            if ret:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                return Image.fromarray(frame)
            else:
                return fallback_img
        else:
            try: return Image.open(path).convert('RGB')
            except: return fallback_img

    def simulate_canvas(self, pil_img):
        target_w, target_h = (1080, 1920) if self.is_vertical else (1920, 1080)
        canvas = Image.new('RGB', (target_w, target_h), (0, 0, 0))
        img_ratio = pil_img.width / pil_img.height
        canvas_ratio = target_w / target_h
        
        if img_ratio > canvas_ratio:
            bg_h = target_h
            bg_w = int(target_h * img_ratio)
        else:
            bg_w = target_w
            bg_h = int(target_w / img_ratio)
            
        bg_img = pil_img.resize((bg_w, bg_h), Image.Resampling.LANCZOS)
        bg_img = bg_img.filter(ImageFilter.GaussianBlur(radius=20))
        crop_x = (bg_w - target_w) // 2
        crop_y = (bg_h - target_h) // 2
        bg_img = bg_img.crop((crop_x, crop_y, crop_x + target_w, crop_y + target_h))
        canvas.paste(bg_img, (0, 0))
        
        if img_ratio > canvas_ratio:
            fg_w = target_w
            fg_h = int(target_w / img_ratio)
        else:
            fg_h = target_h
            fg_w = int(target_h * img_ratio)
            
        fg_img = pil_img.resize((fg_w, fg_h), Image.Resampling.LANCZOS)
        paste_x = (target_w - fg_w) // 2
        paste_y = (target_h - fg_h) // 2
        canvas.paste(fg_img, (paste_x, paste_y))
        
        return canvas

    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.info_lbl = QLabel("Drag text to move it. Use sliders to Scale & Rotate.")
        layout.addWidget(self.info_lbl)

        self.preview_lbl = PreviewLabel(self)
        self.preview_lbl.setAlignment(Qt.AlignCenter)
        
        # FIX: Smaller preview minimums to ensure it doesn't push the window off a 720p screen
        if self.is_vertical: self.preview_lbl.setMinimumSize(270, 480)
        else: self.preview_lbl.setMinimumSize(480, 270)
            
        self.preview_lbl.setStyleSheet("border: 2px solid #4A3A35; background-color: #000;")
        self.preview_lbl.dragged.connect(self.on_drag)
        layout.addWidget(self.preview_lbl, stretch=1)

        ctrl_layout = QHBoxLayout()
        ctrl_layout.addWidget(QLabel("Scale:"))
        self.slider_scale = QSlider(Qt.Horizontal)
        self.slider_scale.setRange(20, 250) 
        self.slider_scale.setValue(int(self.c_s * 100))
        self.slider_scale.valueChanged.connect(self.on_scale_changed)
        ctrl_layout.addWidget(self.slider_scale)
        self.lbl_scale_val = QLabel(f"{self.c_s:.2f}x")
        ctrl_layout.addWidget(self.lbl_scale_val)
        
        ctrl_layout.addWidget(QLabel("Rotation:"))
        self.slider_rot = QSlider(Qt.Horizontal)
        self.slider_rot.setRange(-180, 180)
        self.slider_rot.setValue(int(self.c_r))
        self.slider_rot.valueChanged.connect(self.on_rot_changed)
        ctrl_layout.addWidget(self.slider_rot)
        self.lbl_rot_val = QLabel(f"{self.c_r}°")
        ctrl_layout.addWidget(self.lbl_rot_val)

        btn_reset = QPushButton("Reset Default")
        btn_reset.clicked.connect(self.reset_layout)
        ctrl_layout.addWidget(btn_reset)
        layout.addLayout(ctrl_layout)

        nav_layout = QHBoxLayout()
        if self.parent_editor:
            btn_prev = QPushButton("<< Previous Clip")
            btn_prev.clicked.connect(self.go_prev)
            btn_next = QPushButton("Next Clip >>")
            btn_next.clicked.connect(self.go_next)
            nav_layout.addWidget(btn_prev)
            nav_layout.addWidget(btn_next)
            
        nav_layout.addStretch()
        btn_close = QPushButton("Cancel")
        btn_close.clicked.connect(self.reject)
        btn_save = QPushButton("Save && Close")
        btn_save.setStyleSheet("background-color: #2F6B4C;")
        btn_save.clicked.connect(self.accept)
        nav_layout.addWidget(btn_close)
        nav_layout.addWidget(btn_save)
        layout.addLayout(nav_layout)

    def reset_layout(self):
        self.c_x, self.c_y, self.c_s, self.c_r = 0.5, (0.74 if self.is_vertical else 0.90), 1.0, 0.0
        self.slider_scale.setValue(100)
        self.slider_rot.setValue(0)
        self.refresh_preview()

    def on_drag(self, dx, dy):
        self.c_x = max(0.0, min(1.0, self.c_x + dx))
        self.c_y = max(0.0, min(1.0, self.c_y + dy))
        self.refresh_preview()

    def on_scale_changed(self, val):
        self.c_s = val / 100.0
        self.lbl_scale_val.setText(f"{self.c_s:.2f}x")
        self.refresh_preview()

    def on_rot_changed(self, val):
        self.c_r = float(val)
        self.lbl_rot_val.setText(f"{self.c_r}°")
        self.refresh_preview()

    def refresh_preview(self):
        width, height = self.base_pil_image.width, self.base_pil_image.height
        sample_txt = self.text if self.text else "Sample Caption Text For Preview"
        words = [{"word": w, "start": 0.0, "end": 10.0} for w in sample_txt.split()]
        lines = group_words(words)
        
        # FIX: Multiply scale by 0.90 purely in the preview visual to match FFmpeg .ass burn size perfectly
        visual_scale = self.c_s * 0.90
        
        overlay, _ = render_caption_frame(
            width, height, current_time=0.5, lines=lines,
            pos_x=self.c_x, pos_y=self.c_y, scale=visual_scale, rotation=self.c_r
        )
        
        preview_img = self.base_pil_image.copy()
        if overlay.mode == 'RGBA':
            preview_img.paste(overlay, (0, 0), overlay)
            
        data = preview_img.convert("RGB").tobytes("raw", "RGB")
        qimage = QImage(data, preview_img.width, preview_img.height, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimage).scaled(self.preview_lbl.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview_lbl.setPixmap(pixmap)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.refresh_preview()
        
    def save_current_to_parent(self):
        if not self.parent_editor: return
        row = self.parent_editor.table.currentRow()
        if row >= 0:
            clip = self.parent_editor.project.clips[row]
            clip.caption_x = self.c_x
            clip.caption_y = self.c_y
            clip.caption_scale = self.c_s
            clip.caption_rot = self.c_r
            self.parent_editor.project.is_dirty = True

    def go_prev(self):
        if not self.parent_editor: return
        row = self.parent_editor.table.currentRow()
        if row > 0:
            self.save_current_to_parent()
            self.parent_editor.table.selectRow(row - 1)
            self.load_from_row(row - 1)

    def go_next(self):
        if not self.parent_editor: return
        row = self.parent_editor.table.currentRow()
        if row < len(self.parent_editor.project.clips) - 1:
            self.save_current_to_parent()
            self.parent_editor.table.selectRow(row + 1)
            self.load_from_row(row + 1)

    def load_from_row(self, row):
        clip = self.parent_editor.project.clips[row]
        self.media_path = clip.media_path
        self.text = clip.script_text
        self.c_x = clip.caption_x
        self.c_y = clip.caption_y if clip.caption_y is not None else (0.74 if self.is_vertical else 0.90)
        self.c_s = clip.caption_scale
        self.c_r = clip.caption_rot
        
        self.base_pil_image = self.load_base_frame(self.media_path)
        self.base_pil_image = self.simulate_canvas(self.base_pil_image)
        
        self.slider_scale.blockSignals(True)
        self.slider_rot.blockSignals(True)
        self.slider_scale.setValue(int(self.c_s * 100))
        self.slider_rot.setValue(int(self.c_r))
        self.lbl_scale_val.setText(f"{self.c_s:.2f}x")
        self.lbl_rot_val.setText(f"{self.c_r}°")
        self.slider_scale.blockSignals(False)
        self.slider_rot.blockSignals(False)
        
        self.refresh_preview()

    def get_values(self):
        return self.c_x, self.c_y, self.c_s, self.c_r