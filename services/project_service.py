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
