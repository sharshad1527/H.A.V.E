"""Headless end-to-end render test — no Qt, no PySide6 import.

Bootstraps its own fixtures (2 images + sine voiceover) via ffmpeg.
Run:  python tests/test_render_headless.py
"""
import sys, os, subprocess
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_fixtures")
os.makedirs(D, exist_ok=True)
IMG1, IMG2, VO = (os.path.join(D, n) for n in ("img1.png", "img2.png", "voiceover.mp3"))

def _ensure_fixtures():
    try:
        import imageio_ffmpeg
        ff = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ff = "ffmpeg"
    if not os.path.exists(IMG1):
        subprocess.run([ff, "-y", "-f", "lavfi", "-i", "color=c=red:s=1920x1080:d=1",
                        "-frames:v", "1", IMG1], check=True, capture_output=True)
    if not os.path.exists(IMG2):
        subprocess.run([ff, "-y", "-f", "lavfi", "-i", "color=c=blue:s=1920x1080:d=1",
                        "-frames:v", "1", IMG2], check=True, capture_output=True)
    if not os.path.exists(VO):
        subprocess.run([ff, "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
                        "-c:a", "libmp3lame", VO], check=True, capture_output=True)

_ensure_fixtures()

# Guard: fail loudly if anything drags Qt in
for mod in list(sys.modules):
    if "PySide" in mod or "Qt" in mod.split(".")[0]:
        raise RuntimeError(f"Qt module loaded: {mod}")

from core.video_renderer import VideoRenderer

timeline = [
    {"image": IMG1, "type": "Image",
     "start_time": 0.0, "end_time": 3.0,
     "words": [{"word": "TEST", "start": 0.5, "end": 1.5}],
     "animation": "Zoom In", "transition": "Fade"},
    {"image": IMG2, "type": "Image",
     "start_time": 3.0, "end_time": 6.0,
     "words": [{"word": "DONE", "start": 3.5, "end": 4.5}],
     "animation": "Zoom Out", "transition": "Slide Left"},
]

r = VideoRenderer()
total = r.render_project(
    timeline, VO, os.path.join(D, "out.mp4"),
    "16:9", strict_cuts=False, gap_threshold=1.0,
    progress_callback=lambda m: print("[progress]", m),
)
print("RENDER OK — total:", round(total, 2), "s")
