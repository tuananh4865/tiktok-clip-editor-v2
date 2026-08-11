#!/usr/bin/env python3
"""
Apply speed 1.3x cho tất cả segments trong folder.

Tuấn Anh HARD RULE 10/08: speed 1.3x BẮT BUỘC sau khi cắt gọn, TRƯỚC khi render.

Browser-use/video-use Hard Rule #3: 30ms audio fade preserved.

Usage: python3 apply_speed_130.py <input_dir> <output_dir>
"""

import sys
import os
import subprocess
import subprocess as sp
import json
from pathlib import Path


def get_duration(path: str) -> float:
    """Get video duration using ffprobe."""
    result = sp.run(
        f'ffprobe -v error -show_entries format=duration -of csv=p=0 "{path}"',
        shell=True, capture_output=True, text=True
    )
    return float(result.stdout.strip())


def apply_speed(input_path: str, output_path: str, speed: float = 1.3):
    """Apply speed factor to a single video segment with 30ms fade."""
    duration = get_duration(input_path)
    new_duration = duration / speed
    fade_out = max(0, new_duration - 0.03)
    
    cmd = (
        f'ffmpeg -v error -y -i "{input_path}" '
        f'-filter_complex "[0:v]setpts=PTS/{speed},scale=1080:1920:force_original_aspect_ratio=decrease,'
        f'pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,fps=30,format=yuv420p[v];'
        f'[0:a]atempo={speed},afade=t=in:st=0:d=0.03,afade=t=out:st={fade_out}:d=0.03[a]" '
        f'-map "[v]" -map "[a]" '
        f'-c:v libx264 -preset medium -crf 18 -profile:v high -pix_fmt yuv420p '
        f'-c:a aac -b:a 192k -ar 44100 -ac 2 '
        f'-movflags +faststart '
        f'"{output_path}"'
    )
    result = sp.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Speed failed for {input_path}: {result.stderr[-300:]}")


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 apply_speed_130.py <input_dir> <output_dir>")
        sys.exit(1)
    
    input_dir = sys.argv[1]
    output_dir = sys.argv[2]
    
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Find all .mp4 segments (preserve order)
    segments = sorted([f for f in os.listdir(input_dir) if f.endswith('.mp4') and f.startswith('seg_')])
    
    if not segments:
        print(f"No segments found in {input_dir}")
        sys.exit(1)
    
    print(f"🚀 Applying speed 1.3x to {len(segments)} segments")
    print(f"   Input: {input_dir}")
    print(f"   Output: {output_dir}\n")
    
    same_dir = os.path.abspath(input_dir) == os.path.abspath(output_dir)
    
    total_in_duration = 0
    total_out_duration = 0
    
    for seg in segments:
        in_path = os.path.join(input_dir, seg)
        # If same dir, write to temp file first, then replace
        if same_dir:
            out_path = os.path.join(output_dir, f"_tmp_{seg}")
        else:
            out_path = os.path.join(output_dir, seg)
        
        in_dur = get_duration(in_path)
        apply_speed(in_path, out_path, speed=1.3)
        
        if same_dir:
            os.replace(out_path, in_path)
            out_path = in_path
        
        out_dur = get_duration(out_path)
        
        total_in_duration += in_dur
        total_out_duration += out_dur
        print(f"  {seg}: {in_dur:.2f}s → {out_dur:.2f}s (-{((1 - out_dur/in_dur)*100):.1f}%)")
    
    print(f"\n📊 Summary:")
    print(f"   Total in: {total_in_duration:.2f}s")
    print(f"   Total out: {total_out_duration:.2f}s")
    print(f"   Speed saved: {total_in_duration - total_out_duration:.2f}s ({(1 - total_out_duration/total_in_duration)*100:.1f}% faster)")


if __name__ == "__main__":
    main()