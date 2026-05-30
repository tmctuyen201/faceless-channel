#!/usr/bin/env python3
"""
Social Media Video Generator v6 - Balanced quality + file size.
Generates videos that meet TikTok/YouTube Shorts/Instagram Reels standards.
"""
import os
import subprocess
import json
from datetime import datetime

STYLES = {
    "cooking": {"bg": "0x1a472a", "accent": "0xFF6B35"},
    "horror": {"bg": "0x1a1a2e", "accent": "0xE94560"},
    "comedy": {"bg": "0x2d1b69", "accent": "0xFFD700"},
    "beauty": {"bg": "0x2d1b4e", "accent": "0xFF69B4"},
    "mystery": {"bg": "0x0f0f23", "accent": "0x00FF88"},
    "motivation": {"bg": "0x0f3460", "accent": "0x16C79A"},
}

def esc(s):
    return s.replace("'", "").replace(":", " ").replace("%", " ").replace("\\", " ")[:55]

def generate_video(script, persona_name, duration=15, output_path=None):
    if output_path is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"/home/admin/faceless-channel/output/{ts}_social.mp4"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    style = STYLES.get(persona_name, STYLES["motivation"])
    lines = [l.strip() for l in script.split("\n") if l.strip()][:5]
    if not lines:
        lines = ["AI Generated Content", "Faceless Channel"]

    filters = []

    # 1. Subtle noise for texture (increases bitrate reasonably)
    filters.append("noise=alls=8:allf=t+u")

    # 2. Title (fade in at 0.3s)
    filters.append(
        f"drawtext=text='{esc(persona_name.upper())}':fontsize=52:fontcolor=white:"
        f"x=(w-text_w)/2:y=h*0.08:"
        f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
        f"alpha='if(lt(t,0.3),0,if(lt(t,0.8),(t-0.3)*2,1))'"
    )

    # 3. Subtitle
    filters.append(
        f"drawtext=text='AI Generated Content':fontsize=28:fontcolor={style['accent']}:"
        f"x=(w-text_w)/2:y=h*0.14:"
        f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
        f"alpha='if(lt(t,0.8),0,if(lt(t,1.3),(t-0.8)*2,1))'"
    )

    # 4. Separator
    filters.append(
        f"drawtext=text='____________________________':fontsize=20:fontcolor=0x333344:"
        f"x=(w-text_w)/2:y=h*0.19:"
        f"alpha='if(lt(t,1.3),0,if(lt(t,1.8),(t-1.3)*2,1))'"
    )

    # 5. Content lines with fade + slide
    y_positions = [0.27, 0.37, 0.47, 0.57, 0.67]
    delays = [1.8, 2.8, 3.8, 4.8, 5.8]

    for i, line in enumerate(lines[:5]):
        safe = esc(line)
        y = y_positions[i]
        d = delays[i]

        if i == 0:
            color, size = "white", 38
        elif i % 2 == 1:
            color, size = style["accent"], 34
        else:
            color, size = "0xCCCCCC", 34

        filters.append(
            f"drawtext=text='{safe}':fontsize={size}:fontcolor={color}:"
            f"x=(w-text_w)/2:y='h*{y}+20*max(0,1-(t-{d})*3)':"
            f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
            f"alpha='if(lt(t,{d}),0,min(1,(t-{d})*2))'"
        )

    # 6. CTA pulse (appears at 7s)
    filters.append(
        f"drawtext=text='Follow de xem them video hay!':fontsize=28:fontcolor={style['accent']}:"
        f"x=(w-text_w)/2:y=h*0.78:"
        f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
        f"alpha='if(lt(t,7),0,(0.6+0.4*sin(2*3.14159*t/1.5)))'"
    )

    # 7. Bottom separator + branding
    filters.append(
        f"drawtext=text='____________________________':fontsize=20:fontcolor=0x333344:"
        f"x=(w-text_w)/2:y=h*0.83"
    )
    filters.append(
        f"drawtext=text='aistudy.io.vn':fontsize=36:fontcolor={style['accent']}:"
        f"x=(w-text_w)/2:y=h*0.87:"
        f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
        f"alpha='if(lt(t,7.5),0,min(1,(t-7.5)*2))'"
    )
    filters.append(
        f"drawtext=text='%{{pts\\\\:hms}}':fontsize=18:fontcolor=0x555566:"
        f"x=w*0.8:y=h*0.94"
    )

    vf = ",".join(filters)

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c={style['bg']}:s=1080x1920:d={duration},format=yuv420p",
        "-f", "lavfi", "-i", f"sine=frequency=220:duration={duration}:sample_rate=48000",
        "-vf", vf,
        # VIDEO: Social Media Standards
        "-c:v", "libx264",
        "-profile:v", "high",
        "-level:v", "4.0",
        "-preset", "medium",
        "-crf", "20",
        "-maxrate", "6M",
        "-bufsize", "12M",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        "-g", "60",
        "-keyint_min", "60",
        "-color_primaries", "bt709",
        "-color_trc", "bt709",
        "-colorspace", "bt709",
        # AUDIO
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "48000",
        "-ac", "2",
        # Container
        "-movflags", "+faststart",
        "-shortest",
        output_path
    ]

    print(f"Generating social media video...")
    print(f"  Persona: {persona_name} | Duration: {duration}s")
    print(f"  Encoding: H.264 High, CRF20, maxrate 6M, 30fps, AAC 192k stereo")

    proc = subprocess.run(cmd, capture_output=True, timeout=120)
    if proc.returncode != 0:
        print(f"Error: {proc.stderr.decode()[-500:]}")
        return None

    verify_video(output_path)
    return output_path


