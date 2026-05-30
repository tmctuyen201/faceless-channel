#!/usr/bin/env python3
"""
Dynamic Video Generator - Real images + Ken Burns + transitions + animated text.
Creates social media videos that look like real content.
"""
import os
import subprocess
import json
import glob
import random
from datetime import datetime

ASSETS_DIR = "/home/admin/faceless-channel/assets/images"
W, H = 1080, 1920  # Vertical 9:16
FPS = 30

# Ken Burns effect patterns (zoom + pan combinations)
KENBURNS = [
    (1.0, 1.3, 0.5, 0.5, 0.4, 0.4),    # Zoom in, pan left-up
    (1.3, 1.0, 0.3, 0.3, 0.5, 0.5),    # Zoom out from left-up
    (1.0, 1.2, 0.5, 0.5, 0.6, 0.6),    # Zoom in, pan right-down
    (1.2, 1.0, 0.6, 0.4, 0.5, 0.5),    # Zoom out from right
    (1.0, 1.15, 0.5, 0.3, 0.5, 0.7),   # Slow zoom, pan down
    (1.15, 1.0, 0.5, 0.6, 0.5, 0.4),   # Zoom out, pan up
]

TRANSITIONS = ["fade", "slideleft", "slideup", "circlecrop", "dissolve"]


def get_images(persona_name):
    """Get available images for a persona category."""
    category = persona_name.lower()
    img_dir = os.path.join(ASSETS_DIR, category)
    
    if os.path.exists(img_dir):
        images = sorted(glob.glob(os.path.join(img_dir, "*.jpg")))
        if images:
            return images
    
    # Fallback: use any available images
    all_images = []
    for d in glob.glob(os.path.join(ASSETS_DIR, "*")):
        if os.path.isdir(d):
            all_images.extend(glob.glob(os.path.join(d, "*.jpg")))
    
    return sorted(all_images) if all_images else []


def create_scene(image_path, duration, kb_pattern, text_lines, scene_idx, total_scenes):
    """Create a single scene with Ken Burns effect and text overlay."""
    start_scale, end_scale, start_x, start_y, end_x, end_y = kb_pattern
    
    filters = []
    
    # 1. Scale image to cover 1080x1920 with extra room for zoom
    max_scale = max(start_scale, end_scale)
    scale_w = int(W * max_scale * 1.2)
    scale_h = int(H * max_scale * 1.2)
    filters.append(f"scale={scale_w}:{scale_h}:force_original_aspect_ratio=increase")
    filters.append(f"crop={int(W * max_scale)}:{int(H * max_scale)}")
    
    # 2. Ken Burns: zoom + pan animation
    z_expr = f"zoom+{(end_scale - start_scale) / (duration * FPS):.8f}"
    x_expr = f"iw*{start_x}-(iw/zoom)*{start_x}+((iw/zoom)*{end_x}-(iw/zoom)*{start_x})*on/{int(duration * FPS)}"
    y_expr = f"ih*{start_y}-(ih/zoom)*{start_y}+((ih/zoom)*{end_y}-(ih/zoom)*{start_y})*on/{int(duration * FPS)}"
    
    filters.append(
        f"zoompan=z='{z_expr}':"
        f"x='{x_expr}':y='{y_expr}':"
        f"d={int(duration * FPS)}:s={W}x{H}:fps={FPS}"
    )
    
    # 3. Add dark gradient overlay for text readability
    filters.append("drawbox=x=0:y=0:w=iw:h=ih:color=black@0.3:t=fill")
    
    # 4. Add text overlays with animation
    for i, text in enumerate(text_lines[:3]):
        safe_text = text.replace("'", "").replace(":", " ").replace("%", " ")[:50]
        
        if i == 0:
            y_pos = "h*0.35"
            fontsize = 48
            color = "white"
            delay = 0.3
        elif i == 1:
            y_pos = "h*0.45"
            fontsize = 32
            color = "0xFFD700"
            delay = 0.8
        else:
            y_pos = "h*0.55"
            fontsize = 28
            color = "0xCCCCCC"
            delay = 1.3
        
        # Text shadow
        filters.append(
            f"drawtext=text='{safe_text}':"
            f"fontsize={fontsize + 2}:fontcolor=black@0.5:"
            f"x=(w-text_w)/2+2:y={y_pos}+2:"
            f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
            f"alpha='if(lt(t,{delay}),0,min(1,(t-{delay})*3))'"
        )
        
        # Main text
        filters.append(
            f"drawtext=text='{safe_text}':"
            f"fontsize={fontsize}:fontcolor={color}:"
            f"x=(w-text_w)/2:y={y_pos}:"
            f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
            f"alpha='if(lt(t,{delay}),0,min(1,(t-{delay})*3))'"
        )
    
    # 5. Scene indicator
    filters.append(
        f"drawtext=text='{scene_idx + 1}/{total_scenes}':"
        f"fontsize=18:fontcolor=white@0.6:"
        f"x=w-80:y=h-40:"
        f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    )
    
    # 6. Branding
    filters.append(
        f"drawtext=text='aistudy.io.vn':"
        f"fontsize=16:fontcolor=white@0.4:"
        f"x=20:y=h-40:"
        f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    )
    
    return ",".join(filters)


