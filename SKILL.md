---
name: tiktok-clip-editor-v2
description: Edit TikTok clips theo workflow Tuấn Anh 10/08/2026 — Whisper large-v3-mlx word-by-word → đọc kĩ → cắt repetitive/tangents/filler/silence/pricing → speed 1.3x → render → re-Whisper → ship. Default TikTok spec 1080×1920 30fps với 30ms audio fade. Workspace gọn gàng theo pattern browser-use/video-use trong `/Volumes/Storage-1/Pocket3/Hermes-edit/<project-id>/`. v2.0
tags: [TikTok, video-edit, non-linear, ffmpeg, whisper-large-v3, speed-130, hard-rule-30ms-fade, browser-use-pattern]
---

# TikTok Clip Editor v2 — Tuấn Anh Workflow

> **Workflow đã verify 10/08/2026** sau khi ship nhiều clip (body mist 0093, tripod 0710/0712/0713/0715, đèn LED 0623/0636, case Pocket 3 0492). Áp dụng được cho MỌI clip TikTok review.

## 🚨 6-PHASE WORKFLOW (verbatim từ Tuấn Anh 10/08/2026)

### PHASE 0: Setup workspace

```bash
# Lấy video mới nhất từ Footages (DJI / A001 / iPhone)
FOOTAGES="/Volumes/Storage-1/Pocket3/Footages"
LATEST=$(ls -t "$FOOTAGES"/*.MP4 "$FOOTAGES"/*.mov 2>/dev/null | head -1)
echo "Source: $LATEST"

# Tạo workspace theo pattern browser-use/video-use
# WORKING DIR: /Volumes/Storage-1/Pocket3/Hermes-edit/<project-id>/  (lowercase, temporary)
# SHIP DIR:   /Volumes/Storage-1/Pocket3/Hermes-Edit/                  (uppercase, FINAL output)
PROJECT_ID=$(basename "$LATEST" .MP4 | tr ' ' '_')
WORKSPACE="/Volumes/Storage-1/Pocket3/Hermes-edit/$PROJECT_ID"
SHIP_DIR="/Volumes/Storage-1/Pocket3/Hermes-Edit"
mkdir -p "$WORKSPACE"/{transcripts,clips_graded,verify}

# Verify file
ffprobe -v error -show_entries format=duration:stream=codec_name,width,height,r_frame_rate "$LATEST"
```

**Cấu trúc workspace (browser-use/video-use pattern, applied cho anh):**
```
/Volumes/Storage-1/Pocket3/Hermes-edit/<project-id>/
├── source.mp4                    ← source file (touched only read-only)
├── transcripts/
│   └── audio.json                ← Whisper cache (verbatim audio)
├── project.md                    ← ghi chú: SP, nội dung, USPs, target audience
├── takes_packed.md               ← phrase-level transcript (PRIMARY READING)
├── edl.json                      ← cut decisions (in/out, reason)
├── clips_graded/                 ← per-segment extracts với 30ms fade
├── preview.mp4                   ← intermediate verify
└── final.mp4                     ← ship ready (1080×1920 30fps)
```

### PHASE 1: Whisper large-v3-mlx WORD-BY-WORD

```bash
# Extract WAV 16kHz mono (Whisper requirement)
ffmpeg -v error -y -i "$LATEST" -vn -ac 1 -ar 16000 -c:a pcm_s16le "$WORKSPACE/audio.wav"

# Whisper large-v3-mlx WORD-BY-WORD with timestamp (an toàn hallucinate-resistant)
mlx_whisper --model mlx-community/whisper-large-v3-mlx \
  --language vi \
  --output-format json \
  --output-name audio \
  --word-timestamps True \
  --condition-on-previous-text False \
  --compression-ratio-threshold 2.0 \
  --no-speech-threshold 0.6 \
  --logprob-threshold -0.5 \
  "$WORKSPACE/audio.wav"
# → $WORKSPACE/transcripts/audio.json (word-level timestamps)
```

