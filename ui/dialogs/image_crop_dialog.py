import os
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QWidget, QMessageBox)
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QPixmap
from PIL import Image

class CropCanvas(QWidget):
    def __init__(self, image_path, target_ratio):
        super().__init__()
        self.image_path = image_path
        self.target_ratio = target_ratio
        
        self.pil_img = Image.open(image_path).convert('RGB')
        self.qimg = QPixmap(image_path)
        
        self.crop_rect = QRectF(0, 0, 100, 100) 
        self.dragging = False
        self.last_pos = QPointF()
        self.initialized = False

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self.initialized:
            self._init_rect()
            self.initialized = True

    def _init_rect(self):
        img_w, img_h = self.qimg.width(), self.qimg.height()
        widget_w, widget_h = self.width(), self.height()
        
        scale = min(widget_w / img_w, widget_h / img_h)
        draw_w, draw_h = img_w * scale, img_h * scale
        
        # Maximize crop rect based on strict project ratio
        if draw_w / draw_h > self.target_ratio:
            c_h = draw_h * 0.95
            c_w = c_h * self.target_ratio
        else:
            c_w = draw_w * 0.95
            c_h = c_w / self.target_ratio
            
        c_x = (widget_w - c_w) / 2
        c_y = (widget_h - c_h) / 2
        
        self.crop_rect = QRectF(c_x, c_y, c_w, c_h)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        painter.fillRect(self.rect(), QColor("#121212"))
        
        img_w, img_h = self.qimg.width(), self.qimg.height()
        scale = min(self.width() / img_w, self.height() / img_h)
        draw_w, draw_h = img_w * scale, img_h * scale
        img_x = (self.width() - draw_w) / 2
        img_y = (self.height() - draw_h) / 2
        
        painter.drawPixmap(int(img_x), int(img_y), int(draw_w), int(draw_h), self.qimg)
        
        # Dark Overlay
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 160))
        r = self.crop_rect
        painter.drawRect(0, 0, self.width(), int(r.top()))
        painter.drawRect(0, int(r.bottom()), self.width(), int(self.height() - r.bottom()))
        painter.drawRect(0, int(r.top()), int(r.left()), int(r.height()))
        painter.drawRect(int(r.right()), int(r.top()), int(self.width() - r.right()), int(r.height()))
        
        # Orange Crop Border
        pen = QPen(QColor("#FF7043"), 3)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(self.crop_rect)

        # Rule of Thirds Grid
        pen = QPen(QColor(255, 255, 255, 90), 1, Qt.DashLine)
        painter.setPen(pen)
        painter.drawLine(int(r.left() + r.width()/3), int(r.top()), int(r.left() + r.width()/3), int(r.bottom()))
        painter.drawLine(int(r.left() + 2*r.width()/3), int(r.top()), int(r.left() + 2*r.width()/3), int(r.bottom()))
        painter.drawLine(int(r.left()), int(r.top() + r.height()/3), int(r.right()), int(r.top() + r.height()/3))
        painter.drawLine(int(r.left()), int(r.top() + 2*r.height()/3), int(r.right()), int(r.top() + 2*r.height()/3))

    def mousePressEvent(self, event):
        if self.crop_rect.contains(event.position()):
            self.dragging = True
            self.last_pos = event.position()

    def mouseMoveEvent(self, event):
        if self.dragging:
            delta = event.position() - self.last_pos
            new_rect = self.crop_rect.translated(delta)
            
            img_w, img_h = self.qimg.width(), self.qimg.height()
            scale = min(self.width() / img_w, self.height() / img_h)
            draw_w, draw_h = img_w * scale, img_h * scale
            img_x = (self.width() - draw_w) / 2
            img_y = (self.height() - draw_h) / 2
            
            # Constrain panning to image bounds
            if new_rect.left() < img_x: new_rect.moveLeft(img_x)
            if new_rect.right() > img_x + draw_w: new_rect.moveRight(img_x + draw_w)
            if new_rect.top() < img_y: new_rect.moveTop(img_y)
            if new_rect.bottom() > img_y + draw_h: new_rect.moveBottom(img_y + draw_h)
            
            self.crop_rect = new_rect
            self.last_pos = event.position()
            self.update()

    def mouseReleaseEvent(self, event):
        self.dragging = False

    def wheelEvent(self, event):
        zoom_factor = 1.05 if event.angleDelta().y() > 0 else 0.95
        new_w = self.crop_rect.width() * zoom_factor
        new_h = new_w / self.target_ratio
        
        img_w, img_h = self.qimg.width(), self.qimg.height()
        scale = min(self.width() / img_w, self.height() / img_h)
        draw_w, draw_h = img_w * scale, img_h * scale
        
        if new_w > draw_w or new_h > draw_h or new_w < 50:
            return 
            
        center = self.crop_rect.center()
        new_rect = QRectF(center.x() - new_w/2, center.y() - new_h/2, new_w, new_h)
        
        img_x = (self.width() - draw_w) / 2
        img_y = (self.height() - draw_h) / 2
        
        if new_rect.left() < img_x: new_rect.moveLeft(img_x)
        if new_rect.right() > img_x + draw_w: new_rect.moveRight(img_x + draw_w)
        if new_rect.top() < img_y: new_rect.moveTop(img_y)
        if new_rect.bottom() > img_y + draw_h: new_rect.moveBottom(img_y + draw_h)
        
        self.crop_rect = new_rect
        self.update()
        
    def perform_crop(self):
        img_w, img_h = self.qimg.width(), self.qimg.height()
        scale = min(self.width() / img_w, self.height() / img_h)
        draw_w, draw_h = img_w * scale, img_h * scale
        img_x = (self.width() - draw_w) / 2
        img_y = (self.height() - draw_h) / 2
        
        rel_x = (self.crop_rect.left() - img_x) / scale
        rel_y = (self.crop_rect.top() - img_y) / scale
        rel_w = self.crop_rect.width() / scale
        rel_h = self.crop_rect.height() / scale
        
        box = (int(rel_x), int(rel_y), int(rel_x + rel_w), int(rel_y + rel_h))
        cropped_img = self.pil_img.crop(box)
        
        dir_name = os.path.dirname(self.image_path)
        base_name = os.path.basename(self.image_path)
        name, ext = os.path.splitext(base_name)
        new_path = os.path.join(dir_name, f"{name}_cropped{ext}")
        
        cropped_img.save(new_path)
        return new_path


