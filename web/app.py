"""
Faceless Channel Web App — Fixed Version
FastAPI backend + Linear-style frontend with video playback
"""

import os
import json
import uuid
import asyncio
import subprocess
import re
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from pydantic import BaseModel

# Load .env
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

app = FastAPI(title="Faceless Channel")

# Job storage
jobs = {}

# Personas
PERSONAS = {
    "cooking": {"name": "🍳 Ẩm Thực", "icon": "🍳", "color": "#FF6B35", "topics": ["Bánh bao", "Mì kéo", "Há cảo"]},
    "horror": {"name": "👻 Chuyện Ma", "icon": "👻", "color": "#8B0000", "topics": ["Phòng 404", "Ngôi nhà bỏ hoang"]},
    "comedy": {"name": "😂 Hài Hước", "icon": "😂", "color": "#FFD700", "topics": ["Sếp khó tính", "Đi phỏng vấn"]},
    "beauty": {"name": "💄 Làm Đẹp", "icon": "💄", "color": "#FF69B4", "topics": ["Chăm sóc da", "Trang điểm"]},
    "mystery": {"name": "🕵️ Bí Ẩn", "icon": "🕵️", "color": "#4A0E4E", "topics": ["Vụ mất tích", "Căn phòng khóa"]},
    "motivation": {"name": "💪 Cảm Hứng", "icon": "💪", "color": "#00C853", "topics": ["Khởi nghiệp", "Vượt khó"]},
}

class GenerateRequest(BaseModel):
    persona: str
    language: str = "vi"
    duration: int = 30
    custom_topic: Optional[str] = None

# ===== API =====

@app.get("/api/personas")
async def get_personas():
    return {"personas": PERSONAS}

@app.post("/api/generate")
async def generate_video(req: GenerateRequest, bg: BackgroundTasks):
    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {
        "job_id": job_id, "status": "pending", "persona": req.persona,
        "progress": 0, "step": "Queued", "script": None, "video_url": None,
        "created_at": datetime.now().isoformat(), "error": None,
    }
    bg.add_task(run_pipeline, job_id, req)
    return {"job_id": job_id}

@app.get("/api/job/{job_id}")
async def get_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    return jobs[job_id]

@app.get("/api/jobs")
async def list_jobs():
    return {"jobs": list(jobs.values())}

@app.get("/api/video/{job_id}")
async def stream_video(job_id: str):
    """Stream video for browser playback."""
    if job_id not in jobs:
        raise HTTPException(404)
    job = jobs[job_id]
    if job["status"] != "completed" or not job.get("video_path"):
        raise HTTPException(400, "Not ready")
    
    path = Path(job["video_path"])
    if not path.exists():
        raise HTTPException(404, "File missing")
    
    return FileResponse(
        str(path),
        media_type="video/mp4",
        headers={"Accept-Ranges": "bytes", "Content-Type": "video/mp4"}
    )

@app.get("/api/download/{job_id}")
async def download_video(job_id: str):
    """Download video as attachment."""
    if job_id not in jobs:
        raise HTTPException(404)
    job = jobs[job_id]
    if job["status"] != "completed" or not job.get("video_path"):
        raise HTTPException(400, "Not ready")
    
    path = Path(job["video_path"])
    if not path.exists():
        raise HTTPException(404)
    
    return FileResponse(
        str(path),
        media_type="video/mp4",
        filename=f"faceless_{job_id}.mp4",
        headers={"Content-Disposition": f'attachment; filename="faceless_{job_id}.mp4"'}
    )

# ===== PIPELINE =====

