#!/usr/bin/env python3
"""Apply only the static-demo adaptations to the published dashboard assets."""

import argparse
import hashlib
import json
from pathlib import Path

DEMO = Path(__file__).resolve().parents[1]
WORKSPACE = DEMO.parents[1]
MESSAGE = ("Static demo: recorded runs only. To analyse your own commentary, "
           "run the dashboard locally:")
MAIN_REPO = "https://github.com/egemen-candir/market-book-connector"

COMMENTARY_ANCHOR = '''      <div class="form-group">
        <label for="recent-select">Recent runs</label>'''
COMMENTARY_REPLACEMENT = '''      <div class="form-group">
        <label for="saved-commentary">Commentary</label>
        <textarea id="saved-commentary" rows="8" readonly
          placeholder="Choose a saved result to see its commentary."></textarea>
      </div>

''' + COMMENTARY_ANCHOR

EVALUATE_ANCHOR = '''    <div id="mode-evaluate" class="mode-panel" role="tabpanel" aria-labelledby="tab-evaluate" hidden>
'''
EVALUATE_REPLACEMENT = EVALUATE_ANCHOR + f'''      <div id="static-evaluate-note" class="mock-notice" role="note">
        This is a static page, so evaluations can't run here. To evaluate your own
        commentary, run the dashboard locally:
        <a href="{MAIN_REPO}">{MAIN_REPO}</a>
      </div>

'''

VIEW_ANCHOR = '''      _active.view = view;
      renderNowViewing();'''
VIEW_REPLACEMENT = '''      _active.view = view;
      document.getElementById("saved-commentary").value = (view.input || {}).raw_text || "";
      renderNowViewing();'''

FETCH_ANCHOR = '''function fetchJSON(url) {
  return fetch(url).then(function (resp) {'''
FETCH_REPLACEMENT = '''var STATIC_DEMO_MESSAGE = document.getElementById("static-demo-banner").textContent.trim();

function staticURL(url) {
  var fixed = {
    "/api/curated-runs": "data/curated-runs.json",
    "/api/examples": "data/examples.json",
    "/api/backend-profiles": "data/backend-profiles.json",
    "/api/runs": "data/runs.json"
  };
  if (fixed[url]) return fixed[url];
  var run = url.match(/^\\/api\\/runs\\/([^/]+)\\/(view|status)$/);
  if (run) return "data/runs/" + run[1] + "/" + run[2] + ".json";
  var context = url.match(/^\\/api\\/runs\\/([^/]+)\\/signal_context\\/download\\/(json|yaml)$/);
  if (context) return "data/runs/" + context[1] + "/market_state_context." + context[2];
  throw new Error("This static demo has no endpoint for " + url);
}

function fetchJSON(url) {
  return fetch(staticURL(url)).then(function (resp) {'''

STATE_ANCHOR = '''  run.disabled = empty;
  document.getElementById("raw-input-message").textContent = empty
    ? "Paste commentary or start from an example to enable Run." : "";'''
STATE_REPLACEMENT = '''  run.disabled = true;
  document.getElementById("raw-input-message").textContent = "";
  document.getElementById("run-message").textContent = STATIC_DEMO_MESSAGE;'''

