"""H.A.V.E MCP Server — drive the video engine from any MCP client.

FastMCP 2.x/3.x server exposing coarse, project-scoped tools over the
services/ layer. Long renders run as background jobs (JSON sidecars in
jobs/) so clients never hold a request open for minutes.

Run:  python mcp_server.py            (stdio transport)
      have mcp                        (same thing via the CLI)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastmcp import FastMCP

from services.project_service import ProjectService
from services.sync_service import SyncService
from services.render_service import RenderService, JobManager

mcp = FastMCP("HAVE — AI video engine")
_jobs = JobManager()

_PROJECTS_DIR = os.environ.get("HAVE_PROJECTS_DIR",
                               os.path.join(os.path.dirname(os.path.abspath(__file__)), "projects"))
os.makedirs(_PROJECTS_DIR, exist_ok=True)


def _resolve(path: str) -> str:
    """Resolve project paths against HAVE_PROJECTS_DIR when relative."""
    if os.path.isabs(path):
        return path
    return os.path.join(_PROJECTS_DIR, path)


def _load(path: str):
    p = _resolve(path)
    if not os.path.exists(p):
        raise FileNotFoundError(f"Project file not found: {p}")
    return ProjectService.load_project(p)


# ---------- project tools ----------

@mcp.tool
def create_project(path: str, audio_path: str = None,
                   aspect_ratio: str = "16:9 (Horizontal)", fps: str = "60 FPS",
                   whisper_model: str = "Base") -> dict:
    """Create a brand-new project CSV. Optionally attach the voiceover audio now."""
    p = ProjectService.create_project(_resolve(path), audio_path=audio_path,
                                      aspect_ratio=aspect_ratio, fps=fps,
                                      whisper_model=whisper_model)
    return ProjectService.get_project_state(p)


@mcp.tool
def set_project_settings(path: str, audio_path: str = None, aspect_ratio: str = None,
                         fps: str = None, whisper_model: str = None,
                         strict_cuts: bool = None, gap_threshold: float = None,
                         vignette: bool = None, disable_all_captions: bool = None) -> dict:
    """Update global project settings — attach/replace voiceover audio,
    aspect ratio, fps, whisper model, strict cuts, gap threshold, vignette,
    captions on/off. Only provided fields change. Saves the project."""
    p = _load(path)
    state = ProjectService.set_project_settings(
        p, audio_path=audio_path, aspect_ratio=aspect_ratio, fps=fps,
        whisper_model=whisper_model, strict_cuts=strict_cuts,
        gap_threshold=gap_threshold, vignette=vignette,
        disable_all_captions=disable_all_captions)
    ProjectService.save_project(p)
    return state


@mcp.tool
def load_project(path: str) -> dict:
    """Load a H.A.V.E project CSV and return its full state."""
    return ProjectService.get_project_state(_load(path))


@mcp.tool
def get_project_state(path: str) -> dict:
    """Full serializable dump of a project: settings + all clips."""
    return ProjectService.get_project_state(_load(path))


@mcp.tool
def list_clips(path: str) -> list:
    """List every clip: media, timings, animation/transition, sync state."""
    return ProjectService.list_clips(_load(path))


@mcp.tool
def update_clip_timing(path: str, index: int, start_time: float = None,
                       end_time: float = None) -> dict:
    """Update one clip's start/end times (seconds). Returns the updated clip."""
    p = _load(path)
    updated = ProjectService.update_clip_timing(p, index, start_time, end_time)
    ProjectService.save_project(p)
    return updated


@mcp.tool
def move_clip(path: str, index: int, new_index: int) -> list:
    """Reorder a clip in the timeline. Returns the new clip order."""
    p = _load(path)
    clips = ProjectService.move_clip(p, index, new_index)
    ProjectService.save_project(p)
    return clips


@mcp.tool
def add_clip(path: str, media_path: str, script_text: str = "",
             media_type: str = None, position: int = None) -> dict:
    """Add a new clip (image or video) to the timeline. Auto-detects
    Image/Video from extension unless media_type given."""
    p = _load(path)
    added = ProjectService.add_clip(p, media_path, script_text,
                                    media_type=media_type, position=position)
    ProjectService.save_project(p)
    return added


@mcp.tool
def remove_clip(path: str, index: int) -> list:
    """Delete a clip from the timeline by index. Returns remaining clips."""
    p = _load(path)
    remaining = ProjectService.remove_clip(p, index)
    ProjectService.save_project(p)
    return remaining


