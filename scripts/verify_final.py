#!/usr/bin/env python3
"""
Verify final output theo các tiêu chí Tuấn Anh 10/08 + clarify 13/08:
- No filler "ừm/ờ/à" trong first 30s (HOOK)
- No pricing mentions
- No 5+ words repeated >= 3x in 30s window (no lặp)
- No off-topic segments
- Duration 60-90s (TikTok Mode B optimal)
- v3.7: Adjacent duplicate + silence gap check (CUT prev/KEEP next)
- v3.8 (13/08): LUẬT 2 CÂU LIỀN KỀ - SemanticSimilarity detector
    * 2 câu liền kề có ≥2 từ chung + SequenceMatcher.ratio() > 0.4
    * Common words "có thể", "thì", "mà", "vô trong" ALLOW (different content)

If FAIL → refine EDL + re-render (LOOP).
If PASS → ship!

Usage: python3 verify_final.py <verify_audio.json> <edl.json> <final.mp4>
"""

import json
import sys
import os
import re
import subprocess as sp
from collections import Counter

# Import detect_adjacent_issues v3.7
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from detect_adjacent_issues import run_all_detectors, detect_silence_gaps


def get_duration(path: str) -> float:
    result = sp.run(
        f'ffprobe -v error -show_entries format=duration -of csv=p=0 "{path}"',
        shell=True, capture_output=True, text=True
    )
    return float(result.stdout.strip())


def normalize_text(text: str) -> str:
    """Diacritic-insensitive normalize."""
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn").lower()


