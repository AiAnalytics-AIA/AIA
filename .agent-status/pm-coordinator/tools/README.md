PM coordinator tools (no secrets).
- build.py: Markdown -> styled HTML for PDF. `python build.py in.md out.html "footer label"` (needs `pip install markdown`),
  then `/opt/pw-browsers/chromium-1194/chrome-linux/chrome --headless=new --no-sandbox --disable-gpu --no-pdf-header-footer --print-to-pdf=out.pdf file://$PWD/out.html`.
  Methodology PDF = .planning/mvp-methodology-packet.md (#510) minus the "## Engineering gaps" section; engineering companion = that
  section + a header + PR #510's proposed chunks + ADR 0038 summary. Both carry "Draft ... Source: <file> @ <sha>".
- parse.py: decision-list.md (#516) -> decisions.json (48 items: id, part, title, question, example, options[{key,text}], changes, rec, reckey, sources; Part E rows are in/out).
- template.html: the "AIA scope decisions" page (artifact https://claude.ai/artifact/WdXcN8nQnQX3rW36hF8iVd); replace __DATA__ with decisions.json
  (escape "</" as "<\/"); capabilities {db:{}, user:{scopes:["profile"]}}. To republish from a new session: Artifact action "read" on the URL first, then publish with `url`.
