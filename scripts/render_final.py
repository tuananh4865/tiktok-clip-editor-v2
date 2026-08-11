#!/usr/bin/env python3
"""
Render final 1080×1920 30fps TikTok-spec output via concat demuxer.

Tuấn Anh HARD RULE 10/08: 1080×1920 30fps AAC-LC 44100Hz stereo 192k +faststart.

Browser-use/video-use Hard Rule #2: Per-segment extract → lossless concat demuxer.
Browser-use/video-use Hard Rule #3: 30ms fade đã apply ở extract (preserved by concat).

Usage: python3 render_final.py <clips_dir> <output.mp4>
"""

import sys
import os
import subprocess as sp
from pathlib import Path


def render_final(clips_dir: str, output_path: str):
    """Concat all segments via demuxer, output TikTok-spec MP4."""
    
    # Build list file
    segments = sorted([f for f in os.listdir(clips_dir) if f.endswith('.mp4') and f.startswith('seg_')])
    
    if not segments:
        raise ValueError(f"No segments found in {clips_dir}")
    
    list_path = os.path.join(os.path.dirname(output_path) or '.', 'concat_list.txt')
    with open(list_path, 'w') as f:
        for seg in segments:
            abs_path = os.path.abspath(os.path.join(clips_dir, seg))
            f.write(f"file '{abs_path}'\n")
    
    Path(os.path.dirname(output_path) or '.').mkdir(parents=True, exist_ok=True)
    
    print(f"🎬 Rendering final TikTok-spec output")
    print(f"   Segments: {len(segments)}")
    print(f"   Output: {output_path}\n")
    
    # Concat demuxer + transcode to TikTok spec
    cmd = (
        f'ffmpeg -v error -y -f concat -safe 0 -i "{list_path}" '
        f'-c:v libx264 -preset medium -crf 18 -profile:v high -pix_fmt yuv420p '
        f'-r 30 -s 1080x1920 '
        f'-c:a aac -b:a 192k -ar 44100 -ac 2 '
        f'-movflags +faststart '
        f'"{output_path}"'
    )
    result = sp.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode != 0:
        raise RuntimeError(f"Render failed: {result.stderr[-500:]}")
    
    # Verify output
    verify_cmd = (
        f'ffprobe -v error -show_entries format=duration:stream=codec_name,width,height,r_frame_rate '
        f'-of default=noprint_wrappers=1:nokey=1 "{output_path}"'
    )
    verify_result = sp.run(verify_cmd, shell=True, capture_output=True, text=True)
    
    print(f"📊 Output verification:")
    for line in verify_result.stdout.strip().split('\n'):
        if line.strip():
            print(f"   {line}")
    
    # Cleanup concat list
    try:
        os.remove(list_path)
    except:
        pass
    
    print(f"\n✅ Render complete: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 render_final.py <clips_dir> <output.mp4>")
        sys.exit(1)
    render_final(sys.argv[1], sys.argv[2])