async def run_pipeline(job_id: str, req: GenerateRequest):
    """Full pipeline: script → voice → video."""
    job = jobs[job_id]
    persona = PERSONAS.get(req.persona, PERSONAS["cooking"])
    topic = req.custom_topic or persona["topics"][0]
    
    try:
        # === STEP 1: Generate Script (0-25%) ===
        job["status"] = "processing"
        job["step"] = "📝 Step 1/4: Generating script with AI..."
        job["progress"] = 5
        
        script = await generate_script(topic, req.persona, req.duration)
        job["script"] = script
        job["progress"] = 25
        await asyncio.sleep(0.5)
        
        # === STEP 2: Generate Voice (25-50%) ===
        job["step"] = "🎤 Step 2/4: Generating Vietnamese voice..."
        job["progress"] = 30
        
        voice_path = await generate_voice(script, req.duration, job)
        job["progress"] = 50
        await asyncio.sleep(0.5)
        
        # === STEP 3: Create Visuals (50-75%) ===
        job["step"] = "🎨 Step 3/4: Creating visuals..."
        job["progress"] = 55
        
        video_path = await create_video(script, persona, req.duration, req.language, job)
        job["progress"] = 75
        await asyncio.sleep(0.5)
        
        # === STEP 4: Final Assembly (75-100%) ===
        job["step"] = "🎬 Step 4/4: Assembling final video..."
        job["progress"] = 85
        
        # Merge audio + video if voice exists
        final_path = video_path
        if voice_path and Path(voice_path).exists():
            final_path = await merge_audio_video(video_path, voice_path, job_id)
        
        job["progress"] = 95
        job["step"] = "✅ Finalizing..."
        await asyncio.sleep(0.5)
        
        # Done!
        job["status"] = "completed"
        job["progress"] = 100
        job["step"] = "✅ Complete! Click play to watch."
        job["video_path"] = final_path
        job["video_url"] = f"/api/video/{job_id}"
        
    except Exception as e:
        job["status"] = "failed"
        job["error"] = str(e)[:200]
        job["step"] = f"❌ Error: {str(e)[:100]}"

async def generate_script(topic: str, persona: str, duration: int) -> str:
    """Generate Vietnamese script via OpenRouter."""
    import httpx
    
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key or len(api_key) < 10:
        return fallback_script(topic, persona, duration)
    
    models = ["moonshotai/kimi-k2.6:free", "google/gemma-4-26b-a4b-it:free"]
    
    for model in models:
        try:
            resp = httpx.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "HTTP-Referer": "https://aistudy.io.vn"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": f"Write a {duration}-second Vietnamese {persona} video script. Format: HOOK, SETUP, CONTENT, ENDING. Be natural and engaging. Output ONLY the script in Vietnamese."},
                        {"role": "user", "content": f"Topic: {topic}"}
                    ],
                    "max_tokens": 300, "temperature": 0.8,
                },
                timeout=20,
            )
            if resp.status_code == 200:
                text = resp.json()["choices"][0]["message"]["content"]
                # Clean thinking tags
                text = re.sub(r'<thinking>.*?</thinking>', '', text, flags=re.DOTALL).strip()
                text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
                if len(text) > 20:
                    return text
        except:
            continue
    
    return fallback_script(topic, persona, duration)

def fallback_script(topic: str, persona: str, duration: int) -> str:
    """Fallback script when API unavailable."""
    scripts = {
        "cooking": f"[HOOK] {topic} - Món ngon ai cũng làm được!\n[SETUP] Hôm nay mình sẽ hướng dẫn các bạn cách làm {topic} đơn giản tại nhà.\n[CONTENT] Đầu tiên, chuẩn bị nguyên liệu. Sau đó, làm theo các bước mình hướng dẫn.\n[ENDING] Thử ngay và comment kết quả nhé! Follow để xem thêm nhiều món ngon!",
        "horror": f"[HOOK] {topic} - Bạn có dám nghe?\n[SETUP] Chuyện xảy ra vào đêm khuya, khi mọi người đã ngủ say.\n[CONTENT] Bỗng nhiên, có tiếng động kỳ lạ phát ra từ góc phòng...\n[ENDING] Follow để xem tập tiếp theo. Comment số 3 nếu bạn dám nghe tiếp!",
        "comedy": f"[HOOK] Khi {topic} trở thành thảm họa 😂\n[SETUP] Mọi chuyện bắt đầu từ một tình huống dở khóc dở cười.\n[CONTENT] Không ai ngờ được điều gì sẽ xảy ra tiếp theo!\n[ENDING] Follow để xem thêm nhiều tình huống hài hước!",
        "beauty": f"[HOOK] Bí quyết {topic} mà ai cũng cần biết!\n[SETUP] Hôm nay mình chia sẻ tips {topic} đơn giản nhất.\n[CONTENT] Chỉ cần 3 bước đơn giản, bạn sẽ có kết quả ngay.\n[ENDING] Thử ngay và comment kết quả nhé!",
        "mystery": f"[HOOK] {topic} - Sự thật không ai ngờ!\n[SETUP] Mọi người đều nghĩ họ biết sự thật...\n[CONTENT] Nhưng sự thật đằng sau còn kinh hoàng hơn nhiều.\n[ENDING] Follow để xem phần tiếp theo!",
        "motivation": f"[HOOK] {topic} - Câu chuyện truyền cảm hứng!\n[SETUP] Nhiều người nói rằng điều này là không thể.\n[CONTENT] Nhưng với sự kiên trì, mọi thứ đều có thể xảy ra.\n[ENDING] Bạn có tin vào phép màu? Follow để nghe thêm câu chuyện!",
    }
    return scripts.get(persona, scripts["cooking"])

