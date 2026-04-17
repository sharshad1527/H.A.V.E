import os
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QLabel, QDoubleSpinBox, QWidget)
from PySide6.QtCore import Qt, QUrl, Signal, QPoint
from PySide6.QtGui import QPainter, QColor, QPen, QBrush
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget

class RangeSlider(QWidget):
    """Custom Dual-Handle Slider for Pro Video Trimming"""
    rangeChanged = Signal(float, float)
    positionMoved = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(60)
        self.min_val = 0.0
        self.max_val = 100.0
        self.low = 0.0
        self.high = 100.0
        self.current_pos = 0.0
        
        self.dragging = None # 'low', 'high', or 'pos'
        self.setMouseTracking(True)

    def setRange(self, min_val, max_val):
        self.min_val = min_val
        self.max_val = max_val
        if self.high > max_val: self.high = max_val
        self.update()
        
    def setLow(self, val):
        self.low = max(self.min_val, min(val, self.high))
        self.update()
        
    def setHigh(self, val):
        self.high = min(self.max_val, max(val, self.low))
        self.update()
        
    def setPosition(self, val):
        self.current_pos = max(self.min_val, min(val, self.max_val))
        self.update()

    def _get_x(self, val):
        if self.max_val <= self.min_val: return 0
        return int((val - self.min_val) / (self.max_val - self.min_val) * self.width())

    def _get_val(self, x):
        return self.min_val + (x / self.width()) * (self.max_val - self.min_val)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        
        # Background Track
        track_y = h // 2 - 15
        painter.setBrush(QColor("#1E1715"))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, track_y, w, 30, 4, 4)
        
        if self.max_val > self.min_val:
            x1, x2 = self._get_x(self.low), self._get_x(self.high)
            
            # Active Trim Area
            painter.setBrush(QColor("#FF7043")) # Orange highlight
            painter.drawRoundedRect(x1, track_y, max(1, x2 - x1), 30, 4, 4)
            
            # Handles
            painter.setBrush(QColor("#EAE0D5"))
            painter.drawRoundedRect(x1 - 6, track_y - 5, 12, 40, 3, 3)
            painter.drawRoundedRect(x2 - 6, track_y - 5, 12, 40, 3, 3)
            
            # Playhead
            px = self._get_x(self.current_pos)
            painter.setPen(QPen(QColor("#00E676"), 3)) # Cyan playhead
            painter.drawLine(px, 0, px, h)
            
            # Playhead handle (Fixed QPoint bug)
            painter.setBrush(QColor("#00E676"))
            painter.setPen(Qt.NoPen)
            painter.drawPolygon([QPoint(int(px-6), 0), QPoint(int(px+6), 0), QPoint(int(px), 10)])

    def mousePressEvent(self, event):
        x = event.position().x()
        x1, x2 = self._get_x(self.low), self._get_x(self.high)
        px = self._get_x(self.current_pos)
        
        if abs(x - x1) < 15: self.dragging = 'low'
        elif abs(x - x2) < 15: self.dragging = 'high'
        else:
            self.dragging = 'pos'
            self.current_pos = self._get_val(x)
            self.positionMoved.emit(self.current_pos)
            self.update()

    def mouseMoveEvent(self, event):
        if not self.dragging: return
        
        val = self._get_val(event.position().x())
        val = max(self.min_val, min(val, self.max_val))
        
        if self.dragging == 'low':
            self.low = min(val, self.high - 0.1)
            self.rangeChanged.emit(self.low, self.high)
        elif self.dragging == 'high':
            self.high = max(val, self.low + 0.1)
            self.rangeChanged.emit(self.low, self.high)
        elif self.dragging == 'pos':
            self.current_pos = val
            self.positionMoved.emit(self.current_pos)
            
        self.update()

    def mouseReleaseEvent(self, event):
        self.dragging = None