**Tuấn Anh HARD RULE:** PHẢI dùng `--word-timestamps True` + `--condition-on-previous-text False` để không bị Whisper hallucinate autoregressive loop. Detect loop bằng script `scripts/detect_whisper_loop.py`.

### 🔥 OPTIONAL: RAW VERBATIM mode (verbatim Tuấn Anh 10/08 — không filter gì hết)

Khi cần transcript **100% nguyên bản** (không chỉnh sửa, không normalize, giữ tất cả filler/lặp/hallucinate/sai chính tả để tự LLM đọc hiểu + quyết định cắt):

```bash
# RAW VERBATIM - không filter threshold nào
mlx_whisper \
  --model mlx-community/whisper-large-v3-mlx \
  --language vi \
  --output-format json \
  --output-name audio \
  --word-timestamps True \
  --condition-on-previous-text False \
  --compression-ratio-threshold 2.4 \
  --no-speech-threshold 0.4 \
  --logprob-threshold -1.0 \
  "$WORKSPACE/audio.wav"
```

**Khác biệt vs default:**

| Flag | Default (v2.2) | RAW VERBATIM (v2.3) |
|---|---|---|
| `--compression-ratio-threshold` | 2.0 (filter text khác thường) | **2.4** (giữ text khác thường) |
| `--no-speech-threshold` | 0.6 (filter voice thấp) | **0.4** (giữ voice thấp) |
| `--logprob-threshold` | -0.5 (filter confidence thấp) | **-1.0** (giữ tất cả) |

**Use case RAW VERBATIM:**
- Khi source có giọng nói yếu/nhỏ (Pocket 3, iPhone outdoor)
- Khi muốn tự LLM đọc + quyết định cắt thay vì Whisper filter sẵn
- Khi cần transcript chính xác 100% cho wiki/transcript tham khảo
- Khi anh muốn đọc TOÀN BỘ transcript để hiểu trước khi quyết định cut

**Use case DEFAULT (v2.2):**
- Edit TikTok workflow thông thường
- Khi muốn Whisper pre-filter text rác để LLM tập trung vào content

### PHASE 2: ĐỌC KĨ → Hiểu ngữ cảnh → Xoá repetitive + tangents → **REARRANGE theo Problem-Solution formula (HARD RULE v2.2)**

```bash
# Pack word-level segments thành phrase-level transcript (PRIMARY READING VIEW)
python3 /Users/tuananh4865/.hermes/skills/media/tiktok-clip-editor-v2/scripts/pack_transcript.py \
  "$WORKSPACE/transcripts/audio.json" \
  "$WORKSPACE/takes_packed.md"
```

**Tuấn Anh HARD RULE (verbatim):** *"đọc kĩ transcript liên kết nội dung thành ngữ cảnh để hiểu toàn bộ nội dung clip và xoá đi repetitive content, Remove off-topic tangents and keep only the main points"*

### 🎯 ADJACENT DUPLICATE + SILENCE GAP (verbatim Tuấn Anh 10/08)

**Tuấn Anh HARD RULE 1 (adjacent duplicate):** *"ở 2 câu liền kề nhau thì nếu lặp từ 2 từ trở lên thì hãy cắt câu nằm trước và giữ lại câu sau"*

**Luật đã clarify 13/08/2026 (verbatim từ anh Tuấn Anh):** 
- "có nhớ về luật 2 câu liền kề nhau không được phép trùng từ 2 từ trở lên không?"
- ÁP DỤNG = check 2 câu liền kề (i, i+1) có ≥2 từ chung VÀ semantic similarity > 0.4
- **Common words ≠ duplicate** nếu 2 câu khác NỘI DUNG (vd "có thể", "vô trong", "cái túi" - common filler)
- **CHỈ DUPLICATE nếu** cùng chủ đề + cùng từ vựng (semantic + word overlap)