async def generate_voice(script: str, duration: int, job: dict) -> str:
    """Generate voice using Edge TTS (free)."""
    try:
        import edge_tts
        
        # Extract clean text (remove [TAGS])
        clean_text = re.sub(r'\[.*?\]', '', script).strip()
        if len(clean_text) < 10:
            return None
        
        voice = "vi-VN-HoaiMyNeural"
        output_path = f"/tmp/voice_{job['job_id']}.mp3"
        
        # Calculate rate to match duration
        words = len(clean_text.split())
        target_rate = int((duration / (words / 3.5) - 1) * 100)
        rate = f"+{max(0, min(50, target_rate))}%"
        
        communicate = edge_tts.Communicate(clean_text, voice, rate=rate)
        await communicate.save(output_path)
        
        return output_path
    except Exception as e:
        return None

async def create_video(script: str, persona: dict, duration: int, language: str, job: dict) -> str:
    """Create dynamic video with real images, Ken Burns effects, and transitions."""
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
    
    job_id = job["job_id"]
    output_path = f"/tmp/video_{job_id}.mp4"
    
    # Clean text for display
    clean_script = re.sub(r'\[.*?\]', '', script)
    
    # Try dynamic generator first (real images + Ken Burns)
    try:
        from dynamic_video_gen import generate_video as gen_dynamic
        # Extract persona key from persona dict
        persona_key = None
        for k, v in PERSONAS.items():
            if v["name"] == persona["name"] or v == persona:
                persona_key = k
                break
        if not persona_key:
            persona_key = "cooking"
        
        result = gen_dynamic(
            script=clean_script,
            persona_name=persona_key,
            duration=duration,
            output_path=output_path
        )
        if result:
            return output_path
    except Exception as e:
        print(f"Dynamic gen failed: {e}")
    
    # Fallback to social video generator
    try:
        from social_video_gen import generate_video as gen_social
        result = gen_social(
            script=clean_script,
            persona_name=persona["name"],
            duration=duration,
            output_path=output_path
        )
        if result:
            return output_path
    except Exception as e:
        print(f"Social gen failed: {e}")
    
    # Last resort: simple ffmpeg
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=0x0F3460:s=1080x1920:d={duration},format=yuv420p",
        "-f", "lavfi", "-i", f"sine=frequency=220:duration={duration}",
        "-vf", f"drawtext=text='{persona['name']}':fontsize=48:fontcolor=white:x=(w-text_w)/2:y=h*0.4:fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "-c:v", "libx264", "-profile:v", "high", "-preset", "medium", "-crf", "20",
        "-maxrate", "6M", "-bufsize", "12M",
        "-r", "30", "-g", "60",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart", "-shortest",
        output_path
    ]
    subprocess.run(cmd, capture_output=True, timeout=60)
    
    return output_path

