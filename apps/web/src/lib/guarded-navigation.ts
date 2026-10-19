// Navigation that a stage's own leave guard can stop (research-lead-workbench, review of #483).
// A stage with unsaved local edits (Návrh's narrative or a tracked set) protects them by catching
// clicks on links in the capture phase, asking, and navigating itself if the person agrees. The
// workbench navigates from buttons and from the Lead's view tools, which are not links; so it
// navigates through a link's click: a guard that prevents it wins, otherwise the router moves.

export function guardedNavigate(url: string, push: (url: string) => void, doc: Document = document): void {
  const a = doc.createElement("a");
  a.href = url;
  a.hidden = true;
  a.addEventListener("click", (e) => {
    if (e.defaultPrevented) return;
    e.preventDefault();
    push(url);
  });
  doc.body.appendChild(a);
  try {
    a.click();
  } finally {
    a.remove();
  }
}
