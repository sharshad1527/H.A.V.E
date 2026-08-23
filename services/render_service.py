"""RenderService — headless render orchestration, Qt-free.

Wraps core.video_renderer.VideoRenderer + core.captions_engine with a plain
callback(pct, msg) progress interface. Also hosts the JobManager used by the
MCP server for async render tracking.
"""
import os
import re
import threading
import time
import uuid


class RenderService:
    @staticmethod
    def _progress_adapter(progress):
        """Adapt our callback(pct, msg) into the renderer's callback(msg).

        Renderer messages embed 'NN%'; if the caller gave no pct-aware
        callback we just forward raw messages.
        """
        if progress is None:
            return lambda msg: None
        def cb(msg):
            m = re.search(r"(\d+)%", msg)
            try:
                progress(int(m.group(1)) if m else 0, msg)
            except Exception:
                pass
        return cb

    @classmethod
    def render(cls, project, output_path: str, resolution: str = None,
               fps: int = None, burn_captions: bool = True,
               cancel_event=None, progress=None) -> float:
        """Render a ProjectState to MP4. Returns total render seconds.

        Args:
            project: loaded models.project_model.ProjectState.
            output_path: destination .mp4.
            resolution: override like "16:9" / "9:16"; defaults to project's.
            fps: override 30/60; defaults to project's.
            burn_captions: False => disable_all_captions.
            cancel_event: threading.Event to cooperatively cancel.
            progress: optional callback(pct:int, msg:str).
        """
        from services.sync_service import SyncService
        from core.video_renderer import VideoRenderer

        synced = any(c.is_synced for c in project.clips)
        if not project.clips or not synced:
            raise ValueError("Project has no synced clips. Run sync first.")

        if not project.audio_path or not os.path.exists(project.audio_path):
            raise FileNotFoundError(f"Voiceover audio missing: {project.audio_path}")

        os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)

        render_data = SyncService.build_render_data(project)
        resolution = resolution or ("9:16" if "9:16" in (project.aspect_ratio or "") else "16:9")
        fps = fps or (30 if "30" in (project.fps or "") else 60)

        renderer = VideoRenderer()
        total_time = renderer.render_project(
            render_data, project.audio_path, output_path,
            resolution, project.strict_cuts, project.gap_threshold,
            RenderService._progress_adapter(progress),
            cancel_event=cancel_event, fps=fps, vignette=project.vignette,
            disable_all_captions=(not burn_captions) or project.disable_all_captions,
        )
        return total_time if total_time else 0.0


class JobManager:
    """Async job tracker for long renders (MCP/CLI background mode).

    Status JSON sidecar per job under jobs_dir; safe for polling readers.
    """

    def __init__(self, jobs_dir: str = None):
        self.jobs_dir = jobs_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "jobs")
        os.makedirs(self.jobs_dir, exist_ok=True)
        self._jobs = {}          # job_id -> dict
        self._events = {}        # job_id -> threading.Event (cancel flags)
        self._lock = threading.Lock()

    # ---- internal ----
    def _sidecar_path(self, job_id):
        return os.path.join(self.jobs_dir, f"{job_id}.json")

    def _write_sidecar(self, job_id):
        import json
        path = self._sidecar_path(job_id)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._jobs[job_id], f, indent=2)
        os.replace(tmp, path)

    def _run_job(self, job_id, project, output_path, **kwargs):
        job = self._jobs[job_id]
        cancel_event = self._events[job_id]
        try:
            total = RenderService.render(
                project, output_path,
                cancel_event=cancel_event,
                progress=lambda pct, msg: self._update(job_id, pct=pct, message=msg),
                **kwargs)
            if cancel_event.is_set():
                if os.path.exists(output_path):
                    try: os.remove(output_path)
                    except OSError: pass
                self._update(job_id, status="cancelled", message="Render cancelled.")
            else:
                self._update(job_id, status="completed", pct=100,
                             message=f"Done in {total:.1f}s", output_path=output_path)
        except InterruptedError:
            self._update(job_id, status="cancelled", message="Render cancelled.")
        except Exception as e:
            self._update(job_id, status="failed", message=str(e))

    def _update(self, job_id, **fields):
        with self._lock:
            self._jobs[job_id].update(fields)
            self._jobs[job_id]["updated_at"] = time.time()
            self._write_sidecar(job_id)

    # ---- public API ----
    def start_render(self, project, output_path: str, **kwargs) -> str:
        job_id = uuid.uuid4().hex[:12]
        now = time.time()
        with self._lock:
            self._jobs[job_id] = {
                "job_id": job_id, "type": "render",
                "status": "running", "pct": 0,
                "message": "Queued",
                "output_path": output_path,
                "created_at": now, "updated_at": now,
            }
            self._events[job_id] = threading.Event()
            self._write_sidecar(job_id)
        t = threading.Thread(target=self._run_job,
                             args=(job_id, project, output_path),
                             kwargs=kwargs, daemon=True)
        t.start()
        return job_id

    def get_status(self, job_id: str) -> dict:
        with self._lock:
            job = self._jobs.get(job_id)
            snapshot = dict(job) if job is not None else None
        if snapshot is None and os.path.exists(self._sidecar_path(job_id)):
            import json
            with open(self._sidecar_path(job_id), encoding="utf-8") as f:
                return json.load(f)
        if snapshot is None:
            raise KeyError(f"Unknown job: {job_id}")
        return snapshot

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            ev = self._events.get(job_id)
        if ev is None:
            return False
        ev.set()
        self._update(job_id, message="Cancellation requested...")
        return True