def generate_video(script, persona_name, duration=15, output_path=None):
    """Generate a dynamic video with real images, Ken Burns, transitions."""
    if output_path is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"/home/admin/faceless-channel/output/{ts}_dynamic.mp4"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    images = get_images(persona_name)
    if not images:
        print(f"No images found for {persona_name}, using fallback")
        return generate_fallback(script, persona_name, duration, output_path)
    
    lines = [l.strip() for l in script.split("\n") if l.strip()]
    if not lines:
        lines = ["AI Generated Content", "Faceless Channel"]
    
    # Remove [TAGS]
    lines = [l for l in lines if not l.startswith("[")]
    
    num_scenes = min(len(images), max(4, len(lines)), 6)
    scene_duration = duration / num_scenes
    
    print(f"Generating dynamic video...")
    print(f"  Persona: {persona_name}")
    print(f"  Scenes: {num_scenes} x {scene_duration:.1f}s")
    print(f"  Images: {len(images)} available")
    
    # Create individual scene files
    scene_files = []
    for i in range(num_scenes):
        img = images[i % len(images)]
        kb = KENBURNS[i % len(KENBURNS)]
        
        scene_texts = []
        if i < len(lines):
            scene_texts.append(lines[i])
        if i == 0:
            scene_texts.insert(0, persona_name.upper())
        if i == num_scenes - 1:
            scene_texts.append("Follow for more!")
        
        scene_file = f"/tmp/scene_{i}.mp4"
        vf = create_scene(img, scene_duration, kb, scene_texts, i, num_scenes)
        
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", img,
            "-vf", vf,
            "-t", str(scene_duration),
            "-c:v", "libx264", "-profile:v", "high", "-preset", "medium",
            "-crf", "20", "-maxrate", "6M", "-bufsize", "12M",
            "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-an",
            scene_file
        ]
        
        print(f"  Scene {i+1}/{num_scenes}: {os.path.basename(img)}", end="")
        proc = subprocess.run(cmd, capture_output=True, timeout=60)
        if proc.returncode != 0:
            print(f" Error")
            continue
        
        scene_files.append(scene_file)
        print(f" OK")
    
    if not scene_files:
        return generate_fallback(script, persona_name, duration, output_path)
    
    # Concatenate scenes
    if len(scene_files) > 1:
        final_path = concat_with_xfade(scene_files, scene_duration, output_path)
    else:
        final_path = scene_files[0]
        os.rename(final_path, output_path)
    
    # Add audio
    add_ambient_audio(output_path, duration)
    
    # Verify
    verify_video(output_path)
    
    # Cleanup
    for f in scene_files:
        try: os.remove(f)
        except: pass
    
    return output_path


def concat_with_xfade(scene_files, scene_duration, output_path):
    """Concatenate scenes with xfade transitions."""
    n = len(scene_files)
    if n == 1:
        os.rename(scene_files[0], output_path)
        return output_path
    
    inputs = []
    for f in scene_files:
        inputs.extend(["-i", f])
    
    fade_duration = 0.5
    filter_parts = []
    offset = scene_duration - fade_duration
    filter_parts.append(f"[0:v][1:v]xfade=transition=fade:duration={fade_duration}:offset={offset}[v1]")
    
    for i in range(2, n):
        prev = f"v{i-1}"
        curr = f"v{i}"
        offset = (i * scene_duration) - (i * fade_duration)
        trans = TRANSITIONS[i % len(TRANSITIONS)]
        filter_parts.append(f"[{prev}][{i}:v]xfade=transition={trans}:duration={fade_duration}:offset={offset}[{curr}]")
    
    last_label = f"v{n-1}"
    filter_complex = ";".join(filter_parts)
    
    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", f"[{last_label}]",
        "-c:v", "libx264", "-profile:v", "high", "-preset", "medium",
        "-crf", "20", "-maxrate", "6M", "-bufsize", "12M",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-an",
        output_path
    ]
    
    proc = subprocess.run(cmd, capture_output=True, timeout=120)
    if proc.returncode != 0:
        return concat_simple(scene_files, output_path)
    
    return output_path