**4 DETECTION ALGORITHMS** (match ANY → cut):
1. LEADING_MATCH: 2+ identical leading words at boundary
2. NGRAM_OVERLAP: shared 3-gram phrase between adjacent segments
3. KEY_PHRASE_OVERLAP: shared SP-related terms (ngàm đực, ngàm thao tác...)
4. WORD_OVERLAP_50: 50%+ words shared (anywhere in sentences)

**NEW 13/08/2026 - SEMANTIC_SIMILARITY detector:**
- SequenceMatcher.ratio() > 0.4 AND common words >= 2 → DUPLICATE
- Real case clip_0088 V6: Seg 6→7 sim=0.47 ("gồm hết ... vô trong cái túi" vs "pocket 3 ... vô trong cái túi") → CẮT
- Real case clip_0088 V6: Seg 9→10 sim=0.5 ("nhét lại vô cái túi nhỏ" vs "đây nè cái túi nhỏ") → CẮT

**Tuấn Anh HARD RULE 2 (silence gap):** *"Khoảng lặng nào trên 0.10s cũng phải cắt"*

**Detection workflow:**
```bash
python3 /Users/tuananh4865/.hermes/skills/media/tiktok-clip-editor-v2/scripts/detect_adjacent_issues.py \
  "$WORKSPACE/recheck_dir/audio.json" --min-gap 0.10
```

**Implementation:** `scripts/detect_adjacent_issues.py` (16.1KB - 4 detectors + SequenceMatcher + Vietnamese tone normalization). Output JSON includes `adjacent_duplicates` with `seg_idx_1`, `seg_idx_2`, `detector_name`, `confidence`.

**Auto-cut strategy** (verbatim from HARD RULE 1):
- Nếu duplicate detected → **CẮT CÂU TRƯỚC, GIỮ CÂU SAU** (not cắt cả 2)
- Trừ khi common words chỉ là filler (vd "có thể", "thì", "mà") → ALLOW (không phải duplicate thực sự)

**❌ ANTI-PATTERN (ĐÃ HỌC 13/08):**
**FILTER Anti-FP (nhằm tránh false positive):**
- Common filler words như "có thể", "thì", "mà", "là", "vô trong", "cái túi", "bỏ vô"
- KHI `SequenceMatcher.ratio()` > 0.4 nhưng TẤT CẢ common words đều là filler → SKIP (không phải duplicate thật)
- VÍ DỤ: "Có tới 4 slot" vs "mình có thể bỏ" → common "có" + "có thể" = filler, sim=0.25 → ALLOW
- VÍ DỤ (clip_0088 V6): "gồm hết vô trong cái túi" vs "pocket 3 vô trong cái túi đó" → common "vô trong" KHÔNG phải filler nhưng sim=0.47 + CÙNG NỘI DUNG (bỏ vào túi) → VIOLATION

**✅ DÙNG:**
- Nếu common words ≥2 + ratio > 0.4 → DUPLICATE → CẮT câu trước, giữ câu sau
- Nếu common words ≥2 + ratio > 0.4 + TẤT CẢ common là filler → ALLOW (false positive tránh được)
- Nếu common words <2 → SKIP (chưa đủ overlap)

 
- **KHÔNG dùng keyword counts** (đếm từ "pocket 3 xuất hiện 7 lần") làm duplicate indicator
- Keyword counts chỉ là INFO, không phải FAIL criterion
- 1 từ xuất hiện 5+ lần ≠ duplicate nếu các câu khác nội dung

**✅ ĐÃ VERIFY:** 
- V7 clip_0088: 0 violations theo luật đúng (sem > 0.4 + 2 từ chung + cùng nội dung)
- 5/7 clips đã verify không có duplicate semantic
### PHASE 3: Cut + loại bỏ các đoạn bị lặp + câu treo + lỗi

