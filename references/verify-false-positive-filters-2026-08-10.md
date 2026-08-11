# False positive filter patterns cho verify_final.py

## Vấn đề
`verify_final.py` flag pricing mentions. Nhưng có 3 loại FALSE POSITIVES phổ biến cần filter:

### 1. Tên SP chứa "ngàn" (Whisper STT sai "ngàm" → "ngàn")
- SP "Ngàm thao tác nhanh" → Whisper transcribe thành "ngàn thao tác"
- Tên SP "Ngầm" → "ngầm"
- Verify script filter "ngàn" → FALSE POSITIVE

**Filter:**
```python
import re
r"ngàn\s+thao",   # "ngàn thao tác" = "ngàm thao tác"
r"ngầm\s+thao",   # "ngầm thao tác"
```

### 2. Tên SP chứa "k" (K&F Concept, etc.)
- SP "K&F Concept" → Whisper "k concept" hoặc "k kf"
- Verify script filter "k " → FALSE POSITIVE

**Filter:**
```python
r"k\s+(concept|kf)",
r"kỹ\s+thuật",     # "kỹ thuật"
r"ok\s+",            # "ok luôn" - không phải giá
```

### 3. CTA chứa "link" / "bấm link" 
- CTA: "bấm vào link phía bên dưới để mua hàng"
- Verify script filter "link" → FALSE POSITIVE (CTA là ngoại lệ Tuấn Anh cho phép)

**Filter:**
```python
r"bấm\s+link\s+phía",   # "bấm link phía bên dưới"
r"bấm\s+vào\s+link",    # "bấm vào link"
r"link\s+phía\s+dưới",  # "link phía dưới"
```

## COMPLETE false_positive_patterns list (đã verify 10/08/2026)
```python
false_positive_patterns = [
    r"ngàn\s+thao",
    r"ngầm\s+thao",
    r"k\s+(concept|kf)",
    r"kỹ\s+thuật",
    r"ok\s+",
    r"bấm\s+link\s+phía",
    r"bấm\s+vào\s+link",
    r"link\s+phía\s+dưới",
]
pricing_keywords_filtered = ("ngàn", "k ", "link")
```

## Anti-pattern (TUYỆT ĐỐI KHÔNG)
❌ KHÔNG filter chung chung với substring match:
```python
# SAI - filter quá rộng, bỏ sót giá thật
if "ngàn" in text and "ngàm" not in text:
    pricing_found.append("ngàn")
```
✅ ĐÚNG - dùng regex pattern ngay cạnh:
```python
if re.search(r"ngàn\s+thao", text):
    continue  # Match "ngàn thao" → likely SP name
```

## Real case (10/08/2026)
- Clip DJI_0619 (ngàm thao tác nhanh) v2 PASS
- 5 false positives trước khi filter (ngàn × 3, k × 1, link × 1)
- Sau filter: 0 pricing false positives
- REAL pricing keywords (giá, triệu, 000đ) KHÔNG bị filter

## Khi nào CẬP NHẬT pattern list
Khi có SP mới mà tên chứa "ngàn"/"k"/... → thêm pattern.
Khi CTA câu mới chứa "link" → pattern vẫn cover (không cần thêm).
