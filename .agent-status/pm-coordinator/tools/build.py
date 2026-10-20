import sys, markdown, html
src, out, label = sys.argv[1], sys.argv[2], sys.argv[3]
md = open(src).read()
body = markdown.markdown(md, extensions=['tables', 'sane_lists', 'fenced_code'])
css = """
@page { size: A4; margin: 20mm 18mm 20mm 18mm;
  @bottom-left { content: "LABEL"; font: 8pt Inter, sans-serif; color: #6b7280; }
  @bottom-right { content: counter(page) " / " counter(pages); font: 8pt Inter, sans-serif; color: #6b7280; } }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { font-family: Inter, 'DejaVu Sans', sans-serif; font-size: 9.6pt; line-height: 1.5; color: #111827; }
h1 { font-size: 19pt; line-height: 1.25; margin: 0 0 10pt; color: #0b1220; letter-spacing: -0.01em; }
h2 { font-size: 13.5pt; margin: 20pt 0 6pt; padding-top: 6pt; border-top: 1.5px solid #0e7490; color: #0b1220; break-after: avoid; }
h3 { font-size: 11pt; margin: 14pt 0 4pt; color: #0e7490; break-after: avoid; }
p { margin: 0 0 6pt; } ul, ol { margin: 0 0 6pt 0; padding-left: 16pt; } li { margin: 1.5pt 0; }
code { font-family: 'DejaVu Sans Mono', monospace; font-size: 0.86em; background: #f1f5f9; padding: 0 2pt; border-radius: 2pt; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0 10pt; font-size: 8.4pt; break-inside: auto; }
th, td { border: 0.6pt solid #cbd5e1; padding: 3pt 5pt; vertical-align: top; text-align: left; }
th { background: #e6f4f7; } tr { break-inside: avoid; }
hr { border: 0; border-top: 0.6pt solid #cbd5e1; margin: 10pt 0; }
em { color: #374151; } strong { color: #0b1220; }
""".replace("LABEL", label)
doc = f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>{html.escape(label)}</title><style>{css}</style></head><body>{body}</body></html>"
open(out, 'w').write(doc)