```bash
# Build EDL (Edit Decision List) JSON từ transcript
# Format: [{"start": 0.0, "end": 5.2, "beat": "HOOK", "reason": "..."}, ...]
# SAVE to $WORKSPACE/edl.json

# Extract per-segment với 30ms audio fade (Hard Rule #3 browser-use/video-use)
python3 /Users/tuananh4865/.hermes/skills/media/tiktok-clip-editor-v2/scripts/extract_segments.py \
  "$WORKSPACE/source.mp4" \
  "$WORKSPACE/edl.json" \
  "$WORKSPACE/clips_graded/"
```

**Output:** `$WORKSPACE/clips_graded/seg_001.mp4`, `seg_002.mp4`...

### PHASE 4: Tăng speed 1.3x (Tuấn Anh HARD RULE 10/08)

```bash
# Tuấn Anh HARD RULE: speed 1.3x BẮT BUỘC sau khi cắt gọn, TRƯỚC khi render
# Apply 30ms fade vẫn giữ
python3 /Users/tuananh4865/.hermes/skills/media/tiktok-clip-editor-v2/scripts/apply_speed_130.py \
  "$WORKSPACE/clips_graded/" \
  "$WORKSPACE/clips_graded/"
```

### PHASE 5: Render final 1080×1920 30fps TikTok spec

```bash
# Concat + render final với TikTok spec
# Tuấn Anh HARD RULE 10/08: 1080×1920 30fps AAC-LC 44100Hz stereo 192k +faststart
# afade=t=in:st=0:d=0.03 + afade=t=out:st={dur-0.03}:d=0.03 cho MỖI segment (browser-use Hard Rule #3)

python3 /Users/tuananh4865/.hermes/skills/media/tiktok-clip-editor-v2/scripts/render_final.py \
  "$WORKSPACE/clips_graded/" \
  "$WORKSPACE/final.mp4"
```

**Browser-use/video-use HARD RULE #3 (verbatim):** *"30ms audio fades at every segment boundary (`afade=t=in:st=0:d=0.03,afade=t=out:st={dur-0.03}:d=0.03`). Otherwise audible pops at every cut."*

### PHASE 6: Re-Whisper OUTPUT (loop nếu fail)

```bash
# Tuấn Anh HARD RULE 10/08: "render xong thì check lại với các tiêu chí trên"
# → Re-transcribe FINAL output với condition_on_previous_text=False để check còn sót không

ffmpeg -v error -y -i "$WORKSPACE/final.mp4" -vn -ac 1 -ar 16000 -c:a pcm_s16le "$WORKSPACE/verify.wav"
mlx_whisper --model mlx-community/whisper-large-v3-mlx \
  --language vi --condition-on-previous-text False \
  --output-dir "$WORKSPACE/verify/" --output-name audio --output-format json \
  "$WORKSPACE/verify.wav"

# Run verify với tiêu chí gốc (no repetitive, no off-topic, no filler, no pricing)
python3 /Users/tuananh4865/.hermes/skills/media/tiktok-clip-editor-v2/scripts/verify_final.py \
  "$WORKSPACE/verify/audio.json" \
  "$WORKSPACE/edl.json" \
  "$WORKSPACE/final.mp4"

# If FAIL: refine EDL + re-render từ phase 3
# If PASS: SHIP flat vào Hermes-Edit/

# Step 1: Tạo ship filename
# Format: clip_<SOURCE_BASE>_<PRODUCT-SLUG>_speed130_FINAL.mp4
SHIP_DIR="/Volumes/Storage-1/Pocket3/Hermes-Edit"
# Example: clip_0623_0636_den-LED-kep-dien-thoai_speed130_FINAL.mp4
# (source base + product slug, lấy từ $WORKSPACE/project.md hoặc edl.json)

# Step 2: Copy từ workspace ra ship dir (flat, không folder con)
cp "$WORKSPACE/final.mp4" "$SHIP_DIR/clip_${SOURCE_BASE}_${PRODUCT_SLUG}_speed130_FINAL.mp4"

# Step 3: Log + cleanup
echo "✅ Shipped: $SHIP_DIR/clip_${SOURCE_BASE}_${PRODUCT_SLUG}_speed130_FINAL.mp4"
```