async def merge_audio_video(video_path: str, audio_path: str, job_id: str) -> str:
    """Merge generated voice with video — output stereo audio at 192kbps."""
    output_path = f"/tmp/final_{job_id}.mp4"
    
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-map", "0:v:0", "-map", "1:a:0",
        "-movflags", "+faststart",
        "-shortest",
        output_path
    ]
    
    proc = subprocess.run(cmd, capture_output=True, timeout=30)
    
    if proc.returncode == 0 and Path(output_path).exists():
        return output_path
    return video_path

# ===== FRONTEND =====

@app.get("/", response_class=HTMLResponse)
async def index():
    return """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Faceless Channel</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Inter',sans-serif;background:#0A0A0F;color:#E8E8ED;min-height:100vh}
.app{max-width:800px;margin:0 auto;padding:40px 20px}
.header{text-align:center;margin-bottom:40px}
.header h1{font-size:42px;font-weight:700;background:linear-gradient(135deg,#fff,#7C5CFC);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:8px}
.header p{color:#8B8B9E;font-size:16px}
.badge{display:inline-block;background:rgba(124,92,252,0.15);border:1px solid rgba(124,92,252,0.3);padding:4px 14px;border-radius:100px;font-size:12px;color:#7C5CFC;margin-bottom:16px}
.section{margin-bottom:24px}
.section-label{font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:1.5px;color:#5C5C72;margin-bottom:12px}
.personas{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:24px}
.persona{background:#12121A;border:1px solid #1F1F2E;border-radius:12px;padding:20px;cursor:pointer;transition:all .2s;text-align:center}
.persona:hover{border-color:#7C5CFC;transform:translateY(-2px)}
.persona.selected{border-color:#7C5CFC;box-shadow:0 0 0 1px #7C5CFC,0 8px 24px rgba(124,92,252,0.2)}
.persona-icon{font-size:28px;margin-bottom:8px}
.persona-name{font-size:14px;font-weight:600}
.config{background:#12121A;border:1px solid #1F1F2E;border-radius:12px;padding:24px;margin-bottom:24px}
.config-row{display:flex;gap:16px;margin-bottom:16px}
.field{flex:1}
.field label{display:block;font-size:12px;color:#8B8B9E;margin-bottom:6px}
.field input,.field select{width:100%;background:#1A1A25;border:1px solid #1F1F2E;border-radius:8px;padding:10px 14px;color:#E8E8ED;font-size:14px;font-family:inherit}
.field input:focus,.field select:focus{outline:none;border-color:#7C5CFC}
select{cursor:pointer;appearance:none;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%238B8B9E' d='M6 8L1 3h10z'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right 14px center;padding-right:36px}
.btn{width:100%;padding:14px;background:linear-gradient(135deg,#7C5CFC,#9B7FFF);border:none;border-radius:10px;color:white;font-size:15px;font-weight:600;font-family:inherit;cursor:pointer;transition:all .2s;display:flex;align-items:center;justify-content:center;gap:8px}
.btn:hover{transform:translateY(-1px);box-shadow:0 8px 24px rgba(124,92,252,0.4)}
.btn:disabled{opacity:.5;cursor:not-allowed;transform:none;box-shadow:none}
.btn .spinner{width:18px;height:18px;border:2px solid rgba(255,255,255,.3);border-top-color:white;border-radius:50%;animation:spin .8s linear infinite;display:none}
.btn.loading .spinner{display:block}
.btn.loading .btn-text{display:none}
@keyframes spin{to{transform:rotate(360deg)}}

/* Progress */
.progress{background:#12121A;border:1px solid #1F1F2E;border-radius:12px;padding:24px;margin-bottom:24px;display:none}
.progress.active{display:block}
.progress-header{display:flex;justify-content:space-between;margin-bottom:16px}
.progress-title{font-size:15px;font-weight:600}
.progress-pct{font-size:28px;font-weight:700;color:#7C5CFC}
.progress-bar{width:100%;height:8px;background:#1A1A25;border-radius:4px;overflow:hidden;margin-bottom:12px}
.progress-fill{height:100%;background:linear-gradient(90deg,#7C5CFC,#E94560);border-radius:4px;transition:width .3s;width:0%}
.progress-step{font-size:13px;color:#8B8B9E}
.progress-steps{margin-top:16px;display:flex;flex-direction:column;gap:8px}
.step{display:flex;align-items:center;gap:10px;font-size:13px;color:#5C5C72}
.step.active{color:#7C5CFC;font-weight:500}
.step.done{color:#00C853}
.step-icon{width:20px;height:20px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:11px;background:#1A1A25}
.step.active .step-icon{background:#7C5CFC;color:white}
.step.done .step-icon{background:#00C853;color:white}

/* Result */
.result{background:#12121A;border:1px solid #1F1F2E;border-radius:12px;padding:24px;margin-bottom:24px;display:none}
.result.active{display:block}
.result-title{font-size:18px;font-weight:600;color:#00C853;margin-bottom:20px;display:flex;align-items:center;gap:8px}
.video-container{width:100%;max-width:360px;margin:0 auto 20px;border-radius:12px;overflow:hidden;background:#000}
.video-container video{width:100%;display:block}
.script-box{background:#1A1A25;border-radius:8px;padding:16px;font-size:13px;line-height:1.8;color:#8B8B9E;white-space:pre-wrap;max-height:150px;overflow-y:auto;margin-bottom:20px}
.actions{display:flex;gap:12px}
.btn-secondary{flex:1;padding:12px;background:#1A1A25;border:1px solid #1F1F2E;border-radius:8px;color:#E8E8ED;font-size:13px;font-weight:500;font-family:inherit;cursor:pointer;transition:all .2s}
.btn-secondary:hover{border-color:#7C5CFC;background:#222233}

/* Toast */
.toast-wrap{position:fixed;top:20px;right:20px;z-index:999;display:flex;flex-direction:column;gap:8px}
.toast{background:#12121A;border:1px solid #1F1F2E;border-radius:8px;padding:14px 18px;display:flex;align-items:center;gap:10px;animation:slideIn .3s;box-shadow:0 8px 24px rgba(0,0,0,.4);font-size:13px}
.toast.success{border-left:3px solid #00C853}
.toast.error{border-left:3px solid #FF4757}
.toast.info{border-left:3px solid #7C5CFC}
@keyframes slideIn{from{transform:translateX(100%);opacity:0}to{transform:translateX(0);opacity:1}}

.jobs{margin-top:32px}
.job{background:#12121A;border:1px solid #1F1F2E;border-radius:8px;padding:14px 18px;margin-bottom:8px;display:flex;align-items:center;justify-content:space-between;transition:all .2s}
.job:hover{border-color:#2A2A3A;background:#1A1A25}
.job[onclick]{cursor:pointer}
.job[onclick]:hover{border-color:#7C5CFC;box-shadow:0 0 0 1px rgba(124,92,252,0.2)}
.job-left{display:flex;align-items:center;gap:12px}
.job-dot{width:8px;height:8px;border-radius:50%}
.job-dot.pending{background:#FFA502}
.job-dot.processing{background:#7C5CFC;animation:pulse 1s infinite}
.job-dot.completed{background:#00C853}
.job-dot.failed{background:#FF4757}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
.job-name{font-size:14px;font-weight:500}
.job-time{font-size:11px;color:#5C5C72}
.job-step{font-size:12px;color:#8B8B9E}
.footer{text-align:center;padding:40px 0;color:#5C5C72;font-size:12px}
.footer a{color:#7C5CFC;text-decoration:none}
@media(max-width:600px){.personas{grid-template-columns:repeat(2,1fr)}.config-row{flex-direction:column}.header h1{font-size:28px}}
</style>
</head>
<body>
<div class="app">
    <div class="header">
        <div class="badge">AI Video Generator</div>
        <h1>Faceless Channel</h1>
        <p>Choose persona → Generate AI video → Watch & Download</p>
    </div>

    <div class="section">
        <div class="section-label">① Choose Persona</div>
        <div class="personas" id="personas"></div>
    </div>

    <div class="section">
        <div class="section-label">② Configure</div>
        <div class="config">
            <div class="config-row">
                <div class="field"><label>Language</label><select id="lang"><option value="vi">🇻🇳 Vietnamese</option><option value="th">🇹🇭 Thai</option><option value="en">🇺🇸 English</option></select></div>
                <div class="field"><label>Duration</label><select id="dur"><option value="15">15s</option><option value="30" selected>30s</option><option value="60">60s</option></select></div>
                <div class="field"><label>Topic</label><input type="text" id="topic" placeholder="Custom topic..."></div>
            </div>
            <button class="btn" id="genBtn" onclick="generate()"><div class="spinner"></div><span class="btn-text">🎬 Generate Video</span></button>
        </div>
    </div>

    <div class="progress" id="progress">
        <div class="progress-header">
            <div class="progress-title" id="progTitle">Generating...</div>
            <div class="progress-pct" id="progPct">0%</div>
        </div>
        <div class="progress-bar"><div class="progress-fill" id="progFill"></div></div>
        <div class="progress-step" id="progStep">Initializing...</div>
        <div class="progress-steps">
            <div class="step" id="step1"><div class="step-icon">1</div> Generate Script</div>
            <div class="step" id="step2"><div class="step-icon">2</div> Generate Voice</div>
            <div class="step" id="step3"><div class="step-icon">3</div> Create Visuals</div>
            <div class="step" id="step4"><div class="step-icon">4</div> Assemble Video</div>
        </div>
    </div>

    <div class="result" id="result">
        <div class="result-title">✅ Video Ready!</div>
        <div class="video-container">
            <video id="videoPlayer" controls preload="metadata"></video>
        </div>
        <div class="script-box" id="scriptBox"></div>
        <div class="actions">
            <button class="btn-secondary" onclick="downloadVideo()">⬇️ Download MP4</button>
            <button class="btn-secondary" onclick="generate()">🔄 New Video</button>
        </div>
    </div>

    <div class="jobs" id="jobs"></div>

    <div class="footer">Built by <a href="#">aistudy.io.vn</a> • Powered by OpenRouter AI</div>
</div>

<div class="toast-wrap" id="toasts"></div>

<script>
let selected=null, jobId=null, poll=null;

const P={
    cooking:{name:'🍳 Ẩm Thực',icon:'🍳',color:'#FF6B35'},
    horror:{name:'👻 Chuyện Ma',icon:'👻',color:'#8B0000'},
    comedy:{name:'😂 Hài Hước',icon:'😂',color:'#FFD700'},
    beauty:{name:'💄 Làm Đẹp',icon:'💄',color:'#FF69B4'},
    mystery:{name:'🕵️ Bí Ẩn',icon:'🕵️',color:'#4A0E4E'},
    motivation:{name:'💪 Cảm Hứng',icon:'💪',color:'#00C853'}
};

function init(){
    const g=document.getElementById('personas');
    g.innerHTML=Object.entries(P).map(([k,v])=>`
        <div class="persona" data-p="${k}" onclick="sel('${k}')">
            <div class="persona-icon">${v.icon}</div>
            <div class="persona-name">${v.name}</div>
        </div>
    `).join('');
    loadJobs();
}

function sel(k){
    selected=k;
    document.querySelectorAll('.persona').forEach(c=>c.classList.toggle('selected',c.dataset.p===k));
    toast('info',`Selected: ${P[k].name}`);
}

async function generate(){
    if(!selected){toast('error','Select a persona first!');return}
    const btn=document.getElementById('genBtn');
    btn.classList.add('loading');btn.disabled=true;

    try{
        const r=await fetch('/api/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({persona:selected,language:document.getElementById('lang').value,duration:+document.getElementById('dur').value,custom_topic:document.getElementById('topic').value||null})});
        const d=await r.json();
        jobId=d.job_id;

        document.getElementById('progress').classList.add('active');
        document.getElementById('result').classList.remove('active');
        resetSteps();
        pollStatus();
    }catch(e){toast('error','Failed to start');btn.classList.remove('loading');btn.disabled=false}
}

function pollStatus(){
    if(poll)clearInterval(poll);
    poll=setInterval(async()=>{
        try{
            const r=await fetch(`/api/job/${jobId}`);
            const j=await r.json();

            document.getElementById('progPct').textContent=j.progress+'%';
            document.getElementById('progFill').style.width=j.progress+'%';
            document.getElementById('progStep').textContent=j.step;

            // Update step indicators
            if(j.progress>=5)setActive('step1');
            if(j.progress>=25)setDone('step1');
            if(j.progress>=30)setActive('step2');
            if(j.progress>=50)setDone('step2');
            if(j.progress>=55)setActive('step3');
            if(j.progress>=75)setDone('step3');
            if(j.progress>=85)setActive('step4');
            if(j.progress>=100)setDone('step4');

            if(j.status==='completed'){
                clearInterval(poll);
                showResult(j);
            }else if(j.status==='failed'){
                clearInterval(poll);
                toast('error',j.error||'Generation failed');
                resetBtn();
            }
        }catch(e){}
    },800);
}

function setActive(id){document.getElementById(id).className='step active'}
function setDone(id){document.getElementById(id).className='step done'}
function resetSteps(){['step1','step2','step3','step4'].forEach(id=>document.getElementById(id).className='step')}

function showResult(j){
    document.getElementById('progress').classList.remove('active');
    document.getElementById('result').classList.add('active');

    const player=document.getElementById('videoPlayer');
    player.src=`/api/video/${j.job_id}?t=${Date.now()}`;
    player.load();

    if(j.script)document.getElementById('scriptBox').textContent=j.script;

    toast('success','Video ready! Click play to watch.');
    resetBtn();
    loadJobs();
}

function downloadVideo(){if(jobId)window.open(`/api/download/${jobId}`,'_blank')}
function resetBtn(){document.getElementById('genBtn').classList.remove('loading');document.getElementById('genBtn').disabled=false}

async function loadJobs(){
    try{
        const r=await fetch('/api/jobs');
        const d=await r.json();
        const c=document.getElementById('jobs');
        if(!d.jobs.length){c.innerHTML='<div class="section-label">Recent Jobs</div><p style="color:#5C5C72;text-align:center;padding:32px">No jobs yet</p>';return}
        c.innerHTML='<div class="section-label">Recent Jobs</div>'+d.jobs.reverse().slice(0,10).map(j=>{
            const p=P[j.persona]||{icon:'🎬',name:j.persona};
            const clickable=j.status==='completed'?'cursor:pointer':'';
            return `<div class="job" style="${clickable}" onclick="viewJob('${j.job_id}','${j.status}')">
                <div class="job-left">
                    <div class="job-dot ${j.status}"></div>
                    <div>
                        <div class="job-name">${p.icon} ${p.name}</div>
                        <div class="job-time">${new Date(j.created_at).toLocaleTimeString()}</div>
                    </div>
                </div>
                <div style="display:flex;align-items:center;gap:8px">
                    <div class="job-step">${j.step}</div>
                    ${j.status==='completed'?'<span style="font-size:16px">▶️</span>':''}
                </div>
            </div>`;
        }).join('');
    }catch(e){}
}

async function viewJob(id,status){
    if(status!=='completed')return;
    jobId=id;
    try{
        const r=await fetch(`/api/job/${id}`);
        const j=await r.json();

        // Show result panel
        document.getElementById('progress').classList.remove('active');
        document.getElementById('result').classList.add('active');

        // Load video
        const player=document.getElementById('videoPlayer');
        player.src=`/api/video/${id}?t=${Date.now()}`;
        player.load();

        // Load script
        if(j.script)document.getElementById('scriptBox').textContent=j.script;

        toast('info','Loading video...');
    }catch(e){toast('error','Failed to load video')}
}

function toast(t,m){
    const c=document.getElementById('toasts');
    const icons={success:'✅',error:'❌',info:'ℹ️'};
    const el=document.createElement('div');
    el.className=`toast ${t}`;
    el.innerHTML=`<span>${icons[t]}</span><span>${m}</span>`;
    c.appendChild(el);
    setTimeout(()=>{el.style.opacity='0';setTimeout(()=>el.remove(),300)},3000);
}

init();
</script>
</body>
</html>"""

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
