"""Make render.py's page artifact-ready: strip the document skeleton, add the safe-area gutter.

Usage: python3 artifactize.py out.html pm-status-artifact.html
"""

import re
import sys
from pathlib import Path

VIEWPORT_FIT = '<meta name="claude:viewport-fit-sides" content="cover">'
SAFE_AREA_GUTTER = (
    "body{padding-left:max(16px,env(safe-area-inset-left,0px))!important;"
    "padding-right:max(16px,env(safe-area-inset-right,0px))!important}"
)


def main(src: str, dst: str) -> None:
    s = Path(src).read_text(encoding="utf-8")
    s = re.sub(r"<!doctype html>\s*", "", s, flags=re.I)
    s = re.sub(r"</?html[^>]*>|</?head>|</?body[^>]*>", "", s)
    s = re.sub(r'<meta charset="utf-8">|<meta name="viewport"[^>]*>', "", s)
    s = s.replace("<title>AIA PM Status</title>", "<title>AIA PM Status</title>" + VIEWPORT_FIT, 1)
    s = s.replace("</style>", SAFE_AREA_GUTTER + "</style>", 1)
    Path(dst).write_text(s.strip() + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