**PASS criteria:**
- ✅ No filler "ừm/ờ/à" trong first 30s (HOOK)
- ✅ No pricing mentions
- ✅ No 5+ words repeated ≥ 3x in 30s window
- ✅ No off-topic segments
- ✅ Duration 60-90s

## 🚨 FINAL SHIP LOCATION (HARD RULE 10/08/2026)

**Output cuối cùng (final.mp4) PHẢI xuất ra `/Volumes/Storage-1/Pocket3/Hermes-Edit/` (flat folder), KHÔNG save trong folder con project.**

Format: `clip_<SOURCE_BASE>_<PRODUCT-SLUG>_speed130_FINAL.mp4`

```bash
# Khi ship: copy từ workspace/final.mp4 ra Hermes-Edit (flat)
FINAL="/Volumes/Storage-1/Pocket3/Hermes-Edit/clip_${SOURCE_BASE}_${PRODUCT_SLUG}_speed130_FINAL.mp4"
cp "$WORKSPACE/final.mp4" "$FINAL"
```

**Working dir** vẫn theo project ID ở `/Volumes/Storage-1/Pocket3/Hermes-edit/<project-id>/` (chữ thường + "edit"). **Final ship** ra `/Volumes/Storage-1/Pocket3/Hermes-Edit/` (chuẩn hoa + "Edit").

## 📁 Workspace Convention (browser-use/video-use pattern)

**MỖI project** có folder riêng ở `/Volumes/Storage-1/Pocket3/Hermes-edit/<project-id>/`:

```
Hermes-edit/                                 ← working dir (lowercase, tạm thời)
└── <project-id>/                            ← per-clip workspace
    ├── source.mp4                            
    ├── audio.wav                             
    ├── transcripts/audio.json                
    ├── takes_packed.md                       
    ├── project.md                           
    ├── edl.json                              
    ├── clips_graded/                         
    ├── verify/audio.json                     
    └── final.mp4                              ← intermediate

Hermes-Edit/                                  ← FINAL SHIP output (flat)
├── clip_0623_0636_den-LED-kep-dien-thoai_speed130_FINAL.mp4
├── clip_0492_case-cung-pocket3-KNF_speed130_FINAL.mp4
└── ...
```

**Output final chỉ ship ra `Hermes-Edit/`** (KHÔNG folder con, KHÔNG để trong `Hermes-edit/<project-id>/`).

## 🎬 5 HARD RULES (Tuấn Anh 10/08/2026)

