# Faceless Channel - AI Video Generator

AI-powered faceless video channel system for TikTok, YouTube Shorts, and Instagram Reels.

**Target Market:** Vietnam  
**Domain:** aistudy.io.vn

## Features

- 6 Personas: Cooking, Horror, Comedy, Beauty, Mystery, Motivation
- AI Script Generation: Vietnamese content via OpenRouter (Kimi K2.6)
- Text-to-Speech: Edge TTS with Vietnamese voices
- Social Media Quality Video: H.264 High @ 6Mbps, 30fps, Stereo audio
- Platform Ready: Meets TikTok/YouTube Shorts/Instagram Reels standards
- Web UI: FastAPI backend + Linear-style dark theme frontend

## Video Quality Standards

| Metric | Standard | Our Output |
|--------|----------|------------|
| Resolution | 1080x1920 | 1080x1920 |
| Frame Rate | 30fps | 30fps |
| Video Bitrate | 2-6 Mbps | 6 Mbps |
| Audio | Stereo 128+kbps | Stereo 192kbps |
| Codec | H.264 High | H.264 High |

## Quick Start

```bash
pip install fastapi uvicorn openai pyyaml edge-tts
export OPENROUTER_API_KEY="your...hon3 web/app.py
```

Open http://localhost:8080 and start generating videos!

## Tech Stack

- Backend: FastAPI + Uvicorn
- AI: OpenRouter (Kimi K2.6 free model)
- TTS: Edge TTS
- Video: FFmpeg + Python
- Frontend: Vanilla HTML/CSS/JS (Linear-style dark theme)

## License

MIT
