import os
import platform
import random
import gc
import subprocess
import tempfile
import shutil
import time
import traceback
import re
from concurrent.futures import ThreadPoolExecutor
from core.captions_engine import create_ass_file, get_font_path


class VideoRenderer:
    """FFmpeg-native renderer — bypasses moviepy's slow per-frame Python processing.
    
    Uses ffmpeg's C-based zoompan filter directly for all motion effects,
    which is 10-50x faster than moviepy's Python lambda approach.
    
    v4 — Upgraded to Ultra-Fast Native .ASS Captions Generation
    """

    def __init__(self):
        try:
            import imageio_ffmpeg
            self.ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception as e:
            print(f"Warning: imageio_ffmpeg not found or failed ({e}). Falling back to 'ffmpeg' in PATH.")
            self.ffmpeg = "ffmpeg"

    def _get_media_duration(self, file_path):
        """Instantly fetch media duration using native ffmpeg without loading the file."""
        cmd = [self.ffmpeg, "-hide_banner", "-i", file_path]
        # ffmpeg prints metadata to stderr when no output file is specified
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        _, err = process.communicate()
        
        # Match pattern like "Duration: 00:00:05.23"
        match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", err)
        if match:
            hours, minutes, seconds = match.groups()
            return (float(hours) * 3600) + (float(minutes) * 60) + float(seconds)
        
        print(f"Warning: Could not read duration for {file_path}")
        return 0.0

    def _run_ff(self, args, timeout=120, cancel_event=None):
        """Run ffmpeg silently, raise on error with full crash report."""
        if cancel_event and cancel_event.is_set():
            raise InterruptedError("Render cancelled by user.")

        cmd = [self.ffmpeg] + args
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        start_time = time.time()
        stdout_data, stderr_data = b"", b""
        
        while True:
            if cancel_event and cancel_event.is_set():
                process.terminate()
                process.wait()
                raise InterruptedError("Render cancelled by user.")
            
            try:
                out, err = process.communicate(timeout=0.1)
                if out: stdout_data += out
                if err: stderr_data += err
                break  # process finished
            except subprocess.TimeoutExpired:
                pass # Still running, check cancel_event and timeout again
                
            if timeout and (time.time() - start_time) > timeout:
                process.kill()
                process.wait()
                raise TimeoutError("ffmpeg process timed out.")

        if process.returncode != 0:
            err = stderr_data.decode("utf-8", errors="replace")
            # --- COMPREHENSIVE FFMPEG CRASH REPORT ---
            print("\n" + "="*20 + " FFMPEG CRASH REPORT " + "="*20)
            print(f"COMMAND RUN:\n{' '.join(cmd)}\n")
            print(f"FFMPEG ERROR LOG:\n{err}")
            print("="*61 + "\n")
            raise RuntimeError(f"ffmpeg failed:\n{err[-600:]}")

    def _make_clip(self, img, out, dur, w, h, motion, entry, zamount, first, last, is_video=False, fps=60, trim_start=0.0, trim_end=0.0, trans_dur=0.2, cancel_event=None):
        try:
            dur = float(dur)
            fps = float(fps)
            w = int(w)
            h = int(h)
            zamount = float(zamount) if not isinstance(zamount, dict) else 0.05
        except (TypeError, ValueError):
            pass
        nf = max(int(dur * fps), 2)

        if img == "BLANK_IMAGE":
            self._run_ff([
                "-y", "-f", "lavfi", "-i", f"color=c=black:s={w}x{h}:r={fps}:d={dur:.3f}",
                "-vf", "setsar=1:1,format=yuv420p",
                "-c:v", "libx264", "-preset", "ultrafast", "-tune", "stillimage",
                "-threads", "0",
                "-f", "mpegts", out
            ], cancel_event=cancel_event)
            return

        input_args = []
        pp_mp4 = ""
        is_vertical = (h > w)
        
        if is_video:
            # Native fast duration fetch instead of MoviePy
            v_dur = self._get_media_duration(img)
            
            if trim_end <= 0 or trim_end > v_dur:
                trim_end = v_dur
            actual_v_dur = trim_end - trim_start

            if actual_v_dur < dur:
                pp_mp4 = out + "_pp.mp4"
                self._run_ff([
                    "-y", "-ss", str(trim_start), "-to", str(trim_end), "-i", img,
                    "-filter_complex", "[0:v]reverse[r];[0:v][r]concat=n=2:v=1[v]",
                    "-map", "[v]", "-an",
                    "-c:v", "libx264", "-preset", "ultrafast",
                    "-threads", "0",
                    pp_mp4
                ], cancel_event=cancel_event)
                input_args = ["-stream_loop", "-1", "-i", pp_mp4]
            else:
                input_args = ["-ss", str(trim_start), "-i", img]

        else:
            input_args = ["-i", img]
            
            if motion == "Zoom In":
                bz = 1.0; z = f"{bz}+({zamount}*on/{nf})"
                x = "iw/2-(iw/zoom)/2"; y = "ih/2-(ih/zoom)/2"
            elif motion == "Zoom Out":
                bz = 1.0; z = f"{bz+zamount}-({zamount}*on/{nf})"
                x = "iw/2-(iw/zoom)/2"; y = "ih/2-(ih/zoom)/2"
            elif motion == "Camera Pan Right":
                bz = 1.0 + zamount; z = f"{bz}"
                x = f"(iw-iw/zoom)*0.85*(on/{nf})"; y = "ih/2-(ih/zoom)/2"
            elif motion == "Camera Pan Left":
                bz = 1.0 + zamount; z = f"{bz}"
                x = f"(iw-iw/zoom)*0.85*(1-on/{nf})"; y = "ih/2-(ih/zoom)/2"
            elif motion == "Pendulum":
                bz = 1.0 + zamount; z = f"{bz+0.01}"
                p_dist = random.uniform(0.005, 0.009); p_speed = random.uniform(30, 50) * (fps / 60)
                x = f"iw/2-(iw/zoom)/2+(iw*{p_dist})*sin(on/{p_speed})"; y = "ih/2-(ih/zoom)/2"
            elif motion == "Ken Burns":
                bz = 1.05; z = f"{bz}+({zamount * 0.5}*on/{nf})"
                drift_x = random.choice([-1, 1]) * random.uniform(0.005, 0.010)
                drift_y = random.choice([-1, 1]) * random.uniform(0.003, 0.007)
                x = f"iw/2-(iw/zoom)/2+(iw*{drift_x})*(on/{nf})"
                y = f"ih/2-(ih/zoom)/2+(ih*{drift_y})*(on/{nf})"
            else:
                bz = 1.0; z = f"{bz}"
                x = "iw/2-(iw/zoom)/2"; y = "ih/2-(ih/zoom)/2"

        # --- Build Core Filter Graph (Handles 9:16 Shorts Logic) ---
        filter_graph = ""
        current_pad = "[0:v]"
        
        if is_video:
            if is_vertical:
                filter_graph = (
                    f"{current_pad}split=2[bg_in][fg_in]; "
                    f"[bg_in]scale={w}:{h}:force_original_aspect_ratio=increase,boxblur=20:20,crop={w}:{h}[bg]; "
                    f"[fg_in]scale={w}:{h}:force_original_aspect_ratio=decrease[fg]; "
                    f"[bg][fg]overlay=(W-w)/2:(H-h)/2[comp]"
                )
                current_pad = "[comp]"
            else:
                filter_graph = f"{current_pad}scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}[comp]"
                current_pad = "[comp]"
        else:
            sw, sh = int(w * 1.25), int(h * 1.25)
            w_int, h_int = sw, sh
            
            if is_vertical:
                filter_graph = (
                    f"{current_pad}split=2[bg_in][fg_in]; "
                    f"[bg_in]scale={sw}:{sh}:force_original_aspect_ratio=increase,boxblur=20:20,crop={sw}:{sh}[bg]; "
                    f"[fg_in]scale={sw}:{sh}:force_original_aspect_ratio=decrease[fg]; "
                    f"[bg][fg]overlay=(W-w)/2:(H-h)/2[comp]; "
                    f"[comp]zoompan=z='{z}':x='{x}':y='{y}':d={nf}:s={w_int}x{h_int}:fps={fps}[zp]"
                )
                current_pad = "[zp]"
            else:
                filter_graph = (
                    f"{current_pad}scale={sw}:{sh}:force_original_aspect_ratio=increase:flags=bilinear[scaled]; "
                    f"[scaled]crop={sw}:{sh}[cropped]; "
                    f"[cropped]zoompan=z='{z}':x='{x}':y='{y}':d={nf}:s={w_int}x{h_int}:fps={fps}[zp]"
                )
                current_pad = "[zp]"

        # --- Dynamic Fast Transition Effects ---
        transitions = []
        if first:
            transitions.append("fade=t=in:st=0:d=0.3")
        elif entry == "Fade":
            transitions.append(f"fade=t=in:st=0:d={trans_dur}")
        elif entry == "Mix":
            transitions.append(f"fade=t=in:st=0:d={trans_dur}")
        elif entry == "Bubble Blur":
            transitions.append(f"fade=t=in:st=0:d={trans_dur}")
        elif entry in ("Slide Left", "Slide Right"):
            if entry == "Slide Left":
                transitions.append(f"pad=w='iw*2':h='ih':x='iw':y=0:color=black,crop=w='iw/2':h='ih':x='(iw/2)*min(1,t/{trans_dur})':y=0")
            else:
                transitions.append(f"pad=w='iw*2':h='ih':x=0:y=0:color=black,crop=w='iw/2':h='ih':x='(iw/2)*(1-min(1,t/{trans_dur}))':y=0")
        elif entry in ("Swipe Left", "Swipe Right"):
            if entry == "Swipe Left":
                transitions.append(f"pad=w='iw*2':h='ih':x='iw':y=0:color=black,crop=w='iw/2':h='ih':x='(iw/2)*min(1,t/{trans_dur})':y=0")
            else:
                transitions.append(f"pad=w='iw*2':h='ih':x=0:y=0:color=black,crop=w='iw/2':h='ih':x='(iw/2)*(1-min(1,t/{trans_dur}))':y=0")
        elif entry == "Pull In":
            transitions.append(f"fade=t=in:st=0:d={trans_dur}")
        elif entry == "Pull Out":
            transitions.append(f"fade=t=in:st=0:d={trans_dur}")

        if last:
            # FIX: Removed internal fade. The final FFmpeg merge handles the global fade.
            pass

        if not is_video:
            transitions.append(f"scale={w}:{h}:flags=bicubic")

        if transitions:
            trans_str = ",".join(transitions)
            filter_graph += f"; {current_pad}{trans_str}[outv]"
        else:
            filter_graph += f"; {current_pad}null[outv]"
        
        cmd = ["-y"] + input_args + [
            "-an", 
            "-filter_complex", filter_graph,
            "-map", "[outv]",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-threads", "0",
            "-pix_fmt", "yuv420p",
            "-t", f"{dur:.3f}"
        ]
        
        if not is_video:
            cmd.extend(["-tune", "stillimage"])
        if is_video:
            cmd.extend(["-r", str(fps)])
            
        cmd.extend(["-f", "mpegts", out])
        self._run_ff(cmd, cancel_event=cancel_event)
        
        if is_video and pp_mp4 and os.path.exists(pp_mp4):
            os.remove(pp_mp4)

    def render_project(self, timeline_data, audio_path, output_path,
                       resolution, strict_cuts, gap_threshold, progress_callback, cancel_event=None, fps=60, vignette=True):

        render_start_time = time.time()

        w, h = (1920, 1080) if "16:9" in resolution else (1080, 1920)
        total = len(timeline_data)
        
        if total == 0:
            raise ValueError("Timeline is empty or unsynced project. Sync it first.")

        # --- 1. Validate and Coerce Timings ---
        for item in timeline_data:
            try:
                item["start_time"] = float(str(item.get("start_time", 0.0)).replace('s', '').strip())
                item["end_time"] = float(str(item.get("end_time", 0.0)).replace('s', '').strip())
            except (ValueError, TypeError):
                item["start_time"] = 0.0
                item["end_time"] = 0.0

        valid_clips = [t for t in timeline_data if t["end_time"] > 0.0]
        if not valid_clips and total > 0:
            raise ValueError("Timeline is empty or unsynced project. Sync it first.")

        # --- 2. Normalize Missing Gaps/Overlaps ---
        last_end = 0.0
        for j in range(total):
            st = timeline_data[j]["start_time"]
            et = timeline_data[j]["end_time"]
            
            if st == 0.0 and et == 0.0 and j > 0: continue 
                
            if st < last_end:
                timeline_data[j]["start_time"] = last_end
                st = last_end
            if et <= st:
                timeline_data[j]["end_time"] = st + 0.1
                et = st + 0.1
                
            last_end = et

        # Native fast duration fetch instead of MoviePy
        audio_dur = self._get_media_duration(audio_path)

        tmp = tempfile.mkdtemp(prefix="veditor_")
        try:
            ts_files = []
            audio_segs = []
            total_video_dur = 0.0
            mapped_timeline = []
            
            prev_anim = "Zoom In"

            clip_executor = ThreadPoolExecutor(max_workers=3)
            clip_futures = []

            for i, item in enumerate(timeline_data):
                pct = int((i / total) * 80)
                elapsed = time.time() - render_start_time
                progress_callback(f"Building Clip {i+1}/{total}... {pct}% (elapsed: {elapsed:.0f}s)")

                st = item["start_time"]; et = item["end_time"]
                gt_anim = item.get("animation", "Random")
                gt_trans = item.get("transition", "Random")

                if st == 0.0 and et == 0.0 and i > 0:
                    progress_callback(f"Skipping unmatched clip {i+1}/{total}")
                    continue

                if i < total - 1:
                    ns = None
                    for j in range(i + 1, total):
                        if timeline_data[j]["start_time"] > 0 or timeline_data[j]["end_time"] > 0 or j == 0:
                            ns = timeline_data[j]["start_time"]
                            break
                    if ns is None:
                        ns = et + 0.5 

                    gap = ns - et
                    if strict_cuts and gap > gap_threshold:
                        ae = min(ns, et + 0.7); cd = ae - st
                    elif gap >= 2.0:
                        ae = min(ns, et + 0.7); cd = ae - st
                    else:
                        ae = ns; cd = ns - st
                else:
                    # FIX: Last clip logic. Stop audio exactly after words, add 0.7s to video for the fade.
                    ae = min(et + 0.1, audio_dur + 0.1)
                    cd = (ae - st) + 0.7

                if cd <= 0: cd = 0.1
                if ae <= st: ae = st + max(cd - 0.7, 0.1)
                ae = min(ae, audio_dur + 0.1)
                
                mapped_item = dict(item)
                mapped_st = total_video_dur
                mapped_et = total_video_dur + cd
                new_words = []
                
                # FIX: Clamp word timings so they NEVER spill past the audio cut gap
                for word_obj in item.get("words", []):
                    if isinstance(word_obj, dict):
                        w_orig_start = float(word_obj.get("start", 0.0))
                        w_orig_end = float(word_obj.get("end", 0.0))
                        
                        # If the word occurs in the gap we just cut out, drop it entirely
                        if w_orig_start >= ae:
                            continue
                            
                        # Clamp the word end time so it doesn't extend past our cut
                        clamped_end = min(w_orig_end, ae)
                        
                        nw = dict(word_obj)
                        nw["start"] = mapped_st + max(0.0, w_orig_start - float(st))
                        nw["end"] = mapped_st + max(0.0, clamped_end - float(st))
                        new_words.append(nw)
                        
                mapped_item["start_time"] = mapped_st
                mapped_item["end_time"] = mapped_et
                mapped_item["words"] = new_words
                mapped_timeline.append(mapped_item)
                
                audio_segs.append((st, ae))
                total_video_dur += cd

                raw = item["image"]
                is_blank = (raw == "BLANK_IMAGE")
                m_type = item.get("type", "Image")
                
                simg = "BLANK_IMAGE"
                if m_type == "Video" and not is_blank:
                    absp = os.path.abspath(os.path.normpath(raw.strip(" '\"\t\n\r\ufeff\u200b\u202a\u202c")))
                    if not os.path.exists(absp): raise FileNotFoundError(f"Missing Video: {absp}")
                    simg = absp
                elif not is_blank:
                    absp = os.path.abspath(os.path.normpath(raw.strip(" '\"\t\n\r\ufeff\u200b\u202a\u202c")))
                    if not os.path.exists(absp): raise FileNotFoundError(f"Missing Image: {absp}")
                    simg = absp

                za = random.uniform(0.03, 0.09)
                if gt_anim == "Random":
                    if prev_anim == "Zoom In": mt = random.choices(["Zoom Out", "Camera Pan Left", "Camera Pan Right", "Pendulum", "Ken Burns"], weights=[30, 20, 20, 15, 15])[0]
                    elif prev_anim == "Zoom Out": mt = random.choices(["Zoom In", "Camera Pan Left", "Camera Pan Right", "Pendulum", "Ken Burns"], weights=[30, 20, 20, 15, 15])[0]
                    elif prev_anim in ["Camera Pan Left", "Camera Pan Right"]: mt = random.choices(["Zoom In", "Zoom Out", "Pendulum", "Ken Burns"], weights=[30, 30, 20, 20])[0]
                    elif prev_anim == "Ken Burns": mt = random.choices(["Zoom In", "Zoom Out", "Camera Pan Left", "Camera Pan Right", "Pendulum"], weights=[25, 25, 20, 20, 10])[0]
                    else: mt = random.choices(["Zoom In", "Zoom Out", "Camera Pan Left", "Camera Pan Right", "Pendulum", "Ken Burns"], weights=[20, 20, 18, 18, 14, 10])[0]
                elif gt_anim == "Pan Left": mt = "Camera Pan Left"
                elif gt_anim == "Pan Right": mt = "Camera Pan Right"
                else: mt = gt_anim

                if gt_trans == "Random":
                    ent = random.choices(
                        ["Cut", "Fade", "Mix", "Bubble Blur", "Slide Left", "Slide Right", "Swipe Left", "Swipe Right", "Pull In", "Pull Out"],
                        weights=[25, 20, 15, 10, 5, 5, 5, 5, 5, 5]
                    )[0]
                else:
                    ent = gt_trans

                prev_anim = mt

                is_last_rendered = (i == total - 1)
                if not is_last_rendered:
                    is_last_rendered = all(
                        (timeline_data[k]["start_time"] == 0.0 and timeline_data[k]["end_time"] == 0.0)
                        for k in range(i + 1, total)
                    )

                t_start = item.get("trim_start", 0.0)
                t_end = item.get("trim_end", 0.0)
                
                if i > 0:
                    prev_et = timeline_data[i-1]["end_time"]
                    prev_gap = st - prev_et
                else:
                    prev_gap = 0.5
                    
                max_trans_time = min(0.6, max(0.2, prev_gap + 0.2)) 
                t_dur = random.uniform(0.15, max_trans_time) 
                t_dur = min(t_dur, cd * 0.4) 
                t_dur = max(0.1, round(t_dur, 2))
                
                tsf = os.path.join(tmp, f"clip_{i:04d}.ts")
                if cancel_event and cancel_event.is_set():
                    raise InterruptedError("Render cancelled by user.")

                future = clip_executor.submit(
                    self._make_clip, simg, tsf, cd, w, h, mt, ent, za,
                    (i == 0), is_last_rendered, (m_type == "Video"), fps, t_start, t_end, t_dur, cancel_event
                )
                clip_futures.append(future)
                ts_files.append(tsf)
                gc.collect()

            wait_start = time.time()
            progress_callback("Waiting for all background clips to finish...")
            for f in clip_futures:
                f.result() 
            clip_time = time.time() - wait_start
            print(f"\n========== RENDER TIMINGS ==========")
            print(f"1. Background Clips: {clip_time:.1f} seconds")

            if not ts_files:
                raise ValueError("No valid clips found to render! Make sure your timeline has valid timings.")

            elapsed = time.time() - render_start_time
            progress_callback(f"Stitching video clips... 82% (elapsed: {elapsed:.0f}s)")
            concat_list = os.path.join(tmp, "vlist.txt")
            with open(concat_list, "w") as f:
                for t in ts_files:
                    f.write(f"file '{t}'\n")
            vid_only = os.path.join(tmp, "vid.mp4")
            self._run_ff([
                "-y", "-f", "concat", "-safe", "0",
                "-i", concat_list,
                "-c", "copy", vid_only
            ], timeout=300, cancel_event=cancel_event)

            elapsed = time.time() - render_start_time
            progress_callback(f"Building audio track... 88% (elapsed: {elapsed:.0f}s)")
            
            aud_only = os.path.join(tmp, "aud.aac")
            
            if len(audio_segs) == 1:
                a_st, a_en = audio_segs[0]
                self._run_ff([
                    "-y", "-i", audio_path,
                    "-ss", f"{a_st:.3f}", "-to", f"{a_en:.3f}",
                    "-c:a", "aac", "-b:a", "128k",
                    "-threads", "0",
                    "-vn", aud_only
                ], timeout=300, cancel_event=cancel_event)
            else:
                filter_parts = []
                concat_inputs = []
                for idx, (a_st, a_en) in enumerate(audio_segs):
                    a_en = max(a_st + 0.1, a_en) # FIX: Prevent 0-duration audio chunk crashes
                    filter_parts.append(
                        f"[0:a]atrim=start={a_st:.3f}:end={a_en:.3f},asetpts=PTS-STARTPTS[a{idx}]"
                    )
                    concat_inputs.append(f"[a{idx}]")
                
                n_segs = len(audio_segs)
                filter_complex = ";".join(filter_parts) + ";" + "".join(concat_inputs) + f"concat=n={n_segs}:v=0:a=1[outa]"
                
                self._run_ff([
                    "-y", "-i", audio_path,
                    "-filter_complex", filter_complex,
                    "-map", "[outa]",
                    "-c:a", "aac", "-b:a", "128k",
                    "-threads", "0",
                    "-vn", aud_only
                ], timeout=300, cancel_event=cancel_event)

            cap_start = time.time()
            progress_callback("Generating Captions File...")
            
            # --- NEW ASS CAPTIONS ENGINE CALL ---
            captions_ass = os.path.join(tmp, "captions.ass")
            cap_res = create_ass_file(mapped_timeline, w, h, captions_ass)
            
            cap_time = time.time() - cap_start
            print(f"2. Captions Engine:  {cap_time:.1f} seconds")
            
            progress_callback("Merging final video layers... 95%")
            
            merge_start = time.time()
            print("3. Final FFmpeg Merge (Applying Fade-to-Black)...")

            # FIX: Base the fade out on the actual stitched video duration
            final_dur = total_video_dur
            fade_start = max(0.0, final_dur - 0.7) # Clean 0.7s fade right at the end

            if cap_res and os.path.exists(cap_res):
                # FFmpeg paths on Windows filters MUST have exactly this escaping to prevent crashes
                if platform.system() == "Windows":
                    ass_path = cap_res.replace('\\', '/').replace(':', '\\:')
                    font_dir = os.path.dirname(get_font_path()).replace('\\', '/').replace(':', '\\:')

                else:
                    ass_path = cap_res
                    font_dir = os.path.dirname(get_font_path())
                
                ass_filter = f"ass='{ass_path}':fontsdir='{font_dir}'"
                
                self._run_ff([
                    "-y",
                    "-i", vid_only, "-i", aud_only,
                    "-filter_complex", f"[0:v]{ass_filter},fade=t=out:st={fade_start}:d=0.7[vout]",
                    "-map", "[vout]", "-map", "1:a",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "23", 
                    "-pix_fmt", "yuv420p", 
                    "-threads", "0",
                    "-c:a", "copy",
                    output_path
                ], timeout=3600, cancel_event=cancel_event)
            else:
                self._run_ff([
                    "-y",
                    "-i", vid_only, "-i", aud_only,
                    "-vf", f"fade=t=out:st={fade_start}:d=0.7",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                    "-pix_fmt", "yuv420p",
                    "-threads", "0",
                    "-c:a", "copy",
                    output_path
                ], timeout=3300, cancel_event=cancel_event)

            merge_time = time.time() - merge_start
            print(f"3. Final FFmpeg Merge: {merge_time:.1f} seconds")

            total_time = time.time() - render_start_time
            print(f"TOTAL RENDER TIME: {total_time:.1f} seconds")
            print(f"====================================\n")

            mins = int(total_time // 60)
            secs = int(total_time % 60)
            progress_callback(f"Rendering Complete! 100% — Total time: {mins}m {secs}s")

        except InterruptedError as e:
            # Re-raise so worker can handle graceful stop
            raise e
        except Exception as e:
            # --- COMPREHENSIVE PYTHON CRASH REPORT ---
            err_msg = traceback.format_exc()
            print("\n" + "="*20 + " PYTHON CRASH REPORT " + "="*20)
            print(err_msg)
            print("="*61 + "\n")
            
            progress_callback(f"Render Error: Check terminal console for full crash report. ({type(e).__name__})")
            raise e
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
            gc.collect()

        return total_time