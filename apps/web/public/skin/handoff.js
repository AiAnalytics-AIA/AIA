/*
 * The rebuilt interface's hand-off into the classic one (ADR 0014, decision 8).
 *
 * The web client adds this script only to the pinned 18.6.6 document, so every
 * name it calls is known to exist. A link from /app carries one instruction in
 * the URL fragment, which never reaches a server:
 *
 *   #aia:open=<project id>        openProject1785(id)       -- "Otevřít"
 *   #aia:start=research           startProductionResearch() -- "+ Nový výzkum"
 *   #aia:start=simulation         startSimulationProduct1773()
 *   #aia:go=<route>               go(route), for a route the router knows
 *
 * It waits for the classic boot to finish (NPC_BOOT_STAGE === "ready"), clears
 * the fragment, and calls the classic interface's own function -- the one its
 * own button calls. It changes no DOM, calls nothing else, and ignores any
 * instruction that does not match exactly.
 */
(function () {
  "use strict";
  var ROUTES = [
    "home", "projects", "brief", "plan", "questionnaire", "audience", "persona", "run", "research_progress",
    "results", "verify", "next", "command", "data", "settings", "sim_context", "sim_change", "sim_people",
    "sim_run", "sim_results", "project_overview", "demos", "demo_project", "visualization",
  ];
  var PATTERN = /^#aia:(open|start|go)=([A-Za-z0-9_-]{1,160})$/;

  function run(verb, arg) {
    if (verb === "open") return window.openProject1785(arg);
    if (verb === "start" && arg === "research") return window.startProductionResearch();
    if (verb === "start" && arg === "simulation") return window.startSimulationProduct1773();
    if (verb === "go" && ROUTES.indexOf(arg) >= 0) return window.go(arg);
  }

  // On load, and again when a hand-off link is followed from this same page
  // (only the fragment changes, so the document does not reload).
  function handle() {
    var m = PATTERN.exec(window.location.hash || "");
    if (!m) return;
    var waited = 0;
    (function wait() {
      if (window.NPC_BOOT_STAGE === "ready") {
        try {
          window.history.replaceState(null, "", window.location.pathname + window.location.search);
        } catch {
          /* a fragment left in place is harmless */
        }
        try {
          run(m[1], m[2]);
        } catch (e) {
          console.error("aia-handoff", e);
        }
        return;
      }
      waited += 100;
      if (waited <= 60000) setTimeout(wait, 100);
    })();
  }

  handle();
  window.addEventListener("hashchange", handle);
})();
