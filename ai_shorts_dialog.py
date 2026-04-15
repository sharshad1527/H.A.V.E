import os
import json
import requests
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QLineEdit, QComboBox, QListWidget, QListWidgetItem, QWidget,
    QProgressBar, QMessageBox, QSplitter
)
from PySide6.QtCore import Qt, QThread, Signal

class APIWorker(QThread):
    finished = Signal(list)
    error = Signal(str)
    
    def __init__(self, api_key, model, transcript, target_duration):
        super().__init__()
        self.api_key = api_key
        self.model = model
        self.transcript = transcript
        self.target_duration = target_duration
        
    def run(self):
        try:
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/sharshad1527/h.a.v.e",
                "X-Title": "H.A.V.E. Pro Editor"
            }
            
            target_int = int(self.target_duration)
            min_dur = max(30, target_int - 15) # Enforce a strict minimum based on selection
            
            system_prompt = (
                "You are an expert viral content strategist. "
                "Analyze the provided video transcript and identify the best continuous segments for a short-form video (TikTok/Reels/Shorts). "
                f"\n\n*** CRITICAL DURATION RULES (MUST FOLLOW) ***\n"
                f"1. Each segment MUST be AT LEAST {min_dur} seconds long! The target is {target_int} seconds.\n"
                "2. AI models often make the mistake of selecting short 10-20 second soundbites. DO NOT DO THIS. You MUST group many consecutive lines together to form a complete, longer narrative.\n"
                f"3. Math Check: Ensure that (end_time - start_time) is greater than or equal to {min_dur}.\n"
                "4. Quality over Quantity: It is perfectly fine to return only 1 or 2 long segments instead of many short ones.\n\n"
                "You MUST return ONLY a valid JSON array of objects. Do not include markdown formatting, backticks, or any conversational text. "
                "Each object MUST have these exact keys: 'title' (string), 'start_time' (float), 'end_time' (float), 'reasoning' (string), 'virality_score' (int 1-10)."
            )
            
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Here is the transcript with timestamps:\n{self.transcript}"}
                ]
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            
            if response.status_code == 429:
                self.error.emit(
                    f"API Error 429: Rate Limited.\n\nThe model '{self.model}' is currently overloaded on OpenRouter's servers. "
                    "Please select a different free model from the dropdown and try again.\n\nRaw Error: " + response.text
                )
                return
            elif response.status_code != 200:
                self.error.emit(f"API Error {response.status_code}: {response.text}")
                return
                
            data = response.json()
            try:
                content = data["choices"][0]["message"]["content"]
            except (KeyError, IndexError):
                self.error.emit(f"Unexpected API response structure: {response.text}")
                return
            
            # Clean markdown if present
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            parsed = json.loads(content)
            
            # Handle if the model wrapped the list in a dict like { "shorts": [...] }
            if isinstance(parsed, dict):
                for k, v in parsed.items():
                    if isinstance(v, list):
                        parsed = v
                        break
                        
            if not isinstance(parsed, list):
                self.error.emit(f"The AI did not return a valid list format. It returned:\n{content}")
                return
                
            self.finished.emit(parsed)
            
        except json.JSONDecodeError as e:
            self.error.emit(f"The AI model failed to return valid JSON data. Please try a different model.\nError: {str(e)}")
        except Exception as e:
            self.error.emit(str(e))


