#!/usr/bin/env python3
"""
Faceless Video Harness Agent
Complete video creation pipeline with avatars, backgrounds, music.
"""
import os
import sys
import json
import asyncio
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List
from dataclasses import dataclass, field

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "web"))

@dataclass
class VideoConfig:
    """Video generation configuration."""
    width: int = 1080
    height: int = 1920
    fps: int = 30
    video_bitrate: str = "6M"
    audio_bitrate: str = "192k"
    codec: str = "libx264"
    profile: str = "high"
    preset: str = "medium"
    crf: int = 20
    
@dataclass
class VideoJob:
    """Video generation job state."""
    job_id: str
    persona: str
    topic: str
    duration: int = 30
    language: str = "vi"
    status: str = "pending"
    progress: int = 0
    step: str = ""
    script: Optional[str] = None
    voice_path: Optional[str] = None
    avatar_path: Optional[str] = None
    background_path: Optional[str] = None
    music_path: Optional[str] = None
    video_path: Optional[str] = None
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class FacelessHarness:
    """
    Main harness agent for faceless video creation.
    Orchestrates the full pipeline: script → voice → avatar → background → music → assembly
    """
    
    def __init__(self, config: Optional[VideoConfig] = None):
        self.config = config or VideoConfig()
        self.assets_dir = Path(__file__).parent.parent / "assets"
        self.output_dir = Path(__file__).parent.parent / "output"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load .env file
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip())
        
        # API keys from environment
        self.openrouter_key = os.environ.get("OPENAI_API_KEY", "") or os.environ.get("OPENROUTER_API_KEY", "")
        self.did_key = os.environ.get("DID_API_KEY", "")
        self.pixabay_key = os.environ.get("PIXABAY_API_KEY", "")
        
        # Persona definitions
        self.personas = {
            "cooking": {
                "name": "🍳 Ẩm Thực",
                "color": "#FF6B35",
                "music_query": "cooking background music upbeat",
                "image_dir": "cooking",
            },
            "horror": {
                "name": "👻 Chuyện Ma",
                "color": "#8B0000",
                "music_query": "horror suspense dark ambient",
                "image_dir": "horror",
            },
            "comedy": {
                "name": "😂 Hài Hước",
                "color": "#FFD700",
                "music_query": "comedy funny upbeat playful",
                "image_dir": "comedy",
            },
            "beauty": {
                "name": "💄 Làm Đẹp",
                "color": "#FF69B4",
                "music_query": "beauty elegant soft ambient",
                "image_dir": "beauty",
            },
            "mystery": {
                "name": "🕵️ Bí Ẩn",
                "color": "#4A0E4E",
                "music_query": "mystery suspense tension building",
                "image_dir": "mystery",
            },
            "motivation": {
                "name": "💪 Cảm Hứng",
                "color": "#00C853",
                "music_query": "motivational inspiring uplifting",
                "image_dir": "motivation",
            },
        }
    
    # ===== PIPELINE STEPS =====
    
    async def generate_script(self, job: VideoJob) -> str:
        """Step 1: Generate Vietnamese script using AI."""
        job.step = "📝 Generating script with AI..."
        job.progress = 5
        
        try:
            import httpx
            
            persona = self.personas.get(job.persona, self.personas["cooking"])
            
            resp = httpx.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.openrouter_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "moonshotai/kimi-k2.6:free",
                    "messages": [
                        {
                            "role": "system",
                            "content": f"""Write a {job.duration}-second Vietnamese {job.persona} video script.
Format: HOOK, SETUP, CONTENT, ENDING.
Be natural and engaging for TikTok/YouTube Shorts.
Output ONLY the script in Vietnamese, no explanations."""
                        },
                        {"role": "user", "content": f"Topic: {job.topic}"}
                    ],
                    "max_tokens": 400,
                    "temperature": 0.8,
                },
                timeout=25,
            )
            
            if resp.status_code == 200:
                text = resp.json()["choices"][0]["message"]["content"]
                # Clean thinking tags
                import re
                text = re.sub(r'<thinking>.*?</thinking>', '', text, flags=re.DOTALL).strip()
                text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
                if len(text) > 20:
                    job.script = text
                    job.progress = 25
                    return text
        except Exception as e:
            print(f"Script gen error: {e}")
        
        # Fallback script
        job.script = self._fallback_script(job)
        job.progress = 25
        return job.script
    
    async def generate_voice(self, job: VideoJob) -> str:
        """Step 2: Generate Vietnamese voice using Edge TTS."""
        job.step = "🎤 Generating voice..."
        job.progress = 30
        
        try:
            import edge_tts
            import re
            
            clean_text = re.sub(r'\[.*?\]', '', job.script).strip()
            if len(clean_text) < 10:
                return None
            
            voice = "vi-VN-HoaiMyNeural"
            output_path = str(self.output_dir / f"voice_{job.job_id}.mp3")
            
            # Calculate speech rate to match duration
            words = len(clean_text.split())
            target_rate = int((job.duration / (words / 3.5) - 1) * 100)
            rate = f"+{max(0, min(50, target_rate))}%"
            
            communicate = edge_tts.Communicate(clean_text, voice, rate=rate)
            await communicate.save(output_path)
            
            job.voice_path = output_path
            job.progress = 50
            return output_path
        except Exception as e:
            print(f"Voice gen error: {e}")
            return None
    
    async def generate_avatar(self, job: VideoJob) -> Optional[str]:
        """Step 3: Create talking avatar video using D-ID API."""
        job.step = "🧑 Creating avatar..."
        job.progress = 55
        
        if not self.did_key:
            print("No D-ID API key, skipping avatar")
            return None
        
        if not job.voice_path:
            print("No voice file, skipping avatar")
            return None
        
        try:
            import httpx
            
            # Step 3a: Upload audio to D-ID
            with open(job.voice_path, "rb") as f:
                audio_data = f.read()
            
            # Create talk with audio
            resp = httpx.post(
                "https://api.d-id.com/talks",
                headers={
                    "Authorization": f"Basic {self.did_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "script": {
                        "type": "audio",
                        "audio_url": f"data:audio/mp3;base64,{audio_data.hex()}"
                    },
                    "source_url": "https://create-images-results.d-id.com/DefaultPresenters/Noelle_f/image.jpeg",
                    "config": {
                        "result_format": "mp4",
                        "stitch": True,
                    }
                },
                timeout=30,
            )
            
            if resp.status_code != 201:
                print(f"D-ID create error: {resp.status_code} {resp.text[:200]}")
                return None
            
            talk_id = resp.json()["id"]
            
            # Step 3b: Poll for completion
            for _ in range(60):  # Max 5 minutes
                await asyncio.sleep(5)
                
                status_resp = httpx.get(
                    f"https://api.d-id.com/talks/{talk_id}",
                    headers={"Authorization": f"Basic {self.did_key}"},
                    timeout=15,
                )
                
                if status_resp.status_code == 200:
                    result = status_resp.json()
                    if result.get("status") == "done":
                        # Download avatar video
                        avatar_url = result.get("result_url")
                        if avatar_url:
                            output_path = str(self.output_dir / f"avatar_{job.job_id}.mp4")
                            download = httpx.get(avatar_url, timeout=60)
                            with open(output_path, "wb") as f:
                                f.write(download.content)
                            job.avatar_path = output_path
                            job.progress = 70
                            return output_path
                    elif result.get("status") == "error":
                        print(f"D-ID error: {result.get('error')}")
                        return None
            
            print("D-ID timeout")
            return None
        except Exception as e:
            print(f"Avatar gen error: {e}")
            return None
    
    async def get_background_music(self, job: VideoJob) -> Optional[str]:
        """Step 4: Get background music from Pixabay."""
        job.step = "🎵 Getting background music..."
        
        if not self.pixabay_key:
            print("No Pixabay API key, skipping music")
            return None
        
        try:
            import httpx
            
            persona = self.personas.get(job.persona, self.personas["cooking"])
            query = persona["music_query"]
            
            resp = httpx.get(
                "https://pixabay.com/api/music/",
                params={
                    "key": self.pixabay_key,
                    "q": query,
                    "order": "popular",
                    "per_page": 3,
                },
                timeout=15,
            )
            
            if resp.status_code == 200:
                data = resp.json()
                if data.get("hits"):
                    music_url = data["hits"][0]["audios"]["medium"]["url"]
                    output_path = str(self.output_dir / f"music_{job.job_id}.mp3")
                    download = httpx.get(music_url, timeout=30)
                    with open(output_path, "wb") as f:
                        f.write(download.content)
                    job.music_path = output_path
                    return output_path
        except Exception as e:
            print(f"Music fetch error: {e}")
        
        return None
    
    async def assemble_video(self, job: VideoJob) -> str:
        """Step 5: Assemble final video with FFmpeg."""
        job.step = "🎬 Assembling video..."
        job.progress = 75
        
        output_path = str(self.output_dir / f"final_{job.job_id}.mp4")
        
        # If we have avatar, use it as primary video
        if job.avatar_path and Path(job.avatar_path).exists():
            # Composite avatar over background images
            return await self._assemble_with_avatar(job, output_path)
        else:
            # Use dynamic video generator (images + Ken Burns)
            return await self._assemble_dynamic(job, output_path)
    
    async def _assemble_with_avatar(self, job: VideoJob, output_path: str) -> str:
        """Assemble video with avatar overlay on background."""
        # TODO: Implement avatar + background composition
        # For now, use avatar directly
        if job.avatar_path:
            import shutil
            shutil.copy2(job.avatar_path, output_path)
            job.video_path = output_path
            job.progress = 90
            return output_path
        return await self._assemble_dynamic(job, output_path)
    
    async def _assemble_dynamic(self, job: VideoJob, output_path: str) -> str:
        """Assemble video with dynamic images + Ken Burns."""
        try:
            from dynamic_video_gen import generate_video as gen_dynamic
            
            persona_key = job.persona
            result = gen_dynamic(
                script=job.script,
                persona_name=persona_key,
                duration=job.duration,
                output_path=output_path
            )
            
            if result:
                job.video_path = output_path
                job.progress = 90
                return output_path
        except Exception as e:
            print(f"Dynamic gen error: {e}")
        
        # Fallback to social video generator
        try:
            from social_video_gen import generate_video as gen_social
            result = gen_social(
                script=job.script,
                persona_name=self.personas.get(job.persona, {}).get("name", "cooking"),
                duration=job.duration,
                output_path=output_path
            )
            if result:
                job.video_path = output_path
                job.progress = 90
                return output_path
        except Exception as e:
            print(f"Social gen error: {e}")
        
        return output_path
    
    async def merge_audio(self, job: VideoJob) -> str:
        """Step 6: Merge voice + music + video."""
        job.step = "🔊 Merging audio..."
        
        if not job.video_path or not Path(job.video_path).exists():
            return job.video_path
        
        output_path = str(self.output_dir / f"merged_{job.job_id}.mp4")
        
        # If we have both voice and music, mix them
        if job.voice_path and job.music_path:
            # Mix voice + music, then merge with video
            mixed_audio = str(self.output_dir / f"mixed_{job.job_id}.mp3")
            
            cmd = [
                "ffmpeg", "-y",
                "-i", job.voice_path,
                "-i", job.music_path,
                "-filter_complex",
                "[0:a]volume=1.0[voice];[1:a]volume=0.3[music];[voice][music]amix=inputs=2:duration=first[out]",
                "-map", "[out]",
                "-c:a", "aac", "-b:a", "192k",
                mixed_audio
            ]
            subprocess.run(cmd, capture_output=True, timeout=30)
            
            if Path(mixed_audio).exists():
                job.voice_path = mixed_audio
        
        # Merge audio with video
        audio_path = job.voice_path
        if audio_path and Path(audio_path).exists():
            cmd = [
                "ffmpeg", "-y",
                "-i", job.video_path,
                "-i", audio_path,
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                "-map", "0:v:0", "-map", "1:a:0",
                "-movflags", "+faststart",
                "-shortest",
                output_path
            ]
            proc = subprocess.run(cmd, capture_output=True, timeout=60)
            if proc.returncode == 0 and Path(output_path).exists():
                job.video_path = output_path
                return output_path
        
        return job.video_path
    
    def verify_quality(self, job: VideoJob) -> Dict:
        """Step 7: Verify video quality."""
        job.step = "📊 Verifying quality..."
        
        if not job.video_path or not Path(job.video_path).exists():
            return {"score": 0, "error": "No video file"}
        
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", job.video_path
        ]
        proc = subprocess.run(cmd, capture_output=True, timeout=30)
        if proc.returncode != 0:
            return {"score": 0, "error": "ffprobe failed"}
        
        data = json.loads(proc.stdout.decode())
        v = next((s for s in data["streams"] if s["codec_type"] == "video"), {})
        a = next((s for s in data["streams"] if s["codec_type"] == "audio"), {})
        f = data["format"]
        
        vb = int(v.get("bit_rate", 0)) / 1000
        ab = int(a.get("bit_rate", 0)) / 1000
        fps_str = v.get("r_frame_rate", "0/1")
        try:
            n, d = map(int, fps_str.split("/"))
            fps = n / d if d else 0
        except:
            fps = 0
        
        profile = v.get("profile", "")
        ch = int(a.get("channels", 0))
        w, h = int(v.get("width", 0)), int(v.get("height", 0))
        
        score = 0
        if w >= 1080 and h >= 1920: score += 20
        if fps >= 30: score += 15
        if vb >= 3000: score += 25
        elif vb >= 2000: score += 18
        elif vb >= 1000: score += 10
        if ab >= 128: score += 20
        if ch >= 2: score += 10
        if "High" in profile: score += 10
        
        return {
            "score": score,
            "resolution": f"{w}x{h}",
            "fps": fps,
            "video_bitrate": f"{vb:.0f}kbps",
            "audio_bitrate": f"{ab:.0f}kbps",
            "channels": ch,
            "profile": profile,
            "size_mb": int(f.get("size", 0)) / 1024 / 1024,
            "duration": float(f.get("duration", 0)),
        }
    
    # ===== FULL PIPELINE =====
    
    async def run_pipeline(self, persona: str, topic: str, duration: int = 30, language: str = "vi") -> VideoJob:
        """Run the complete video generation pipeline."""
        job_id = datetime.now().strftime("%Y%m%d_%H%M%S")[:15]
        job = VideoJob(
            job_id=job_id,
            persona=persona,
            topic=topic,
            duration=duration,
            language=language,
        )
        
        job.status = "processing"
        
        try:
            # Step 1: Generate script
            await self.generate_script(job)
            
            # Step 2: Generate voice
            await self.generate_voice(job)
            
            # Step 3: Create avatar (if D-ID key available)
            await self.generate_avatar(job)
            
            # Step 4: Get background music
            await self.get_background_music(job)
            
            # Step 5: Assemble video
            await self.assemble_video(job)
            
            # Step 6: Merge audio
            await self.merge_audio(job)
            
            # Step 7: Verify quality
            quality = self.verify_quality(job)
            
            job.status = "completed"
            job.progress = 100
            job.step = f"✅ Complete! Quality: {quality.get('score', 0)}/100"
            
        except Exception as e:
            job.status = "failed"
            job.error = str(e)[:200]
            job.step = f"❌ Error: {str(e)[:100]}"
        
        return job
    
    # ===== HELPERS =====
    
    def _fallback_script(self, job: VideoJob) -> str:
        """Fallback script when AI unavailable."""
        templates = {
            "cooking": f"[HOOK] {job.topic} - Món ngon ai cũng làm được!\n[SETUP] Hôm nay mình sẽ hướng dẫn các bạn cách làm {job.topic} đơn giản tại nhà.\n[CONTENT] Đầu tiên, chuẩn bị nguyên liệu. Sau đó, làm theo các bước mình hướng dẫn.\n[ENDING] Thử ngay và comment kết quả nhé!",
            "horror": f"[HOOK] {job.topic} - Bạn có dám nghe?\n[SETUP] Chuyện xảy ra vào đêm khuya, khi mọi người đã ngủ say.\n[CONTENT] Bỗng nhiên, có tiếng động kỳ lạ phát ra từ góc phòng...\n[ENDING] Follow để xem tập tiếp theo!",
            "comedy": f"[HOOK] Khi {job.topic} trở thành thảm họa 😂\n[SETUP] Mọi chuyện bắt đầu từ một tình huống dở khóc dở cười.\n[CONTENT] Không ai ngờ được điều gì sẽ xảy ra tiếp theo!\n[ENDING] Follow để xem thêm nhiều tình huống hài hước!",
            "beauty": f"[HOOK] Bí quyết {job.topic} mà ai cũng cần biết!\n[SETUP] Hôm nay mình chia sẻ tips {job.topic} đơn giản nhất.\n[CONTENT] Chỉ cần 3 bước đơn giản, bạn sẽ có kết quả ngay.\n[ENDING] Thử ngay và comment kết quả nhé!",
            "mystery": f"[HOOK] {job.topic} - Sự thật không ai ngờ!\n[SETUP] Mọi người đều nghĩ họ biết sự thật...\n[CONTENT] Nhưng sự thật đằng sau còn kinh hoàng hơn nhiều.\n[ENDING] Follow để xem phần tiếp theo!",
            "motivation": f"[HOOK] {job.topic} - Câu chuyện truyền cảm hứng!\n[SETUP] Nhiều người nói rằng điều này là không thể.\n[CONTENT] Nhưng với sự kiên trì, mọi thứ đều có thể xảy ra.\n[ENDING] Bạn có tin vào phép màu? Follow để nghe thêm!",
        }
        return templates.get(job.persona, templates["cooking"])


