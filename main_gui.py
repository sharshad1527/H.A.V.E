import sys
import os
import re
import time
import traceback
import copy
import random
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QPushButton, QLabel, QTableWidget, 
                               QTableWidgetItem, QHeaderView, QProgressBar, 
                               QFileDialog, QComboBox, QMessageBox, QMenu, QCheckBox, 
                               QDoubleSpinBox, QSizePolicy, QStackedWidget, QStyledItemDelegate, QStyle,
                               QLineEdit, QAbstractSpinBox)
from PySide6.QtCore import Qt, QThread, Signal, QSize, QUrl, QEvent
from PySide6.QtGui import QColor, QIcon, QPixmap, QShortcut, QKeySequence
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget

from project_model import ProjectState, Clip
from whisper_engine import AudioSyncEngine
from video_renderer import VideoRenderer
from caption_preview_dialog import CaptionPreviewDialog
from video_trim_dialog import VideoTrimDialog
from image_crop_dialog import ImageCropDialog
from ai_shorts_dialog import AIShortsDialog

# Import the new Word Editor Dialog
from word_editor_dialog import WordEditorDialog

# --- GLOBAL MESSAGE BOX OVERRIDES ---
original_critical = QMessageBox.critical
original_warning = QMessageBox.warning

def copyable_critical(parent, title, text, buttons=QMessageBox.Ok, defaultButton=QMessageBox.NoButton):
    msg = QMessageBox(parent)
    msg.setIcon(QMessageBox.Critical)
    msg.setWindowTitle(title)
    msg.setText(str(text))
    msg.setTextInteractionFlags(Qt.TextSelectableByMouse) 
    copy_btn = msg.addButton("📋 Copy Error", QMessageBox.ActionRole)
    msg.addButton(QMessageBox.Ok)
    msg.exec()
    if msg.clickedButton() == copy_btn:
        QApplication.clipboard().setText(str(text))
    return QMessageBox.Ok

def copyable_warning(parent, title, text, buttons=QMessageBox.Ok, defaultButton=QMessageBox.NoButton):
    msg = QMessageBox(parent)
    msg.setIcon(QMessageBox.Warning)
    msg.setWindowTitle(title)
    msg.setText(str(text))
    msg.setTextInteractionFlags(Qt.TextSelectableByMouse)
    copy_btn = msg.addButton("📋 Copy Warning", QMessageBox.ActionRole)
    msg.addButton(QMessageBox.Ok)
    msg.exec()
    if msg.clickedButton() == copy_btn:
        QApplication.clipboard().setText(str(text))
    return QMessageBox.Ok

QMessageBox.critical = copyable_critical
QMessageBox.warning = copyable_warning

# --- GLOBAL CRASH REPORTER ---
def global_exception_handler(exc_type, exc_value, exc_tb):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    err_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    print("\n" + "="*40 + "\nCRITICAL CRASH DETECTED\n" + "="*40)
    print(err_msg)
    try:
        with open("simply_human_crash_report.txt", "w") as f:
            f.write(err_msg)
    except: pass
    
    if QApplication.instance():
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle("Application Crashed!")
        msg.setText("The app crashed. A full diagnostic report was saved to 'simply_human_crash_report.txt'.")
        msg.setDetailedText(err_msg)
        copy_btn = msg.addButton("📋 Copy Error to Clipboard", QMessageBox.ActionRole)
        msg.addButton(QMessageBox.Ok)
        msg.exec()
        if msg.clickedButton() == copy_btn:
            QApplication.clipboard().setText(err_msg)

sys.excepthook = global_exception_handler

# --- RASPBERRY COFFEE PRO THEME ---
RASPBERRY_PRO_STYLESHEET = """
QMainWindow, QDialog { background-color: #261E1B; }
QWidget { color: #EAE0D5; font-family: 'Segoe UI', Roboto, sans-serif; font-size: 10pt; }

QTableWidget {
    background-color: #362A26; alternate-background-color: #2E231F;
    gridline-color: #4A3A35; border: 1px solid #4A3A35; border-radius: 6px;
    selection-background-color: #FF7043; selection-color: #121212;
}
QHeaderView::section {
    background-color: #4A3A35; padding: 6px; border: none;
    border-right: 1px solid #362A26; border-bottom: 1px solid #362A26;
    font-weight: bold; color: #EAE0D5;
}

QPushButton {
    background-color: #4A3A35; color: #EAE0D5; border: 1px solid #5C4B45;
    border-radius: 4px; padding: 6px 12px; font-weight: bold;
}
QPushButton:hover { background-color: #5C4B45; border-color: #FF7043; }
QPushButton:pressed { background-color: #FF7043; color: #121212; }

QPushButton.primary { background-color: #FF7043; color: #121212; border: none; }
QPushButton.primary:hover { background-color: #FF8A65; }
QPushButton.primary:disabled { background-color: #3A2B27; color: #887C77; border: 1px dashed #5C4B45; }
QPushButton:disabled { background-color: #2E231F; color: #666666; border-color: #4A3A35;}

QPushButton.sidebar {
    text-align: left; padding: 12px 15px; font-size: 10pt; 
    background-color: transparent; border: none; border-left: 4px solid transparent; border-radius: 0px;
}
QPushButton.sidebar:hover { background-color: #362A26; border-left: 4px solid #FF7043; }
QPushButton.sidebar:disabled { color: #555555; background-color: transparent; border: none; }

QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #362A26; border: 1px solid #4A3A35;
    border-radius: 4px; padding: 4px 8px; color: #EAE0D5;
}
QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover { border-color: #FF7043; }
QComboBox::drop-down { border: none; width: 20px; }

QLabel#AppTitle { font-size: 16pt; font-weight: bold; color: #FF7043; padding: 10px; }
QLabel#Header { color: #A09088; font-size: 9pt; font-weight: bold; text-transform: uppercase; padding-left: 10px; }

QProgressBar {
    border: 1px solid #4A3A35; border-radius: 4px; text-align: center;
    background-color: #2E231F; color: #EAE0D5; font-weight: bold;
}
QProgressBar::chunk { background-color: #FF7043; border-radius: 3px; }

QScrollBar:vertical { background: #261E1B; width: 12px; margin: 0px; }
QScrollBar::handle:vertical { background: #4A3A35; min-height: 20px; border-radius: 6px; margin: 2px; }
QScrollBar::handle:vertical:hover { background: #FF7043; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }

QWidget#InspectorPanel {
    background-color: #362A26; 
    border: 1px solid #4A3A35; 
    border-radius: 6px; 
    margin-top: 10px;
}
"""

