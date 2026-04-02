# Stage 3 — Coverage-Guided Harness Refinement

## Tổng quan

Stage 3 nhận output từ Stage 2, không chỉnh sửa Stage 1 hay Stage 2.
Mục tiêu: phát hiện harness bị stuck, chẩn đoán nguyên nhân qua 3 signal, gửi feedback cho LLM để refine, rồi chạy atheris thật.

```
Stage 1                 Stage 2                   Stage 3
──────────────          ──────────────────         ──────────────────────────
findings              → harness_ssrf.py       →    coverage_runner.py
oracle patterns         fuzz_hints: [...]           ↓
fuzz_hints                                     collect signals
                                                    ↓
                                               stuck? ──No──→ run atheris
                                                    │
                                                   Yes
                                                    ↓
                                               build LLM payload
                                                    ↓
                                               LLM refine harness
                                                    ↓
                                               loop lại (max 3 lần)
```

---

## Input

| Trường | Nguồn | Mô tả |
|--------|-------|-------|
| `harness_file` | Stage 2 output | File `.py` chứa `TestOneInput` |
| `fuzz_hints` | Stage 1 label | List string gợi ý shape input |
| `target_module` | Đọc từ import line trong harness | VD: `gradio.image_utils` |
| `oracle_contracts` | Đọc từ `_COMPILED_PATTERNS`, `_RAISE_MESSAGE` | Không được LLM modify |

---

## Bước 1 — Chuẩn bị sample inputs từ fuzz_hints

Không dùng corpus riêng. `fuzz_hints` từ Stage 1 đã encode domain knowledge của oracle.

```
fuzz_hints: ["169.254.1.1/path", "1.2.3.4", "localhost.local"]
→ prepend "http://" khi cần (detect tự động nếu hint chưa có scheme)
→ encode UTF-8 → bytes → truyền vào TestOneInput(data)
```

Lý do không seed thêm: tránh bias — fuzzer tự mutate từ shape gợi ý thay vì confirm payload đã biết.

---

## Bước 2 — Thu thập 3 signal

### Signal 1 — Coverage Diff

**Đo:** `basic_blocks_hit / total_basic_blocks` của target function.

**Cách:**
```python
import coverage
cov = coverage.Coverage(branch=True, source=[target_module])
cov.start()
# chạy TestOneInput với từng fuzz_hint
cov.stop()
# đọc data.arcs() → đếm BB hit vs total
```

**Threshold stuck:** `< 50%` BB được hit sau khi chạy hết sample inputs.

**Output ví dụ:**
```
Coverage: 4/12 basic blocks hit (33%)
```

---

### Signal 2 — Branch Trace

**Đo:** Arc nào chưa được execute — chỉ ra branch bị chặn trên đường đến sink.

**Cách:**
```python
hit_arcs     = set(data.arcs(filepath))
all_arcs     = set(analysis.arc_possibilities())
missing_arcs = all_arcs - hit_arcs
# map (line_s, line_d) → source line content
```

**Output ví dụ:**
```
Line 47 → 48 not taken: if is_http_url_like(image_file):
```

**Ưu tiên cao nhất** vì chỉ ra đường đến sink (`httpx.get`) bị chặn — đây là root cause của SSRF harness bị stuck.

**Trigger on-demand callee fetch:**
- Nếu branch missing chứa tên một hàm (VD: `is_http_url_like`)
  → tự động `inspect.getsource(callee_fn)` và đính kèm vào LLM payload
  → **không fetch trước**, chỉ fetch khi Signal 2 chỉ đích danh callee đó

---

### Signal 3 — Exception Trace

**Đo:** Exception type + tần suất khi chạy sample inputs.

**Cách:**
```python
exception_counter = defaultdict(int)
try:
    TestOneInput(raw)
except Exception as e:
    exception_counter[type(e).__name__] += 1
```

**Output ví dụ:**
```
FileNotFoundError: 3/3 inputs (100%)
```

**Ý nghĩa:** Fuzzer đang bị kẹt ở nhánh `else → open(file)` — không bao giờ reach `httpx.get()`.

---

## Bước 3 — Điều kiện trigger refine

```
Signal 2: sink branch missing          → TRIGGER (ưu tiên cao nhất)
Signal 1: cov < 50%                    → TRIGGER
Signal 3: 1 exception type > 80%       → TRIGGER

Tất cả xanh                            → chạy atheris thật
```

Nếu nhiều signal cùng trigger, ưu tiên theo thứ tự: Signal 2 > Signal 1 > Signal 3.

---

