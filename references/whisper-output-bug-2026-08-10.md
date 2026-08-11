# Bug: Whisper large-v3-mlx outputs to CURRENT WORKING DIRECTORY, not workspace

## Symptom
Chạy `mlx_whisper` với đường dẫn tuyệt đối cho input audio.wav:
```bash
mlx_whisper --model mlx-community/whisper-large-v3-mlx \
  --output-format json --output-name audio \
  audio.wav
```

Whisper TẠO `audio.json` ở **CWD (current working directory)** thay vì ở workspace đã setup. Trong test thực tế 10/08/2026, output đã được tạo ở:
```
/Users/tuananh4865/.hermes/skills/media/tiktok-clip-editor-v2/scripts/audio.json
```
(KHÔNG phải ở workspace `/Volumes/Storage-1/Pocket3/Hermes-edit/<project-id>/transcripts/`)

## Root cause
`mlx_whisper` không nhận `--output-dir` parameter như đã nghĩ — nó output ra CWD bất kể input path.

## FIX
Dùng `--output-dir` flag VỚI đường dẫn TUYỆT ĐỐI:
```bash
cd "$WORKSPACE"  # ← phải cd vào workspace trước
mlx_whisper --model mlx-community/whisper-large-v3-mlx \
  --language vi \
  --output-format json \
  --output-name audio \
  --output-dir "$WORKSPACE/transcripts" \
  --word-timestamps True \
  --condition-on-previous-text False \
  "$WORKSPACE/audio.wav"
```

## Alternative FIX (nếu đã output sai chỗ)
```bash
# Manually mv từ CWD sang workspace
mv "$(pwd)/audio.json" "$WORKSPACE/transcripts/audio.json"
```

## Verify sau khi fix
```bash
ls -lh "$WORKSPACE/transcripts/audio.json"
# Nếu file tồn tại + size > 50KB → OK
```

## Bonus: --condition-on-previous-text flag syntax
- ✅ ĐÚNG: `--condition-on-previous-text False` (HYPHEN)
- ❌ SAI: `--condition_on_previous_text False` (UNDERSCORE) → mlx_whisper báo unknown arg

## Bonus 2: mlx_whisper thường ghi file VTT/SRT/TXT kèm JSON
Khi dùng `--output-format json`, mlx_whisper vẫn tạo `audio.vtt`, `audio.srt`, `audio.tsv`, `audio.txt` cùng `audio.json`. Cần cleanup nếu không cần:
```bash
rm -f "$WORKSPACE/transcripts/audio.vtt" \
      "$WORKSPACE/transcripts/audio.srt" \
      "$WORKSPACE/transcripts/audio.tsv" \
      "$WORKSPACE/transcripts/audio.txt"
# Giữ lại audio.json cho workflow
```

## Real case (10/08/2026)
```bash
# Đã làm (SAI):
mlx_whisper --model mlx-community/whisper-large-v3-mlx \
  --output-format json --output-name audio audio.wav
# → output ra /Users/tuananh4865/.hermes/skills/media/tiktok-clip-editor-v2/scripts/audio.json
# → scripts/ phình size với Whisper output rác

# FIX (ĐÚNG):
cd /Volumes/Storage-1/Pocket3/Hermes-edit/<project-id>
mlx_whisper --model mlx-community/whisper-large-v3-mlx \
  --output-format json --output-name audio \
  --output-dir ./transcripts \
  audio.wav
```
