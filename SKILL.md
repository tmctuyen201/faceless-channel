# Harness Agent - Faceless Video Creation

## Overview
The harness agent orchestrates a complete faceless video creation pipeline for Vietnamese content (TikTok/YouTube Shorts). It generates scripts, voice, avatars, backgrounds, and music, then assembles everything into a polished video.

## Pipeline Steps
1. **Script Generation** - AI-generated Vietnamese scripts (OpenRouter API)
2. **Voice Synthesis** - Vietnamese TTS via Edge TTS (`vi-VN-HoaiMyNeural`)
3. **Avatar Creation** - Talking avatar via D-ID API (optional)
4. **Background Music** - Royalty-free music from Pixabay
5. **Video Assembly** - FFmpeg-based video assembly with Ken Burns effects
6. **Audio Merge** - Voice + music mixing and merging
7. **Quality Verification** - Automated quality scoring (resolution, bitrate, fps)

## Files
- `harness/agent.py` - Main pipeline agent (`FacelessHarness` class)
- `harness/mcp_server.py` - MCP server exposing tools for AI agents
- `harness/cli.py` - CLI entry point

## Personas
| Key | Name | Theme |
|-----|------|-------|
| cooking | 🍳 Ẩm Thực | Food/cooking content |
| horror | 👻 Chuyện Ma | Horror stories |
| comedy | 😂 Hài Hước | Comedy/funny |
| beauty | 💄 Làm Đẹp | Beauty tips |
| mystery | 🕵️ Bí Ẩn | Mystery/true crime |
| motivation | 💪 Cảm Hứng | Motivational |

## Usage

### CLI
```bash
python3 harness/cli.py generate --persona cooking --topic "Bánh bao"
python3 harness/cli.py script --persona horror --topic "Ngôi nhà ma"
python3 harness/cli.py quality --video output/final_xxx.mp4
python3 harness/cli.py personas
```

### MCP Tools
- `faceless_generate` - Full video generation
- `faceless_script` - Script-only generation
- `faceless_quality` - Video quality check
- `faceless_personas` - List available personas

### Environment Variables
- `OPENAI_API_KEY` or `OPENROUTER_API_KEY` - For script generation
- `DID_API_KEY` - For avatar creation (optional)
- `PIXABAY_API_KEY` - For background music (optional)

## Architecture
The agent uses an async pipeline pattern where each step updates the `VideoJob` state. Steps gracefully degrade if optional APIs are unavailable (avatar/music skipped, fallback scripts used).