1. **Speed 1.3x BẮT BUỘC** - áp dụng SAU khi cắt gọn, TRƯỚC khi render
2. **1080×1920 30fps TikTok spec BẮT BUỘC** - default cho mọi clip
3. **30ms audio fade BẮT BUỘC** ở MỖI segment boundary (browser-use Hard Rule #3) - `afade=t=in:st=0:d=0.03,afade=t=out:st={dur-0.03}:d=0.03`
4. **Problem-Solution REARRANGED BẮT BUỘC** - HOOK = PAIN thật → PAIN_CONTEXT → PAIN_DEPTH → SOLUTION_REVEAL → USP_PROOF → RECAP → CTA (default cho mọi clip mới từ 10/08/2026)
5. **Adjacent duplicate + silence gap BẮT BUỘC cut** - 2+ words lặp liền kề = CUT prev/KEEP next. Gap > 0.10s = FAIL. Detect bằng `scripts/detect_adjacent_issues.py`

## 🚫 Anti-patterns (lesson hôm nay 10/08)

- ❌ Dùng 30s transcript cache preview (PHẢI Whisper FULL source 100-300s)
- ❌ Build KEEP ranges từ FIRST/LAST 5 segments (PHẢI đọc TOÀN BỘ)
- ❌ LINEAR keep_plan theo source-space order (PHẢI rearrange theo narrative)
- ❌ Tin subagent PASS verdict nếu token limit fail (self-verify thay thế KHÔNG được)
- ❌ Apply PRE-PASS trước khi có output file (POST-RENDER verify)

## 📂 Reference: browser-use/video-use

Skill design tham khảo `https://github.com/browser-use/video-use`:
- **Hard Rule #3**: 30ms audio fade at every segment boundary
- **Hard Rule #2**: Per-segment extract → lossless `-c copy` concat, not single-pass filtergraph
- **Hard Rule #6**: Never cut inside a word. Snap every cut edge to a word boundary
- **Hard Rule #9**: Cache transcripts per source
- **Directory layout**: `<videos_dir>/edit/` for session outputs

## Scripts

- `scripts/pack_transcript.py` - Word-level JSON → phrase-level `takes_packed.md` (PRIMARY reading)
- `scripts/detect_whisper_loop.py` - Detect autoregressive hallucinate loop
- `scripts/extract_segments.py` - EDL → per-segment extracts với 30ms fade
- `scripts/apply_speed_130.py` - Speed 1.3x với 30ms fade preserved
- `scripts/render_final.py` - Concat demuxer → 1080×1920 30fps TikTok spec
- `scripts/verify_final.py` - Re-Whisper final + check no filler/lặp/pricing

## 📋 Version History

- **v3.0 (10/08/2026)** - detect_adjacent_issues.py upgrade với 4 detection algorithms: LEADING_MATCH (2+ words identical leading) + NGRAM_OVERLAP (3-gram shared + 4+ total overlap) + KEY_PHRASE_OVERLAP (SP terms + 2+ extra words) + WORD_OVERLAP_50 (50%+ shared words, 5-12 word sentences). Vietnamese diacritic-insensitive normalize. SKIP_PHRASES filter cho narrative emphasis. Cut 4 dup trong v7 (DJI_0619): verify[02] 'Nó rất là tốn thời gian' + verify[13/15] 'ngàm đực' + verify[18] 'mình tìm hiểu trên mạng'.
- **v2.7 (10/08/2026)** - HARD RULE #5 added: Adjacent duplicate (2+ leading words) = CUT prev/KEEP next. Silence gap > 0.10s = FAIL. `detect_adjacent_issues.py` upgraded to HIGH-only detection (no more strict/loose split).
- **v2.6 (10/08/2026)** - NEW `detect_adjacent_issues.py` script. Phát hiện adjacent duplicate 3+ words strict + 2+ loose + silence gap. Verified DJI_0619 v2 FAIL.
- **v2.5 (10/08/2026)** - Thêm RAW VERBATIM mode cho Whisper. Lệnh `--compression-ratio-threshold 2.4 --no-speech-threshold 0.4 --logprob-threshold -1.0` giữ 100% text verbatim, không filter. Phù hợp khi LLM muốn tự đọc + quyết định cắt thay vì Whisper filter sẵn.
- **v2.4 (10/08/2026)** - Problem-Solution REARRANGED HARD RULE added. Default 7-beat narrative (HOOK_PROBLEM→PAIN_CONTEXT→PAIN_DEPTH→SOLUTION_REVEAL→USP_PROOF→RECAP→CTA) cho mọi clip mới. Verified v2 PASS (DJI_0619 ngàm thao tác nhanh).
- **v2.3 (10/08/2026)** - FINAL ship location FLAT to `/Volumes/Storage-1/Pocket3/Hermes-Edit/` (KHÔNG folder con). Working dir vẫn theo project ID ở `Hermes-edit/<project-id>/` (lowercase, tạm thời).
- **v2.2 (10/08/2026)** - Workflow 6-PHASE theo yêu cầu Tuấn Anh 10/08. Workspace browser-use/video-use pattern ở `/Volumes/Storage-1/Pocket3/Hermes-edit/<project-id>/`. 3 HARD RULES: speed 1.3x + 1080×1920 30fps + 30ms audio fade.
