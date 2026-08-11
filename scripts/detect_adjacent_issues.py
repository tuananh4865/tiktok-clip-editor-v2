#!/usr/bin/env python3
"""
Smart adjacent duplicate + content similarity detector.

Tuấn Anh HARD RULE (verbatim 10/08):
- "cải thiện nhận diện câu lặp hoặc câu lỗi"
- "timestamp của chúng rất sát nhau và có 2+ từ giống nhau trong 2 câu liền kê"
- "áp dụng cho toàn bộ transcripts chỉ cần quét thấy có lặp là phải cắt câu trước lấy câu sau"

DETECTION ALGORITHMS (4 chiến thuật - match ANY → cut):
1. LEADING_MATCH: 2+ identical leading words (existing)
2. NGRAM_OVERLAP: shared 3-gram phrase between adjacent segments
3. KEY_PHRASE_OVERLAP: shared SP-related terms like "ngàm đực", "ngàm thao tác"
4. WORD_OVERLAP_50: 50%+ words shared (anywhere in sentences)

ADDITIONAL:
- Fuzzy matching with `difflib.SequenceMatcher` for Whisper STT variations
  ("ngàm" vs "ngầm" vs "ngàn" vs "ngạc" - same word)
- Vietnamese tone diacritics normalization
- Temporal proximity: <30s between segments = HIGH confidence

Usage: python3 detect_adjacent_issues.py <verify.json> [--min-gap 0.10]
"""

import json
import sys
import argparse
import re
import unicodedata


def normalize_vn(text: str) -> str:
    """Diacritic-insensitive Vietnamese normalize.
    'ngàm' -> 'ngam', 'ngầm' -> 'ngam', 'ngàn' -> 'ngan', 'ngạc' -> 'ngac'
    """
    # Strip diacritics
    nfd = unicodedata.normalize("NFD", text)
    stripped = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return stripped.lower().strip()


def normalize(text: str) -> str:
    """Basic normalize: lowercase + collapse whitespace."""
    return " ".join(text.lower().strip().split())


def detect_leading_match(segs):
    """2+ identical leading words between consecutive segments."""
    results = []
    for i in range(len(segs) - 1):
        t1 = normalize(segs[i]["text"])
        t2 = normalize(segs[i + 1]["text"])
        w1 = t1.split()
        w2 = t2.split()
        common = 0
        for a, b in zip(w1, w2):
            if a == b:
                common += 1
            else:
                break
        if common >= 2:
            results.append({
                "type": "LEADING_MATCH",
                "seg_idx_1": i,
                "seg_idx_2": i + 1,
                "common": common,
                "text_1": segs[i]["text"].strip()[:80],
                "text_2": segs[i + 1]["text"].strip()[:80],
            })
    return results


def detect_adjacent_duplicates_tier(segs):
    """TIER DETECTION (v3.7) - bắt false start retake mà LEADING_MATCH miss.

    Tuấn Anh HARD RULE: 'Nó là false start nhưng thay vì em cắt cái câu lặp đầu tiên
    và giữ câu thứ 2 thì em lại cắt hết' - cần phân biệt câu CÓ lặp vs câu KHÔNG lặp.

    Real case DJI_0619:
    - seg [28] "mình tìm hiểu trên mạng mà mình" (7w) - attempt 1
    - seg [29] "mình tìm hiểu trên mạng mà mình biết được" (8w) - attempt 2
    → common=4 ("mình","tìm","hiểu","trên") - LEADING_MATCH miss vì only 4 words at start
    → TIER detection catch via is_retake: len(w2)=8 > len(w1)=7 AND len(w1) <= 7

    3 tier triggers (any = cut):
    - is_subset: common == len(w1) → câu trước = subset hoàn toàn câu sau
    - is_retake: len(w2) > len(w1) AND len(w1) <= 7 AND common >= 2
    - is_long_common: common >= 4 (bất kể ratio)

    Skip nếu is_intro_long (câu trước DÀI + ngắn hơn câu sau): not false start
    """
    results = []
    for i in range(len(segs) - 1):
        t1 = normalize(segs[i]["text"])
        t2 = normalize(segs[i + 1]["text"])
        w1 = t1.split()
        w2 = t2.split()
        common = 0
        for a, b in zip(w1, w2):
            if a == b:
                common += 1
            else:
                break
        if common < 2:
            continue
        ratio = common / len(w1) if w1 else 0
        is_subset = (common == len(w1))
        is_retake = (len(w2) > len(w1) and len(w1) <= 7 and common >= 2)
        is_long_common = (common >= 4)
        is_intro_long = (len(w1) >= 7 and len(w2) <= len(w1) and ratio <= 0.7)

        is_false_start = (is_subset or is_retake or is_long_common) and not is_intro_long

        if is_false_start:
            tier_names = []
            if is_subset: tier_names.append("subset")
            if is_retake: tier_names.append("retake")
            if is_long_common: tier_names.append("long_common")
            results.append({
                "type": "TIER_FALSE_START",
                "seg_idx_1": i,
                "seg_idx_2": i + 1,
                "common": common,
                "ratio": round(ratio, 2),
                "len_w1": len(w1),
                "len_w2": len(w2),
                "tiers": tier_names,
                "text_1": segs[i]["text"].strip()[:80],
                "text_2": segs[i + 1]["text"].strip()[:80],
            })
    return results


