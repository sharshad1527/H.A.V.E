"""H.A.V.E CLI — headless control of the video engine.

All commands call the services/ layer only; no Qt anywhere.
"""
import os
import sys
import threading

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.project_service import ProjectService
from services.sync_service import SyncService
from services.render_service import RenderService, JobManager

app = typer.Typer(help="H.A.V.E — AI voiceover-synced video engine (headless CLI)", no_args_is_help=True)
clips_app = typer.Typer(help="Inspect and edit timeline clips", no_args_is_help=True)
app.add_typer(clips_app, name="clips")

console = Console()
_job_manager = None  # lazy singleton


def _get_jobs() -> JobManager:
    global _job_manager
    if _job_manager is None:
        _job_manager = JobManager()
    return _job_manager


def _load(path: str):
    try:
        return ProjectService.load_project(path)
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/] {e}")
        raise typer.Exit(1)


@app.command()
def info(project: str = typer.Argument(..., help="Project CSV path")):
    """Show project settings and clip summary."""
    p = _load(project)
    state = ProjectService.get_project_state(p)
    table = Table(title=f"H.A.V.E Project — {project}")
    table.add_column("Setting", style="cyan")
    table.add_column("Value")
    for k in ("audio_path", "aspect_ratio", "fps", "whisper_model",
              "strict_cuts", "gap_threshold", "vignette", "disable_all_captions"):
        table.add_row(k, str(state[k]))
    synced = sum(1 for c in state["clips"] if c["is_synced"])
    table.add_row("clips", f"{state['clip_count']} ({synced} synced)")
    console.print(table)


@clips_app.command("list")
def clips_list(project: str = typer.Argument(..., help="Project CSV path")):
    """List all clips with timings."""
    p = _load(project)
    table = Table(title="Timeline Clips")
    for col in ("#", "media", "start", "end", "anim/trans", "synced"):
        table.add_column(col)
    for i, c in enumerate(ProjectService.list_clips(p)):
        table.add_row(
            str(i),
            os.path.basename(c["media_path"])[:28] or "(blank)",
            f"{c['start_time']:.2f}", f"{c['end_time']:.2f}",
            f"{c['animation']}/{c['transition']}",
            "[green]yes[/]" if c["is_synced"] else "[red]no[/]",
        )
    console.print(table)


@clips_app.command("trim")
def clips_trim(project: str = typer.Argument(..., help="Project CSV path"),
               index: int = typer.Argument(..., help="Clip index"),
               start: float = typer.Option(None, "--start", help="New start time (s)"),
               end: float = typer.Option(None, "--end", help="New end time (s)"),
               save: bool = typer.Option(True, "--save/--no-save", help="Save back to CSV")):
    """Update one clip's timing boundaries."""
    p = _load(project)
    try:
        result = ProjectService.update_clip_timing(p, index, start, end)
    except IndexError as e:
        console.print(f"[red]Error:[/] {e}")
        raise typer.Exit(1)
    console.print(f"Clip {index}: start={result['start_time']:.2f} end={result['end_time']:.2f}")
    if save:
        out = ProjectService.save_project(p)
        console.print(f"[green]Saved[/] -> {out}")


@clips_app.command("move")
def clips_move(project: str = typer.Argument(..., help="Project CSV path"),
               index: int = typer.Argument(..., help="Clip index"),
               to: int = typer.Argument(..., help="New index"),
               save: bool = typer.Option(True, "--save/--no-save")):
    """Reorder a clip in the timeline."""
    p = _load(project)
    try:
        ProjectService.move_clip(p, index, to)
    except IndexError as e:
        console.print(f"[red]Error:[/] {e}")
        raise typer.Exit(1)
    console.print(f"Moved clip {index} -> {to}")
    if save:
        ProjectService.save_project(p)
        console.print("[green]Saved[/]")


@app.command()
def sync(project: str = typer.Argument(..., help="Project CSV path"),
         model: str = typer.Option(None, "--model", "-m", help="tiny|base|small override")):
    """Whisper-transcribe the voiceover and sync script lines to it."""
    p = _load(project)
    if model:
        p.whisper_model = model
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  BarColumn(), TaskProgressColumn(), console=console) as progress_bar:
        task = progress_bar.add_task("Syncing...", total=100)
        def on_progress(msg):
            progress_bar.update(task, description=msg[:60])
        try:
            timeline, elapsed = SyncService.sync_project(p, progress=on_progress)
        except Exception as e:
            console.print(f"[red]Sync failed:[/] {e}")
            raise typer.Exit(1)
        progress_bar.update(task, completed=100)
    ProjectService.save_project(p)
    console.print(f"[green]Sync complete[/] ({elapsed:.1f}s) — {len(timeline)} lines aligned. Saved -> {p.filepath}")