class ImageCropDialog(QDialog):
    def __init__(self, image_path, target_ratio, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Crop Image (Aspect Locked)")
        
        # --- DYNAMICALLY RESIZE WINDOW FOR SHORTS CROPPING ---
        # If target ratio is < 1.0 (meaning it's 9:16 vertical), make the window tall instead of wide
        if target_ratio < 1.0:
            self.setMinimumSize(600, 850)
        else:
            self.setMinimumSize(900, 600)
            
        if hasattr(parent, "styleSheet"): self.setStyleSheet(parent.styleSheet())
        
        self.cropped_path = None
        
        layout = QVBoxLayout(self)
        
        lbl_info = QLabel("Left-Click & Drag to pan the crop box. Scroll mouse wheel to zoom in/out.")
        lbl_info.setStyleSheet("color: #B0B0B0; font-size: 11pt;")
        layout.addWidget(lbl_info)
        
        self.canvas = CropCanvas(image_path, target_ratio)
        layout.addWidget(self.canvas, stretch=1)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        
        btn_save = QPushButton("✓ Apply Crop")
        btn_save.setProperty("class", "primary")
        btn_save.clicked.connect(self.apply_crop)
        
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)

    def apply_crop(self):
        try:
            self.cropped_path = self.canvas.perform_crop()
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Crop Error", str(e))
            
    def get_cropped_path(self):
        return self.cropped_path