## Bước 4 — LLM Payload

### Cấu trúc

```
[ALWAYS INCLUDED]
─────────────────────────────────────────────
harness_code          : full source harness hiện tại
target_function_source: source của function mục tiêu
oracle_contracts      : _COMPILED_PATTERNS + _RAISE_MESSAGE
fuzz_hints_used       : list sample inputs đã chạy

[SIGNAL 1 — nếu stuck]
─────────────────────────────────────────────
basic_blocks_hit      : 4
total_basic_blocks    : 12
unhit_lines           : [47, 48, 52]

[SIGNAL 2 — nếu sink branch missing]
─────────────────────────────────────────────
missing_arc           : (47, 48)
source_line           : "if is_http_url_like(image_file):"
callee_source         : <on-demand: inspect.getsource(is_http_url_like)>
                        → chỉ có mặt khi Signal 2 chỉ đích danh callee

[SIGNAL 3 — nếu exception dominant]
─────────────────────────────────────────────
dominant_exception    : "FileNotFoundError"
frequency             : "3/3 (100%)"
last_traceback        : <stripped to 3 lines>

[INSTRUCTION]
─────────────────────────────────────────────
- Chỉ được sửa phần ngoài FIXED CONTRACTS
- Không thay đổi _COMPILED_PATTERNS, _RAISE_MESSAGE, _TAINTED_PARAMS
- Không thêm import ngoài stdlib + mock
- Trả về full harness đã sửa, không giải thích thêm
```

### On-demand callee fetch — logic

```python
def fetch_callee_if_needed(missing_arcs, target_module):
    callees = {}
    for (src_line, _) in missing_arcs:
        fn_name = extract_fn_call_at_line(target_module, src_line)
        if fn_name and fn_name not in callees:
            try:
                fn_obj = getattr(importlib.import_module(target_module), fn_name)
                callees[fn_name] = inspect.getsource(fn_obj)
            except Exception:
                pass  # callee không fetch được → bỏ qua
    return callees
```

Fetch tối đa **3 callee** mỗi lần refine để tránh context bloat.

---

## Bước 5 — Vòng lặp có giới hạn

```
MAX_ATTEMPTS = 3

attempt 1:
  payload = signals + fuzz_hints
  → LLM patch gate hoặc hardcode prefix

attempt 2 (nếu vẫn stuck):
  payload += callee source (nếu chưa có)
  → LLM hiểu precondition sâu hơn

attempt 3 (nếu vẫn stuck):
  payload += toàn bộ callee đã fetch
  → last resort

sau attempt 3 vẫn stuck:
  → flag "manual_review_needed": true
  → lưu lại signal + harness cuối
  → dừng, không loop thêm
```

Lý do giới hạn 3: tránh LLM hallucinate harness pass coverage check nhưng oracle bị vô hiệu hóa.

---

## Bước 6 — Validation sau refine

Trước khi accept harness mới từ LLM, kiểm tra:

```
1. Oracle contracts còn nguyên?
   → so sánh _COMPILED_PATTERNS, _RAISE_MESSAGE với bản gốc

2. Coverage tăng so với trước?
   → chạy lại coverage runner với harness mới
   → phải có ít nhất 1 BB mới được hit

3. Harness compile không?
   → py_compile.compile(harness_file)

Fail bất kỳ điều kiện nào → reject harness, thử lại hoặc escalate
```

---

## Output của Stage 3

| File | Mô tả |
|------|-------|
| `harness_ssrf_refined.py` | Harness đã được refine, sẵn sàng chạy atheris |
| `stage3_report.json` | Signal thu thập được, số lần refine, trạng thái |
| `corpus/` | Seed corpus từ fuzz_hints (đã prepend scheme) |

---

## Quyết định thiết kế đã chốt

| Quyết định | Lựa chọn |
|-----------|---------|
| Sample inputs | Lấy từ `fuzz_hints` Stage 1, không tạo riêng |
| Callee fetch | On-demand khi Signal 2 chỉ đích danh callee |
| Callee fetch limit | Tối đa 3 callee/lần refine |
| Refinement scope | Chỉ sửa ngoài FIXED CONTRACTS |
| Max attempts | 3 lần, sau đó flag manual review |
| Coverage tool | `coverage.py` với `branch=True` |

---

## Tham khảo

- CoverUp (2024): Coverage-guided LLM test generation với on-demand context retrieval
- HarnessAgent (2025): Tool-augmented agentic framework, hybrid retrieval pool
- OSS-Fuzz-gen: Callsite extraction thay vì full source dump