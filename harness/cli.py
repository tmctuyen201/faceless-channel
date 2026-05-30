#!/usr/bin/env python3
"""
Faceless Video Harness CLI
Quick commands for video generation.
"""
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from agent import FacelessHarness, VideoJob


async def main():
    if len(sys.argv) < 2:
        print("""
🎬 Faceless Video Harness CLI

Usage:
  python3 harness/cli.py generate --persona cooking --topic "Bánh bao"
  python3 harness/cli.py script --persona cooking --topic "Bánh bao"
  python3 harness/cli.py quality --video /path/to/video.mp4
  python3 harness/cli.py personas

Personas: cooking, horror, comedy, beauty, mystery, motivation
        """)
        return
    
    command = sys.argv[1]
    harness = FacelessHarness()
    
    if command == "generate":
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--persona", default="cooking")
        parser.add_argument("--topic", required=True)
        parser.add_argument("--duration", type=int, default=30)
        args = parser.parse_args(sys.argv[2:])
        
        print(f"🎬 Generating video: {args.persona} - {args.topic}")
        job = await harness.run_pipeline(
            persona=args.persona,
            topic=args.topic,
            duration=args.duration,
        )
        print(f"\n{'='*60}")
        print(f"Status: {job.status}")
        print(f"Video: {job.video_path}")
        print(f"{'='*60}")
    
    elif command == "script":
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--persona", default="cooking")
        parser.add_argument("--topic", required=True)
        parser.add_argument("--duration", type=int, default=30)
        args = parser.parse_args(sys.argv[2:])
        
        job = VideoJob(job_id="cli", persona=args.persona, topic=args.topic, duration=args.duration)
        script = await harness.generate_script(job)
        print(script)
    
    elif command == "quality":
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--video", required=True)
        args = parser.parse_args(sys.argv[2:])
        
        job = VideoJob(job_id="cli", persona="cooking", topic="check")
        job.video_path = args.video
        quality = harness.verify_quality(job)
        import json
        print(json.dumps(quality, indent=2))
    
    elif command == "personas":
        for k, v in harness.personas.items():
            print(f"  {v['name']} ({k})")
    
    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    asyncio.run(main())
