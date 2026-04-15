import os
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
                               QListWidget, QListWidgetItem, QAbstractItemView, QMessageBox)
from PySide6.QtCore import Qt

class WordEditorDialog(QDialog):
    def __init__(self, project, current_row, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Word Editor - Clip {current_row + 1}")
        self.setMinimumSize(600, 450)
        
        if hasattr(parent, "styleSheet"):
            self.setStyleSheet(parent.styleSheet())

        self.project = project
        self.current_row = current_row
        self.clip = self.project.clips[self.current_row]

        self.setup_ui()
        self.refresh_list()

    def setup_ui(self):
        layout = QHBoxLayout(self)

        # --- LEFT PANEL: List ---
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("Words in this Clip (Select multiple with Ctrl/Shift):", styleSheet="color: #A09088; font-weight: bold;"))
        
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list_widget.setStyleSheet("""
            QListWidget { background-color: #1E1715; border: 1px solid #4A3A35; border-radius: 6px; outline: none; }
            QListWidget::item { padding: 10px; border-bottom: 1px solid #362A26; color: #EAE0D5; font-size: 11pt; }
            QListWidget::item:selected { background-color: #362A26; border-left: 4px solid #00E676; color: #FFFFFF; font-weight: bold; }
        """)
        left_layout.addWidget(self.list_widget)
        layout.addLayout(left_layout, stretch=2)

        # --- RIGHT PANEL: Actions ---
        right_layout = QVBoxLayout()
        right_layout.addWidget(QLabel("Actions:", styleSheet="color: #A09088; font-weight: bold;"))

        self.btn_pull = QPushButton("⬆️ Pull Last Word from Prev Clip")
        self.btn_pull.setStyleSheet("text-align: left; padding: 10px;")
        self.btn_pull.clicked.connect(self.pull_from_prev)
        
        self.btn_push = QPushButton("⬇️ Push Selected to Next Clip")
        self.btn_push.setStyleSheet("text-align: left; padding: 10px;")
        self.btn_push.clicked.connect(self.push_to_next)
        
        right_layout.addWidget(self.btn_pull)
        right_layout.addWidget(self.btn_push)
        
        right_layout.addSpacing(20)
        
        self.btn_del = QPushButton("🗑️ Delete Selected Words")
        self.btn_del.setStyleSheet("QPushButton { text-align: left; padding: 10px; } QPushButton:hover { background-color: #FF4C4C; color: white; border-color: #FF4C4C; }")
        self.btn_del.clicked.connect(self.delete_selected)
        right_layout.addWidget(self.btn_del)
        
        right_layout.addStretch()

        btn_close = QPushButton("✓ Apply & Close")
        btn_close.setProperty("class", "primary")
        btn_close.setMinimumHeight(40)
        btn_close.clicked.connect(self.accept)
        right_layout.addWidget(btn_close)

        layout.addLayout(right_layout, stretch=1)

    def refresh_list(self):
        self.list_widget.clear()
        for i, w in enumerate(self.clip.words):
            # Display word text alongside its precise start and end times
            item = QListWidgetItem(f"{w['word']}   ({w.get('start', 0.0):.2f}s - {w.get('end', 0.0):.2f}s)")
            item.setData(Qt.UserRole, i)
            self.list_widget.addItem(item)

        # Disable buttons if they hit timeline boundaries
        self.btn_pull.setEnabled(self.current_row > 0 and len(self.project.clips[self.current_row - 1].words) > 0)
        self.btn_push.setEnabled(self.current_row < len(self.project.clips) - 1 and len(self.clip.words) > 0)

    def delete_selected(self):
        items = self.list_widget.selectedItems()
        if not items: return
        
        indices = [item.data(Qt.UserRole) for item in items]
        self.clip.words = [w for i, w in enumerate(self.clip.words) if i not in indices]
        
        self.update_script_and_bounds(self.current_row)
        self.refresh_list()
        self.project.is_dirty = True

    def push_to_next(self):
        items = self.list_widget.selectedItems()
        if not items: return
        if self.current_row >= len(self.project.clips) - 1: return

        # Sort indices in reverse so popping doesn't break the list
        indices = sorted([item.data(Qt.UserRole) for item in items], reverse=True)
        next_clip = self.project.clips[self.current_row + 1]

        words_to_move = []
        for i in indices:
            words_to_move.append(self.clip.words.pop(i))

        # Reverse back to maintain the original spoken order
        words_to_move.reverse() 

        # Prepend to the next clip
        next_clip.words = words_to_move + next_clip.words

        self.update_script_and_bounds(self.current_row)
        self.update_script_and_bounds(self.current_row + 1)
        self.refresh_list()
        self.project.is_dirty = True

    def pull_from_prev(self):
        if self.current_row == 0: return
        prev_clip = self.project.clips[self.current_row - 1]
        if not prev_clip.words: return

        # Pop the very last word from the previous clip
        word_to_move = prev_clip.words.pop(-1)
        
        # Insert at the very beginning of the current clip
        self.clip.words.insert(0, word_to_move)

        self.update_script_and_bounds(self.current_row - 1)
        self.update_script_and_bounds(self.current_row)
        self.refresh_list()
        self.project.is_dirty = True

    def update_script_and_bounds(self, row):
        """Automatically tightens the clip start/end boundaries based on the new words"""
        clip = self.project.clips[row]
        clip.script_text = " ".join([w['word'] for w in clip.words])
        
        if clip.words:
            clip.start_time = clip.words[0].get('start', clip.start_time)
            clip.end_time = clip.words[-1].get('end', clip.end_time)