@mcp.tool
def update_clip_media(path: str, index: int, media_path: str,
                      media_type: str = None) -> dict:
    """Swap the media file of an existing clip (e.g. replace an image)."""
    p = _load(path)
    updated = ProjectService.update_clip_media(p, index, media_path,
                                               media_type=media_type)
    ProjectService.save_project(p)
    return updated


@mcp.tool
def update_clip_text(path: str, index: int, script_text: str) -> dict:
    """Change a clip's script line — the text Whisper syncs against.
    Re-sync after changing text for accurate timings."""
    p = _load(path)
    updated = ProjectService.update_clip_text(p, index, script_text)
    ProjectService.save_project(p)
    return updated


@mcp.tool
def set_clip_effect(path: str, index: int, animation: str = None,
                    transition: str = None) -> dict:
    """Set animation and/or transition for one clip. Use "Random" to let the
    engine pick weighted-random. Animations: Zoom In, Zoom Out, Camera Pan
    Left/Right, Pan Left/Right, Pendulum, Ken Burns. Transitions: Cut, Fade,
    Mix, Bubble Blur, Slide Left/Right, Swipe Left/Right, Pull In, Pull Out."""
    p = _load(path)
    updated = ProjectService.set_clip_effect(p, index, animation, transition)
    ProjectService.save_project(p)
    return updated


@mcp.tool
def set_caption_layout(path: str, index: int, x: float = None, y: float = None,
                       scale: float = None, rotation: float = None,
                       show: bool = None) -> dict:
    """Adjust caption layout for one clip: x/y position (0..1 fractions),
    scale, rotation degrees, show/hide."""
    p = _load(path)
    updated = ProjectService.set_caption_layout(p, index, x=x, y=y,
                                                scale=scale, rotation=rotation,
                                                show=show)
    ProjectService.save_project(p)
    return updated


# ---------- sync / captions ----------

@mcp.tool
def transcribe_and_sync(path: str, model_size: str = "base") -> dict:
    """Whisper-transcribe the voiceover and align script lines to word
    timestamps. Saves synced timings back into the project."""
    p = _load(path)
    timeline, elapsed = SyncService.sync_project(p)
    ProjectService.save_project(p)
    return {"synced_lines": len(timeline), "elapsed_seconds": round(elapsed, 1),
            "saved_to": p.filepath}


@mcp.tool
def generate_captions(path: str) -> dict:
    """Generate the styled .ass caption file for the current timeline."""
    import tempfile
    from core.captions_engine import create_ass_file
    p = _load(path)
    w, h = (1080, 1920) if "9:16" in (p.aspect_ratio or "") else (1920, 1080)
    render_data = SyncService.build_render_data(p)
    base = os.path.splitext(os.path.basename(path))[0]
    out = os.path.join(tempfile.gettempdir(), f"have_caps_{base}.ass")
    res = create_ass_file(render_data, w, h, out,
                          disable_all_captions=p.disable_all_captions)
    if not res or not os.path.exists(res):
        raise RuntimeError("Caption generation produced no file.")
    return {"caption_file": res}


# ---------- render (async job pattern) ----------

@mcp.tool
def start_render_job(path: str, output_path: str,
                     burn_captions: bool = True) -> dict:
    """Start rendering the synced project in the background. Returns a job_id;
    poll with get_job_status. Never blocks on long renders."""
    p = _load(path)
    out = output_path if os.path.isabs(output_path) else os.path.join(_PROJECTS_DIR, output_path)
    job_id = _jobs.start_render(p, out, burn_captions=burn_captions)
    return {"job_id": job_id, "output": out}


@mcp.tool
def render_project_blocking(path: str, output_path: str,
                            burn_captions: bool = True) -> dict:
    """Render synchronously and wait. Only for short projects — prefer
    start_render_job for real videos."""
    p = _load(path)
    out = output_path if os.path.isabs(output_path) else os.path.join(_PROJECTS_DIR, output_path)
    total = RenderService.render(p, out, burn_captions=burn_captions)
    return {"output": out, "render_seconds": round(total, 1)}


@mcp.tool
def get_job_status(job_id: str) -> dict:
    """Poll a background render job: status, percent, message, output path."""
    return _jobs.get_status(job_id)


@mcp.tool
def cancel_job(job_id: str) -> dict:
    """Request cooperative cancellation of a running render job."""
    ok = _jobs.cancel(job_id)
    return {"job_id": job_id, "cancel_requested": ok}


# ---------- entry ----------

def run_server():
    mcp.run()  # stdio transport


if __name__ == "__main__":
    run_server()