class VideoTrimDialog(QDialog):
    def __init__(self, video_path, parent=None, start_val=0.0, end_val=0.0):
        super().__init__(parent)
        self.setWindowTitle("Trim Video (Pro)")
        self.setMinimumSize(850, 550)
        
        if hasattr(parent, "styleSheet"):
            self.setStyleSheet(parent.styleSheet())
            
        self.video_path = video_path

        layout = QVBoxLayout(self)
        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background-color: #000; border: 1px solid #4A3A35; border-radius: 6px;")
        layout.addWidget(self.video_widget, stretch=1)

        # Custom Timeline Slider
        self.slider = RangeSlider()
        self.slider.rangeChanged.connect(self.on_range_changed)
        self.slider.positionMoved.connect(self.seek_video)
        layout.addWidget(self.slider)

        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)
        self.player.setSource(QUrl.fromLocalFile(self.video_path))
        
        controls = QHBoxLayout()
        self.btn_play = QPushButton("▶ Play/Pause")
        self.btn_play.setFixedWidth(120)
        self.btn_play.clicked.connect(self.toggle_play)
        controls.addWidget(self.btn_play)
        
        controls.addWidget(QLabel("Start:"))
        self.spin_start = QDoubleSpinBox()
        self.spin_start.setRange(0, 9999)
        self.spin_start.setSingleStep(0.1)
        self.spin_start.setValue(start_val)
        self.spin_start.valueChanged.connect(self.slider.setLow)
        controls.addWidget(self.spin_start)
        
        controls.addWidget(QLabel("End:"))
        self.spin_end = QDoubleSpinBox()
        self.spin_end.setRange(0, 9999)
        self.spin_end.setSingleStep(0.1)
        self.spin_end.setValue(end_val)
        self.spin_end.valueChanged.connect(self.slider.setHigh)
        controls.addWidget(self.spin_end)
        
        controls.addStretch()
        
        self.btn_save = QPushButton("✓ Apply Trim")
        self.btn_save.setProperty("class", "primary")
        self.btn_save.setFixedWidth(120)
        self.btn_save.clicked.connect(self.accept)
        controls.addWidget(self.btn_save)

        layout.addLayout(controls)

        self.player.durationChanged.connect(self.on_duration_changed)
        self.player.positionChanged.connect(self.on_position_changed)
        self.saved_end = end_val
        self._is_seeking = False

    def on_duration_changed(self, dur_ms):
        dur_s = dur_ms / 1000.0
        self.slider.setRange(0.0, dur_s)
        self.spin_start.setMaximum(dur_s)
        self.spin_end.setMaximum(dur_s)
        
        if self.saved_end == 0.0 or self.saved_end > dur_s:
            self.spin_end.setValue(dur_s)
            self.slider.setHigh(dur_s)
        else:
            self.spin_end.setValue(self.saved_end)
            self.slider.setHigh(self.saved_end)
            
        self.slider.setLow(self.spin_start.value())

    def on_position_changed(self, pos_ms):
        if self._is_seeking: return
        pos_s = pos_ms / 1000.0
        self.slider.setPosition(pos_s)
        
        if self.spin_end.value() > 0 and pos_s >= self.spin_end.value():
            self.player.setPosition(int(self.spin_start.value() * 1000))

    def on_range_changed(self, low, high):
        self.spin_start.blockSignals(True)
        self.spin_end.blockSignals(True)
        self.spin_start.setValue(low)
        self.spin_end.setValue(high)
        self.spin_start.blockSignals(False)
        self.spin_end.blockSignals(False)

    def seek_video(self, pos_s):
        self._is_seeking = True
        self.player.setPosition(int(pos_s * 1000))
        self._is_seeking = False

    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            pos_s = self.player.position() / 1000.0
            if pos_s >= self.spin_end.value() or pos_s < self.spin_start.value():
                self.player.setPosition(int(self.spin_start.value() * 1000))
            self.player.play()

    def get_trim(self):
        return self.spin_start.value(), self.spin_end.value()

    def closeEvent(self, event):
        self.player.stop()
        super().closeEvent(event)