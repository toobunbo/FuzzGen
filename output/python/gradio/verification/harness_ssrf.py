import atheris
import sys
import re
from unittest.mock import patch, MagicMock
# import atheris
atheris.instrument_all()  # instrument toàn bộ bytecode đã load
from gradio.image_utils import extract_svg_content

# with atheris.instrument_imports():
#     from gradio.image_utils import extract_svg_content


# === FIXED CONTRACTS (DO NOT MODIFY) ===
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
_RAISE_MESSAGE  = "PY/FULL-SSRF: httpx.get() called with attacker-controlled internal/metadata URL — captured={captured} pattern={matched_pattern}"
_TAINTED_PARAMS = [{"name": "image_file", "index": 0, "type": "str | Path"}]
# ========================================

# === ORACLE CONTEXT ===
# strategy         : patch_call
# patch_target     : gradio.image_utils.httpx.get
# target_arg_index : 0
# target_arg_name  : None
# input_strategy   : direct_params
# signature        : def extract_svg_content(image_file: str | Path)
# condition        : The URL passed to httpx.get() points to an internal/private IP, localhost, or cloud metadata endpoint, confirming SSRF exploitation with no validation blocking the request
# capture_what     : The URL argument passed to httpx.get() — the full attacker-controlled URL reaching the HTTP sink
# skip_hint        : not (isinstance(image_file, str) and ('http://' in image_file or 'https://' in image_file or 'file://' in image_file))
# seed_corpus      : ["http://169.254.169.254/latest/meta-data/", "http://127.0.0.1:8080/admin", "http://localhost/internal", "http://192.168.1.1/", "http://10.0.0.1/secret", "http://metadata.google.internal/computeMetadata/v1/"]
# ========================================

def TestOneInput(data):
    fdp = atheris.FuzzedDataProvider(data)

    image_file = fdp.ConsumeUnicodeNoSurrogates(len(data))

    # Skip guard derived from skip_hint
    if not (isinstance(image_file, str) and ('http://' in image_file or 'https://' in image_file or 'file://' in image_file)):
        return

    mock_response = MagicMock(status_code=200, text="<svg></svg>", content=b"<svg></svg>")

    calls = []

    def mock_httpx_get(*args, **kwargs):
        calls.append(MagicMock(args=args, kwargs=kwargs))
        return mock_response

    try:
        with patch("gradio.image_utils.httpx.get", side_effect=mock_httpx_get):
            extract_svg_content(image_file)

        for call in calls:
            if call.args:
                captured = str(call.args[0])
            else:
                captured = ""
            for pattern in _COMPILED_PATTERNS:
                if pattern.search(captured):
                    raise RuntimeError(_RAISE_MESSAGE.replace("{captured}", captured).replace("{matched_pattern}", pattern.pattern))

    except RuntimeError:
        raise
    except Exception:
        pass


if __name__ == "__main__":
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()