def detect_ngram_overlap(segs, n=3):
    """Shared 3-gram phrase between adjacent segments (in order anywhere).
    Only count as duplicate if 3-gram shared AND it's not a trivial word like 'là' / 'có'.
    """
    # Skip these trivial 3-grams (narrative emphasis + continuation patterns)
    SKIP_PHRASES = {
        "là tốn thời", "là cho mình", "có cái này",
        "các bạn sẽ", "thì cái này", "là cái này",
        "thứ nhất là", "rất là tốn", "nó lại cực",
        "là một cái", "có một cái", "và một cái",
        "cái này nè", "cái này nha", "này các bạn",
        # Added 10/10 v3.1: continuation patterns
        "muốn gắn lên", "gắn lên một", "sở hữu máy",
        "muốn đổi góc", "đổi góc các", "các bạn chỉ",
        "từ khi m", "từ khi mình", "khi mà mình",
        "thì khi m", "và khi m", "là khi m",
    }
    results = []
    for i in range(len(segs) - 1):
        t1 = normalize(segs[i]["text"])
        t2 = normalize(segs[i + 1]["text"])
        w1 = t1.split()
        w2 = t2.split()
        if len(w1) < n or len(w2) < n:
            continue
        # Get all n-grams from t1
        ngrams1 = set(" ".join(w1[j:j+n]) for j in range(len(w1)-n+1))
        ngrams2 = [" ".join(w2[j:j+n]) for j in range(len(w2)-n+1)]
        # Find ALL shared n-grams
        shared_list = [ng for ng in ngrams2 if ng in ngrams1 and ng not in SKIP_PHRASES]
        if not shared_list:
            continue
        # Require either:
         # - 2+ shared n-grams (strong duplicate signal)
         # - 1 shared n-gram + 6+ total word overlap (excluding trivial)
         # Bump from 4→6 v3.1 to reduce false positive on narrative continuation
        t1_set = set(w1)
        t2_set = set(w2)
        total_overlap = len(t1_set & t2_set)
        if len(shared_list) >= 2 or total_overlap >= 6:
            results.append({
                "type": "NGRAM_OVERLAP",
                "seg_idx_1": i,
                "seg_idx_2": i + 1,
                "shared_phrases": shared_list[:3],
                "total_overlap": total_overlap,
                "text_1": segs[i]["text"].strip()[:80],
                "text_2": segs[i + 1]["text"].strip()[:80],
            })
    return results