def verify_video(path):
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", path]
    proc = subprocess.run(cmd, capture_output=True, timeout=30)
    if proc.returncode != 0:
        return None

    data = json.loads(proc.stdout.decode())
    v = next((s for s in data["streams"] if s["codec_type"] == "video"), {})
    a = next((s for s in data["streams"] if s["codec_type"] == "audio"), {})
    f = data["format"]

    vb = int(v.get("bit_rate", 0)) / 1000
    ab = int(a.get("bit_rate", 0)) / 1000
    dur = float(f.get("duration", 0))
    size_mb = int(f.get("size", 0)) / 1024 / 1024

    fps_str = v.get("r_frame_rate", "0/1")
    try:
        n, d = map(int, fps_str.split("/"))
        fps = n / d if d else 0
    except:
        fps = 0

    profile = v.get("profile", "?")
    ch = int(a.get("channels", 0))
    w, h = int(v.get("width", 0)), int(v.get("height", 0))

    score = 0
    print(f"\n{'='*60}")
    print(f"VIDEO QUALITY REPORT")
    print(f"{'='*60}")
    print(f"File: {path}")
    print(f"Size: {size_mb:.2f} MB | Duration: {dur:.1f}s")
    print()

    checks = []
    if w >= 1080 and h >= 1920:
        score += 20; checks.append(f"Resolution: {w}x{h}")
    else:
        checks.append(f"Resolution: {w}x{h}")

    if fps >= 30:
        score += 15; checks.append(f"Frame Rate: {fps:.0f}fps")
    else:
        checks.append(f"Frame Rate: {fps:.0f}fps")

    if vb >= 3000:
        score += 25; checks.append(f"Video Bitrate: {vb:.0f}kbps (excellent)")
    elif vb >= 2000:
        score += 18; checks.append(f"Video Bitrate: {vb:.0f}kbps (good)")
    elif vb >= 1000:
        score += 10; checks.append(f"Video Bitrate: {vb:.0f}kbps (fair)")
    else:
        checks.append(f"Video Bitrate: {vb:.0f}kbps (low)")

    if ab >= 128:
        score += 20; checks.append(f"Audio Bitrate: {ab:.0f}kbps")
    elif ab >= 64:
        score += 10; checks.append(f"Audio Bitrate: {ab:.0f}kbps")
    else:
        checks.append(f"Audio Bitrate: {ab:.0f}kbps")

    if ch >= 2:
        score += 10; checks.append(f"Audio: Stereo")
    else:
        checks.append(f"Audio: Mono")

    if "High" in profile:
        score += 10; checks.append(f"Profile: {profile}")
    else:
        checks.append(f"Profile: {profile}")

    for c in checks:
        print(f"  {c}")

    if score >= 90: grade = "EXCELLENT"
    elif score >= 70: grade = "GOOD"
    elif score >= 50: grade = "FAIR"
    else: grade = "POOR"

    print(f"\n  Quality Score: {score}/100 - {grade}")
    print(f"\n  Social Media Ready: {'YES' if score >= 70 else 'Needs work'}")
    print(f"{'='*60}")
    return score


if __name__ == "__main__":
    test = """The Best Pho Recipe
Step 1: Prepare the broth with beef bones
Step 2: Toast the spices for maximum flavor
Step 3: Simmer for 6 hours
Step 4: Assemble with fresh herbs"""
    generate_video(test, "cooking", 15, "/home/admin/faceless-channel/output/test_v6.mp4")
