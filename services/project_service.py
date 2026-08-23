"""ProjectService — load/save/inspect H.A.V.E projects without any Qt dependency.

Thin, headless wrapper around models.project_model.ProjectState. This is the
single source of truth for CLI and MCP layers; the GUI may use it too.
"""
import os
from models.project_model import ProjectState


class ProjectService:
    """Stateless operations on project files."""

    @staticmethod
    def new_project() -> ProjectState:
        return ProjectState()

    # Valid effect values (must match core/video_renderer.py motion presets
    # and transition handling; "Random" lets the renderer pick weighted-random)
    VALID_ANIMATIONS = ["Random", "Zoom In", "Zoom Out", "Camera Pan Left",
                        "Camera Pan Right", "Pan Left", "Pan Right",
                        "Pendulum", "Ken Burns"]
    VALID_TRANSITIONS = ["Random", "Cut", "Fade", "Mix", "Bubble Blur",
                         "Slide Left", "Slide Right", "Swipe Left",
                         "Swipe Right", "Pull In", "Pull Out"]

    @staticmethod
    def create_project(path: str, audio_path: str = None,
                       aspect_ratio: str = "16:9 (Horizontal)", fps: str = "60 FPS",
                       whisper_model: str = "Base") -> ProjectState:
        """Create a brand-new empty project CSV with a *PROJECT_META* header."""
        if os.path.exists(path):
            raise FileExistsError(f"Project already exists: {path}")
        if audio_path is not None and not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        project = ProjectState()
        project.audio_path = audio_path
        project.aspect_ratio = aspect_ratio
        project.fps = fps
        project.whisper_model = whisper_model
        project.save_to_csv(path)
        project.filepath = path
        return project

    @staticmethod
    def set_project_settings(project: ProjectState, audio_path=None,
                             aspect_ratio=None, fps=None, whisper_model=None,
                             strict_cuts=None, gap_threshold=None,
                             vignette=None, disable_all_captions=None) -> dict:
        """Update any subset of global project settings. Returns updated state."""
        if audio_path is not None:
            if not os.path.exists(audio_path):
                raise FileNotFoundError(f"Audio file not found: {audio_path}")
            project.audio_path = audio_path
        if aspect_ratio is not None:
            ar = aspect_ratio.strip()
            if "16:9" not in ar and "9:16" not in ar and "1:1" not in ar:
                raise ValueError(f"aspect_ratio must contain 16:9, 9:16 or 1:1 — got: {ar}")
            project.aspect_ratio = ar
        if fps is not None:
            fps_s = str(fps)
            if "30" not in fps_s and "60" not in fps_s:
                raise ValueError(f"fps must mention 30 or 60 — got: {fps_s}")
            project.fps = fps_s
        if whisper_model is not None:
            m = whisper_model.strip().capitalize()
            if m not in ("Tiny", "Base", "Small"):
                raise ValueError(f"whisper_model must be Tiny/Base/Small — got: {whisper_model}")
            project.whisper_model = m
        if strict_cuts is not None:
            project.strict_cuts = bool(strict_cuts)
        if gap_threshold is not None:
            g = float(gap_threshold)
            if g < 0:
                raise ValueError("gap_threshold must be >= 0")
            project.gap_threshold = g
        if vignette is not None:
            project.vignette = bool(vignette)
        if disable_all_captions is not None:
            project.disable_all_captions = bool(disable_all_captions)
        project.is_dirty = True
        return ProjectService.get_project_state(project)

    @staticmethod
    def add_clip(project: ProjectState, media_path: str, script_text: str = "",
                 media_type: str = None, position: int = None) -> dict:
        """Append (or insert at position) a new clip to the timeline."""
        from models.project_model import Clip
        media_path = media_path.strip()
        if not os.path.exists(media_path) and media_path != "BLANK_IMAGE":
            raise FileNotFoundError(f"Media file not found: {media_path}")
        clip = Clip()
        clip.media_path = media_path
        clip.script_text = script_text or ""
        if media_type is None:
            ext = os.path.splitext(media_path)[1].lower()
            clip.media_type = "Video" if ext in ('.mp4', '.mov', '.avi', '.mkv', '.ts') else "Image"
        else:
            mt = media_type.strip().capitalize()
            if mt not in ("Image", "Video"):
                raise ValueError(f"media_type must be Image/Video — got: {media_type}")
            clip.media_type = mt
        n = len(project.clips)
        pos = n if position is None else max(0, min(int(position), n))
        project.clips.insert(pos, clip)
        project.is_dirty = True
        return ProjectService.get_clip(clip, pos)

    @staticmethod
    def remove_clip(project: ProjectState, index: int) -> list:
        """Delete a clip from the timeline. Returns remaining clips."""
        n = len(project.clips)
        if index < 0 or index >= n:
            raise IndexError(f"Clip index {index} out of range (0..{n-1}).")
        project.clips.pop(index)
        project.is_dirty = True
        return ProjectService.list_clips(project)

    @staticmethod
    def update_clip_media(project: ProjectState, index: int, media_path: str,
                          media_type: str = None) -> dict:
        """Swap the media file of an existing clip."""
        if index < 0 or index >= len(project.clips):
            raise IndexError(f"Clip index {index} out of range (0..{len(project.clips)-1}).")
        media_path = media_path.strip()
        if not os.path.exists(media_path) and media_path != "BLANK_IMAGE":
            raise FileNotFoundError(f"Media file not found: {media_path}")
        clip = project.clips[index]
        clip.media_path = media_path
        if media_type is not None:
            mt = media_type.strip().capitalize()
            if mt not in ("Image", "Video"):
                raise ValueError(f"media_type must be Image/Video — got: {media_type}")
            clip.media_type = mt
        else:
            ext = os.path.splitext(media_path)[1].lower()
            clip.media_type = "Video" if ext in ('.mp4', '.mov', '.avi', '.mkv', '.ts') else "Image"
        project.is_dirty = True
        return ProjectService.get_clip(clip, index)

    @staticmethod
    def update_clip_text(project: ProjectState, index: int, script_text: str) -> dict:
        """Change the script line of a clip (the text Whisper syncs against)."""
        if index < 0 or index >= len(project.clips):
            raise IndexError(f"Clip index {index} out of range (0..{len(project.clips)-1}).")
        clip = project.clips[index]
        clip.script_text = script_text
        project.is_dirty = True
        return ProjectService.get_clip(clip, index)

    @staticmethod
    def set_clip_effect(project: ProjectState, index: int,
                        animation: str = None, transition: str = None) -> dict:
        """Set animation and/or transition for one clip ("Random" allowed)."""
        if index < 0 or index >= len(project.clips):
            raise IndexError(f"Clip index {index} out of range (0..{len(project.clips)-1}).")
        clip = project.clips[index]
        if animation is not None:
            a = animation.strip()
            if a not in ProjectService.VALID_ANIMATIONS:
                raise ValueError(f"animation '{a}' not valid. Valid: {ProjectService.VALID_ANIMATIONS}")
            clip.animation = a
        if transition is not None:
            t = transition.strip()
            if t not in ProjectService.VALID_TRANSITIONS:
                raise ValueError(f"transition '{t}' not valid. Valid: {ProjectService.VALID_TRANSITIONS}")
            clip.transition = t
        project.is_dirty = True
        return ProjectService.get_clip(clip, index)

    @staticmethod
    def set_caption_layout(project: ProjectState, index: int, x: float = None,
                           y: float = None, scale: float = None,
                           rotation: float = None, show: bool = None) -> dict:
        """Adjust caption placement/style for one clip."""
        if index < 0 or index >= len(project.clips):
            raise IndexError(f"Clip index {index} out of range (0..{len(project.clips)-1}).")
        clip = project.clips[index]
        if x is not None:
            if not 0.0 <= float(x) <= 1.0:
                raise ValueError("caption x must be 0.0..1.0 (fraction of width)")
            clip.caption_x = float(x)
        if y is not None:
            if not 0.0 <= float(y) <= 1.0:
                raise ValueError("caption y must be 0.0..1.0 (fraction of height)")
            clip.caption_y = float(y)
        if scale is not None:
            s = float(scale)
            if s <= 0:
                raise ValueError("caption scale must be > 0")
            clip.caption_scale = s
        if rotation is not None:
            clip.caption_rot = float(rotation)
        if show is not None:
            clip.show_caption = bool(show)
        project.is_dirty = True
        return ProjectService.get_clip(clip, index)

    @staticmethod
    def load_project(path: str) -> ProjectState:
        if not path or not os.path.exists(path):
            raise FileNotFoundError(f"Project file not found: {path}")
        project = ProjectState()
        is_full = project.load_from_csv(path)
        # Raw-script CSVs (no *PROJECT_META* row) still populate clips;
        # caller can check project.filepath / clip sync state as needed.
        return project

    @staticmethod
    def save_project(project: ProjectState, path: str = None) -> str:
        target = path or project.filepath
        if not target:
            raise ValueError("No save path provided and project has no filepath.")
        project.save_to_csv(target)
        project.filepath = target
        project.is_dirty = False
        return target

    @staticmethod
    def get_project_state(project: ProjectState) -> dict:
        """Full serializable dump — used by MCP get_project_state."""
        return {
            "filepath": project.filepath,
            "audio_path": project.audio_path,
            "aspect_ratio": project.aspect_ratio,
            "fps": project.fps,
            "whisper_model": project.whisper_model,
            "strict_cuts": project.strict_cuts,
            "gap_threshold": project.gap_threshold,
            "vignette": project.vignette,
            "disable_all_captions": project.disable_all_captions,
            "is_dirty": project.is_dirty,
            "clip_count": len(project.clips),
            "clips": [ProjectService.get_clip(c, i) for i, c in enumerate(project.clips)],
        }

    @staticmethod
    def get_clip(clip, index: int) -> dict:
        return {
            "index": index,
            "media_type": clip.media_type,
            "media_path": clip.media_path,
            "script_text": clip.script_text,
            "start_time": clip.start_time,
            "end_time": clip.end_time,
            "animation": clip.animation,
            "transition": clip.transition,
            "trim_start": clip.trim_start,
            "trim_end": clip.trim_end,
            "caption_x": clip.caption_x,
            "caption_y": clip.caption_y,
            "caption_scale": clip.caption_scale,
            "caption_rot": clip.caption_rot,
            "show_caption": clip.show_caption,
            "whisper_confidence": clip.whisper_confidence,
            "word_count": len(clip.words),
            "is_synced": clip.is_synced,
            "is_blank": clip.is_blank,
        }

    @staticmethod
    def list_clips(project: ProjectState) -> list:
        return [ProjectService.get_clip(c, i) for i, c in enumerate(project.clips)]

    @staticmethod
    def update_clip_timing(project: ProjectState, index: int,
                           start_time: float = None, end_time: float = None):
        """Update one clip's timings with basic sanity clamping."""
        if index < 0 or index >= len(project.clips):
            raise IndexError(f"Clip index {index} out of range (0..{len(project.clips)-1}).")
        clip = project.clips[index]
        if start_time is not None:
            clip.start_time = max(0.0, float(start_time))
        if end_time is not None:
            et = float(end_time)
            st = clip.start_time
            if et <= st:
                et = st + 0.1
            clip.end_time = et
        project.is_dirty = True
        return ProjectService.get_clip(clip, index)

    @staticmethod
    def move_clip(project: ProjectState, index: int, new_index: int):
        """Reorder a clip in the timeline."""
        n = len(project.clips)
        if index < 0 or index >= n:
            raise IndexError(f"Clip index {index} out of range (0..{n-1}).")
        new_index = max(0, min(n - 1, int(new_index)))
        clip = project.clips.pop(index)
        project.clips.insert(new_index, clip)
        project.is_dirty = True
        return ProjectService.list_clips(project)
