import os
import subprocess
import glob
import math
from collections import deque
import cv2
import numpy as np
import re
from PIL import Image, ImageDraw, ImageFont, ImageFilter

def get_font_path():
    cwd = os.path.dirname(os.path.abspath(__file__))
    font_dir = os.path.join(cwd, "font")
    if os.path.exists(font_dir):
        for root, _, files in os.walk(font_dir):
            for file in files:
                if file.lower().endswith(".ttf") or file.lower().endswith(".otf"):
                    return os.path.join(root, file)
                if "bold" in file.lower() or "black" in file.lower() or "heavy" in file.lower():
                    return os.path.join(root, file)
    return "arial.ttf"

def group_words(words, max_chars=25):
    """Group words into chunks, completely stripping out hyphens/dashes, and converting to UPPERCASE."""
    chunks = []
    current_chunk = []
    current_len = 0
    
    for word_info in words:
        # Strip all dash variants out, but leave ? and , intact
        cleaned_text = re.sub(r'[—\-–_~]', '', word_info['word']).strip()
        
        if not cleaned_text:
            continue # If the word was entirely just a dash, completely skip it!
            
        word_info['word'] = cleaned_text.upper() # ALL CAPS
        w_len = len(word_info['word'])
        
        if (current_len + w_len > max_chars and current_chunk) or len(current_chunk) >= 5:
            chunks.append(current_chunk)
            current_chunk = [word_info]
            current_len = w_len + 1  
        else:
            current_chunk.append(word_info)
            current_len += w_len + 1
            
    if current_chunk:
        chunks.append(current_chunk)
        
    lines = []
    for chunk in chunks:
        if not chunk: continue
        line_text = " ".join([w['word'] for w in chunk])
        start_time = chunk[0]['start']
        end_time = chunk[-1]['end']
        lines.append({
            "text": line_text,
            "start": start_time,
            "end": end_time,
            "words": chunk
        })
    return lines