# ===== CLI =====

async def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Faceless Video Harness")
    subparsers = parser.add_subparsers(dest="command")
    
    # Generate command
    gen_parser = subparsers.add_parser("generate", help="Full video generation")
    gen_parser.add_argument("--persona", default="cooking", choices=["cooking", "horror", "comedy", "beauty", "mystery", "motivation"])
    gen_parser.add_argument("--topic", required=True, help="Video topic")
    gen_parser.add_argument("--duration", type=int, default=30, help="Duration in seconds")
    gen_parser.add_argument("--language", default="vi")
    
    # Quality command
    qual_parser = subparsers.add_parser("quality", help="Check video quality")
    qual_parser.add_argument("--video", required=True, help="Video file path")
    
    args = parser.parse_args()
    
    if args.command == "generate":
        harness = FacelessHarness()
        job = await harness.run_pipeline(
            persona=args.persona,
            topic=args.topic,
            duration=args.duration,
            language=args.language,
        )
        print(f"\n{'='*60}")
        print(f"Job: {job.job_id}")
        print(f"Status: {job.status}")
        print(f"Progress: {job.progress}%")
        print(f"Step: {job.step}")
        if job.video_path:
            print(f"Video: {job.video_path}")
        if job.error:
            print(f"Error: {job.error}")
        print(f"{'='*60}")
    
    elif args.command == "quality":
        harness = FacelessHarness()
        job = VideoJob(job_id="check", persona="cooking", topic="check")
        job.video_path = args.video
        quality = harness.verify_quality(job)
        print(json.dumps(quality, indent=2))
    
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
