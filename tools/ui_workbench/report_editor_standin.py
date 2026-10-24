"""The report editor's stand-in Document Server, for the workbench (artifact-report RPT8d).

ONLYOFFICE Docs is not run on this machine. The workbench's API is configured as if one were at
``ORIGIN`` (fictional, never resolved) and is given a fetcher that reads a save from ``SAVES``
instead of fetching it over the network (``app.state.editor_fetcher``, as a test's is). The
browser side is a stand-in ``api.js`` the journey serves for ``ORIGIN``
(``fixtures/report_editor/api.js``). What a Document Server does on a save, this module's ``save``
command does: it writes the saved DOCX where the fetcher reads it and posts the callback, signed
with the workbench's editor secret as ONLYOFFICE signs it.

    python tools/ui_workbench/report_editor_standin.py save --facade http://127.0.0.1:8780 \\
        --study STU-… --run RUN-… --config tmp/ui-workbench/editor-config.json --text "99,9 %"

Local only: the secret is the workbench's, fictional, and nothing here leaves the machine.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import time
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

REPO = Path(__file__).resolve().parents[2]
SAVES = REPO / "tmp" / "ui-workbench" / "editor-saves"
#: The stand-in Document Server's origin and AIA's public origin as it would reach it: https, as
#: the settings require, and under .invalid, so nothing ever resolves them.
ORIGIN = "https://docs.workbench.invalid"
CALLBACK_BASE = "https://aia.workbench.invalid"
#: The workbench's editor secret: fictional, local, and at least the 32 characters required.
SECRET = "workbench-report-editor-secret-fictional-local"
WORKBENCH_EMAIL = "workbench@example.invalid"
_NAME = re.compile(r"^[A-Za-z0-9._-]{1,80}$")


def settings() -> dict[str, str]:
    """The API settings that switch the editor on for the workbench."""
    return {
        "onlyoffice_url": ORIGIN,
        "onlyoffice_jwt_secret": SECRET,
        "onlyoffice_callback_base": CALLBACK_BASE,
    }


class WorkbenchSaves:
    """The API's save fetcher here: a file of ``SAVES`` for a URL the live fetcher would accept
    from ``ORIGIN``, refused by the same reason a live one gives otherwise."""

    def __init__(self, root: Path = SAVES) -> None:
        self._root = root

    def __call__(self, url: str) -> bytes:
        from aia_core.infrastructure.editor_fetch import CACHE_PATH, SaveFetchRefused, allowed

        if not allowed(url, ORIGIN):
            raise SaveFetchRefused("not_the_editors_file")
        name = urlsplit(url).path[len(CACHE_PATH) :]
        path = self._root / name
        if not _NAME.match(name) or not path.is_file():
            raise SaveFetchRefused("document_server_restarted")
        return path.read_bytes()


def edited(docx: bytes, text: str) -> bytes:
    """``docx`` with the first locked number's text replaced by ``text``: one changed control, as a
    researcher's edit of a number code wrote would be. A number is a ledger ref's control (a tag
    with no kind before a colon, nor a part after ``#``), not the design, run or map spans."""
    source = zipfile.ZipFile(io.BytesIO(docx))
    body = source.read("word/document.xml").decode("utf-8")
    controls = re.finditer(
        r"<w:sdt>(?:(?!<w:sdt>).)*?<w:tag w:val=\"([^\"]+)\"/>.*?</w:sdtContent>", body, re.S
    )
    control = next((c for c in controls if not re.search(r"[:#]", c[1])), None)
    if control is None:
        raise SystemExit("the draft holds no locked number to edit")
    inner = re.sub(
        r"(<w:t(?: [^>]*)?>)[^<]*(</w:t>)", lambda m: f"{m[1]}{text}{m[2]}", control[0], count=1
    )
    body = body[: control.start()] + inner + body[control.end() :]
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as target:
        for item in source.infolist():
            data = (
                body.encode("utf-8") if item.filename == "word/document.xml" else source.read(item)
            )
            target.writestr(item, data)
    return out.getvalue()


def _request(
    url: str, *, data: bytes | None = None, headers: dict[str, str] | None = None
) -> bytes:
    request = urllib.request.Request(
        url, data=data, headers=headers or {}, method="POST" if data else "GET"
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return bytes(response.read())


def save(
    facade: str, study: str, run: str, config: dict[str, object], text: str
) -> dict[str, object]:
    """One save as a Document Server makes it: the composed draft with one number edited, written
    where the fetcher reads it, and the callback (status 6, a forcesave) posted, signed."""
    import jwt

    host = urlsplit(facade).hostname
    if host not in ("127.0.0.1", "localhost"):
        raise SystemExit("the stand-in posts to the local facade only")
    auth = {"Authorization": f"Bearer {WORKBENCH_EMAIL}"}
    draft = _request(
        f"{facade}/api/v1/studies/{study}/research/runs/{run}/report/download", headers=auth
    )
    SAVES.mkdir(parents=True, exist_ok=True)
    name = f"save-{int(time.time() * 1000)}.docx"
    (SAVES / name).write_bytes(edited(draft, text))
    document = config["document"]
    editor = config["editorConfig"]
    assert isinstance(document, dict) and isinstance(editor, dict)
    user = editor["user"]
    assert isinstance(user, dict)
    callback = urlsplit(str(editor["callbackUrl"]))
    payload = {
        "key": document["key"],
        "status": 6,
        "url": f"{ORIGIN}/cache/files/{name}",
        "users": [user["id"]],
        # The time of the last change the file holds, as ONLYOFFICE signs it: now, the edit
        # this save stands for having been made before it.
        "lastsave": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
    }
    now = int(time.time())
    token = jwt.encode({**payload, "iat": now, "exp": now + 300}, SECRET)
    body = json.dumps({**payload, "token": token}).encode("utf-8")
    answer = _request(
        f"{facade}{callback.path}?{callback.query}",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    return dict(json.loads(answer))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    one = sub.add_parser("save", help="store one edited save through the callback")
    one.add_argument("--facade", default="http://127.0.0.1:8780")
    one.add_argument("--study", required=True)
    one.add_argument("--run", required=True)
    one.add_argument(
        "--config", required=True, help="the editor config the page was handed, as JSON"
    )
    one.add_argument("--text", required=True, help="the edited number's new text")
    args = ap.parse_args(argv)
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    print(json.dumps(save(args.facade, args.study, args.run, config, args.text)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