def render_caption_frame(width, height, current_time, lines, 
                         pos_x=0.5, pos_y=0.90, scale=1.0, rotation=0.0,
                         history=None, bg_color=(0, 0, 0, 0), 
                         text_color=(255, 255, 255, 255), 
                         highlight_color=(247, 112, 0, 255),
                         base_color=(0, 0, 0, 0)):
    """PRESERVED FOR REAL-TIME GUI PREVIEW: Renders a single Pillow frame perfectly matching the .ass styling."""
    try:
        width = int(width)
        height = int(height)
        scale = float(scale) if not isinstance(scale, dict) else 1.0
        pos_x = float(pos_x) if not isinstance(pos_x, dict) else 0.5
        pos_y = float(pos_y) if not isinstance(pos_y, dict) else 0.90
        rotation = float(rotation) if not isinstance(rotation, dict) else 0.0
        current_time = float(current_time)
    except (TypeError, ValueError):
        scale, pos_x, pos_y, rotation = 1.0, 0.5, 0.90, 0.0

    if history is None:
        history = deque(maxlen=5)
        
    active_line = None
    for i, line in enumerate(lines):
        # End exactly when the next one begins to avoid overlap
        if i < len(lines) - 1:
            line_end = min(line["end"] + 0.1, lines[i+1]["start"])
        else:
            line_end = line["end"] + 0.1
            
        if line["start"] <= current_time < line_end:
            active_line = line
            break
            
    if not active_line and lines:
        last_line = lines[-1]
        if last_line["start"] <= current_time <= (last_line["end"] + 0.5):
            active_line = last_line

    img = Image.new('RGBA', (width, height), base_color)
    if not active_line:
        return img, history
        
    draw = ImageDraw.Draw(img)
    font_path = get_font_path()
    
    base_font_size = max(24, int(width * 0.04 * scale))
    try:
        font = ImageFont.truetype(font_path, base_font_size)
    except:
        font = ImageFont.load_default()
        
    line_words = active_line.get("words", [])
    if not line_words:
        return img, history
        
    space_w = draw.textbbox((0, 0), " ", font=font)[2]
    total_text_width = 0
    word_widths = []
    
    for w in line_words:
        w_bbox = draw.textbbox((0, 0), w["word"], font=font)
        w_width = w_bbox[2] - w_bbox[0]
        word_widths.append(w_width)
        total_text_width += w_width
        
    total_text_width += space_w * (len(line_words) - 1)
    
    text_h = draw.textbbox((0, 0), "AY", font=font)[3] - draw.textbbox((0, 0), "AY", font=font)[1]
    bg_pad_x = int(base_font_size * 0.8)
    bg_pad_y = int(base_font_size * 1.8)
    
    canvas_w = int(total_text_width + bg_pad_x * 2)
    canvas_h = int(text_h + bg_pad_y * 2)
    
    temp_img = Image.new('RGBA', (canvas_w, canvas_h), (0, 0, 0, 0))
    temp_draw = ImageDraw.Draw(temp_img)
    
    shadow_layer = Image.new('RGBA', (canvas_w, canvas_h), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow_layer)
    
    # MATCHING ASS \bord6 \shad5 \blur5
    # Text border is 6% of font size. Shadow offset is 5%. Blur is 5%.
    text_stroke = max(2, int(base_font_size * 0.06))
    shadow_offset = max(2, int(base_font_size * 0.05))
    shadow_stroke = text_stroke
    blur_radius = max(2, int(base_font_size * 0.05))

    current_x = bg_pad_x
    for i, w in enumerate(line_words):
        shadow_draw.text((current_x + shadow_offset, bg_pad_y + shadow_offset), 
                         w["word"], font=font, fill=(0, 0, 0, 255),
                         stroke_width=shadow_stroke, stroke_fill=(0, 0, 0, 255))
        current_x += word_widths[i] + space_w
        
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    
    # 2 pastes is perfect to match ASS styling. 6 makes it too bulky.
    for _ in range(2):  
        temp_img.paste(shadow_layer, (0, 0), shadow_layer)
    
    current_x = bg_pad_x
    for i, w in enumerate(line_words):
        
        if i < len(line_words) - 1:
            next_start = line_words[i+1]["start"]
            is_active = w["start"] <= current_time < next_start
        else:
            is_active = w["start"] <= current_time <= (w["end"] + 0.1)

        current_color = highlight_color if is_active else text_color
                   
        temp_draw.text((current_x, bg_pad_y), w["word"], font=font, fill=current_color,
                       stroke_width=text_stroke, stroke_fill=(0, 0, 0, 255))
                   
        current_x += word_widths[i] + space_w
        
    if rotation != 0.0:
        temp_img = temp_img.rotate(-rotation, resample=Image.BICUBIC, expand=True) 
            
    center_x = int(width * pos_x)
    center_y = int(height * pos_y)
    paste_x = center_x - temp_img.width // 2
    paste_y = center_y - temp_img.height // 2
    
    img.paste(temp_img, (paste_x, paste_y), temp_img)
    return img, history