class ScriptColumnDelegate(QStyledItemDelegate):
    def __init__(self, parent=None, gui_ref=None):
        super().__init__(parent)
        self.gui_ref = gui_ref

    def paint(self, painter, option, index):
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, QColor("#4A3A35")) 
            fg_data = index.data(Qt.ForegroundRole)
            if fg_data and hasattr(fg_data, "color"): painter.setPen(fg_data.color()) 
            elif fg_data: painter.setPen(fg_data)
            else: painter.setPen(QColor("#EAE0D5"))
                
            text = index.data(Qt.DisplayRole)
            if text:
                rect = option.rect.adjusted(6, 0, -6, 0)
                elided_text = option.fontMetrics.elidedText(text, Qt.ElideRight, rect.width())
                painter.drawText(rect, Qt.AlignLeft | Qt.AlignVCenter, elided_text)
        else:
            super().paint(painter, option, index)
            
    def createEditor(self, parent, option, index):
        """Intercepts double clicks on the script column to open the Word Editor"""
        if index.column() == 2 and self.gui_ref:
            row = index.row()
            clip = self.gui_ref.project.clips[row]
            was_processed = (clip.end_time > 0.0) or (clip.whisper_confidence != 100.0)
            
            if was_processed:
                dlg = WordEditorDialog(self.gui_ref.project, row, self.gui_ref)
                dlg.exec()
                
                # ULTRA FAST REFRESH: Only update the affected rows without hitting the disk!
                if row > 0: self.gui_ref._refresh_row_ui(row - 1, update_image=False)
                self.gui_ref._refresh_row_ui(row, update_image=False)
                if row < len(self.gui_ref.project.clips) - 1: self.gui_ref._refresh_row_ui(row + 1, update_image=False)
                
                return None
                
        return super().createEditor(parent, option, index)

class WhisperWorker(QThread):
    whisper_done = Signal(list, float)
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, audio_path, script_data, model_size="tiny"):
        super().__init__()
        self.audio_path = audio_path
        self.script_data = script_data
        self.model_size = model_size
        self.engine = None

    def run(self):
        try:
            import gc
            try: import torch
            except ImportError: torch = None
            start_time = time.time()
            self.progress.emit(f"Loading Whisper Model ({self.model_size})...")
            
            self.engine = AudioSyncEngine(model_size=self.model_size)
            self.progress.emit("Transcribing Audio... (This may take a minute)")
            segments = self.engine.transcribe_audio(self.audio_path)
            self.progress.emit("Matching Script to Audio Timeline...")
            timeline = self.engine.match_script_to_audio(self.script_data, segments)
            
            gc.collect()
            if torch and torch.cuda.is_available(): torch.cuda.empty_cache()
            self.whisper_done.emit(timeline, time.time() - start_time)
            time.sleep(0.1)
        except Exception as e:
            err_msg = traceback.format_exc()
            self.error.emit(f"Critical AI Error: {str(e)}\n\nSee simply_human_crash_report.txt for details.")

class RenderWorker(QThread):
    progress = Signal(str)
    render_done = Signal(float)
    error = Signal(str)

    def __init__(self, timeline_data, audio_path, output_path, resolution, strict_cuts, gap_threshold, fps=60, vignette=True):
        super().__init__()
        self.timeline_data = timeline_data; self.audio_path = audio_path; self.output_path = output_path
        self.resolution = resolution; self.strict_cuts = strict_cuts; self.gap_threshold = gap_threshold
        self.fps = fps; self.vignette = vignette

    def run(self):
        try:
            renderer = VideoRenderer()
            total_time = renderer.render_project(
                self.timeline_data, self.audio_path, self.output_path, 
                self.resolution, self.strict_cuts, self.gap_threshold, lambda msg: self.progress.emit(msg),
                fps=self.fps, vignette=self.vignette
            )
            self.render_done.emit(total_time if total_time else 0.0)
        except Exception as e: self.error.emit(str(e))

class AutoEditorGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simply Human - Pro Editor")
        self.setStyleSheet(RASPBERRY_PRO_STYLESHEET)
        self.resize(1200, 620)
        self.setMinimumSize(950, 550)
        
        # --- CORE MVC STATE ---
        self.project = ProjectState()
        self.main_project_state = None
        self._updating_ui = False
        self._updating_inspector = False
        
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.audio_output.setVolume(1.0) 
        self.player.setAudioOutput(self.audio_output)
        self._pending_seek_ms = None
        self._stop_position_ms = 0
        self.player.positionChanged.connect(self._check_audio_pos)

        app = QApplication.instance()
        if app: app.installEventFilter(self)

        self.setup_ui()
        self.setup_shortcuts()

    def eventFilter(self, source, event):
        if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key_Space:
            focus_widget = QApplication.focusWidget()
            if isinstance(focus_widget, (QLineEdit, QAbstractSpinBox, QPushButton, QComboBox, QCheckBox)) or self.table.state() == QTableWidget.EditingState:
                return super().eventFilter(source, event)
            
            self.play_current_segment()
            return True 
            
        return super().eventFilter(source, event)

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 10, 10)
        main_layout.setSpacing(10)

        # 1. LEFT SIDEBAR
        sidebar_widget = QWidget()
        sidebar_widget.setFixedWidth(180)
        sidebar_widget.setStyleSheet("background-color: #1E1715; border-right: 1px solid #362A26;")
        sidebar_layout = QVBoxLayout(sidebar_widget)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(5)
        
        lbl_brand = QLabel("Simply Human")
        lbl_brand.setObjectName("AppTitle")
        sidebar_layout.addWidget(lbl_brand)
        
        sidebar_layout.addWidget(QLabel("PIPELINE", objectName="Header"))
        
        self.btn_load_audio = QPushButton("🎙️ 1. Load Audio")
        self.btn_load_csv = QPushButton("📂 2. Load Script")
        self.btn_process_whisper = QPushButton("⚡ 3. Sync Whisper")
        for btn in [self.btn_load_audio, self.btn_load_csv, self.btn_process_whisper]:
            btn.setProperty("class", "sidebar")
            sidebar_layout.addWidget(btn)

        sidebar_layout.addSpacing(15)
        sidebar_layout.addWidget(QLabel("AI TOOLS", objectName="Header"))
        self.btn_ai_shorts = QPushButton("✨ AI Shorts Clip")
        self.btn_ai_shorts.setProperty("class", "sidebar")
        self.btn_ai_shorts.setEnabled(False) 
        self.btn_ai_shorts.clicked.connect(self.open_ai_shorts)
        
        self.btn_ai_chapters = QPushButton("📑 Auto Chapters")
        self.btn_ai_chapters.setProperty("class", "sidebar")
        self.btn_ai_chapters.setEnabled(False) 
        sidebar_layout.addWidget(self.btn_ai_shorts)
        sidebar_layout.addWidget(self.btn_ai_chapters)

        sidebar_layout.addSpacing(15)
        sidebar_layout.addWidget(QLabel("PROJECT", objectName="Header"))
        self.btn_return_main = QPushButton("🔙 Return to Main")
        self.btn_return_main.setProperty("class", "sidebar")
        self.btn_return_main.setStyleSheet("background-color: #3A2B27; border-left: 4px solid #FFAA00; color: #EAE0D5;")
        self.btn_return_main.hide()
        self.btn_return_main.clicked.connect(self.return_to_main_project)
        sidebar_layout.addWidget(self.btn_return_main)
        
        self.btn_new_project = QPushButton("📄 New Project")
        self.btn_open_project = QPushButton("📂 Open Project")
        self.btn_save_project = QPushButton("💾 Save Project")
        for btn in [self.btn_new_project, self.btn_open_project, self.btn_save_project]:
            btn.setProperty("class", "sidebar")
            sidebar_layout.addWidget(btn)
        
        sidebar_layout.addStretch()
        self.btn_render = QPushButton("🎬 Render Final")
        sidebar_layout.addWidget(self.btn_render)
        main_layout.addWidget(sidebar_widget)

        # 2. CENTER WORKSPACE
        center_layout = QVBoxLayout()
        center_layout.setContentsMargins(0, 10, 0, 0)
        settings_layout = QHBoxLayout()
        self.lbl_status = QLabel("Ready")
        self.lbl_status.setStyleSheet("color: #FF7043; font-weight: bold;")
        
        self.combo_aspect_ratio = QComboBox()
        self.combo_aspect_ratio.addItems(["16:9 (Horizontal)", "9:16 (Vertical)"])
        self.combo_fps = QComboBox()
        self.combo_fps.addItems(["60 FPS", "30 FPS"])
        self.combo_whisper_model = QComboBox()
        self.combo_whisper_model.addItems(["Tiny", "Small", "Base"])
        self.combo_whisper_model.setCurrentIndex(2)
        
        self.cb_strict_cuts = QCheckBox("Strict Cuts")
        self.spin_gap = QDoubleSpinBox()
        self.spin_gap.setRange(0.1, 5.0); self.spin_gap.setSingleStep(0.1); self.spin_gap.setValue(0.6)
        self.cb_vignette = QCheckBox("Vignette")
        
        settings_layout.addWidget(self.lbl_status)
        settings_layout.addStretch()
        settings_layout.addWidget(QLabel("Aspect:"))
        settings_layout.addWidget(self.combo_aspect_ratio)
        settings_layout.addWidget(QLabel("FPS:"))
        settings_layout.addWidget(self.combo_fps)
        settings_layout.addWidget(QLabel("Model:"))
        settings_layout.addWidget(self.combo_whisper_model)
        settings_layout.addWidget(self.cb_strict_cuts)
        settings_layout.addWidget(self.spin_gap)
        settings_layout.addWidget(self.cb_vignette)
        center_layout.addLayout(settings_layout)

        self.table = QTableWidget(0, 7) 
        self.table.setHorizontalHeaderLabels(["Type", "Media", "Script Line", "Start", "End", "Animation", "Transition"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch) 
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(45)
        self.table.setIconSize(QSize(40, 40))
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        
        self.table.setItemDelegateForColumn(2, ScriptColumnDelegate(self.table, self))
        
        self.table.itemSelectionChanged.connect(self.on_table_selection_changed)
        self.table.itemChanged.connect(self.on_table_item_changed)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.cellDoubleClicked.connect(self.handle_cell_double_click)
        
        center_layout.addWidget(self.table)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0); self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        center_layout.addWidget(self.progress_bar)
        main_layout.addLayout(center_layout, stretch=1)

        # 3. RIGHT INSPECTOR PANEL
        self.inspector_widget = QWidget()
        self.inspector_widget.setObjectName("InspectorPanel") 
        self.inspector_widget.setFixedWidth(290)
        self.inspector_widget.setEnabled(False)
        insp_layout = QVBoxLayout(self.inspector_widget)
        insp_layout.setContentsMargins(15, 15, 15, 15)
        
        lbl_insp_title = QLabel("INSPECTOR")
        lbl_insp_title.setStyleSheet("font-weight: bold; color: #FF7043; border: none; font-size: 11pt;")
        insp_layout.addWidget(lbl_insp_title)
        
        self.preview_stack = QStackedWidget()
        self.preview_stack.setFixedSize(256, 144) 
        self.lbl_inspector_preview = QLabel()
        self.lbl_inspector_preview.setAlignment(Qt.AlignCenter)
        self.lbl_inspector_preview.setStyleSheet("background-color: #1E1715; border: 1px solid #4A3A35;")
        self.insp_video_widget = QVideoWidget()
        self.insp_video_widget.setStyleSheet("background-color: #000; border: 1px solid #4A3A35;")
        self.preview_stack.addWidget(self.lbl_inspector_preview)
        self.preview_stack.addWidget(self.insp_video_widget)
        insp_layout.addWidget(self.preview_stack, alignment=Qt.AlignHCenter)
        
        self.btn_insp_play = QPushButton("▶ Play Clip")
        self.btn_insp_play.hide()
        self.btn_insp_play.clicked.connect(self.toggle_insp_playback)
        insp_layout.addWidget(self.btn_insp_play)
        
        self.insp_player = QMediaPlayer()
        self.insp_audio_output = QAudioOutput()
        self.insp_player.setAudioOutput(self.insp_audio_output)
        self.insp_player.setVideoOutput(self.insp_video_widget)
        self.insp_player.positionChanged.connect(self.check_insp_video_pos)
        self._insp_video_stop_ms = 0
        insp_layout.addSpacing(15)
        
        self.combo_insp_type = QComboBox()
        self.combo_insp_type.addItems(["Image", "Video"])
        self.combo_insp_type.currentTextChanged.connect(self.on_inspector_change)
        insp_layout.addWidget(QLabel("Media Type:", styleSheet="border:none; color: #A09088;"))
        insp_layout.addWidget(self.combo_insp_type)
        
        self.combo_insp_anim = QComboBox()
        self.combo_insp_anim.addItems(["Random", "Static", "Zoom In", "Zoom Out", "Pan Left", "Pan Right", "Pendulum", "Ken Burns"])
        self.combo_insp_anim.currentTextChanged.connect(self.on_inspector_change)
        insp_layout.addWidget(QLabel("Clip Animation:", styleSheet="border:none; color: #A09088;"))
        insp_layout.addWidget(self.combo_insp_anim)
        
        self.combo_insp_trans = QComboBox()
        self.combo_insp_trans.addItems(["Random", "Cut", "Fade", "Mix", "Bubble Blur", "Slide Left", "Slide Right", "Swipe Left", "Swipe Right", "Pull In", "Pull Out"])
        self.combo_insp_trans.currentTextChanged.connect(self.on_inspector_change)
        insp_layout.addWidget(QLabel("Entry Transition:", styleSheet="border:none; color: #A09088;"))
        insp_layout.addWidget(self.combo_insp_trans)
        insp_layout.addSpacing(15)
        
        self.btn_insp_edit_media = QPushButton("📐 Edit Media")
        self.btn_insp_edit_media.clicked.connect(self.open_media_editor)
        self.btn_insp_caption = QPushButton("📝 Edit Caption (C)")
        self.btn_insp_caption.clicked.connect(self.open_caption_preview)
        self.btn_insp_clear = QPushButton("🗑️ Make Blank")
        self.btn_insp_clear.clicked.connect(self.make_cell_blank)
        
        insp_layout.addWidget(self.btn_insp_edit_media)
        insp_layout.addWidget(self.btn_insp_caption)
        insp_layout.addWidget(self.btn_insp_clear)
        insp_layout.addStretch()
        
        btn_random_anim = QPushButton("🎲 Random Anims")
        btn_random_anim.clicked.connect(self.randomize_animations)
        btn_random_trans = QPushButton("🎲 Random Trans")
        btn_random_trans.clicked.connect(self.randomize_transitions)
        
        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(btn_random_anim)
        buttons_layout.addWidget(btn_random_trans)
        insp_layout.addLayout(buttons_layout)
        main_layout.addWidget(self.inspector_widget)

        self.btn_new_project.clicked.connect(self.new_project)
        self.btn_open_project.clicked.connect(self.load_csv)
        self.btn_save_project.clicked.connect(self.save_project)
        self.btn_load_audio.clicked.connect(self.load_audio)
        self.btn_load_csv.clicked.connect(self.load_csv)
        self.btn_process_whisper.clicked.connect(self.run_whisper_sync)
        self.btn_render.clicked.connect(self.run_render)

        self.combo_aspect_ratio.currentTextChanged.connect(self.on_setting_changed)
        self.combo_fps.currentTextChanged.connect(self.on_setting_changed)
        self.combo_whisper_model.currentTextChanged.connect(self.on_setting_changed)
        self.cb_strict_cuts.stateChanged.connect(self.on_setting_changed)
        self.cb_vignette.stateChanged.connect(self.on_setting_changed)
        self.spin_gap.valueChanged.connect(self.on_setting_changed)

        self.sync_ui_to_model()

    def setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(self.new_project)
        QShortcut(QKeySequence("Ctrl+O"), self).activated.connect(self.load_csv)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.save_project)
        QShortcut(QKeySequence("Ctrl+I"), self).activated.connect(self.insert_line_below_selected)
        QShortcut(QKeySequence("Return"), self).activated.connect(self.insert_line_below_selected)
        QShortcut(QKeySequence("Backspace"), self).activated.connect(self.delete_current_line)
        QShortcut(QKeySequence("Delete"), self).activated.connect(self.delete_current_line)
        QShortcut(QKeySequence("C"), self).activated.connect(self.open_caption_preview)
        QShortcut(QKeySequence("T"), self).activated.connect(self.open_media_editor)
        QShortcut(QKeySequence("R"), self).activated.connect(self.open_media_editor)

    # --- MODEL SYNCHRONIZATION ---
    def sync_ui_to_model(self, select_row=None):
        """FULL TABLE REBUILD (Only used when adding/removing rows or loading projects)"""
        self._updating_ui = True
        curr_row = self.table.currentRow() if select_row is None else select_row
        
        self.combo_aspect_ratio.setCurrentText(self.project.aspect_ratio)
        self.combo_fps.setCurrentText(self.project.fps)
        self.combo_whisper_model.setCurrentText(self.project.whisper_model)
        self.cb_strict_cuts.setChecked(self.project.strict_cuts)
        self.spin_gap.setValue(self.project.gap_threshold)
        self.cb_vignette.setChecked(self.project.vignette)
        
        self._resize_preview_window()
        if self.project.audio_path: self.btn_load_audio.setStyleSheet("color: #FF7043; border-left: 4px solid #FF7043;")
        else: self.btn_load_audio.setStyleSheet("")
        
        if len(self.project.clips) > 0: self.btn_load_csv.setStyleSheet("color: #FF7043; border-left: 4px solid #FF7043;")
        else: self.btn_load_csv.setStyleSheet("")
            
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for i, clip in enumerate(self.project.clips):
            self.table.insertRow(i)
            self._fill_table_row(i, clip)
        self.table.blockSignals(False)
        self._updating_ui = False
        
        if 0 <= curr_row < self.table.rowCount(): self.table.selectRow(curr_row)
        elif self.table.rowCount() > 0: self.table.selectRow(0)
        self.update_button_states()

    def _fill_table_row(self, row, clip):
        item_type = QTableWidgetItem(clip.media_type)
        item_type.setFlags(item_type.flags() & ~Qt.ItemIsEditable) 
        self.table.setItem(row, 0, item_type)
        
        clean_path = os.path.normpath(clip.media_path.strip(" '\"\t\n\r\ufeff\u200b\u202a\u202c")) if clip.media_path else "BLANK_IMAGE"
        item_img = QTableWidgetItem(f" {self._truncate_filename(clean_path, 15)}")
        if clip.media_type == "Image" and clean_path != "BLANK_IMAGE" and os.path.exists(clean_path):
            pixmap = QPixmap(clean_path)
            if not pixmap.isNull():
                item_img.setIcon(QIcon(pixmap.scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
        elif clip.media_type == "Video" and clean_path != "BLANK_IMAGE":
            item_img.setText(f" 🎬 {self._truncate_filename(clean_path, 12)}")
            
        item_img.setFlags(item_img.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, 1, item_img)
        
        script_item = QTableWidgetItem(clip.script_text)
        was_processed = (clip.end_time > 0.0) or (clip.whisper_confidence != 100.0)
        
        if not was_processed:
            script_item.setForeground(QColor("#A09088"))
            script_item.setToolTip("Unsynced (Run Whisper to map timings)")
            st_str, et_str = "Unsynced", "Unsynced"
        else:
            if clip.whisper_confidence >= 85: script_item.setForeground(QColor("#00CC66"))
            elif clip.whisper_confidence >= 50: script_item.setForeground(QColor("#FFAA00"))
            else: script_item.setForeground(QColor("#FF4C4C"))
                
            if clip.whisper_confidence == 0.0:
                script_item.setToolTip(f"AI Confidence: 0.0% (Audio not found in timeline)")
                st_str, et_str = "0.00s", "0.00s"
            else:
                script_item.setToolTip(f"AI Confidence: {clip.whisper_confidence:.1f}%")
                st_str, et_str = f"{clip.start_time:.2f}s", f"{clip.end_time:.2f}s"
                
        self.table.setItem(row, 2, script_item)
        self.table.setItem(row, 3, QTableWidgetItem(st_str))
        self.table.setItem(row, 4, QTableWidgetItem(et_str))
        
        item_anim = QTableWidgetItem(clip.animation)
        item_anim.setFlags(item_anim.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, 5, item_anim)
        
        item_trans = QTableWidgetItem(clip.transition)
        item_trans.setFlags(item_trans.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, 6, item_trans)

    def _refresh_row_ui(self, row, update_image=False):
        """ULTRA FAST REFRESH: Updates UI for a specific row without rebuilding the entire table. Fixes dropdown lag!"""
        if row < 0 or row >= len(self.project.clips) or row >= self.table.rowCount():
            return
            
        clip = self.project.clips[row]
        self.table.blockSignals(True)
        
        if update_image:
            self._fill_table_row(row, clip)
        else:
            # Col 2: Script
            script_item = self.table.item(row, 2)
            if script_item:
                script_item.setText(clip.script_text)
                was_processed = (clip.end_time > 0.0) or (clip.whisper_confidence != 100.0)
                if not was_processed:
                    script_item.setForeground(QColor("#A09088"))
                    script_item.setToolTip("Unsynced (Run Whisper to map timings)")
                    st_str, et_str = "Unsynced", "Unsynced"
                else:
                    if clip.whisper_confidence >= 85: script_item.setForeground(QColor("#00CC66"))
                    elif clip.whisper_confidence >= 50: script_item.setForeground(QColor("#FFAA00"))
                    else: script_item.setForeground(QColor("#FF4C4C"))
                        
                    if clip.whisper_confidence == 0.0:
                        script_item.setToolTip(f"AI Confidence: 0.0% (Audio not found in timeline)")
                        st_str, et_str = "0.00s", "0.00s"
                    else:
                        script_item.setToolTip(f"AI Confidence: {clip.whisper_confidence:.1f}%")
                        st_str, et_str = f"{clip.start_time:.2f}s", f"{clip.end_time:.2f}s"
                
                # Col 3 & 4: Timings
                if self.table.item(row, 3): self.table.item(row, 3).setText(st_str)
                if self.table.item(row, 4): self.table.item(row, 4).setText(et_str)
                
            # Col 5 & 6: Anim & Trans
            if self.table.item(row, 5): self.table.item(row, 5).setText(clip.animation)
            if self.table.item(row, 6): self.table.item(row, 6).setText(clip.transition)
            
        self.table.blockSignals(False)
        self.update_button_states()

    def _truncate_filename(self, path, max_len=12):
        if not path or path == "BLANK_IMAGE": return "Blank Cell"
        base = os.path.basename(path)
        name, ext = os.path.splitext(base)
        if len(name) > max_len: return name[:max_len] + ".." + ext
        return base

    def on_setting_changed(self, *args):
        if self._updating_ui: return
        self.project.aspect_ratio = self.combo_aspect_ratio.currentText()
        self.project.fps = self.combo_fps.currentText()
        self.project.whisper_model = self.combo_whisper_model.currentText()
        self.project.strict_cuts = self.cb_strict_cuts.isChecked()
        self.project.vignette = self.cb_vignette.isChecked()
        self.project.gap_threshold = self.spin_gap.value()
        self.project.is_dirty = True
        self._resize_preview_window()
        self.update_button_states()

    def _resize_preview_window(self):
        is_vert = "9:16" in self.project.aspect_ratio
        if is_vert: self.preview_stack.setFixedSize(144, 256)
        else: self.preview_stack.setFixedSize(256, 144)
        if self.table.currentRow() >= 0:
            self.on_table_selection_changed()

    def update_button_states(self):
        has_rows = len(self.project.clips) > 0
        has_audio = bool(self.project.audio_path)
        is_synced = any(c.is_synced for c in self.project.clips)

        self.btn_save_project.setEnabled(self.project.is_dirty and (has_rows or has_audio))
        self.btn_save_project.setText("💾 Save Project*" if self.project.is_dirty else "💾 Save Project")

        self.btn_render.setEnabled(has_rows and is_synced)
        if has_rows and is_synced:
            self.btn_render.setStyleSheet("QPushButton { margin: 10px; border-radius: 4px; padding: 10px; font-weight: bold; font-size: 11pt; background-color: #FF7043; color: #121212; border: none; } QPushButton:hover { background-color: #FF8A65; }")
            self.btn_render.setToolTip("Render final video")
        else:
            self.btn_render.setStyleSheet("QPushButton { margin: 10px; border-radius: 4px; padding: 10px; font-weight: bold; font-size: 11pt; background-color: #3A2B27; color: #887C77; border: 1px dashed #5C4B45; }")
            self.btn_render.setToolTip("Sync with Whisper to enable Render")

        self.btn_process_whisper.setEnabled(has_audio and has_rows)
        self.btn_ai_shorts.setEnabled(has_rows and is_synced)

    # --- RIPPLE EDITING & TABLE INTERACTION ---
    def on_table_item_changed(self, item):
        if self._updating_ui: return
        row, col = item.row(), item.column()
        clip = self.project.clips[row]

        if col == 2:
            clip.script_text = item.text()
            self.project.is_dirty = True
            self.update_button_states()
        
        elif col in [3, 4]: 
            try:
                val = max(0.0, float(item.text().replace('s', '').strip()))
            except ValueError:
                self._refresh_row_ui(row, update_image=False) 
                return

            delta = 0.0
            
            if col == 3: 
                delta = val - clip.start_time
                if delta != 0.0:
                    clip.start_time = val
                    clip.end_time += delta 
            
            elif col == 4: 
                delta = val - clip.end_time
                if delta != 0.0:
                    clip.end_time = val

            # Fast Ripple Effect
            if delta != 0.0:
                for i in range(row + 1, len(self.project.clips)):
                    if self.project.clips[i].start_time > 0 or self.project.clips[i].end_time > 0:
                        self.project.clips[i].start_time += delta
                        self.project.clips[i].end_time += delta
                        self._refresh_row_ui(i, update_image=False)
                
                self.project.is_dirty = True
                self._refresh_row_ui(row, update_image=False)

    def on_table_selection_changed(self):
        if self._updating_ui: return
        row = self.table.currentRow()
        if row < 0:
            self.inspector_widget.setEnabled(False)
            self.lbl_inspector_preview.clear()
            self.insp_player.stop()
            return
            
        self._updating_inspector = True
        self.inspector_widget.setEnabled(True)
        clip = self.project.clips[row]
        
        self.combo_insp_type.setCurrentText(clip.media_type)
        self.combo_insp_anim.setCurrentText(clip.animation)
        self.combo_insp_trans.setCurrentText(clip.transition)
        
        if clip.media_type == "Video":
            self.btn_insp_edit_media.setText("✂️ Trim Video (T)")
            self.btn_insp_edit_media.setEnabled(not clip.is_blank)
            self.preview_stack.setCurrentWidget(self.insp_video_widget)
            self.btn_insp_play.show()
            self.btn_insp_play.setText("▶ Play Clip")
            if not clip.is_blank and os.path.exists(clip.media_path):
                self.insp_player.setSource(QUrl.fromLocalFile(clip.media_path))
            else: self.insp_player.stop()
        else:
            self.btn_insp_edit_media.setText("📐 Crop Image (R)")
            self.btn_insp_edit_media.setEnabled(not clip.is_blank)
            self.preview_stack.setCurrentWidget(self.lbl_inspector_preview)
            self.btn_insp_play.hide()
            self.insp_player.stop()
            if not clip.is_blank and os.path.exists(clip.media_path):
                w, h = self.preview_stack.width(), self.preview_stack.height()
                self.lbl_inspector_preview.setPixmap(QPixmap(clip.media_path).scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self.lbl_inspector_preview.clear()
                self.lbl_inspector_preview.setText("⬛\nBlank")
        self._updating_inspector = False

    def on_inspector_change(self):
        if self._updating_inspector or self._updating_ui: return
        row = self.table.currentRow()
        if row < 0: return
        
        clip = self.project.clips[row]
        new_type = self.combo_insp_type.currentText()
        needs_image_update = False
        
        if new_type != clip.media_type:
            if new_type == "Video":
                file_name, _ = QFileDialog.getOpenFileName(self, "Select Video", "", "Videos (*.mp4 *.mov *.avi *.mkv)")
            else:
                file_name, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Images (*.png *.jpg *.jpeg)")
                
            if file_name:
                clip.media_type = new_type
                clip.media_path = os.path.normpath(file_name)
                needs_image_update = True
            else:
                self._updating_inspector = True
                self.combo_insp_type.setCurrentText(clip.media_type)
                self._updating_inspector = False
                return

        clip.animation = self.combo_insp_anim.currentText()
        clip.transition = self.combo_insp_trans.currentText()
        self.project.is_dirty = True
        
        # Fast UI Update
        self._refresh_row_ui(row, update_image=needs_image_update)
        
        if needs_image_update:
            self.on_table_selection_changed()

    # --- PLAYBACK & EDITING ---
    def toggle_insp_playback(self):
        row = self.table.currentRow()
        if row < 0: return
        
        if self.insp_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.insp_player.pause()
            self.btn_insp_play.setText("▶ Play Clip")
            return
            
        clip = self.project.clips[row]
        req_duration = clip.end_time - clip.start_time
        if req_duration <= 0: req_duration = 3.0
        
        self.insp_player.setPosition(int(clip.trim_start * 1000))
        self._insp_video_stop_ms = int((clip.trim_start + req_duration) * 1000)
        self.insp_player.play()
        self.btn_insp_play.setText("⏸ Pause")

    def check_insp_video_pos(self, pos_ms):
        if self._insp_video_stop_ms > 0 and pos_ms >= self._insp_video_stop_ms:
            self.insp_player.pause()
            self._insp_video_stop_ms = 0
            self.btn_insp_play.setText("▶ Play Clip")

    def open_media_editor(self):
        row = self.table.currentRow()
        if row < 0: return
        clip = self.project.clips[row]
        if clip.is_blank or not os.path.exists(clip.media_path): return
            
        if clip.media_type == "Image":
            target_ratio = 16/9 if "16:9" in self.project.aspect_ratio else 9/16
            dlg = ImageCropDialog(clip.media_path, target_ratio, self)
            if dlg.exec():
                new_path = dlg.get_cropped_path()
                if new_path:
                    clip.media_path = new_path
                    self.project.is_dirty = True
                    self._refresh_row_ui(row, update_image=True)
                    self.on_table_selection_changed()
        elif clip.media_type == "Video":
            dlg = VideoTrimDialog(clip.media_path, self, start_val=clip.trim_start, end_val=clip.trim_end)
            if dlg.exec():
                new_s, new_e = dlg.get_trim()
                clip.trim_start, clip.trim_end = new_s, new_e
                self.project.is_dirty = True
                self._refresh_row_ui(row, update_image=False)

    # --- PROJECT FILE I/O ---
    def new_project(self):
        if self.project.is_dirty:
            if QMessageBox.question(self, 'Unsaved Changes', 'Discard unsaved changes?', QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.No: return
        self.project = ProjectState()
        self.main_project_state = None
        self.btn_return_main.hide()
        
        self.btn_process_whisper.setStyleSheet("")
        self.btn_load_audio.setStyleSheet("")
        self.btn_load_csv.setStyleSheet("")
        self.inspector_widget.setEnabled(False)
        self.lbl_inspector_preview.clear()
        self.lbl_inspector_preview.setText("⬛\nBlank")
        self.insp_player.stop()
        
        self.sync_ui_to_model()
        self.lbl_status.setText("Ready")

    def load_audio(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Select Audio", "", "Audio (*.mp3 *.wav *.m4a)")
        if file_name:
            self.project.audio_path = file_name
            self.project.is_dirty = True
            self.sync_ui_to_model()
            self.lbl_status.setText("Audio Loaded")

    def load_csv(self):
        if self.project.is_dirty and len(self.project.clips) > 0:
            if QMessageBox.question(self, 'Unsaved Changes', 'Discard current timeline to open this script?', QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.No: return
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Project/CSV", "", "CSV Files (*.csv)")
        if file_name:
            try:
                existing_audio = self.project.audio_path
                new_project = ProjectState()
                is_full = new_project.load_from_csv(file_name)
                
                if not is_full:
                    new_project.filepath = None
                    new_project.is_dirty = True
                    
                if not new_project.audio_path and existing_audio:
                    new_project.audio_path = existing_audio
                    
                self.project = new_project
                self.main_project_state = None
                self.btn_return_main.hide()
                self.sync_ui_to_model()
                self.lbl_status.setText(f"Loaded {len(self.project.clips)} lines.")
            except Exception as e: QMessageBox.critical(self, "Error", f"Failed to load CSV: {e}")

    def save_project(self):
        if len(self.project.clips) == 0 and not self.project.audio_path: return
        file_name = self.project.filepath
        if not file_name:
            default_name = "my_project.csv"
            if self.main_project_state and self.main_project_state.filepath:
                default_name = f"{os.path.splitext(self.main_project_state.filepath)[0]}_short.csv"
            file_name, _ = QFileDialog.getSaveFileName(self, "Save Project", default_name, "CSV Files (*.csv)")
            if not file_name: return
        try:
            self.project.save_to_csv(file_name)
            self.lbl_status.setText("Project Saved!")
            self.update_button_states()
        except Exception as e: QMessageBox.critical(self, "Save Error", f"Failed to save project:\n{e}")

    # --- AI SHORTS ---
    def open_ai_shorts(self):
        timeline = [{"start_time": str(c.start_time), "end_time": str(c.end_time), "script_line": c.script_text} for c in self.project.clips]
        dlg = AIShortsDialog(timeline, self)
        if dlg.exec():
            self.generate_short_project(dlg.get_selected_segment())

    def generate_short_project(self, segment):
        st, et = segment['start'], segment['end']
        if not self.main_project_state: self.main_project_state = copy.deepcopy(self.project)
            
        short_clips = []
        for c in self.main_project_state.clips:
            if c.end_time > st and c.start_time < et:
                new_c = copy.deepcopy(c)
                new_c.caption_y = 0.74 
                short_clips.append(new_c)
                
        self.project = ProjectState()
        self.project.filepath = f"{os.path.splitext(self.main_project_state.filepath)[0]}_short.csv" if self.main_project_state.filepath else None
        self.project.audio_path = self.main_project_state.audio_path
        self.project.aspect_ratio = "9:16 (Vertical)"
        self.project.fps = self.main_project_state.fps
        self.project.whisper_model = self.main_project_state.whisper_model
        self.project.strict_cuts = self.main_project_state.strict_cuts
        self.project.gap_threshold = self.main_project_state.gap_threshold
        self.project.clips = short_clips
        self.project.is_dirty = True
        
        self.btn_return_main.show()
        self.sync_ui_to_model()
        self.lbl_status.setText(f"Short Project Loaded: {segment['title']}")

    def return_to_main_project(self):
        if not self.main_project_state: return
        if self.project.is_dirty:
            if QMessageBox.question(self, 'Unsaved Changes', 'Discard changes to this short and return to main project?', QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.No: return
        self.project = self.main_project_state
        self.main_project_state = None
        self.btn_return_main.hide()
        self.sync_ui_to_model()
        self.lbl_status.setText("Returned to Main Project.")

    # --- ACTIONS ---
    def randomize_animations(self):
        self.table.blockSignals(True)
        for i, c in enumerate(self.project.clips): 
            c.animation = random.choice(["Zoom In", "Zoom Out", "Pan Left", "Pan Right", "Pendulum", "Ken Burns"])
            item = self.table.item(i, 5)
            if item: item.setText(c.animation)
        self.project.is_dirty = True
        self.table.blockSignals(False)
        
        row = self.table.currentRow()
        if row >= 0:
            self._updating_inspector = True
            self.combo_insp_anim.setCurrentText(self.project.clips[row].animation)
            self._updating_inspector = False

    def randomize_transitions(self):
        self.table.blockSignals(True)
        for i, c in enumerate(self.project.clips): 
            c.transition = random.choice(["Cut", "Fade", "Mix", "Bubble Blur", "Slide Left", "Slide Right", "Swipe Left", "Swipe Right", "Pull In", "Pull Out"])
            item = self.table.item(i, 6)
            if item: item.setText(c.transition)
        self.project.is_dirty = True
        self.table.blockSignals(False)
        
        row = self.table.currentRow()
        if row >= 0:
            self._updating_inspector = True
            self.combo_insp_trans.setCurrentText(self.project.clips[row].transition)
            self._updating_inspector = False

    def insert_line_below_selected(self):
        row = self.table.currentRow()
        target_idx = row + 1 if row >= 0 else len(self.project.clips)
        new_clip = Clip()
        new_clip.media_path = "Double_Click_To_Add_Image.png"
        new_clip.script_text = "Type new split line here..."
        self.project.clips.insert(target_idx, new_clip)
        self.project.is_dirty = True
        self.sync_ui_to_model(select_row=target_idx) # Addition needs full rebuild

    def delete_current_line(self):
        row = self.table.currentRow()
        if row >= 0:
            self.project.clips.pop(row)
            self.project.is_dirty = True
            self.sync_ui_to_model(select_row=min(row, len(self.project.clips)-1)) # Deletion needs full rebuild

    def make_cell_blank(self):
        row = self.table.currentRow()
        if row >= 0:
            self.project.clips[row].media_path = "BLANK_IMAGE"
            self.project.is_dirty = True
            self._refresh_row_ui(row, update_image=True)
            self.on_table_selection_changed()

    def show_context_menu(self, pos):
        menu = QMenu(self)
        add_action = menu.addAction("Insert New Line Below")
        delete_action = menu.addAction("Delete This Line")
        clear_action = menu.addAction("Remove Media (Make Blank)")
        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if action == add_action: self.insert_line_below_selected()
        elif action == delete_action: self.delete_current_line()
        elif action == clear_action: self.make_cell_blank()

    def handle_cell_double_click(self, row, col):
        if col == 1:
            clip = self.project.clips[row]
            if clip.media_type == "Video": file_name, _ = QFileDialog.getOpenFileName(self, "Select Replacement Video", "", "Videos (*.mp4 *.mov *.avi *.mkv)")
            else: file_name, _ = QFileDialog.getOpenFileName(self, "Select Replacement Image", "", "Images (*.png *.jpg *.jpeg)")
            if file_name:
                clip.media_path = os.path.normpath(file_name)
                self.project.is_dirty = True
                self._refresh_row_ui(row, update_image=True)
                self.on_table_selection_changed()

    def play_current_segment(self):
        row = self.table.currentRow()
        if row < 0 or not self.project.audio_path: return
        clip = self.project.clips[row]
        if not clip.is_synced: return
            
        start_sec = max(0.0, clip.start_time - 0.2)
        end_sec = clip.end_time + 0.2
        seek_ms = int(start_sec * 1000)
        duration_ms = int((end_sec - start_sec) * 1000)
        if duration_ms <= 0: return

        self.player.pause()
        self._stop_position_ms = seek_ms + duration_ms
        
        target_url = QUrl.fromLocalFile(self.project.audio_path)
        
        if self.player.source() == target_url:
            self.player.setPosition(seek_ms)
            self.player.play()
        else:
            self._pending_seek_ms = seek_ms
            try: self.player.mediaStatusChanged.disconnect(self._on_media_ready)
            except RuntimeError: pass
            self.player.mediaStatusChanged.connect(self._on_media_ready)
            self.player.setSource(target_url)

    def _check_audio_pos(self, pos_ms):
        if getattr(self, '_stop_position_ms', 0) > 0 and pos_ms >= self._stop_position_ms:
            self.player.pause()
            self._stop_position_ms = 0

    def _on_media_ready(self, status):
        if status == QMediaPlayer.MediaStatus.LoadedMedia and self._pending_seek_ms is not None:
            self.player.setPosition(self._pending_seek_ms)
            self.player.play()
            self._pending_seek_ms = None
            try: self.player.mediaStatusChanged.disconnect(self._on_media_ready)
            except RuntimeError: pass

    def open_caption_preview(self):
        row = self.table.currentRow()
        if row < 0: return
        clip = self.project.clips[row]
        is_vert = "9:16" in self.project.aspect_ratio
        
        c_y = clip.caption_y if clip.caption_y is not None else (0.74 if is_vert else 0.90)
            
        dlg = CaptionPreviewDialog(clip.media_path, clip.script_text, clip.caption_x, c_y, clip.caption_scale, clip.caption_rot, self, is_vertical=is_vert)
        if dlg.exec():
            n_x, n_y, n_s, n_r = dlg.get_values()
            clip.caption_x, clip.caption_y, clip.caption_scale, clip.caption_rot = n_x, n_y, n_s, n_r
            self.project.is_dirty = True

    def run_whisper_sync(self):
        if not self.project.audio_path or not self.project.clips: return
        current_script_data = [{"image": c.media_path, "text": c.script_text} for c in self.project.clips]
        model_size = "tiny" if "Tiny" in self.project.whisper_model else "small" if "Small" in self.project.whisper_model else "base"
        self.btn_process_whisper.setEnabled(False)
        self.progress_bar.setRange(0, 0)
        
        self.worker = WhisperWorker(self.project.audio_path, current_script_data, model_size=model_size)
        self.worker.progress.connect(lambda msg: self.lbl_status.setText(msg))
        self.worker.whisper_done.connect(self.on_sync_finished)
        self.worker.error.connect(lambda err: QMessageBox.critical(self, "Sync Error", str(err)))
        self.worker.start()

    def on_sync_finished(self, timeline, elapsed_secs):
        try:
            for i, item in enumerate(timeline):
                if i < len(self.project.clips):
                    clip = self.project.clips[i]
                    clip.start_time = item.get("start_time", 0.0)
                    clip.end_time = item.get("end_time", 0.0)
                    clip.whisper_confidence = item.get("confidence", 100.0)
                    clip.words = item.get("words", [])
            
            safe_last_end = 0.0
            for i, clip in enumerate(self.project.clips):
                st = max(clip.start_time, safe_last_end)
                
                if i < len(self.project.clips) - 1:
                    next_st = self.project.clips[i+1].start_time
                    et = min(clip.end_time, next_st)
                else:
                    et = clip.end_time
                    
                if et - st < 0.2:
                    et = st + 0.2
                    
                clip.start_time = st
                clip.end_time = et
                safe_last_end = et
                
            self.project.is_dirty = True
            self.sync_ui_to_model()
            
            self.progress_bar.setRange(0, 100); self.progress_bar.setValue(100)
            self.btn_process_whisper.setEnabled(True)
            self.lbl_status.setText(f"Sync Complete! (took {int(elapsed_secs//60)}m {int(elapsed_secs%60)}s)")
            self.btn_process_whisper.setStyleSheet("color: #FF7043; border-left: 4px solid #FF7043;")
        except Exception as e:
            QMessageBox.critical(self, "UI Update Error", f"Crash during UI table update:\n{traceback.format_exc()}")

    def run_render(self):
        is_synced = any(c.is_synced for c in self.project.clips)
        if not self.project.clips or not is_synced: return
        
        default_name = "final_short.mp4" if self.main_project_state else "final_video.mp4"
        output_file, _ = QFileDialog.getSaveFileName(self, "Save Video As", default_name, "MP4 Video (*.mp4)")
        if not output_file: return 

        render_data = []
        is_vert = "9:16" in self.project.aspect_ratio
        
        safe_last_end = 0.0
        for i, c in enumerate(self.project.clips):
            st = max(c.start_time, safe_last_end)
            
            if i < len(self.project.clips) - 1:
                next_st = self.project.clips[i+1].start_time
                et = min(c.end_time, next_st)
            else:
                et = c.end_time + 0.2
                
            if et - st < 0.2:
                et = st + 0.2
            
            render_data.append({
                "type": c.media_type, "image": c.media_path, "script_line": c.script_text,
                "start_time": st, "end_time": et, "animation": c.animation, "transition": c.transition, 
                "trim_start": c.trim_start, "trim_end": c.trim_end, "caption_x": c.caption_x, 
                "caption_y": c.caption_y if c.caption_y is not None else (0.74 if is_vert else 0.90), 
                "caption_scale": c.caption_scale, "caption_rot": c.caption_rot, "words": c.words
            })
            safe_last_end = et

        self.btn_render.setEnabled(False)
        self.progress_bar.setRange(0, 100); self.progress_bar.setValue(0)
        self.render_worker = RenderWorker(
            render_data, self.project.audio_path, output_file, 
            self.project.aspect_ratio, self.project.strict_cuts, self.project.gap_threshold, 
            30 if "30" in self.project.fps else 60, self.project.vignette
        )
        self.render_worker.progress.connect(self.handle_render_progress)
        self.render_worker.render_done.connect(lambda elapsed: self.on_render_finished(elapsed, output_file))
        self.render_worker.error.connect(lambda err: QMessageBox.critical(self, "Error", str(err)))
        self.render_worker.start()

    def handle_render_progress(self, msg):
        self.lbl_status.setText(msg)
        match = re.search(r'(\d+)%', msg)
        if match: self.progress_bar.setValue(int(match.group(1)))

    def on_render_finished(self, elapsed_secs, output_file):
        self.progress_bar.setValue(100)
        self.btn_render.setEnabled(True)
        self.lbl_status.setText(f"Video Rendered! (took {int(elapsed_secs//60)}m {int(elapsed_secs%60)}s)")
        os.startfile(os.path.dirname(output_file))

    def closeEvent(self, event):
        if self.project.is_dirty:
            reply = QMessageBox.question(self, 'Unsaved Changes', 'Save changes before exiting?', QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                self.save_project()
                if self.project.is_dirty: event.ignore(); return
            elif reply == QMessageBox.Cancel: event.ignore(); return
        
        if (hasattr(self, 'render_worker') and self.render_worker.isRunning()) or (hasattr(self, 'worker') and self.worker.isRunning()):
            if QMessageBox.question(self, 'Task in Progress', 'Working in background. Force quit?', QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.No:
                event.ignore(); return
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AutoEditorGUI()
    window.show()
    sys.exit(app.exec())