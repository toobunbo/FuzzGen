# test_manual.py
import sys
from unittest.mock import patch, MagicMock
import re

from gradio.image_utils import extract_svg_content

_COMPILED_PATTERNS = [
    re.compile("https?://169\\.254\\.169\\.254", re.IGNORECASE),
    re.compile("https?://127\\.0\\.0\\.1", re.IGNORECASE),
    re.compile("https?://localhost", re.IGNORECASE),
    re.compile("https?://0\\.0\\.0\\.0", re.IGNORECASE),
    re.compile("https?://10\\.", re.IGNORECASE),
    re.compile("https?://192\\.168\\.", re.IGNORECASE),
    re.compile("https?://172\\.(1[6-9]|2[0-9]|3[01])\\.", re.IGNORECASE),
    re.compile("https?://\\[::1\\]", re.IGNORECASE),
    re.compile("https?://metadata\\.google\\.internal", re.IGNORECASE),
    re.compile("file://", re.IGNORECASE),
]

TEST_INPUTS = [
    "http://169.254.169.254/latest/meta-data/",
    "http://127.0.0.1:8080/admin",
    "http://localhost/internal",
    "http://192.168.1.1/",
    "http://10.0.0.1/secret",
    "http://metadata.google.internal/computeMetadata/v1/",
]

for image_file in TEST_INPUTS:
    mock_response = MagicMock(status_code=200, text="<svg></svg>", content=b"<svg></svg>")
    calls = []

    def mock_httpx_get(*args, **kwargs):
        calls.append(MagicMock(args=args, kwargs=kwargs))
        return mock_response

    print(f"\n[TEST] input: {image_file}")
    try:
        with patch("gradio.image_utils.httpx.get", side_effect=mock_httpx_get):
            extract_svg_content(image_file)

        if not calls:
            print("  → httpx.get() KHÔNG được gọi (input bị filter trước đó)")
            continue

        for call in calls:
            captured = str(call.args[0]) if call.args else ""
            print(f"  → httpx.get() được gọi với: {captured}")
            for pattern in _COMPILED_PATTERNS:
                if pattern.search(captured):
                    print(f"  ❌ SSRF DETECTED! pattern: {pattern.pattern}")
                    break
            else:
                print("  ✅ Không match pattern nào")

    except Exception as e:
        print(f"  ⚠ Exception: {e}")