/*
 * AIA's hand-off into the classic interface (ADR 0014 decision 8, ADR 0015).
 *
 * The web client adds this script only to the pinned 18.6.6 document, served at
 * /classic, so every name it calls is known to exist. A link from /app carries
 * one instruction in the URL fragment, which never reaches a server:
 *
 *   #aia:open=<project id>        openProject1785(id)       -- "Otevřít"
 *   #aia:open=<project id>@<route>   the same, landing on go(route) instead of the
 *                                 overview: a rebuilt research step handing off to one that is not
 *   #aia:start=research           startProductionResearch() -- "+ Nový výzkum"
 *   #aia:start=simulation         startSimulationProduct1773()
 *   #aia:go=<route>               go(route), for a route the router knows
 *   #aia:switch=research|simulation|library   switchProduct1776(kind) -- the rail's
 *                                 "Výzkum" / "Simulace" / "Data Library"
 *   #aia:assistant=open           openAssistant1791()       -- "AI asistent"
 *   #aia:support=bundle           createSupportBundle(...)  -- "Diagnostika"
 *   #aia:dimension=research       openDimensionResearch1793(label) -- a proposed dimension's
 *                                 "Deep Research"; the label, free text, is read once from
 *                                 sessionStorage["aia:dimension-research"], never from the URL
 *
 * It waits for the classic boot to finish (NPC_BOOT_STAGE === "ready"), clears
 * the fragment, and calls the classic interface's own function -- the one its
 * own button calls. It calls nothing else, and ignores any instruction that
 * does not match exactly.
 *
 * It adds one element to the page, outside the classic interface's own tree:
 * a bar saying this is the classic interface, temporarily, with "Zpět do AIA"
 * back to the AIA page the person came from (sessionStorage["aia:return"], an
 * /app path only), else to the client directory. The classic interface is never
 * where a person is without knowing it (ADR 0015 decision 4).
 */
(function () {
  "use strict";
  var ROUTES = [
    "home", "projects", "brief", "plan", "questionnaire", "audience", "persona", "run", "research_progress",
    "results", "verify", "next", "command", "data", "settings", "sim_context", "sim_change", "sim_people",
    "sim_run", "sim_results", "project_overview", "demos", "demo_project", "visualization",
  ];
  var PATTERN = /^#aia:(open|start|go|switch|assistant|support|dimension)=([A-Za-z0-9_-]{1,160})(?:@([a-z_]{1,40}))?$/;

  function run(verb, arg, step) {
    if (verb === "open" && step) {
      if (ROUTES.indexOf(step) < 0) return;
      // openProject1785 ends with go('project_overview'), and that screen draws
      // itself asynchronously: a go(step) after it is painted over a moment
      // later. So while the project opens, that one call draws the step instead.
      var go = window.go;
      var swapped = false;
      window.go = function (route) {
        if (route === "project_overview" && !swapped) {
          swapped = true;
          window.go = go;
          return go(step);
        }
        return go.apply(this, arguments);
      };
      var restore = function () {
        if (window.go !== go) window.go = go;
      };
      return Promise.resolve(window.openProject1785(arg)).then(
        function () {
          restore();
          if (!swapped) go(step);
        },
        function (e) {
          restore();
          throw e;
        },
      );
    }
    if (verb === "open") return window.openProject1785(arg);
    if (verb === "dimension" && arg === "research") {
      var label = null;
      try {
        label = window.sessionStorage.getItem("aia:dimension-research");
        window.sessionStorage.removeItem("aia:dimension-research");
      } catch {
        label = null;
      }
      if (label) return window.openDimensionResearch1793(label);
      return;
    }
    if (verb === "start" && arg === "research") return window.startProductionResearch();
    if (verb === "start" && arg === "simulation") return window.startSimulationProduct1773();
    if (verb === "go" && ROUTES.indexOf(arg) >= 0) return window.go(arg);
    if (verb === "switch" && ["research", "simulation", "library"].indexOf(arg) >= 0) return window.switchProduct1776(arg);
    if (verb === "assistant" && arg === "open") return window.openAssistant1791();
    if (verb === "support" && arg === "bundle") return window.createSupportBundle(window.LAST_FAILED_JOB_ID || "");
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
          Promise.resolve(run(m[1], m[2], m[3])).catch(function (e) {
            console.error("aia-handoff", e);
          });
        } catch (e) {
          console.error("aia-handoff", e);
        }
        return;
      }
      waited += 100;
      if (waited <= 60000) setTimeout(wait, 100);
    })();
  }

  var RETURN = /^\/app(\/[A-Za-z0-9_%.-]*)*(\?[A-Za-z0-9_%.=&-]*)?$/;

  function returnTo() {
    var path = null;
    try {
      path = window.sessionStorage.getItem("aia:return");
    } catch {
      path = null;
    }
    return path && RETURN.test(path) && path.indexOf("..") < 0 ? path : "/app/clients";
  }

  function bar() {
    if (!document.body || document.getElementById("aia-return-bar")) return;
    var el = document.createElement("div");
    el.id = "aia-return-bar";
    el.className = "aia-return-bar";
    el.setAttribute("role", "region");
    el.setAttribute("aria-label", "Klasické rozhraní 18.6.6");
    var label = document.createElement("span");
    label.textContent = "Klasické rozhraní 18.6.6 · dočasně";
    var back = document.createElement("a");
    back.href = returnTo();
    back.textContent = "Zpět do AIA";
    el.appendChild(label);
    el.appendChild(back);
    document.body.appendChild(el);
  }

  // Product-only retirement. The independent oracle never receives this script.
  function retireConnections() {
    if (typeof document.querySelectorAll !== "function") return;
    var waited = 0;
    (function install() {
      if (window.NPC_BOOT_STAGE !== "ready") {
        waited += 100;
        if (waited <= 60000) setTimeout(install, 100);
        return;
      }
      var go = window.go;
      window.go = function (route) {
        if (route === "settings") return window.location.assign("/app/settings");
        return go.apply(this, arguments);
      };
      window.renderSettings = function () { window.location.assign("/app/settings"); };
      window.ensureClaudeReady1776 = function () {
        window.alert("AI návrhové asistenty zatím nejsou převedeny do AIA. Amazon Bedrock zajišťuje odpovědi respondentů.");
        return Promise.resolve(false);
      };
      function clean() {
        if (document.getElementById("anthKey1790") || document.getElementById("anthKey") || document.getElementById("openaiKey")) {
          window.location.assign("/app/settings");
          return;
        }
        document.querySelectorAll("#keyState, #claudeState, .hubState1783 > div, button[onclick], select[onchange]").forEach(function (el) {
          var action = el.getAttribute("onclick") || el.getAttribute("onchange") || "";
          var oldStatus = el.id === "keyState" || el.id === "claudeState" ||
            (el.parentElement && el.parentElement.classList.contains("hubState1783") && /Claude Code/.test(el.textContent));
          var oldControl = /setupClaudeCode|saveClaudeApi|testClaudeApi|continueClaudeApi|setInlineAIProvider|setAIProvider/.test(action) ||
            (/go\(['"]settings['"]\)/.test(action) && /Claude Code/.test(el.textContent));
          if (oldStatus || oldControl) el.hidden = true;
        });
      }
      clean();
      if (typeof window.MutationObserver === "function") {
        new window.MutationObserver(clean).observe(document.body, { childList: true, subtree: true });
      }
    })();
  }

  bar();
  retireConnections();
  handle();
  window.addEventListener("hashchange", handle);
})();
