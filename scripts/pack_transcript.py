#!/usr/bin/env python3
"""
Pack Word-level Whisper JSON → phrase-level takes_packed.md

PRIMARY READING VIEW cho LLM editor.
Mỗi phrase = một nhóm words với silence gap >= 0.5s giữa các phrases.

Usage: python3 pack_transcript.py <audio.json> <output.md>
"""

import json
import sys
import os

def pack_transcript(json_path: str, md_path: str, silence_gap: float = 0.5):
    """Convert Whisper word-level JSON to phrase-level markdown."""
    with open(json_path) as f:
        data = json.load(f)
    
    # Handle both word-level and segment-level formats
    if "words" in data and isinstance(data["words"], list) and data["words"] and "word" in data["words"][0]:
        words = data["words"]
    elif "segments" in data:
        # Flatten all words from segments
        words = []
        for seg in data["segments"]:
            if "words" in seg:
                for w in seg["words"]:
                    words.append(w)
            else:
                # Treat segment text as single word entry
                words.append({
                    "word": seg.get("text", "").strip(),
                    "start": seg.get("start", 0),
                    "end": seg.get("end", 0)
                })
    else:
        raise ValueError(f"Unknown JSON structure in {json_path}")
    
    if not words:
        raise ValueError(f"No words found in {json_path}")
    
    # Group into phrases by silence gaps
    phrases = []
    current_phrase = {
        "words": [words[0]],
        "start": words[0].get("start", 0),
        "end": words[0].get("end", 0)
    }
    
    for i, w in enumerate(words[1:], 1):
        prev_end = words[i-1].get("end", 0)
        curr_start = w.get("start", 0)
        gap = curr_start - prev_end
        
        if gap >= silence_gap:
            phrases.append(current_phrase)
            current_phrase = {
                "words": [w],
                "start": w.get("start", 0),
                "end": w.get("end", 0)
            }
        else:
            current_phrase["words"].append(w)
            current_phrase["end"] = w.get("end", 0)
    
    phrases.append(current_phrase)
    
    # Write to markdown
    with open(md_path, "w") as f:
        f.write(f"# Transcript Packed ({len(phrases)} phrases)\n\n")
        f.write(f"Source: `{os.path.basename(json_path)}`\n")
        f.write(f"Total duration: {phrases[-1]['end']:.2f}s\n\n")
        f.write("---\n\n")
        
        for i, p in enumerate(phrases, 1):
            text = " ".join(w.get("word", "") for w in p["words"])
            start = p["start"]
            end = p["end"]
            duration = end - start
            f.write(f"## [{i:03d}] {start:.2f}s-{end:.2f}s ({duration:.2f}s)\n")
            f.write(f"{text}\n\n")
    
    print(f"✅ Packed {len(phrases)} phrases → {md_path}")
    print(f"   Total duration: {phrases[-1]['end']:.2f}s")
    print(f"   Avg phrase duration: {phrases[-1]['end']/len(phrases):.2f}s")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 pack_transcript.py <audio.json> <output.md>")
        sys.exit(1)
    pack_transcript(sys.argv[1], sys.argv[2])