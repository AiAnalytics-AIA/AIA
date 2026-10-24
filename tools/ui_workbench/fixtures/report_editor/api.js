// The report editor's stand-in api.js (artifact-report RPT8d), served by report_editor_journey.mjs
// for the stand-in Document Server's origin (report_editor_standin.py). It defines what ONLYOFFICE's
// api.js defines, DocsAPI.DocEditor, and draws nothing of a document: a frame naming the version it
// was configured with and its mode. The journey drives its events (window.__standinEditor) as the
// Document Server would fire them: ready, a person starting an edit, a save reaching the server.
(function () {
  "use strict";
  function DocEditor(placeholderId, config) {
    var host = document.getElementById(placeholderId);
    var frame = document.createElement("div");
    frame.setAttribute("data-standin-editor", config.editorConfig && config.editorConfig.mode);
    frame.setAttribute("role", "document");
    frame.setAttribute("aria-label", "Zástupný editor zprávy");
    frame.style.cssText = "height:100%;display:flex;align-items:center;justify-content:center;font:14px sans-serif";
    frame.textContent = "Zástupný editor: " + (config.document && config.document.title) + " (" + (config.editorConfig && config.editorConfig.mode) + ")";
    if (host) host.replaceWith(frame);
    var events = config.events || {};
    window.__standinEditor = { config: config, events: events, destroyed: false };
    setTimeout(function () { if (events.onAppReady) events.onAppReady(); }, 50);
    this.destroyEditor = function () {
      window.__standinEditor.destroyed = true;
      frame.remove();
    };
  }
  window.DocsAPI = { DocEditor: DocEditor };
})();
