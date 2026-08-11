#!/usr/bin/env python3
"""
Extract per-segment clips từ source MP4 dựa trên EDL JSON.

Browser-use/video-use Hard Rule #2: Per-segment extract → lossless -c copy concat.
Browser-use/video-use Hard Rule #3: 30ms afade in/out ở MỖI segment.

Tuấn Anh 10/08 HARD RULE: afade=t=in:st=0:d=0.03 + afade=t=out:st={dur-0.03}:d=0.03

EDL format:
[
  {"start": 0.5, "end": 5.2, "beat": "HOOK", "reason": "..."},
  {"start": 8.0, "end": 20.0, "beat": "USP", "reason": "..."}
]

Output: ${OUTPUT_DIR}/seg_001.mp4, seg_002.mp4, etc.

Usage: python3 extract_segments.py <source.mp4> <edl.json> <output_dir>
"""

import json
import sys
import os
import subprocess
from pathlib import Path

# Browser-use Hard Rule #3: 30ms audio fade
FADE_DURATION = 0.03


def build_ffmpeg_command(source: str, start: float, end: float, out_path: str) -> str:
    """Build ffmpeg per-segment extract command with 30ms fade."""
    duration = end - start
    
    # Validate window
    if duration <= 0:
        raise ValueError(f"Invalid window: {start}-{end}")
    
    fade_out_start = max(0, duration - FADE_DURATION)
    
    # Browser-use Hard Rule #2: -c copy where possible, but afade requires re-encode
    # We accept the re-encode cost because 30ms afade is REQUIRED
    cmd = (
        f'ffmpeg -v error -y -ss {start:.3f} -i "{source}" -t {duration:.3f} '
        f'-vf "scale=1080:1920:force_original_aspect_ratio=decrease,'
        f'pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,'
        f'fps=30,format=yuv420p" '
        f'-af "afade=t=in:st=0:d={FADE_DURATION},afade=t=out:st={fade_out_start:.3f}:d={FADE_DURATION}" '
        f'-c:v libx264 -preset medium -crf 18 -profile:v high -pix_fmt yuv420p '
        f'-c:a aac -b:a 192k -ar 44100 -ac 2 '
        f'-movflags +faststart '
        f'-shortest '
        f'"{out_path}"'
    )
    return cmd


def extract_segments(source: str, edl_path: str, output_dir: str):
    """Extract all segments based on EDL."""
    
    with open(edl_path) as f:
        edl = json.load(f)
    
    if not edl:
        raise ValueError(f"Empty EDL: {edl_path}")
    
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    print(f"📦 Extracting {len(edl)} segments from {source}")
    print(f"   Output: {output_dir}\n")
    
    for i, seg in enumerate(edl, 1):
        start = seg.get("start", 0)
        end = seg.get("end", 0)
        beat = seg.get("beat", "?")
        reason = seg.get("reason", "")
        
        out_path = os.path.join(output_dir, f"seg_{i:03d}.mp4")
        cmd = build_ffmpeg_command(source, start, end, out_path)
        
        print(f"  [{i:03d}] {beat:6s} {start:.2f}s-{end:.2f}s ({end-start:.2f}s) {reason[:40]}")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"    ❌ FAILED: {result.stderr[-200:]}")
            raise RuntimeError(f"Segment {i} failed")
    
    print(f"\n✅ Extracted {len(edl)} segments successfully")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python3 extract_segments.py <source.mp4> <edl.json> <output_dir>")
        sys.exit(1)
    extract_segments(sys.argv[1], sys.argv[2], sys.argv[3])