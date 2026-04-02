# FuzzGen Framework

FuzzGen là một nền tảng tự động hóa mạnh mẽ thuộc dự án **XXXXXXXXXXX**, được thiết kế để tự động sinh mã nguồn **Fuzzing Harness** bằng Python (dựa trên bộ nhân Fuzzer `Atheris`). Hệ thống sử dụng Sức mạnh của **LLM (Trí tuệ Nhân tạo)** để đọc hiểu các lỗ hổng tìm thấy bởi CodeQL/Semgrep, từ đó tự động viết logic giả lập tấn công và chặn bắt các rủi ro bảo mật.

## Cấu trúc Hệ thống

FuzzGen hoạt động theo một quy trình (Pipeline) hai giai đoạn (2 Stages):

- **Stage 1 (Oracle Reasoner):** Nhận file `findings.json` (báo cáo lỗ hổng tĩnh) và các file log CodeQL chứa cấu trúc nội hàm (signature). Gửi toàn bộ dữ liệu tới **LLM** qua `litellm`. LLM đóng vai trò như một chuyên gia bảo mật để quyết định chiến thuật nhồi Input và điều kiện để kích nổ lỗi (Oracle). Kết quả trả về file `oracle_spec.json`.
- **Stage 2 (Harness Generator):** Đọc file cấu hình `oracle_spec.json`. Thông qua **Jinja2 Template Engine**, tự động kết xuất ra mã nguồn Python đóng vai trò là Fuzzing Harness chuẩn bị cho Framework Atheris.

---

## 1. Yêu cầu Cài đặt (Prerequisites)

- **Python:** Khuyên dùng `Python 3.10` hoặc `3.11` (Bắt buộc nếu mục tiêu Fuzzing của bạn là thư viện code cũ mà Pandas/Numpy chưa hỗ trợ Python 3.13).
- **Môi trường ảo (Virtual Env):** 
  ```bash
  conda create -n fuzzgen_env python=3.10
  conda activate fuzzgen_env
  ```
- **Thư viện Framework:**
  ```bash
  pip install atheris litellm jinja2 pyyaml python-dotenv
  ```

## 2. Cấu hình AI (Litellm)

Đổi tên file hoặc tạo file `.env` ở thư mục gốc của FuzzGen để thiết lập LLM. FuzzGen hỗ trợ mọi Model (OpenAI, Google Gemini, Ollama) vì dùng core `litellm`.

**Ví dụ dùng Gemini:**
```properties
LLM_PROVIDER=gemini
LLM_MODEL=gemini-1.5-pro-latest
GEMINI_API_KEY=AIzaSy_YOUR_API_KEY
```

**Ví dụ dùng Ollama (Local/Offline):**
```properties
LLM_PROVIDER=ollama
LLM_MODEL=llama3
# OLLAMA_API_BASE=http://localhost:11434 (Mặc định)
```

---

## 3. Hướng dẫn Chạy Framework

### Chạy Stage 1: Phân tích & Suy luận lổ hổng
Lệnh dưới đây sẽ đọc lỗ hổng đầu vào. Chương trình sẽ gọi AI, hiểu mã nguồn và tạo kịch bản test đổ ra file `oracle_spec.json` ở cùng thư mục với thư mục findings.

```bash
python src/run_stage1.py \
  --finding output/python/superset/verifycation_result/findings.json
```

### Chạy Stage 2: Sinh mã Code Fuzzing (Harness)
Dựa vào kết quả của Stage 1, Generator sẽ Render file mã nguồn đuôi ánh xạ Python.

```bash
python src/run_stage2.py \
  --finding output/python/superset/verifycation_result/findings.json \
  --spec output/python/superset/verifycation_result/oracle_spec.json
```
File đầu ra của bạn sẽ được đặt trong thư mục `--out-dir` (ví dụ: `harness_py_bad-tag-filter.py`).

---

## 4. Hướng dẫn Kích hoạt Fuzzing

Một khi đã có file `harness.py`, việc thi hành nó đòi hỏi bạn phải thỏa mãn toàn bộ thư viện phụ thuộc (Dependencies) của mã nguồn mục tiêu.

### A. Chuẩn bị Thư viện Mục tiêu
Giả sử bạn đang Fuzzing dự án `superset`. Bạn bắt buộc phải khai báo đường dẫn tới dự án đó cho Python:
```bash
export PYTHONPATH="/home/caterpie/FuzzGen/repos/python/superset:$PYTHONPATH"
```

**(BẮT BUỘC):** Cài đặt đầy đủ các thư viện mà dự án mục tiêu yêu cầu. Nếu bỏ sót, Python sẽ văng lỗi `ModuleNotFoundError: No module named 'celery/flask/sqlalchemy...'` lúc bắt đầu Fuzzing.
```bash
cd repos/python/superset
pip install -r requirements.txt
```

### B. Chạy Atheris
Quay trở lại FuzzGen, rạo thư mục lưu log để Atheris tự học và Fuzz hiệu quả hơn qua từng thế hệ đột biến:
```bash
mkdir -p crash_corpus
```

Chạy Fuzzing Harness vô tận hoặc giới hạn thời gian chạy:
```bash
# Chạy trong 60 giây
python output/python/superset/verifycation_result/harness/harness_py_bad-tag-filter.py crash_corpus/ -max_total_time=60

# Chạy đúng 10,000 lượt inputs
python output/python/superset/verifycation_result/harness/harness_py_bad-tag-filter.py crash_corpus/ -runs=10000
```

Nếu một đầu vào gây lỗi thỏa mãn điều kiện Oracle đề ra của LLM, Atheris sẽ in dòng **`Oracle check triggered`**, thoát chương trình và nhả ra tệp test case gây crash (ví dụ `crash-xxxxxxxxx`) cho bạn.
