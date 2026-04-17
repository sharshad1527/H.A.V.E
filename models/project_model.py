import os
import csv
import copy

class Clip:
    """Represents a single media segment in the timeline."""
    def __init__(self):
        self.media_type = "Image"
        self.media_path = ""
        self.script_text = ""
        self.start_time = 0.0
        self.end_time = 0.0
        self.animation = "Random"
        self.transition = "Random"
        self.trim_start = 0.0
        self.trim_end = 0.0
        self.caption_x = 0.5
        self.caption_y = None  # None allows dynamic default assignment based on Aspect Ratio
        self.caption_scale = 1.0
        self.caption_rot = 0.0
        
        # Whisper sync metadata
        self.words = []
        self.whisper_confidence = 100.0

    @property
    def is_blank(self):
        return not self.media_path or self.media_path == "BLANK_IMAGE"

    @property
    def is_synced(self):
        return self.end_time > 0.0

class ProjectState:
    """Central Truth: Holds all timeline data and global settings independent of the UI."""
    def __init__(self):
        self.filepath = None
        self.audio_path = None
        self.aspect_ratio = "16:9 (Horizontal)"
        self.fps = "60 FPS"
        self.whisper_model = "Base"
        self.strict_cuts = True
        self.gap_threshold = 0.6
        self.vignette = True
        self.clips = []
        self.is_dirty = False

    def load_from_csv(self, file_path):
        """Loads CSV data into memory and returns True if it's a full project, False if just raw script."""
        self.clips.clear()
        self.filepath = file_path
        is_full_project = False
        
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) > 0 and row[0] == "*PROJECT_META*":
                    is_full_project = True
                    if len(row) > 1 and row[1] and row[1] != "None": self.audio_path = row[1]
                    if len(row) > 2: self.aspect_ratio = row[2]
                    if len(row) > 3: self.strict_cuts = (row[3].lower() == 'true')
                    if len(row) > 4: self.fps = row[4]
                    if len(row) > 5: self.whisper_model = row[5]
                    if len(row) > 6:
                        try: self.gap_threshold = float(row[6])
                        except ValueError: pass
                    continue

                if len(row) >= 2:
                    clip = Clip()
                    
                    # Core Media Loading
                    if row[0] in ["Image", "Video"]:
                        clip.media_type = row[0].strip()
                        clip.media_path = row[1].strip()
                        clip.script_text = row[2].strip()
                    else:
                        clip.media_path = row[0].strip()
                        clip.script_text = row[1].strip()
                        clip.media_type = "Video" if any(clip.media_path.lower().endswith(ext) for ext in ['.mp4', '.mov', '.avi', '.mkv', '.ts']) else "Image"

                    # Timings
                    try:
                        st_str = row[3].strip() if len(row) > 3 else "Unsynced"
                        clip.start_time = float(st_str.replace('s', '')) if st_str != "Unsynced" else 0.0
                    except ValueError: clip.start_time = 0.0
                    
                    try:
                        et_str = row[4].strip() if len(row) > 4 else "Unsynced"
                        clip.end_time = float(et_str.replace('s', '')) if et_str != "Unsynced" else 0.0
                    except ValueError: clip.end_time = 0.0

                    # Effects
                    clip.animation = row[5].strip() if len(row) > 5 else "Random"
                    clip.transition = row[6].strip() if len(row) > 6 else "Random"

                    # Trim Settings
                    try: clip.trim_start = float(row[7]) if len(row) > 7 and row[7] else 0.0
                    except ValueError: clip.trim_start = 0.0

                    try: clip.trim_end = float(row[8]) if len(row) > 8 and row[8] else 0.0
                    except ValueError: clip.trim_end = 0.0

                    # Caption Layout
                    try: clip.caption_x = float(row[9]) if len(row) > 9 and row[9] else 0.5
                    except ValueError: clip.caption_x = 0.5

                    try: clip.caption_y = float(row[10]) if len(row) > 10 and row[10] else None
                    except ValueError: clip.caption_y = None

                    try: clip.caption_scale = float(row[11]) if len(row) > 11 and row[11] else 1.0
                    except ValueError: clip.caption_scale = 1.0

                    try: clip.caption_rot = float(row[12]) if len(row) > 12 and row[12] else 0.0
                    except ValueError: clip.caption_rot = 0.0
                    
                    self.clips.append(clip)
                    
        self.is_dirty = False
        return is_full_project
        
    def save_to_csv(self, file_path):
        """Serializes current memory state safely to CSV."""
        self.filepath = file_path
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            metadata = [
                "*PROJECT_META*", str(self.audio_path) if self.audio_path else "",
                self.aspect_ratio, str(self.strict_cuts),
                self.fps, self.whisper_model, str(self.gap_threshold)
            ]
            writer.writerow(metadata)

            for clip in self.clips:
                st_str = f"{clip.start_time:.2f}s" if clip.is_synced else "Unsynced"
                et_str = f"{clip.end_time:.2f}s" if clip.is_synced else "Unsynced"
                
                writer.writerow([
                    clip.media_type, clip.media_path, clip.script_text,
                    st_str, et_str, clip.animation, clip.transition,
                    clip.trim_start, clip.trim_end, clip.caption_x,
                    clip.caption_y if clip.caption_y is not None else "",
                    clip.caption_scale, clip.caption_rot
                ])
        self.is_dirty = False