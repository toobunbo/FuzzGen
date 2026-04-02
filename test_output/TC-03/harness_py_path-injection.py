import atheris
import sys
import re


with atheris.instrument_imports():
    from server.file_handler import read_user_file

# === ORACLE SPEC ===
# oracle_type      : inspect_return
# input_strategy   : direct_params
# monitor_strategy : inspect_return
# patch_target     : None
# capture_what     : os.path.join() call with dangerous path or open() called with potentially traversed path
# tainted_params   : [{"name": "filename", "index": -1, "type": "str"}]
# trigger_patterns : [".* '../' .*", "os.path.join\\(\\) returns path starting with /"]
# expected_exceptions: ["FileNotFoundError", "IsADirectoryError"]
# cleanup_needed   : False
# cleanup_desc     : None
# attack_scenario  : Attacker supplies a filename with '../' to cause directory traversal via os.path.join() and opens the resulting path.
# function_signature: def read_user_file(filename: str)

def TestOneInput(data):
    fdp = atheris.FuzzedDataProvider(data)
    
    # FDP Block
    filename = fdp.ConsumeUnicodeNoSurrogates(fdp.ConsumeIntInRange(0, 4096))
    
    # Function Call Block
    try:
        result = read_user_file(filename)
    except Exception as e:
        if str(e) not in ["FileNotFoundError", "IsADirectoryError"]:
            raise RuntimeError("Dangerous path detected: {}".format(filename))
        return
    
    # Oracle Check Block
    if re.search(r".* '../' .*", result) or re.search(r"os.path.join\\(\\) returns path starting with /", result):
        raise RuntimeError("Dangerous path detected: {}".format(filename))

atheris.Setup(sys.argv, TestOneInput)
atheris.Fuzz()