def create_ass_file(timeline_data, width, height, output_path):
    """
    NEW PIPELINE: Parses the timeline and writes a highly optimized .ass subtitle file. 
    This bypasses Python frame-drawing completely, allowing FFmpeg to burn text instantly.
    """
    all_lines = []
    
    for item in timeline_data:
        words = item.get("words", [])
        if not words or len(words) == 0:
            txt = item.get("script_line", "")
            if not txt or txt == "Unsynced" or txt == "Type new split line here...":
                continue
            st = item.get("start_time", 0.0)
            et = item.get("end_time", st + 5.0)
            
            cleaned_txt = re.sub(r'[—\-–_~]', ' ', txt)
            raw_words = cleaned_txt.split()
            if not raw_words:
                continue
            
            time_per_word = (et - st) / len(raw_words)
            words = []
            for i, w in enumerate(raw_words):
                words.append({
                    "word": w,
                    "start": st + (i * time_per_word),
                    "end": st + ((i + 1) * time_per_word)
                })

        c_x = item.get("caption_x", 0.5)
        c_y = item.get("caption_y", 0.90) 
        c_scale = item.get("caption_scale", 1.0)
        c_rot = item.get("caption_rot", 0.0)
        
        item_lines = group_words(words, max_chars=25)
        for line in item_lines:
            line["c_x"] = c_x
            line["c_y"] = c_y
            line["c_scale"] = c_scale
            line["c_rot"] = c_rot
            all_lines.append(line)
            
    all_lines.sort(key=lambda x: x["start"])
    
    font_path = get_font_path()
    try:
        font = ImageFont.truetype(font_path, 24)
        font_family = font.getname()[0]
    except:
        font_family = "Arial"

    ass_content = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        # \an5 (alignment 5) ensures the text center point is exactly on our coordinates
        f"Style: Default,{font_family},100,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,5,10,5,10,10,10,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
    ]

    def format_time(seconds):
        if seconds < 0: seconds = 0
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = seconds % 60
        return f"{h:01d}:{m:02d}:{s:05.2f}"

    for i, line in enumerate(all_lines):
        
        l_start = line["start"] # Removed the -0.1 offset to prevent overlap
        
        if i < len(all_lines) - 1:
            # End EXACTLY when the next line begins to avoid them sticking together
            l_end = min(line["end"] + 0.1, all_lines[i+1]["start"])
        else:
            l_end = line["end"] + 0.1
        
        pos_x = int(width * line["c_x"])
        pos_y = int(height * line["c_y"])
        c_rot = line["c_rot"]
        c_scale = line["c_scale"]
        
        # In ASS, positive \frz rotates counter-clockwise. Our UI expects clockwise, so we negate it.
        rot_tag = f"\\frz{-c_rot}" if c_rot != 0 else ""
        font_size = int(max(24, width * 0.04 * c_scale))
        
        # \\bord6\\shad5\\blur5 perfectly spreads a dark glow evenly around the text
        text_prefix = f"{{\\pos({pos_x},{pos_y})\\fs{font_size}{rot_tag}\\bord6\\shad5\\blur5}}"
        
        line_words = line.get("words", [])
        if not line_words: continue

        # Time Slice 1: Line Start -> First Word (All White)
        A_0 = line_words[0]["start"]
        if A_0 > l_start:
            plain_text = " ".join(w["word"] for w in line_words)
            ass_content.append(f"Dialogue: 0,{format_time(l_start)},{format_time(A_0)},Default,,0,0,0,,{text_prefix}{plain_text}")

        # Time Slice 2: Word-by-Word Orange Highlight Slicing
        for w_idx, w in enumerate(line_words):
            A_i = max(w["start"], l_start) # Clamp start time
            
            if w_idx < len(line_words) - 1:
                D_i = line_words[w_idx+1]["start"]
            else:
                D_i = min(w["end"] + 0.1, l_end)
            
            # Prevent negative or zero duration slices
            if A_i >= D_i:
                continue

            display_words = []
            for j, curr_w in enumerate(line_words):
                if j == w_idx:
                    # Hex BGR format for Orange: 0070F7
                    display_words.append(f"{{\\c&H0070F7&}}{curr_w['word']}{{\\c&HFFFFFF&}}")
                else:
                    display_words.append(curr_w['word'])
                    
            text_content = text_prefix + " ".join(display_words)
            ass_content.append(f"Dialogue: 0,{format_time(A_i)},{format_time(D_i)},Default,,0,0,0,,{text_content}")

        # Time Slice 3: Last Word -> Line End (All White)
        D_n = min(line_words[-1]["end"] + 0.1, l_end)
        if D_n < l_end:
            plain_text = " ".join(w["word"] for w in line_words)
            ass_content.append(f"Dialogue: 0,{format_time(D_n)},{format_time(l_end)},Default,,0,0,0,,{text_prefix}{plain_text}")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(ass_content))
        
    print(f"Generated ultra-fast native .ass subtitle file: {output_path}")
    return output_path