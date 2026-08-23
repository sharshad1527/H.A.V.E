"""Full-control verification: create project -> attach audio -> mutate clips ->
set effects -> sync-check state -> render. Zero GUI involvement."""
import os, sys, subprocess
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_fixtures")
os.makedirs(D, exist_ok=True)
def _ensure_fixtures():
    try:
        import imageio_ffmpeg
        ff = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ff = "ffmpeg"
    from PIL import Image
    for name, color in (("img1.png", (200, 40, 40)), ("img2.png", (40, 40, 200))):
        fp = os.path.join(D, name)
        if not os.path.exists(fp):
            Image.new("RGB", (1920, 1080), color).save(fp)
    vo = os.path.join(D, "voiceover.mp3")
    if not os.path.exists(vo):
        subprocess.run([ff, "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
                        "-c:a", "libmp3lame", vo], check=True, capture_output=True)

from services import ProjectService, SyncService, RenderService
from models.project_model import Clip

P = os.path.join(D, "fullctl.csv")
if os.path.exists(P):
    os.remove(P)

# 1. Create from scratch WITH audio attached
p = ProjectService.create_project(P, audio_path=os.path.join(D, "voiceover.mp3"),
                                  aspect_ratio="16:9 (Horizontal)", fps="60 FPS")
assert p.audio_path.endswith("voiceover.mp3")
print("1. create_project with audio OK")

# 2. set_project_settings: swap model + gap + strict cuts
ProjectService.set_project_settings(p, whisper_model="small", gap_threshold=0.8,
                                    strict_cuts=False)
assert p.whisper_model == "Small" and p.gap_threshold == 0.8 and p.strict_cuts is False
print("2. set_project_settings OK (model/gap/strict)")

# 3. add_clip x3 (auto type detect), insert at position
ProjectService.add_clip(p, os.path.join(D, "img1.png"), "line one")
ProjectService.add_clip(p, os.path.join(D, "img2.png"), "line two")
added = ProjectService.add_clip(p, os.path.join(D, "img1.png"), "middle!", position=1)
assert added["index"] == 1 and len(p.clips) == 3
print("3. add_clip (append + insert-at) OK")

# 4. update_clip_media / text / timing / move / remove
ProjectService.update_clip_media(p, 0, os.path.join(D, "img2.png"))
assert p.clips[0].media_path.endswith("img2.png") and p.clips[0].media_type == "Image"
ProjectService.update_clip_text(p, 0, "changed line")
assert p.clips[0].script_text == "changed line"
ProjectService.update_clip_timing(p, 0, 0.0, 2.5)
ProjectService.update_clip_timing(p, 2, 2.5, 6.0)
ProjectService.move_clip(p, 1, 2)   # middle clip to end
assert p.clips[2].script_text == "middle!"
ProjectService.remove_clip(p, 1)
assert len(p.clips) == 2
print("4. media/text/timing/move/remove OK")

# 5. set_clip_effect validation + application
try:
    ProjectService.set_clip_effect(p, 0, animation="DoesNotExist")
    raise AssertionError("should have raised")
except ValueError as e:
    pass
ProjectService.set_clip_effect(p, 0, animation="Ken Burns", transition="Slide Left")
ProjectService.set_clip_effect(p, 1, transition="Random")
assert p.clips[0].animation == "Ken Burns" and p.clips[0].transition == "Slide Left"
print("5. set_clip_effect (valid + invalid rejected) OK")

# 6. caption layout
ProjectService.set_caption_layout(p, 0, y=0.85, scale=1.2, rotation=3.0, show=False)
c = p.clips[0]
assert c.caption_y == 0.85 and c.caption_scale == 1.2 and c.caption_rot == 3.0 and c.show_caption is False
try:
    ProjectService.set_caption_layout(p, 0, y=7.0)
    raise AssertionError("should have raised")
except ValueError:
    pass
print("6. set_caption_layout (bounds enforced) OK")

# 7. save/reload round-trip preserves everything
ProjectService.save_project(p)
p2 = ProjectService.load_project(P)
assert p2.audio_path.endswith("voiceover.mp3")
assert p2.whisper_model == "Small" and abs(p2.gap_threshold - 0.8) < 1e-9
assert p2.clips[0].animation == "Ken Burns"
rd = SyncService.build_render_data(p2)
# clip 1 ("middle!") is unsynced -> excluded from render data; clip 0 keeps full duration
assert len(rd) == 1 and rd[0]["caption_y"] == 0.85, rd
assert abs(rd[0]["end_time"] - rd[0]["start_time"] - 2.7) < 0.31, rd
print("7. CSV round-trip preserves full state OK")

# 8. render the mutated project end-to-end
total = RenderService.render(p2, os.path.join(D, "fullctl_out.mp4"))
print(f"8. RenderService.render of mutated project OK — {total:.1f}s")
