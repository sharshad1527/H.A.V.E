import whisper
import string
import re
import unicodedata
import torch

# Use rapidfuzz for ~10-100x faster fuzzy matching than difflib
try:
    from rapidfuzz import fuzz
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    import difflib
    RAPIDFUZZ_AVAILABLE = False


# Build a comprehensive punctuation removal table ONCE
_PUNCT_CHARS = set(string.punctuation)
for c in range(0x10000):
    ch = chr(c)
    if unicodedata.category(ch).startswith('P') or unicodedata.category(ch).startswith('S'):
        _PUNCT_CHARS.add(ch)
_PUNCT_CHARS.update('…—–''""•·«»‹›¿¡')
_STRIP_TABLE = str.maketrans('', '', ''.join(_PUNCT_CHARS))


def _clean_text(text):
    """Normalize text for matching: lowercase, strip ALL punctuation (including unicode), collapse whitespace."""
    t = text.lower().translate(_STRIP_TABLE)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


class AudioSyncEngine:
    def __init__(self, model_size="base"):
        print(f"Loading Whisper model '{model_size}'...")
        self.model = whisper.load_model(model_size)
        self.model_size = model_size
        self.use_fp16 = torch.cuda.is_available()
        print(f"Model loaded successfully. (fp16={'enabled' if self.use_fp16 else 'disabled - CPU mode'})")

    def transcribe_audio(self, audio_path):
        print(f"Transcribing audio from: {audio_path}")
        result = self.model.transcribe(audio_path, fp16=self.use_fp16, word_timestamps=True)
        
        all_words = []
        for segment in result.get("segments", []):
            words = segment.get("words", [])
            seg_start = segment["start"]
            seg_end = segment["end"]
            
            needs_proportional_fallback = False
            if not words:
                needs_proportional_fallback = True
            elif len(words) > 1:
                first_word_duration = words[0]["end"] - words[0]["start"]
                segment_duration = seg_end - seg_start
                if first_word_duration >= (segment_duration - 0.2):
                    needs_proportional_fallback = True
            
            if needs_proportional_fallback:
                raw_words = segment.get("text", "").split()
                if not raw_words: continue
                time_per_word = (seg_end - seg_start) / len(raw_words)
                for i, w in enumerate(raw_words):
                    clean_w = _clean_text(w)
                    if clean_w:
                        all_words.append({
                            "word": clean_w,
                            "raw_word": w,
                            "start": seg_start + (i * time_per_word),
                            "end": seg_start + ((i + 1) * time_per_word)
                        })
            else:
                for word_data in words:
                    clean_w = _clean_text(word_data["word"])
                    if clean_w:
                        all_words.append({
                            "word": clean_w,
                            "raw_word": word_data["word"],
                            "start": word_data["start"],
                            "end": word_data["end"]
                        })
        return all_words

    def _similarity(self, a, b):
        """Fast similarity score (0-1.0). Uses rapidfuzz if available, else difflib."""
        if RAPIDFUZZ_AVAILABLE:
            return fuzz.ratio(a, b) / 100.0  
        else:
            return difflib.SequenceMatcher(None, a, b).ratio()

    def _get_window_sizes(self, base_size):
        """Return a list of window sizes to test (handles Whisper adding/dropping short filler words)."""
        sizes = [base_size]
        variance = max(1, min(4, int(base_size * 0.3)))
        for i in range(1, variance + 1):
            if base_size - i > 0:
                sizes.append(base_size - i)
            sizes.append(base_size + i)
        return sizes

    def _map_words(self, raw_script_text, whisper_words):
        """Maps user's raw script text perfectly to the detected Whisper timing boundaries."""
        # Replace dashes/hyphens with spaces so they are cleanly split and ignored
        # This prevents punctuation from stealing spoken timestamps and throwing off sync!
        cleaned_script_text = re.sub(r'[—\-–_~]', ' ', raw_script_text)
        raw_script_words = cleaned_script_text.split()
        
        line_words = []
        if whisper_words and raw_script_words:
            for w_idx, s_word in enumerate(raw_script_words):
                ratio = w_idx / len(raw_script_words)
                c_idx = int(ratio * len(whisper_words))
                
                w_start = whisper_words[c_idx]['start']
                if c_idx < len(whisper_words) - 1:
                    w_end = whisper_words[c_idx + 1]['start']
                else:
                    w_end = whisper_words[c_idx]['end']
                
                if w_end <= w_start: w_end = w_start + 0.1
                
                line_words.append({
                    "word": s_word,
                    "start": w_start,
                    "end": w_end
                })
        return line_words

    def match_script_to_audio(self, script_data, all_words):
        """Two-pass anchoring algorithm."""
        word_strings = [w["word"] for w in all_words]
        total_words = len(all_words)
        
        results = [None] * len(script_data)
        
        def _bounded_search(target_text, search_start, search_end, early_exit_score=0.92):
            target_words = target_text.split()
            if not target_words: return 0, 0, 0
            
            w_sizes = self._get_window_sizes(len(target_words))
            best_score, best_start, best_end = 0, 0, 0
            
            for ws in w_sizes:
                if ws < 1: continue
                range_end = min(search_end, total_words) - ws + 1
                if range_end <= search_start: continue
                
                for i in range(search_start, range_end):
                    chunk_text = " ".join(word_strings[i : i + ws])
                    score = self._similarity(target_text, chunk_text)
                    if score > best_score:
                        best_score, best_start, best_end = score, i, i + ws - 1
                    if score > early_exit_score:
                        return best_score, best_start, best_end
                        
            return best_score, best_start, best_end

        # ==========================================
        # PASS 1: FIND ANCHORS
        # ==========================================
        search_start_idx = 0
        for i, line_data in enumerate(script_data):
            target_text = _clean_text(line_data['text'])
            if not target_text: continue
            
            target_words = target_text.split()
            ws_base = len(target_words)
            
            local_end = min(search_start_idx + max(ws_base * 4, 300), total_words)
            score, start_idx, end_idx = _bounded_search(target_text, search_start_idx, local_end)
            
            if score < 0.85:
                wide_end = min(search_start_idx + 2000, total_words)
                score, start_idx, end_idx = _bounded_search(target_text, local_end, wide_end)

            if score >= 0.85:
                safe_end_idx = min(end_idx, total_words - 1)
                st = all_words[start_idx]['start']
                en = all_words[safe_end_idx]['end']
                if en <= st: en = st + 0.1
                
                mapped_words = self._map_words(line_data['text'], all_words[start_idx : safe_end_idx + 1])
                
                results[i] = {
                    "image": line_data['image'],
                    "script_line": line_data['text'],
                    "start_time": st,
                    "end_time": en,
                    "confidence": round(score * 100, 2),
                    "word_start_idx": start_idx,
                    "word_end_idx": safe_end_idx,
                    "is_anchor": True,
                    "words": mapped_words
                }
                search_start_idx = safe_end_idx + 1

        # ==========================================
        # PASS 2: FILL GAPS USING ANCHOR BOUNDARIES
        # ==========================================
        for i, res in enumerate(results):
            if res is not None: continue 
            
            target_text = _clean_text(script_data[i]['text'])
            target_words = target_text.split()
            if not target_words: 
                results[i] = {
                    "image": script_data[i]['image'],
                    "script_line": script_data[i]['text'],
                    "start_time": 0.0, "end_time": 0.0, "confidence": 0.0,
                    "word_start_idx": 0, "word_end_idx": 0, "is_anchor": False, "words": []
                }
                continue

            prev_anchor_end_idx = 0
            for j in range(i - 1, -1, -1):
                if results[j] and results[j].get("is_anchor"):
                    prev_anchor_end_idx = results[j]["word_end_idx"] + 1
                    break
                    
            next_anchor_start_idx = total_words
            for j in range(i + 1, len(script_data)):
                if results[j] and results[j].get("is_anchor"):
                    next_anchor_start_idx = results[j]["word_start_idx"]
                    break

            bound_start = prev_anchor_end_idx
            bound_end = next_anchor_start_idx
            
            min_required_words = max(1, len(target_words) // 2)
            if bound_end - bound_start < min_required_words:
                results[i] = {
                    "image": script_data[i]['image'],
                    "script_line": script_data[i]['text'],
                    "start_time": 0.0, "end_time": 0.0, "confidence": 0.0,
                    "word_start_idx": 0, "word_end_idx": 0, "is_anchor": False, "words": []
                }
                continue

            score, start_idx, end_idx = _bounded_search(target_text, bound_start, bound_end)
            
            if score >= 0.15:
                safe_end_idx = min(end_idx, total_words - 1)
                st = all_words[start_idx]['start']
                en = all_words[safe_end_idx]['end']
                if en <= st: en = st + 0.1
                
                mapped_words = self._map_words(script_data[i]['text'], all_words[start_idx : safe_end_idx + 1])
                
                results[i] = {
                    "image": script_data[i]['image'],
                    "script_line": script_data[i]['text'],
                    "start_time": st,
                    "end_time": en,
                    "confidence": round(score * 100, 2),
                    "word_start_idx": start_idx,
                    "word_end_idx": safe_end_idx,
                    "is_anchor": False,
                    "words": mapped_words
                }
            else:
                results[i] = {
                    "image": script_data[i]['image'],
                    "script_line": script_data[i]['text'],
                    "start_time": 0.0, "end_time": 0.0, "confidence": 0.0,
                    "word_start_idx": 0, "word_end_idx": 0, "is_anchor": False, "words": []
                }
        
        for r in results:
            if r:
                r.pop("word_start_idx", None)
                r.pop("word_end_idx", None)
                r.pop("is_anchor", None)
                
        final_timeline = [r if r is not None else {
            "image": script_data[i]['image'],
            "script_line": script_data[i]['text'],
            "start_time": 0.0, "end_time": 0.0, "confidence": 0.0, "words": []
        } for i, r in enumerate(results)]

        return final_timeline