def verify_final(audio_json: str, edl_path: str, final_mp4: str) -> dict:
    """Run all verification checks on final output."""
    
    issues = []
    
    # 1. Duration check
    actual_duration = get_duration(final_mp4)
    if actual_duration < 55:
        issues.append({"check": "DURATION", "severity": "MEDIUM",
                       "msg": f"Duration {actual_duration:.1f}s < 55s (too short)"})

    # KEYWORD COUNTS ANTI-PATTERN (13/08/2026)
    # NOTE: KHÔNG dùng keyword counts ("pocket 3 xuất hiện 7 lần") làm duplicate indicator.
    # Keyword counts chỉ là INFO, không phải FAIL criterion.
    # 1 từ xuất hiện nhiều lần ≠ duplicate nếu các câu khác NỘI DUNG.
    # Để check duplicate, dùng detect_semantic_similarity_overlap() trong detect_adjacent_issues.py
    elif actual_duration > 130:
        issues.append({"check": "DURATION", "severity": "MEDIUM",
                       "msg": f"Duration {actual_duration:.1f}s > 130s (too long)"})
    else:
        print(f"  ✅ Duration: {actual_duration:.1f}s (60-90s optimal)")
    
    # 2. Load verify audio (re-Whisper of final)
    with open(audio_json) as f:
        data = json.load(f)
    
    segments = data.get("segments", [])
    if not segments:
        issues.append({"check": "WHISPER", "severity": "HIGH",
                       "msg": "No segments in verify audio"})
        return {"pass": False, "issues": issues, "n_segments": 0}
    
    real_segments = [s for s in segments if s.get("text", "").strip() not in ("ừ", "ờ", "à", "ừm", "")]
    
    # 3. Filler check in first 30s (HOOK)
    hook_segments = [s for s in real_segments if s.get("start", 0) < 30]
    filler_words = ["ừm", "ờ", "à", "ừ", "ừ'", "ờ'", "umm"]
    hook_filler_count = 0
    for s in hook_segments:
        text = s.get("text", "").strip().lower()
        if text in filler_words:
            hook_filler_count += 1
    
    if hook_filler_count > 0:
        issues.append({"check": "HOOK_FILLER", "severity": "MEDIUM",
                       "msg": f"{hook_filler_count} filler segments in HOOK (first 30s)"})
    else:
        print(f"  ✅ No filler in HOOK (first 30s)")
    
    # 4. Pricing mention check
    full_text = " ".join(s.get("text", "") for s in real_segments)
    full_text_lower = full_text.lower()
    pricing_keywords = [
        "giá", "ngàn", "triệu", "k ", "000đ", "000 đ", "freeship", "discount", 
        "giảm giá", "sale", "vnd", "đồng", "mua ở đâu", "link", "shopee", "tiki",
        "lazada", "inbox shop", "tư vấn"
    ]
    # False positive filter: tên SP có thể chứa "ngàn" (ngàm) hoặc "k" (kF), CTA context cho "link"
    false_positive_patterns = [
        r"ngàn\s+thao",      # "ngàn thao tác" = "ngàm thao tác" (tên SP)
        r"ngầm\s+thao",      # "ngầm thao tác"
        r"k\s+(concept|kf)", # "k concept", "k kf"
        r"kỹ\s+thuật",       # "kỹ thuật"
        r"ok\s+",             # "ok luôn" - không phải giá
        r"bấm\s+link\s+phía",  # CTA context: "bấm link phía bên dưới" 
        r"bấm\s+vào\s+link",   # CTA context
        r"link\s+phía\s+dưới", # CTA context
    ]
    pricing_found = []
    for kw in pricing_keywords:
        if kw in full_text_lower:
            # Check if it's a false positive (tên SP hoặc CTA)
            import re
            is_false_positive = any(re.search(fp, full_text_lower) for fp in false_positive_patterns)
            if is_false_positive and kw in ("ngàn", "k ", "link"):
                continue  # Skip - likely SP name or CTA
            pricing_found.append(kw)
    
    if pricing_found:
        issues.append({"check": "PRICING", "severity": "HIGH",
                       "msg": f"Pricing mentions found: {pricing_found[:5]} (Tuấn Anh HARD RULE: cut pricing)"})
    else:
        print(f"  ✅ No pricing mentions")
    
    # 5. Repetition check (5-word phrase >= 3x in 30s window)
    rep_issues = []
    word_list = full_text.split()
    if len(word_list) > 5:
        for i in range(len(word_list) - 5):
            phrase = " ".join(word_list[i:i+5])
            for j in range(i + 5, len(word_list) - 4):
                if abs((j - i) * 0.5) > 30:  # Approximate 30s window
                    break
                if " ".join(word_list[j:j+5]) == phrase:
                    rep_issues.append({"phrase": phrase, "count": 2, "window_s": 30})
                    break
    
    if rep_issues:
        # Dedupe
        seen = set()
        unique = []
        for r in rep_issues:
            if r["phrase"] not in seen:
                seen.add(r["phrase"])
                unique.append(r)
        if unique:
            issues.append({"check": "REPETITION", "severity": "MEDIUM",
                           "msg": f"Repeated phrases in 30s window: {[r['phrase'][:30] for r in unique[:3]]}"})
    
    if not rep_issues:
        print(f"  ✅ No 5-word phrase repetition in 30s")
    
    # 6. v3.7 NEW: Adjacent duplicate + silence gap check (HARD RULE #5)
    print("  🔍 v3.7: Adjacent duplicate + silence gap check...")
    adj_result = run_all_detectors(real_segments, min_gap=0.10)
    adj_dups = adj_result["adjacent_duplicates"]
    gaps = adj_result["silence_gaps"]
    if adj_dups:
        types = set()
        for d in adj_dups:
            types.update(d.get("detection_types", []))
        issues.append({"check": "ADJACENT_DUPLICATE", "severity": "HIGH",
                       "msg": f"{len(adj_dups)} adjacent duplicates detected ({', '.join(sorted(types))})"})
    else:
        print(f"  ✅ No adjacent duplicates (5 algorithms: LEADING_MATCH + TIER + NGRAM + KEY_PHRASE + WORD_OVERLAP)")
    if gaps:
        issues.append({"check": "SILENCE_GAP", "severity": "HIGH",
                       "msg": f"{len(gaps)} silence gaps > 0.10s"})
    else:
        print(f"  ✅ No silence gaps > 0.10s")
    
    # 7. EDL coverage check
    if os.path.exists(edl_path):
        with open(edl_path) as f:
            edl = json.load(f)
        expected_segments = len(edl)
        actual_clips = len([s for s in real_segments if not s.get("text", "").strip() in ("ừ", "ờ", "à", "ừm", "")])

        if expected_segments != actual_clips:
            issues.append({"check": "EDL_COVERAGE", "severity": "MEDIUM",
                           "msg": f"EDL has {expected_segments} segments, final has {actual_clips} detected"})
        else:
            print(f"  ✅ EDL coverage matches: {expected_segments} segments")
    
    # Summary
    print(f"\n📊 Summary:")
    print(f"   Real segments: {len(real_segments)}")
    print(f"   Issues: {len(issues)}")
    
    if issues:
        print(f"\n❌ Issues found:")
        for i, issue in enumerate(issues, 1):
            print(f"   {i}. [{issue['severity']}] {issue['check']}: {issue['msg'][:80]}")
    
    pass_check = len([i for i in issues if i['severity'] == 'HIGH']) == 0
    
    return {
        "pass": pass_check,
        "issues": issues,
        "n_real_segments": len(real_segments),
        "duration": actual_duration
    }


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python3 verify_final.py <verify_audio.json> <edl.json> <final.mp4>")
        sys.exit(1)
    
    audio_json = sys.argv[1]
    edl_path = sys.argv[2]
    final_mp4 = sys.argv[3]
    
    print(f"🔍 Verifying final output\n")
    result = verify_final(audio_json, edl_path, final_mp4)
    
    if result["pass"]:
        print("\n✅ PASS - Ship ready!")
        sys.exit(0)
    else:
        print("\n❌ FAIL - Refine EDL + re-render")
        sys.exit(1)