SUBMIT_ANCHOR = '''document.getElementById("run-button").addEventListener("click", function () {
  var text = document.getElementById("raw-input").value.trim();
  var runMsg = document.getElementById("run-message");
  runMsg.textContent = "";
  if (!text) {
    updateCommentaryState();          // inline message under the box; result untouched
    document.getElementById("raw-input").focus();
    return;
  }
  var sel = modelSelection();
  // Always explicit: the displayed choice is what runs (explicit override wins).
  var payload = { backend: sel.backend, raw_input_text: text };
  if (sel.builder !== ROLES_FILE) payload.builder_backend = sel.builder;
  if (sel.evaluator !== ROLES_FILE) payload.evaluator_backend = sel.evaluator;
  var button = this;
  button.disabled = true;

  fetch("/api/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  }).then(function (resp) {
    return resp.json().then(function (data) {
      if (!resp.ok) throw new Error(data.error || ("HTTP " + resp.status));
      _active = { runId: data.run_id, source: "submitted",
                  view: { outcome: "running", meta: {} },
                  roles: { builder: roleDisplay(sel.builder), evaluator: roleDisplay(sel.evaluator) },
                  submittedAt: Date.now() };
      resetSelectorsExcept("submitted");
      setHash(data.run_id);
      renderNowViewing();
      updateGuideContext(null);
      renderRunning(data.run_id, sel.backend);
      // Bring the run's identity + running screen into view.
      document.getElementById("now-viewing").scrollIntoView({ block: "start" });
    });
  }).catch(function (err) {
    runMsg.textContent = "The server did not start the run: " + err.message;
  }).then(function () { updateCommentaryState(); });
});'''
SUBMIT_REPLACEMENT = '''document.getElementById("run-button").addEventListener("click", function () {
  document.getElementById("run-message").textContent = STATIC_DEMO_MESSAGE;
});'''


def patched_sources(source_code):
    changes = {
        "index.html": [
            ("stylesheet path", 'href="/static/app.css"', 'href="static/app.css"'),
            ("script path", 'src="/static/app.js"', 'src="static/app.js"'),
            ("demo banner", '<header class="app-header">\n',
             '<header class="app-header">\n'
             f'  <p id="static-demo-banner" class="banner" role="note">{MESSAGE} '
             f'<a href="{MAIN_REPO}">{MAIN_REPO}</a></p>\n'),
            ("disabled run button",
             '<button id="run-button" type="button" aria-describedby="run-message">',
             '<button id="run-button" type="button" aria-describedby="run-message" disabled>'),
            ("saved commentary tile", COMMENTARY_ANCHOR, COMMENTARY_REPLACEMENT),
            ("evaluate static-page note", EVALUATE_ANCHOR, EVALUATE_REPLACEMENT),
        ],
        "app.js": [
            ("static request mapping", FETCH_ANCHOR, FETCH_REPLACEMENT),
            ("persistent disabled state and message", STATE_ANCHOR, STATE_REPLACEMENT),
            ("submit message without POST", SUBMIT_ANCHOR, SUBMIT_REPLACEMENT),
            ("show opened run commentary", VIEW_ANCHOR, VIEW_REPLACEMENT),
        ],
    }
    # Read and validate ALL anchors before any destination is written.
    originals = {name: (source_code / "dashboard/static" / name).read_text(encoding="utf-8")
                 for name in changes}
    for name, replacements in changes.items():
        for label, anchor, _replacement in replacements:
            count = originals[name].count(anchor)
            if count != 1:
                raise ValueError(f"{name}: {label}: expected exactly one anchor; found {count}")
    patched = {}
    for name, replacements in changes.items():
        result = originals[name]
        for _label, anchor, replacement in replacements:
            result = result.replace(anchor, replacement, 1)
        target = Path("index.html") if name == "index.html" else Path("static/app.js")
        patched[target] = result.encode("utf-8")
    return patched, {name: [label for label, _a, _r in replacements]
                     for name, replacements in changes.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-code", type=Path,
                        default=WORKSPACE.with_name(WORKSPACE.name + "_OS"))
    parser.add_argument("--check", action="store_true", help="Validate anchors and outputs without writing")
    args = parser.parse_args()
    try:
        outputs, changes = patched_sources(args.source_code.resolve())
        if args.check:
            if any(not (DEMO / path).is_file() or (DEMO / path).read_bytes() != content
                   for path, content in outputs.items()):
                raise ValueError("Front-end outputs differ from the anchored changes")
        else:
            for path, content in outputs.items():
                target = DEMO / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Applier stopped without writing: {exc}\n")
    print(json.dumps({"mode": "check" if args.check else "apply", "changes": changes,
                      "sha256": {path.as_posix(): hashlib.sha256(content).hexdigest()
                                 for path, content in outputs.items()}}, sort_keys=True))


if __name__ == "__main__":
    main()