class AIShortsDialog(QDialog):
    def __init__(self, timeline_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI Shorts Creator (Pro)")
        self.setMinimumSize(1000, 650)
        
        if hasattr(parent, "styleSheet"):
            self.setStyleSheet(parent.styleSheet())
            
        self.timeline_data = timeline_data
        self.selected_segment = None
        self.settings_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "openrouter_settings.json")
        
        self.setup_ui()
        self.load_settings()
        
    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # --- LEFT PANEL: Settings & Generation ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        lbl_title = QLabel("✨ AI Viral Clip Analyzer")
        lbl_title.setStyleSheet("font-size: 14pt; font-weight: bold; color: #FF7043;")
        left_layout.addWidget(lbl_title)
        
        left_layout.addWidget(QLabel("OpenRouter API Key:"))
        self.txt_api_key = QLineEdit()
        self.txt_api_key.setEchoMode(QLineEdit.Password)
        self.txt_api_key.setPlaceholderText("sk-or-v1-...")
        left_layout.addWidget(self.txt_api_key)
        
        left_layout.addWidget(QLabel("AI Model (Free Options Included):"))
        self.combo_model = QComboBox()
        self.combo_model.setEditable(True)
        self.combo_model.addItems([
            "google/gemini-2.5-flash-free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "mistralai/mistral-nemo-free",
            "microsoft/phi-3-mini-128k-instruct:free",
            "stepfun/step-3.5-flash:free"
        ])
        left_layout.addWidget(self.combo_model)
        
        left_layout.addWidget(QLabel("Target Duration:"))
        self.combo_duration = QComboBox()
        self.combo_duration.addItems(["30 Seconds", "60 Seconds", "90 Seconds"])
        self.combo_duration.setCurrentIndex(1)
        left_layout.addWidget(self.combo_duration)
        
        left_layout.addSpacing(20)
        
        self.btn_analyze = QPushButton("🚀 Analyze Project")
        self.btn_analyze.setProperty("class", "primary")
        self.btn_analyze.clicked.connect(self.run_analysis)
        left_layout.addWidget(self.btn_analyze)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.hide()
        left_layout.addWidget(self.progress_bar)
        
        self.lbl_status = QLabel("Ready to analyze timeline.")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setStyleSheet("color: #A09088;")
        left_layout.addWidget(self.lbl_status)
        
        left_layout.addStretch()
        
        # --- RIGHT PANEL: Results ---
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        right_layout.addWidget(QLabel("Suggested Viral Shorts:", styleSheet="font-weight: bold; font-size: 12pt;"))
        
        self.list_results = QListWidget()
        self.list_results.setStyleSheet("""
            QListWidget { background-color: #1E1715; border: 1px solid #4A3A35; border-radius: 6px; } 
            QListWidget::item { border-bottom: 1px solid #362A26; } 
            QListWidget::item:selected { background-color: #362A26; border-left: 4px solid #FF7043; }
        """)
        right_layout.addWidget(self.list_results)
        
        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        
        self.btn_create = QPushButton("🎬 Create Short from Selection")
        self.btn_create.setProperty("class", "primary")
        self.btn_create.setEnabled(False)
        self.btn_create.clicked.connect(self.create_short)
        
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(self.btn_create)
        right_layout.addLayout(btn_layout)
        
        self.list_results.itemSelectionChanged.connect(self.on_selection_changed)
        
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([350, 650])

    def load_settings(self):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r") as f:
                    data = json.load(f)
                    self.txt_api_key.setText(data.get("openrouter_api_key", ""))
                    if "openrouter_model" in data:
                        self.combo_model.setCurrentText(data["openrouter_model"])
            except:
                pass

    def save_settings(self):
        data = {
            "openrouter_api_key": self.txt_api_key.text().strip(),
            "openrouter_model": self.combo_model.currentText().strip()
        }
        try:
            with open(self.settings_file, "w") as f:
                json.dump(data, f)
        except:
            pass
            
    def compile_transcript(self):
        transcript_lines = []
        for row in self.timeline_data:
            try:
                if isinstance(row, dict):
                    st_val = str(row.get("start_time", "0")).replace('s','').strip()
                    et_val = str(row.get("end_time", "0")).replace('s','').strip()
                    txt = str(row.get("script_line", "")).strip()
                else:
                    st_val = str(row[3]).replace('s','').strip()
                    et_val = str(row[4]).replace('s','').strip()
                    txt = str(row[2]).strip()
                    
                st = float(st_val) if st_val and st_val != "Unsynced" else 0.0
                et = float(et_val) if et_val and et_val != "Unsynced" else 0.0
                
                if txt and txt != "Unsynced":
                    if et > st:
                        transcript_lines.append(f"[{st:.1f} - {et:.1f}] {txt}")
                    else:
                        transcript_lines.append(f"[Timeline] {txt}")
            except Exception as e:
                print(f"Skipping row due to error: {e}")
                continue
        return "\n".join(transcript_lines)

    def run_analysis(self):
        api_key = self.txt_api_key.text().strip()
        if not api_key:
            QMessageBox.warning(self, "Missing API Key", "Please enter your OpenRouter API Key.")
            return
            
        self.save_settings()
        
        transcript = self.compile_transcript()
        if not transcript:
            QMessageBox.warning(self, "No Transcript", "The timeline is empty or unsynced. Sync it with Whisper first.")
            return

        dur_text = self.combo_duration.currentText().split()[0]
        
        self.btn_analyze.setEnabled(False)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.show()
        self.lbl_status.setText(f"Connecting to OpenRouter ({self.combo_model.currentText()})... Analyzing timeline.")
        self.list_results.clear()
        self.btn_create.setEnabled(False)
        
        self.worker = APIWorker(api_key, self.combo_model.currentText(), transcript, dur_text)
        self.worker.finished.connect(self.on_analysis_finished)
        self.worker.error.connect(self.on_analysis_error)
        self.worker.start()

    def on_analysis_finished(self, results):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.btn_analyze.setEnabled(True)
        self.lbl_status.setText(f"Successfully generated {len(results)} viral clip options.")
        
        for idx, item in enumerate(results):
            title = item.get("title", f"Short Option {idx+1}")
            score = item.get("virality_score", 5)
            st = float(item.get("start_time", 0.0))
            et = float(item.get("end_time", 0.0))
            reason = item.get("reasoning", "")
            
            list_item = QListWidgetItem()
            
            widget = QWidget()
            layout = QVBoxLayout(widget)
            layout.setContentsMargins(15, 10, 15, 10)
            
            lbl_title = QLabel(f"🔥 {score}/10 | {title}  ({et-st:.1f}s)")
            lbl_title.setStyleSheet("font-weight: bold; color: #EAE0D5; font-size: 11pt;")
            layout.addWidget(lbl_title)
            
            lbl_times = QLabel(f"⏱️ Cut Range: {st:.1f}s - {et:.1f}s")
            lbl_times.setStyleSheet("color: #FF7043; font-size: 9pt;")
            layout.addWidget(lbl_times)
            
            lbl_reason = QLabel(reason)
            lbl_reason.setWordWrap(True)
            lbl_reason.setStyleSheet("color: #A09088; font-size: 9pt; margin-top: 5px;")
            layout.addWidget(lbl_reason)
            
            list_item.setSizeHint(widget.sizeHint())
            
            list_item.setData(Qt.UserRole, {
                "start": st,
                "end": et,
                "title": title
            })
            
            self.list_results.addItem(list_item)
            self.list_results.setItemWidget(list_item, widget)

    def on_analysis_error(self, err):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.btn_analyze.setEnabled(True)
        self.lbl_status.setText("Failed to analyze.")
        
        QMessageBox.critical(self, "API Error", f"OpenRouter API encountered an issue:\n\n{err}")

    def on_selection_changed(self):
        self.btn_create.setEnabled(len(self.list_results.selectedItems()) > 0)

    def create_short(self):
        items = self.list_results.selectedItems()
        if not items: return
        self.selected_segment = items[0].data(Qt.UserRole)
        self.accept()

    def get_selected_segment(self):
        return self.selected_segment