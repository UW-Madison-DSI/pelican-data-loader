"""Smoke test that renders the Streamlit app once and fails on any uncaught error.

Run at image build time so an app that cannot start (bad imports, bad module
layout) fails the build instead of being deployed. Streamlit's /_stcore/health
endpoint returns "ok" even when the script raises, so it cannot catch this.

Requires no database: the tabs surface connection problems as st.error, which
this test tolerates. Only uncaught exceptions are treated as failures.
"""

import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

MAIN_SCRIPT = Path(__file__).resolve().parent / "main.py"
EXPECTED_TABS = 2


def main() -> int:
    app = AppTest.from_file(str(MAIN_SCRIPT), default_timeout=120)
    app.run()

    if app.exception:
        print(f"FAIL: {len(app.exception)} uncaught exception(s) while rendering {MAIN_SCRIPT}:", file=sys.stderr)
        for exception in app.exception:
            print(f"  {exception.value}", file=sys.stderr)
        return 1

    if not app.title:
        print("FAIL: app rendered no title, it likely exited early", file=sys.stderr)
        return 1

    tab_count = len(app.tabs)
    if tab_count != EXPECTED_TABS:
        print(f"FAIL: expected {EXPECTED_TABS} tabs, rendered {tab_count}", file=sys.stderr)
        return 1

    print(f"OK: rendered '{app.title[0].value}' with {tab_count} tabs")
    for error in app.error:
        print(f"  note: st.error shown (expected without a database): {error.value.splitlines()[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