@app.command()
def render(project: str = typer.Argument(..., help="Project CSV path"),
           output: str = typer.Option(None, "-o", "--output", help="Output mp4 path"),
           background: bool = typer.Option(False, "--background", "-b", help="Run as tracked job and exit"),
           wait: bool = typer.Option(False, "--wait", help="Wait for a --background job to finish")):
    """Render the synced project to MP4."""
    p = _load(project)
    output = output or "final_video.mp4"

    if background:
        job_id = _get_jobs().start_render(p, output)
        console.print(f"[green]Job started:[/] {job_id}")
        console.print(f"Poll with: have job-status {job_id}")
        if not wait:
            return
        import time as _time
        with console.status("Rendering in background..."):
            while True:
                st = _get_jobs().get_status(job_id)
                if st["status"] in ("completed", "failed", "cancelled"):
                    break
                _time.sleep(2)
        _print_job(st)
        if st["status"] != "completed":
            raise typer.Exit(1)
        return

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  BarColumn(), TaskProgressColumn(), console=console) as progress_bar:
        task = progress_bar.add_task("Rendering...", total=100)
        try:
            total = RenderService.render(
                p, output,
                progress=lambda pct, msg: progress_bar.update(
                    task, completed=pct, description=msg[:60]))
        except Exception as e:
            console.print(f"[red]Render failed:[/] {e}")
            raise typer.Exit(1)
        progress_bar.update(task, completed=100)
    mins, secs = int(total // 60), int(total % 60)
    console.print(f"[green]Render complete[/] — {output} ({mins}m {secs}s)")


def _print_job(st: dict):
    color = {"completed": "green", "failed": "red", "cancelled": "yellow"}.get(st["status"], "cyan")
    console.print(f"[{color}]Job {st['job_id']}: {st['status']}[/] ({st.get('pct', 0)}%) — {st.get('message','')}")
    if st.get("output_path") and st["status"] == "completed":
        console.print(f"Output: {st['output_path']}")


@app.command()
def job_status(job_id: str = typer.Argument(..., help="Job id from `have render --background`")):
    """Poll a background render job."""
    try:
        _print_job(_get_jobs().get_status(job_id))
    except KeyError as e:
        console.print(f"[red]{e}[/]")
        raise typer.Exit(1)


@app.command()
def job_cancel(job_id: str = typer.Argument(...)):
    """Cancel a running background render job."""
    ok = _get_jobs().cancel(job_id)
    console.print("[green]Cancellation requested.[/]" if ok else "[red]Unknown job.[/]")
    if not ok:
        raise typer.Exit(1)


@app.command()
def shorts(project: str = typer.Argument(..., help="Project CSV path"),
           count: int = typer.Option(3, "--count", "-n")):
    """Generate viral-shorts candidates from the transcript (AI dialog in GUI; here lists top segments)."""
    p = _load(project)
    words = [w for c in p.clips for w in (c.words or [])]
    if len(words) < 30:
        console.print("[yellow]Not enough transcribed words for shorts segmentation.[/]")
        raise typer.Exit(1)
    # 30-60s sliding windows ranked by word density (headless heuristic;
    # the GUI's OpenRouter-powered picker remains the premium path)
    segs = []
    i = 0
    while i < len(words):
        j, t0 = i, words[i].get("start", 0.0)
        while j < len(words) and words[j].get("end", 0.0) - t0 < 12.0:
            j += 1
        if j - i >= 10:
            segs.append((t0, words[j-1].get("end", t0 + 30), j - i))
        i = j
    segs.sort(key=lambda s: -s[2])
    table = Table(title="Top shorts segments (word-density heuristic)")
    table.add_column("#")
    table.add_column("start", style="cyan")
    table.add_column("end", style="cyan")
    table.add_column("words")
    for n, (a, b, wc) in enumerate(segs[:count]):
        table.add_row(str(n + 1), f"{a:.1f}s", f"{b:.1f}s", str(wc))
    console.print(table)


@app.command()
def mcp():
    """Start the MCP server (stdio)."""
    from mcp_server import run_server
    run_server()


if __name__ == "__main__":
    app()
