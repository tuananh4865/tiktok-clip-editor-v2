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

**Tuấn Anh HARD RULE 2 (silence gap):** *"Khoảng lặng nào trên 0.10s cũng phải cắt"*

**Detection script:** `scripts/detect_adjacent_issues.py`

```bash
python3 /Users/tuananh4865/.hermes/skills/media/tiktok-clip-editor-v2/scripts/detect_adjacent_issues.py \
  "$WORKSPACE/verify/verify.json"
```

**Logic:**
- 2 câu liền kề có **2+ words identical ở đầu** → **CUT câu trước, KEEP câu sau** (HIGH severity)
- Gap > **0.10s** giữa 2 segments → **FAIL** (HIGH severity)
- 0 issues = PASS, > 0 issues = FAIL → phải refine EDL + re-render

**Verify transcript có issues:**
```bash
python3 detect_adjacent_issues.py /path/to/verify.json --quiet
# Output JSON với adjacent_duplicates + silence_gaps lists
```

**Real case 10/08 DJI_0619:**
- Source raw: 7 adjacent duplicates detected (false starts trong Whisper STT)
- Final v3: 0 issues (đã skip 0.5-12.2s duplicate "trời ơi một cái phụ kiện")

**Tuấn Anh verbatim:** *"sắp xếp lại nội dung cho thu hút hơn có retension cao hơn theo công thức vấn đề giải pháp"*

**Mặc định ÁP DỤNG Problem-Solution REARRANGED** cho MỌI clip (trừ khi user explicit yêu cầu "giữ nguyên" hoặc "cơ bản").

**Công thức 7 ranges Problem-Solution:**

| # | Range | Content | Lấy từ source (range nguyên gốc) |
|---|---|---|---|
| 1 | **HOOK_PROBLEM** | Mở bằng PAIN thật (worst case scenario) | Từ middle/source - segment có PAIN mạnh nhất |
| 2 | **PAIN_CONTEXT** | Intro ngữ cảnh (anh đang quay video...) | Từ đầu source - segment giới thiệu |
| 3 | **PAIN_DEPTH** | 3 vấn đề cụ thể (tốn thời gian, nguy hiểm...) | Sau PAIN_CONTEXT |
| 4 | **SOLUTION_REVEAL** | Giới thiệu SP (USP chính) | Sau PAIN trong source |
| 5 | **USP_PROOF** | Demo cụ thể / social proof | Từ segments sau SOLUTION |
| 6 | **RECAP** | Pain đã giải quyết | Từ segments cuối (trước CTA) |
| 7 | **CTA** | "Bấm link phía dưới" (GIỮ NGUYÊN CTA) | Từ segments cuối |

**Verified case (DJI_0619 - ngàm thao tác nhanh):**
- v1 (linear HOOK→SETUP→PAIN→USP→BENEFIT→DEMO→RECAP) = 96.66s
- v2 (Problem-Solution REARRANGED: HOOK_PROBLEM→PAIN_CONTEXT→PAIN_DEPTH→SOLUTION_REVEAL→USP_PROOF→RECAP→CTA) = 97.96s ✅
- Retension cao hơn vì HOOK mở bằng PAIN thật (rớt máy) thay vì intro SP mơ hồ

**Template EDL Problem-Solution (copy và điều chỉnh):**
```json
[
  {"start": <PAIN-STRONGEST-SOURCE-TIME>, "end": <PAIN-END>, "beat": "HOOK_PROBLEM", "reason": "Mở bằng PAIN thật - viewer thấy relatable"},
  {"start": <SOURCE-INTRO-START>, "end": <SOURCE-INTRO-END>, "beat": "PAIN_CONTEXT", "reason": "Tạo bối cảnh: anh đang làm gì"},
  {"start": <PAIN-DEPTH-START>, "end": <PAIN-DEPTH-END>, "beat": "PAIN_DEPTH", "reason": "3 vấn đề cụ thể: 1)... 2)... 3)..."},
  {"start": <SOLUTION-START>, "end": <SOLUTION-END>, "beat": "SOLUTION_REVEAL", "reason": "SP ra mắt + USP chính"},
  {"start": <DEMO-START>, "end": <DEMO-END>, "beat": "USP_PROOF", "reason": "Demo cụ thể visual"},
  {"start": <RECAP-START>, "end": <RECAP-END>, "beat": "RECAP", "reason": "Recap pain đã giải"},
  {"start": <CTA-START>, "end": <CTA-END>, "beat": "CTA", "reason": "Bấm link phía dưới - GIỮ NGUYÊN CTA"}
]
```

**Decision matrix (Tuấn Anh 06/08 + 10/08):**
| User signal | Mode |
|---|---|
| "edit clip về X" (default) | **Problem-Solution REARRANGED** |
| "chỉ cắt ghép cơ bản" / "giữ nguyên source order" | Linear (v1) |
| "thu hút hơn" / "retention cao" | **Problem-Solution REARRANGED** |
| "đừng sắp xếp lại" | Linear (v1) |

**EM TỰ ĐỘNG ÁP DỤNG Problem-Solution cho mọi clip mới**, trừ khi user explicit nói "giữ nguyên source order" hoặc "chỉ cắt ghép cơ bản".

**REMOVE these (verbatim Tuấn Anh 10/08):**
- ❌ **Repetitive content** (câu/ý lặp từ 2-3 lần)
- ❌ **Off-topic tangents** (rời khỏi chủ đề chính)
- ❌ **Câu treo** (câu không có predicate)
- ❌ **Câu lỗi** (filler kéo dài, hallucinate, false start)
- ❌ **Filler "ừm", "ờ", "à", "kiểu như", "thì là"**
- ❌ **Khoảng lặng** (silence > 0.5s)
- ❌ **Pricing talk** - Tuấn Anh HARD RULE: **"Cut out any parts where I talk about pricing"**

Workflow tự đọc hiểu (3 bước):
1. **Đọc TOÀN BỘ `takes_packed.md`** - KHÔNG scan keywords, phải đọc cả transcript
2. **Identify narrative arc** - HOOK → SETUP → USP → DEMO → PROOF → CTA
3. **Map mỗi phrase vào beat** - phrase nào phục vụ narrative → KEEP. Phrase nào repeat/tangent → DROP.

**REMOVE these (verbatim Tuấn Anh 10/08):**
- ❌ **Repetitive content** (câu/ý lặp từ 2-3 lần)
- ❌ **Off-topic tangents** (rời khỏi chủ đề chính)
- ❌ **Câu treo** (câu không có predicate)
- ❌ **Câu lỗi** (filler kéo dài, hallucinate, false start)
- ❌ **Filler "ừm", "ờ", "à", "kiểu như", "thì là"**
- ❌ **Khoảng lặng** (silence > 0.5s)
- ❌ **Pricing talk** - Tuấn Anh HARD RULE: **"Cut out any parts where I talk about pricing"**

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