def concat_simple(scene_files, output_path):
    """Simple concatenation fallback."""
    list_file = "/tmp/scenes.txt"
    with open(list_file, "w") as f:
        for sf in scene_files:
            f.write(f"file '{sf}'\n")
    
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", list_file,
        "-c:v", "libx264", "-profile:v", "high", "-preset", "medium",
        "-crf", "20", "-maxrate", "6M", "-bufsize", "12M",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-an",
        output_path
    ]
    
    subprocess.run(cmd, capture_output=True, timeout=60)
    return output_path


def add_ambient_audio(video_path, duration):
    """Add ambient audio tone to video."""
    temp = video_path + ".tmp.mp4"
    
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-f", "lavfi", "-i", f"sine=frequency=220:duration={duration}:sample_rate=48000",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart",
        "-shortest",
        temp
    ]
    
    proc = subprocess.run(cmd, capture_output=True, timeout=30)
    if proc.returncode == 0:
        os.replace(temp, video_path)
    else:
        try: os.remove(temp)
        except: pass


def generate_fallback(script, persona_name, duration, output_path):
    """Fallback with solid color + animated text."""
    lines = [l.strip() for l in script.split("\n") if l.strip()][:3]
    
    filters = [
        f"noise=alls=8:allf=t+u",
        f"drawtext=text='{persona_name.upper()}':fontsize=48:fontcolor=white:x=(w-text_w)/2:y=h*0.35:fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:alpha='if(lt(t,0.5),0,min(1,(t-0.5)*2))'",
    ]
    
    if lines:
        safe = lines[0].replace("'", "").replace(":", " ")[:50]
        filters.append(f"drawtext=text='{safe}':fontsize=32:fontcolor=0xFFD700:x=(w-text_w)/2:y=h*0.45:alpha='if(lt(t,1),0,min(1,(t-1)*2))'")
    
    filters.append(f"drawtext=text='aistudy.io.vn':fontsize=28:fontcolor=0x16C79A:x=(w-text_w)/2:y=h*0.85")
    
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=0x0F3460:s=1080x1920:d={duration},format=yuv420p",
        "-f", "lavfi", "-i", f"sine=frequency=220:duration={duration}:sample_rate=48000",
        "-vf", ",".join(filters),
        "-c:v", "libx264", "-profile:v", "high", "-preset", "medium",
        "-crf", "20", "-maxrate", "6M", "-bufsize", "12M",
        "-r", "30", "-g", "60",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart", "-shortest",
        output_path
    ]
    
    subprocess.run(cmd, capture_output=True, timeout=60)
    verify_video(output_path)
    return output_path


def verify_video(path):
    """Verify video quality."""
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
    size_mb = int(f.get("size", 0)) / 1024 / 1024
    dur = float(f.get("duration", 0))
    
    print(f"\n{'='*60}")
    print(f"DYNAMIC VIDEO QUALITY REPORT")
    print(f"{'='*60}")
    print(f"Size: {size_mb:.2f} MB | Duration: {dur:.1f}s")
    print(f"Video: {v.get('width')}x{v.get('height')} @ {v.get('r_frame_rate')}fps")
    print(f"Bitrate: {vb:.0f}kbps | Audio: {ab:.0f}kbps {a.get('channels')}ch")
    print(f"Profile: {v.get('profile')}")
    print(f"{'='*60}")
    return vb


if __name__ == "__main__":
    test = """Banh bao - Mon ngon ai cung lam duoc!
Huong dan cach lam banh bao don gian tai nha.
Chuan bi nguyen lieu: bot mi, men no, thit heo.
Nha bot va u trong 1 tieng.
Hap banh trong 20 phut la xong!"""
    generate_video(test, "cooking", 20, "/home/admin/faceless-channel/output/test_dynamic.mp4")