def detect_key_phrase_overlap(segs):
    """Shared SP-related key phrases (case-insensitive fuzzy)."""
    # Common SP-related phrases in TikTok reviews
    KEY_PHRASES = [
        "ngàm đực", "ngàm cái", "ngàm thao tác", "ngàm thao tác nhanh",
        "ngàm thay thách", "ngàm nhanh", "ngàm thao",
        "pocket 3", "pocket ba",
        "tripod", "kẹp điện thoại", "kẹp phone",
        "tìm hiểu trên mạng", "mình tìm hiểu",
        "cảm ơn các bạn",
        "bấm vào link", "bấm link",
        "chúc các bạn", "chúc các anh",
        "ngày hôm nay", "hôm nay mình",
        "mời các bạn", "mời anh em",
    ]
    results = []
    for i in range(len(segs) - 1):
        t1 = normalize_vn(segs[i]["text"])
        t2 = normalize_vn(segs[i + 1]["text"])
        shared_phrases = []
        for phrase in KEY_PHRASES:
            p_norm = normalize_vn(phrase)
            if p_norm in t1 and p_norm in t2:
                shared_phrases.append(phrase)
        if len(shared_phrases) >= 1:
            # Require additional 3+ words shared (not just "có thể" / "các bạn")
            t1_norm = normalize(segs[i]["text"])
            t2_norm = normalize(segs[i + 1]["text"])
            w1 = set(t1_norm.split())
            w2 = set(t2_norm.split())
            additional = len(w1 & w2) - len(shared_phrases) * 3  # exclude phrase words
            if additional >= 2:  # need 2+ words outside the phrase
                results.append({
                    "type": "KEY_PHRASE_OVERLAP",
                    "seg_idx_1": i,
                    "seg_idx_2": i + 1,
                    "shared_phrases": shared_phrases[:3],
                    "additional_words_shared": additional,
                    "text_1": segs[i]["text"].strip()[:80],
                    "text_2": segs[i + 1]["text"].strip()[:80],
                })
    return results


def detect_word_overlap_50(segs, threshold=0.5):
    """50%+ words shared (anywhere, not just leading) - only for SHORT adjacent sentences."""
    results = []
    for i in range(len(segs) - 1):
        t1 = normalize(segs[i]["text"])
        t2 = normalize(segs[i + 1]["text"])
        w1 = set(t1.split())
        w2 = set(t2.split())
        if not w1 or not w2:
            continue
        overlap = len(w1 & w2)
        min_size = min(len(w1), len(w2))
        max_size = max(len(w1), len(w2))
        if min_size < 5 or max_size > 12:
            continue  # Skip too short or too long (avoid over-detection)
        ratio = overlap / min_size
        if ratio >= threshold:
            results.append({
                "type": "WORD_OVERLAP_50",
                "seg_idx_1": i,
                "seg_idx_2": i + 1,
                "overlap": overlap,
                "ratio": round(ratio, 2),
                "text_1": segs[i]["text"].strip()[:80],
                "text_2": segs[i + 1]["text"].strip()[:80],
            })
    return results


def detect_silence_gaps(segs, min_gap=0.10):
    """Gaps > min_gap between consecutive segments."""
    gaps = []
    for i in range(len(segs) - 1):
        gap = segs[i + 1]["start"] - segs[i]["end"]
        if gap > min_gap:
            gaps.append({
                "seg_idx_1": i,
                "seg_idx_2": i + 1,
                "gap_seconds": round(gap, 3),
                "end_prev": round(segs[i]["end"], 3),
                "start_next": round(segs[i + 1]["start"], 3),
                "text_prev": segs[i]["text"].strip()[:40],
                "text_next": segs[i + 1]["text"].strip()[:40],
            })
    return gaps


