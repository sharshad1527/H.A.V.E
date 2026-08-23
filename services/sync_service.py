"""SyncService — Whisper transcription + script alignment, Qt-free.

Ports the logic out of ui/main_gui.py WhisperWorker.run() and
AutoEditorGUI.on_sync_finished() into a plain callable API.
"""
import time


class SyncService:
    # Mirrors the GUI's model-name mapping (main_gui.py run_whisper_sync)
    MODEL_MAP = {"tiny": "tiny", "small": "small", "base": "base"}

    @classmethod
    def transcribe_and_sync(cls, audio_path: str, script_data: list,
                            model_size: str = "base", progress=None):
        """Transcribe audio with Whisper and align the user's script lines to it.

        Args:
            audio_path: path to master voiceover.
            script_data: list of {"image": path, "text": line} dicts.
            model_size: "tiny" | "base" | "small".
            progress: optional callback(str) for status messages.

        Returns:
            timeline list — one dict per script line with start_time,
            end_time, words[], confidence.
        """
        if not audio_path:
            raise ValueError("audio_path is required.")
        if not script_data:
            raise ValueError("script_data is empty — nothing to sync.")

        report = progress or (lambda msg: None)
        model_size = cls.MODEL_MAP.get(str(model_size).lower(), "base")

        from core.whisper_engine import AudioSyncEngine

        start_time = time.time()
        report(f"Loading Whisper Model ({model_size})...")
        engine = AudioSyncEngine(model_size=model_size)

        report("Transcribing Audio... (This may take a minute)")
        segments = engine.transcribe_audio(audio_path)

        report("Matching Script to Audio Timeline...")
        timeline = engine.match_script_to_audio(script_data, segments)

        elapsed = time.time() - start_time
        report(f"Sync Complete ({elapsed:.1f}s)")
        return timeline, elapsed

    @staticmethod
    def apply_timeline_to_project(project, timeline: list):
        """Write sync results back into ProjectState clips.

        Ports the overlap-resolution post-processing that used to live in
        AutoEditorGUI.on_sync_finished() (ui/main_gui.py) — no Qt involved.
        """
        for i, item in enumerate(timeline):
            if i >= len(project.clips):
                break
            clip = project.clips[i]
            clip.start_time = item.get("start_time", 0.0)
            clip.end_time = item.get("end_time", 0.0)
            clip.whisper_confidence = item.get("confidence", 100.0)
            clip.words = item.get("words", [])

        safe_last_end = 0.0
        n = len(project.clips)
        for i, clip in enumerate(project.clips):
            st = max(clip.start_time, safe_last_end)
            if i < n - 1:
                next_st = project.clips[i + 1].start_time
                et = min(clip.end_time, next_st)
            else:
                et = clip.end_time
            if et - st < 0.2:
                et = st + 0.2
            clip.start_time = st
            clip.end_time = et
            safe_last_end = et

        project.is_dirty = True

    @classmethod
    def sync_project(cls, project, progress=None):
        """One-call headless sync of a loaded ProjectState."""
        if not project.audio_path:
            raise ValueError("Project has no audio_path set.")
        if not project.clips:
            raise ValueError("Project has no clips to sync.")

        script_data = [{"image": c.media_path, "text": c.script_text}
                       for c in project.clips]
        timeline, elapsed = cls.transcribe_and_sync(
            project.audio_path, script_data,
            model_size=project.whisper_model, progress=progress)
        cls.apply_timeline_to_project(project, timeline)
        return timeline, elapsed

    @staticmethod
    def build_render_data(project) -> list:
        """Convert ProjectState clips into renderer-ready dicts.

        Ports AutoEditorGUI.run_render()'s render_data construction
        (overlap clamping + caption defaults) — Qt-free.
        """
        render_data = []
        is_vert = "9:16" in (project.aspect_ratio or "")
        # Only synced clips participate — mirrors the renderer's own skip of
        # unmatched clips. Without this, an unsynced clip's 0.0 start_time
        # would crush its predecessor's end time via min() below.
        active = [(i, c) for i, c in enumerate(project.clips) if c.is_synced]
        n = len(active)
        safe_last_end = 0.0
        for pos, (i, c) in enumerate(active):
            st = max(c.start_time, safe_last_end)
            if pos < n - 1:
                next_st = active[pos + 1][1].start_time
                et = min(c.end_time, next_st)
            else:
                et = c.end_time + 0.2
            if et - st < 0.2:
                et = st + 0.2

            render_data.append({
                "type": c.media_type, "image": c.media_path,
                "script_line": c.script_text,
                "start_time": st, "end_time": et,
                "animation": c.animation, "transition": c.transition,
                "trim_start": c.trim_start, "trim_end": c.trim_end,
                "caption_x": c.caption_x,
                "caption_y": c.caption_y if c.caption_y is not None else (0.74 if is_vert else 0.90),
                "caption_scale": c.caption_scale, "caption_rot": c.caption_rot,
                "words": c.words, "show_caption": c.show_caption,
            })
            safe_last_end = et
        return render_data
