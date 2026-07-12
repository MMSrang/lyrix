# Lyrix

Spotify-style synced lyrics for any audio file - powered by local, offline AI.

## What is Lyrix?

Lyrix is a Windows desktop audio player that shows synced, karaoke-style lyrics for whatever you are playing - your own recordings, voice memos, or commercial music. Everything runs locally after installation; no data leaves your machine unless you explicitly enable optional online lookups.

## Features

- Open any audio file (double-click, "Open with", or drag-and-drop) and get instant, scrolling, synced transcription
- Local speech-to-text via faster-whisper (multiple model sizes, automatic or manual GPU/CPU selection)
- Optional speaker diarization (pyannote.audio) - labels who is speaking ("Person A" / "Person B")
- Optional sound and music event tagging (PANNs) - e.g. "[Music]", "[Applause]"
- Optional online lookup for commercial music: cover art (iTunes) and official lyrics (LRCLIB), combined with AI-generated timestamps for accurate sync
- Modular installer - install only the components you need, add or remove them later from Settings
- Fully offline by default; online features are opt-in and disabled out of the box

## Installation

1. Download the latest Lyrix-Setup exe file from the Releases page
2. Run the installer and choose which AI components to install (Whisper, speaker separation, sound recognition, optional NVIDIA GPU acceleration)
3. Launch Lyrix, open an audio file, and watch the lyrics scroll in sync

Windows may show a "Windows protected your PC" SmartScreen warning because the app is not code-signed yet. Click "More info" then "Run anyway" to continue.

## System requirements

- Windows 10 or 11 (64-bit)
- Roughly 1-3 GB free disk space, depending on which AI components you install
- NVIDIA GPU optional but recommended for faster transcription

## Privacy

Lyrix processes everything locally by default. Online features (cover art and lyrics lookup) are switched off by default and can be enabled individually in Settings.

## License

Lyrix's own code is released under the MIT License. It bundles or downloads third-party AI models (Whisper, pyannote.audio, PANNs), which are subject to their own licenses - see the respective upstream projects for details.

## Credits

Built with faster-whisper, pyannote.audio, PANNs, PySide6, LRCLIB, and the iTunes Search API.
