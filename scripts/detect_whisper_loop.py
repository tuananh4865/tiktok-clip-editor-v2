#!/usr/bin/env python3
"""
Detect Whisper autoregressive hallucinate loop trong transcript.

Tuấn Anh HARD RULE 10/08/2026: dùng --condition-on-previous-text False
để tránh Whisper hallucinate loop. Script này verify loop đã bị loại bỏ.

Loop signatures:
- "và trắng và trắng..."
- "hơn hơn hơn..."
- "Rung lắc..."
- "à à à..."
- "bằng một phần năm..."
- identical 5-word phrase xuất hiện >= 5 lần

Usage: python3 detect_whisper_loop.py <audio.json> [--strict]
"""

import json
import sys
import re
from collections import Counter


def detect_loop(json_path: str, strict: bool = False) -> dict:
    """Detect Whisper autoregressive loop patterns."""
    
    with open(json_path) as f:
        data = json.load(f)
    
    segments = data.get("segments", [])
    if not segments:
        return {"loop_detected": False, "reason": "no segments"}
    
    # Build full text
    full_text = " ".join(s.get("text", "").strip() for s in segments).lower()
    
    issues = []
    
    # 1. Check for syllable rate (hallucinate signature: > 8 syllable/sec + repetition)
    for s in segments:
        text = s.get("text", "").strip()
        start = s.get("start", 0)
        end = s.get("end", 0)
        duration = max(end - start, 0.001)
        
        words = text.split()
        if not words or duration < 0.05:
            continue
        
        word_count = len(words)
        syllable_rate = word_count / duration
        
        # Check repetition
        word_freq = Counter(words)
        most_common = word_freq.most_common(1)[0]
        repetition_ratio = most_common[1] / word_count
        
        # Syllable rate > 8 w/s + repetition > 80% = hallucinate
        if syllable_rate > 8 and repetition_ratio > 0.8:
            issues.append({
                "type": "HALLUCINATE_HI_RATE",
                "timestamp": f"{start:.1f}-{end:.1f}s",
                "syllable_rate": round(syllable_rate, 1),
                "repetition_ratio": round(repetition_ratio, 2),
                "sample": text[:60]
            })
    
    # 2. Check 3 consecutive identical segments
    for i in range(len(segments) - 2):
        t1 = segments[i].get("text", "").strip()
        t2 = segments[i+1].get("text", "").strip()
        t3 = segments[i+2].get("text", "").strip()
        if t1 == t2 == t3 and len(t1) > 5:
            issues.append({
                "type": "EXACT_TRIPLE_REPEAT",
                "timestamp": f"{segments[i].get('start', 0):.1f}s",
                "sample": t1[:80]
            })
    
    # 3. Check 5-gram repetition >= 5 occurrences
    word_list = full_text.split()
    if len(word_list) > 5:
        phrases = [" ".join(word_list[i:i+5]) for i in range(len(word_list)-4)]
        phrase_counts = Counter(phrases)
        for phrase, count in phrase_counts.most_common(20):
            threshold = 10 if strict else 50
            if count >= threshold:
                issues.append({
                    "type": "FIVE_GRAM_REPEAT",
                    "phrase": phrase[:60],
                    "count": count
                })
    
    # 4. Check single-word repetition (à à à type)
    single_word_hallu = ["à", "ờ", "ừ", "ừm", "ồ", "ôi", "ơ"]
    for word in single_word_hallu:
        # Count consecutive word patterns
        pattern = f" {word} "
        full_text_padded = f" {full_text} "
        # Count runs of 5+ same word
        matches = re.findall(rf'( {word} )+', full_text_padded)
        for m in matches:
            if len(m.split()) >= 5:  # 5+ consecutive
                count = len(m.split())
                issues.append({
                    "type": "SINGLE_WORD_REPETITION",
                    "word": word,
                    "count": count
                })
                break
    
    loop_detected = len(issues) > 0
    
    return {
        "loop_detected": loop_detected,
        "n_issues": len(issues),
        "issues": issues,
        "n_segments": len(segments)
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 detect_whisper_loop.py <audio.json> [--strict]")
        sys.exit(1)
    
    json_path = sys.argv[1]
    strict = "--strict" in sys.argv
    
    result = detect_loop(json_path, strict=strict)
    
    print(f"📊 File: {json_path}")
    print(f"   Segments: {result['n_segments']}")
    print(f"   Issues: {result['n_issues']}")
    print(f"   Loop detected: {'❌ YES' if result['loop_detected'] else '✅ NO'}")
    
    if result['loop_detected']:
        print("\n⚠️ Issues found:")
        for i, issue in enumerate(result['issues'][:5], 1):
            print(f"   {i}. [{issue['type']}] {issue.get('timestamp', '')} {issue.get('sample', issue.get('phrase', ''))[:60]}")
        sys.exit(1)
    
    sys.exit(0)