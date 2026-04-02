# AUTO-GENERATED ATHERIS HARNESS SKELETON
# rule_id  : py/full-ssrf
# function : extract_svg_content
# file     : gradio/image_utils.py
# ================================================================
import atheris
import sys
import re

from unittest.mock import patch, MagicMock

with atheris.instrument_imports():

    from gradio.image_utils import extract_svg_content


# === FIXED CONTRACTS (DO NOT MODIFY) ===
_COMPILED_PATTERNS = [

    re.compile("169\\.254\\.169\\.254", re.IGNORECASE),

    re.compile("(?:^|[/@])127\\.0\\.0\\.1", re.IGNORECASE),

    re.compile("(?:^|[/@])localhost", re.IGNORECASE),

    re.compile("(?:^|[/@])10\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}", re.IGNORECASE),

    re.compile("(?:^|[/@])192\\.168\\.\\d{1,3}\\.\\d{1,3}", re.IGNORECASE),

    re.compile("(?:^|[/@])172\\.(?:1[6-9]|2\\d|3[01])\\.\\d{1,3}\\.\\d{1,3}", re.IGNORECASE),

    re.compile("^file://", re.IGNORECASE),

    re.compile("(?:^|[/@])0\\.0\\.0\\.0", re.IGNORECASE),

]
_RAISE_MESSAGE  = "PY/FULL-SSRF: Attacker-controlled URL reached httpx.get() with no SSRF protection \u2014 internal/metadata endpoint accessible"
_TAINTED_PARAMS = [{"index": 0, "name": "image_file", "type": "str | Path"}]
# ========================================

# === CONTEXT FOR REASONING ===
# monitor_strategy  : patch_call
# patch_target      : gradio.image_utils.httpx.get
# input_strategy    : direct_params
# function_signature: def extract_svg_content(image_file: str | Path)
# condition_desc    : The URL argument reaching httpx.get() contains an internal/private IP address, cloud metadata endpoint (169.254.169.254), localhost, or file:// scheme — confirming SSRF exploitation with no sanitization
# capture_what      : The URL argument passed to httpx.get() — confirms SSRF when it contains internal IPs, cloud metadata endpoints, or localhost addresses
# ========================================


# === PATCH_CALL SKELETON ===
# 1. Generate fuzz inputs from FDP — use ConsumeUnicodeNoSurrogates for str,
#    ConsumeBytes for bytes. Split buffer by param count, not ConsumeIntInRange.
# 2. Setup mock return value appropriate for the target function.
# 3. Patch `gradio.image_utils.httpx.get` and call `extract_svg_content`.
# 4. After the call, iterate mock_get.call_args_list.
#    Extract the URL/path/cmd argument (check both call.args and call.kwargs).
#    Run each pattern in _COMPILED_PATTERNS against the captured argument.
#    On match → raise RuntimeError(_RAISE_MESSAGE).
# 5. except RuntimeError: raise  — never swallow oracle raises.
#    except Exception: pass       — swallow only non-oracle exceptions.


def TestOneInput(data):
    fdp = atheris.FuzzedDataProvider(data)

    param_count = max(len(_TAINTED_PARAMS), 1)
    image_file = fdp.ConsumeUnicodeNoSurrogates(len(data) // param_count)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = ""
    mock_response.content = b""

    try:
        with patch("gradio.image_utils.httpx.get", return_value=mock_response) as mock_fn:
            try:
                extract_svg_content(image_file)
            except RuntimeError:
                raise
            except Exception:
                pass
            for call in mock_fn.call_args_list:
                captured = (
                    str(call.args[0]) if call.args
                    else str(
                        call.kwargs.get("url")
                        or call.kwargs.get("path")
                        or call.kwargs.get("cmd")
                        or call.kwargs.get("sql")
                        or ""
                    )
                )
                for pattern in _COMPILED_PATTERNS:
                    if pattern.search(captured):
                        raise RuntimeError(_RAISE_MESSAGE)
    except RuntimeError:
        raise
    except Exception:
        pass

atheris.Setup(sys.argv, TestOneInput)
atheris.Fuzz()