---
title: "Project: H.A.V.E"
created: 2026-07-19
updated: 2026-07-19
type: project
tags: [soft-psychology, cognitive-science, video-scripting]
sources: []
---

# 🚀 H.A.V.E (AI Voiceover, Camera animation scripting, and Caption generator pipeline.)

## 🛠️ Stack & Functionality
**Harshad's Automated Video Engine**  
A script-driven video editing and rendering pipeline built entirely in Python.  
![Main UI](assets/images/main_ui.png)

## **🛑 The "Why" (Why I built this)**

I got tired of the manual editing grind. If you've ever made heavily scripted, caption-heavy videos, you know the pain: chopping up audio, perfectly aligning visuals to spoken words, and manually keyframing zoom effects. It takes hours.  
I realized I didn't need another traditional timeline editor like Premiere or DaVinci; I needed a workflow automation tool.  
So, I built H.A.V.E.. You give it a script and a master voiceover track, and the engine uses [[concept_whisper|OpenAI's Whisper]] to figure out exactly when you said what. It automatically maps your media to those timestamps, adds dynamic camera movements, and burns word-by-word highlighted captions into the final render. What used to take hours now takes minutes.

## **🧠 Under the Hood (The Tech Stack Flex)**

I didn't just string together a few basic Python libraries. This thing is heavily optimized for speed and performance:

* **[[concept_ffmpeg_rendering|Native FFmpeg C-Bindings]] (Goodbye MoviePy):** I originally tried using moviepy, but Python-based frame-by-frame rendering is painfully slow. I ripped it out and wrote a custom rendering engine (video\_renderer.py) that constructs massive, complex lavfi filter graphs. It passes the work directly to FFmpeg's zoompan and overlay filters, resulting in 10x-50x faster export times.  
* **RapidFuzz Optimized Syncing:** The two-pass anchoring algorithm that matches your script to Whisper's output uses rapidfuzz under the hood. It’s exponentially faster than standard difflib for text alignment.  
* **Ultra-Fast .ass Caption Generation:** Instead of drawing text onto image frames in Python, the captions\_engine.py dynamically generates an optimized Advanced SubStation Alpha (.ass) file. It handles styling, drop shadows, and that viral "current-word orange highlight" effect, allowing FFmpeg to burn

## 📜 Recent Commits & Current State
The latest 5 commits logged from the git repository:
```text
91803f0 ..
9fa6e92 feat: Caption Enable Disable, For Whole Automation or Just a clip
7d8387a Refactor: reorganize directory structure and fix pathing/icon bugs
afbf7ab Update README.md
2365f92 README Fix
```