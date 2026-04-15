# **H.A.V.E. 🎬**

**Harshad's Automated Video Engine**  
A script-driven video editing and rendering pipeline built entirely in Python.  
*\[Drop your main UI screenshot here \- e.g., \!\[Main UI\](images/main\_ui.png)\]*

## **🛑 The "Why" (Why I built this)**

I got tired of the manual editing grind. If you've ever made heavily scripted, caption-heavy videos, you know the pain: chopping up audio, perfectly aligning visuals to spoken words, and manually keyframing zoom effects. It takes hours.  
I realized I didn't need another traditional timeline editor like Premiere or DaVinci; I needed a workflow automation tool.  
So, I built H.A.V.E.. You give it a script and a master voiceover track, and the engine uses OpenAI's Whisper to figure out exactly when you said what. It automatically maps your media to those timestamps, adds dynamic camera movements, and burns word-by-word highlighted captions into the final render. What used to take hours now takes minutes.

## **🧠 Under the Hood (The Tech Stack Flex)**

I didn't just string together a few basic Python libraries. This thing is heavily optimized for speed and performance:

* **Native FFmpeg C-Bindings (Goodbye MoviePy):** I originally tried using moviepy, but Python-based frame-by-frame rendering is painfully slow. I ripped it out and wrote a custom rendering engine (video\_renderer.py) that constructs massive, complex lavfi filter graphs. It passes the work directly to FFmpeg's zoompan and overlay filters, resulting in 10x-50x faster export times.  
* **RapidFuzz Optimized Syncing:** The two-pass anchoring algorithm that matches your script to Whisper's output uses rapidfuzz under the hood. It’s exponentially faster than standard difflib for text alignment.  
* **Ultra-Fast .ass Caption Generation:** Instead of drawing text onto image frames in Python, the captions\_engine.py dynamically generates an optimized Advanced SubStation Alpha (.ass) file. It handles styling, drop shadows, and that viral "current-word orange highlight" effect, allowing FFmpeg to burn the text instantly during the final merge.

## **✨ The "Pro" Features**

*\[Drop a GIF/Image of the Inspector Panel or Word Editor here\]*

* **Granular Word-Boundary Editor:** AI transcription isn't always perfect. I built a custom dialog (word\_editor\_dialog.py) that lets you literally pull and push specific words between clips to fix timing boundaries without touching a traditional timeline.  
* **AI Viral Shorts Generator:** Hooked up to the OpenRouter API (supports LLaMA, Gemini, Mistral). It analyzes your full transcript and automatically finds high-retention 30-60 second segments to spin off as TikToks/Reels.  
* **Non-Destructive Media Editing:** Custom PySide6 widgets for aspect-ratio-locked image cropping and dual-handle video trimming.  
* **Dynamic Camera Motions:** Automatically applies Ken Burns, Pendulum, and Panning animations to static images based on clip duration to keep viewer retention high.

## **⚙️ The Workflow (1-2-3-4)**

1. **Load Audio:** Import your master voiceover track (.mp3, .wav, .m4a).  
2. **Load Script:** Import a basic CSV containing your script lines and intended media files.  
3. **Sync Whisper:** Hit the sync button. The app transcribes the audio and maps the exact start/end times of every word to your script segments.  
4. **Inspect & Render:** Use the right-hand Inspector Panel to swap media or change animations. When it looks good, hit Render Final.

## **🛠️ Installation & Setup**

* Python 3.9+ is required.  
* FFmpeg is strictly required. It must be installed on your system and accessible in your system's PATH.

### **Install dependencies:**

```bash
pip install PySide6 openai-whisper torch rapidfuzz opencv-python numpy Pillow requests imageio-ffmpeg moviepy
```

**Note:** Installing torch with CUDA support is highly recommended if using an Nvidia GPU. It makes Whisper transcription near-instant.

### **Run the app:**

```bash
python main_gui.py
```

## **📐 Known Quirks & "Designed For"**

I built this specifically for my own content style, so it has some opinionated design choices:

* **Strict Cuts:** The app prefers tight pacing. If there is a massive gap of silence in your audio between script lines, the renderer is designed to trim the dead air automatically (adjustable via the "Gap" threshold).  
* **CSV Format:** It expects a very specific CSV structure for saving/loading projects (handled internally by project\_model.py).  
* **Fallback Fonts:** The caption engine looks for a local font/ folder. If it can't find your heavy/bold fonts, it will fall back to Arial.

## **🗺️ Roadmap**

* \[ \] Auto Chapter Creator: Automatically analyze the script/transcription to generate timestamped YouTube chapters for seamless video navigation.
* \[ \] Custom Caption Styles: Allow different fonts, colors, background boxes, and dynamic entry animations beyond the current default preset.
* \[ \] Custom Effects Creator: Build a UI to let users create and save their own custom zoom/pan/transition presets.
* \[ \] UI Upgrades: Continue refining the PySide6 interface for an even smoother, more professional user experience.


## **🤖 AI Transparency Note**

I'm a big believer in using the best tools available. I used AI (LLMs) heavily during the development of this project to crush PySide6 UI boilerplate, debug absolute nightmare FFmpeg filter graph syntax, and structure the MVC architecture. Using AI allowed me to focus purely on the core logic, performance optimizations, and building a workflow that actually solves my editing problems.

## **📄 License**

This project is licensed under the **GNU General Public License v3.0 (GPLv3)**.  
You are free to use, modify, and distribute this software under the terms of the GPLv3 license. Any derivative work must also be distributed under the same license.  
See the LICENSE file for full details.