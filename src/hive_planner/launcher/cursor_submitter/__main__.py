"""Do not run this from Hive to submit a chat.

There is no workbench function in this process. Calling it here would skip
the host. The host imports ``apply_request`` and passes ``submitChatMaybeAbortCurrent``.
"""

from __future__ import annotations

import sys


def main() -> int:
    print(
        "cursor_submitter waits for a workbench host. "
        "This process does not call submitChatMaybeAbortCurrent.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
