import atheris
import sys
import re


with atheris.instrument_imports():
    from app.db.query import execute_query


def TestOneInput(data):
    fdp = atheris.FuzzedDataProvider(data)

    # FDP Block - Generate inputs
    query = fdp.ConsumeUnicodeNoSurrogates(fdp.ConsumeIntInRange(0, 4096))
    user_input = fdp.ConsumeUnicodeNoSurrogates(fdp.ConsumeIntInRange(0, 4096))

    # Function Call Block - Call target function with generated inputs
    try:
        result = execute_query(query, user_input)
    except Exception as e:
        if not isinstance(e, RuntimeError):
            raise RuntimeError("Unexpected exception occurred during query execution")
        else:
            raise

    # Oracle Check Block - Implement strategy: inspect_return
    trigger_patterns = re.compile(r"SELECT.* FROM", re.IGNORECASE)

    if trigger_patterns.search(str(result)):
        raise RuntimeError("SQL injection detected in execute_query. The user input was injected into the SQL string.")


atheris.Setup(sys.argv, TestOneInput)
atheris.Fuzz()