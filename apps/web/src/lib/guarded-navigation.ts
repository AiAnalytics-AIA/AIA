// Navigation that a stage's own leave guard can stop (research-lead-workbench, review of #483).
// A stage with unsaved local edits (Návrh's narrative or a tracked set) protects them by catching
// clicks on links in the capture phase, asking, and navigating itself if the person agrees. The
// workbench navigates from buttons and from the Lead's view tools, which are not links; so it
// navigates through a link's click: a guard that prevents it wins, otherwise the router moves.

/** True when it navigated now; false when a guard stopped the click (the guard may navigate later, on its own). */
export function guardedNavigate(url: string, push: (url: string) => void, doc: Document = document): boolean {
  const a = doc.createElement("a");
  a.href = url;
  a.hidden = true;
  let pushed = false;
  a.addEventListener("click", (e) => {
    if (e.defaultPrevented) return;
    e.preventDefault();
    pushed = true;
    push(url);
  });
  doc.body.appendChild(a);
  try {
    a.click();
  } finally {
    a.remove();
  }
  return pushed;
}