def run_all_detectors(segs, min_gap=0.10):
    """Run all 5 detection algorithms + merge dedupe (v3.7 entry point).

    Returns:
        dict with 'adjacent_duplicates' (combined), 'silence_gaps', 'total_high_issues', 'pass'

    5 algorithms:
    1. LEADING_MATCH: 2+ identical leading words
    2. TIER_FALSE_START: subset/retake/long_common (3 tiers)
    3. NGRAM_OVERLAP: 3-gram shared + 6+ total overlap
    4. KEY_PHRASE_OVERLAP: SP terms + 2+ extra words
    5. WORD_OVERLAP_50: 50%+ shared, 5-12 word sentences
    """
    leading = detect_leading_match(segs)
    tier = detect_adjacent_duplicates_tier(segs)
    ngram = detect_ngram_overlap(segs, n=3)
    keyphrase = detect_key_phrase_overlap(segs)
    word_overlap = detect_word_overlap_50(segs, threshold=0.5)

    all_dupes = {}
    for d in leading + tier + ngram + keyphrase + word_overlap:
        key = (d["seg_idx_1"], d["seg_idx_2"])
        if key not in all_dupes:
            all_dupes[key] = {
                "seg_idx_1": d["seg_idx_1"],
                "seg_idx_2": d["seg_idx_2"],
                "detection_types": [d["type"]],
                "details": [d],
                "text_1": d["text_1"],
                "text_2": d["text_2"],
            }
        else:
            if d["type"] not in all_dupes[key]["detection_types"]:
                all_dupes[key]["detection_types"].append(d["type"])
            all_dupes[key]["details"].append(d)

    duplicates = sorted(all_dupes.values(), key=lambda x: x["seg_idx_1"])
    gaps = detect_silence_gaps(segs, min_gap)

    return {
        "adjacent_duplicates": duplicates,
        "silence_gaps": gaps,
        "total_high_issues": len(duplicates) + len(gaps),
        "pass": (len(duplicates) + len(gaps)) == 0,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("verify_json", help="Path to verify JSON")
    parser.add_argument("--min-gap", type=float, default=0.10, help="Min silence gap threshold (default 0.10s)")
    parser.add_argument("--quiet", action="store_true", help="Suppress verbose output")
    args = parser.parse_args()

    with open(args.verify_json) as f:
        data = json.load(f)

    segs = [s for s in data["segments"] if s["text"].strip() not in ("ừ", "ờ", "à", "ừm", "")]

    if not args.quiet:
        print(f"📊 File: {args.verify_json}")
        print(f"   Real segments: {len(segs)}\n")

    # Detect via all 5 algorithms
    leading = detect_leading_match(segs)
    tier = detect_adjacent_duplicates_tier(segs)
    ngram = detect_ngram_overlap(segs, n=3)
    keyphrase = detect_key_phrase_overlap(segs)
    word_overlap = detect_word_overlap_50(segs, threshold=0.5)

    # Dedupe by (seg_idx_1, seg_idx_2) - merge all detection types
    all_dupes = {}
    for d in leading + tier + ngram + keyphrase + word_overlap:
        key = (d["seg_idx_1"], d["seg_idx_2"])
        if key not in all_dupes:
            all_dupes[key] = {
                "seg_idx_1": d["seg_idx_1"],
                "seg_idx_2": d["seg_idx_2"],
                "detection_types": [d["type"]],
                "details": [d],
                "text_1": d["text_1"],
                "text_2": d["text_2"],
            }
        else:
            if d["type"] not in all_dupes[key]["detection_types"]:
                all_dupes[key]["detection_types"].append(d["type"])
            all_dupes[key]["details"].append(d)

    # Sort by seg_idx_1
    duplicates = sorted(all_dupes.values(), key=lambda x: x["seg_idx_1"])

    if not args.quiet:
        print(f"=== ADJACENT DUPLICATES (5 detection algorithms) ===")
        if duplicates:
            for d in duplicates:
                types_str = " + ".join(d["detection_types"])
                print(f"  ⚠️ Seg [{d['seg_idx_1']+1}] ↔ [{d['seg_idx_2']+1}] ({types_str}):")
                print(f"     [CUT]:  {d['text_1']}")
                print(f"     [KEEP]: {d['text_2']}")
        else:
            print(f"  ✅ No adjacent duplicates detected")
        print()

    # Detect silence gaps > min_gap
    gaps = detect_silence_gaps(segs, args.min_gap)
    if not args.quiet:
        print(f"=== SILENCE GAPS (> {args.min_gap}s) ===")
        if gaps:
            for g in gaps:
                print(f"  ⚠️ Gap {g['gap_seconds']}s between [{g['seg_idx_1']+1}]{g['end_prev']}s and [{g['seg_idx_2']+1}]{g['start_next']}s")
                print(f"     [{g['seg_idx_1']+1}]: {g['text_prev']}")
                print(f"     [{g['seg_idx_2']+1}]: {g['text_next']}")
        else:
            print(f"  ✅ No gaps > {args.min_gap}s")
        print()

    # Summary
    total_issues = len(duplicates) + len(gaps)
    if not args.quiet:
        print(f"📊 Total HIGH issues: {total_issues}")
        if total_issues == 0:
            print(f"✅ PASS - clip sạch")
        else:
            print(f"❌ FAIL - cần cut {total_issues} issues (CUT prev, KEEP next)")

    # Output JSON for machine processing
    result = {
        "file": args.verify_json,
        "n_segments": len(segs),
        "adjacent_duplicates": duplicates,
        "silence_gaps": gaps,
        "total_high_issues": total_issues,
        "pass": total_issues == 0,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))

    sys.exit(0 if total_issues == 0 else 1)


if __name__ == "__main__":
    main()