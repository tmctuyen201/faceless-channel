#!/usr/bin/env python3
"""
Faceless Video MCP Server
Exposes video generation tools via MCP protocol.
"""
import os
import sys
import json
import asyncio
from pathlib import Path
from typing import Any, Dict

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent))

from agent import FacelessHarness, VideoJob

# MCP server implementation
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    HAS_MCP = True
except ImportError:
    HAS_MCP = False
    print("MCP not installed, running in standalone mode")


# Initialize harness
harness = FacelessHarness()

if HAS_MCP:
    server = Server("faceless-video")
    
    @server.list_tools()
    async def list_tools():
        return [
            Tool(
                name="faceless_generate",
                description="Generate a complete faceless video with script, voice, images, and music",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "persona": {
                            "type": "string",
                            "enum": ["cooking", "horror", "comedy", "beauty", "mystery", "motivation"],
                            "description": "Video persona/category"
                        },
                        "topic": {
                            "type": "string",
                            "description": "Video topic"
                        },
                        "duration": {
                            "type": "integer",
                            "default": 30,
                            "description": "Video duration in seconds"
                        },
                    },
                    "required": ["persona", "topic"]
                }
            ),
            Tool(
                name="faceless_script",
                description="Generate a Vietnamese video script",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "persona": {"type": "string"},
                        "topic": {"type": "string"},
                        "duration": {"type": "integer", "default": 30},
                    },
                    "required": ["persona", "topic"]
                }
            ),
            Tool(
                name="faceless_quality",
                description="Check video quality and get a score",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "video_path": {"type": "string", "description": "Path to video file"}
                    },
                    "required": ["video_path"]
                }
            ),
            Tool(
                name="faceless_personas",
                description="List available video personas",
                inputSchema={"type": "object", "properties": {}}
            ),
        ]
    
    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]):
        if name == "faceless_generate":
            job = await harness.run_pipeline(
                persona=arguments["persona"],
                topic=arguments["topic"],
                duration=arguments.get("duration", 30),
            )
            return [TextContent(
                type="text",
                text=json.dumps({
                    "job_id": job.job_id,
                    "status": job.status,
                    "progress": job.progress,
                    "step": job.step,
                    "video_path": job.video_path,
                    "script": job.script,
                    "error": job.error,
                }, indent=2, ensure_ascii=False)
            )]
        
        elif name == "faceless_script":
            job = VideoJob(
                job_id="temp",
                persona=arguments["persona"],
                topic=arguments["topic"],
                duration=arguments.get("duration", 30),
            )
            script = await harness.generate_script(job)
            return [TextContent(type="text", text=script)]
        
        elif name == "faceless_quality":
            job = VideoJob(job_id="check", persona="cooking", topic="check")
            job.video_path = arguments["video_path"]
            quality = harness.verify_quality(job)
            return [TextContent(
                type="text",
                text=json.dumps(quality, indent=2)
            )]
        
        elif name == "faceless_personas":
            personas = {
                k: {"name": v["name"], "color": v["color"]}
                for k, v in harness.personas.items()
            }
            return [TextContent(
                type="text",
                text=json.dumps(personas, indent=2, ensure_ascii=False)
            )]
        
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    
    async def run_mcp():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())
    
    if __name__ == "__main__":
        asyncio.run(run_mcp())

else:
    # Standalone mode - run as HTTP API
    from fastapi import FastAPI
    import uvicorn
    
    app = FastAPI(title="Faceless Video MCP")
    
    @app.get("/tools")
    async def list_tools():
        return {
            "tools": [
                {"name": "faceless_generate", "description": "Generate complete video"},
                {"name": "faceless_script", "description": "Generate Vietnamese script"},
                {"name": "faceless_quality", "description": "Check video quality"},
                {"name": "faceless_personas", "description": "List personas"},
            ]
        }
    
    @app.post("/tools/faceless_generate")
    async def generate(persona: str, topic: str, duration: int = 30):
        job = await harness.run_pipeline(persona=persona, topic=topic, duration=duration)
        return {
            "job_id": job.job_id,
            "status": job.status,
            "video_path": job.video_path,
            "script": job.script,
        }
    
    @app.post("/tools/faceless_script")
    async def script(persona: str, topic: str, duration: int = 30):
        job = VideoJob(job_id="temp", persona=persona, topic=topic, duration=duration)
        result = await harness.generate_script(job)
        return {"script": result}
    
    @app.post("/tools/faceless_quality")
    async def quality(video_path: str):
        job = VideoJob(job_id="check", persona="cooking", topic="check")
        job.video_path = video_path
        return harness.verify_quality(job)
    
    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8090)
