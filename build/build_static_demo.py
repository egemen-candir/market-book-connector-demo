#!/usr/bin/env python3
"""Export retained runs using the published dashboard's read-only view builder."""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

# Imports from the source checkout must never create bytecode there.
sys.dont_write_bytecode = True
DEMO = Path(__file__).resolve().parents[1]
WORKSPACE = DEMO.parents[1]


def json_bytes(value):
    # Match the HTTP server's date handling as well as deterministic formatting.
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                       default=str) + "\n").encode("utf-8")


def collect_outputs(source_code, runs_root):
    sys.path.insert(0, str(source_code))
    from dashboard import connector_dashboard as dashboard

    if Path(dashboard.__file__).resolve() != source_code / "dashboard/connector_dashboard.py":
        raise ValueError("The imported dashboard is not from the requested source checkout")
    dashboard._set_runs_root(runs_root)
    entries = json.loads((DEMO / "build/demo_runs.json").read_text(encoding="utf-8"))["runs"]
    ids = [entry["id"] for entry in entries]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate run IDs in demo_runs.json")
    # Validate every listed folder and manifest before preparing any output.
    for entry in entries:
        run_id = entry["id"]
        if not re.fullmatch(r"[A-Za-z0-9_-]+", run_id) or entry.get("expect") is not None:
            raise ValueError("Invalid run ID or non-null expectation")
        run_dir = runs_root / run_id
        if not run_dir.is_dir() or not (run_dir / "run_manifest.json").is_file():
            raise ValueError(f"Missing run folder or run_manifest.json: {run_id}")

    outputs = {}
    curated = []
    omitted = []
    outcomes = Counter()
    contexts = 0
    for entry in entries:
        run_id = entry["id"]
        run_dir = runs_root / run_id
        manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
        view = dashboard.build_run_view(run_dir)
        if view is None:
            omitted.append(run_id)
            continue
        target = Path("data/runs") / run_id
        downloads = view.get("provenance", {}).get("downloads", {})
        for kind in ("json", "yaml"):
            key = "context_" + kind
            if key in downloads:
                downloads[key] = (target / ("market_state_context." + kind)).as_posix()
            context_file = run_dir / "signal_context" / ("market_state_context." + kind)
            if context_file.is_file():
                outputs[target / context_file.name] = context_file.read_bytes()
                contexts += 1
        outputs[target / "view.json"] = json_bytes(view)
        outputs[target / "status.json"] = json_bytes({
            "run_id": run_id,
            "status": "ok" if manifest.get("overall_status") == "ok" else "failed",
        })
        curated.append({"id": run_id, "label": entry["label"], "expect": None})
        outcomes[view["outcome"]] += 1

    outputs[Path("data/curated-runs.json")] = json_bytes({"curated_runs": curated})
    outputs[Path("data/runs.json")] = json_bytes({"runs": []})
    outputs[Path("data/examples.json")] = json_bytes({
        "examples": [{key: value for key, value in example.items() if key != "path"}
                     for example in dashboard._scan_examples()],
    })
    cfg = dashboard._load_backend_config(source_code / "connector/configs/backend_profiles.example.yaml")
    outputs[Path("data/backend-profiles.json")] = json_bytes({
        "profiles_version": cfg.get("profiles_version", ""),
        "default": "mock",
        "profiles": {
            name: {"backend_type": profile.get("backend_type", ""),
                   "timeout_seconds": profile.get("timeout_seconds")}
            for name, profile in cfg.get("profiles", {}).items()
        },
        "role_pins": dashboard._role_pins(source_code / "connector/configs/roles.example.yaml"),
    })
    outputs[Path("static/app.css")] = (source_code / "dashboard/static/app.css").read_bytes()
    return outputs, {"rendered_runs": len(curated), "omitted_runs": omitted,
                     "outcomes": dict(sorted(outcomes.items())),
                     "context_files": contexts, "files": len(outputs),
                     "run_history": "empty"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-code", type=Path,
                        default=WORKSPACE.with_name(WORKSPACE.name + "_OS"))
    parser.add_argument("--runs-root", type=Path, default=WORKSPACE / "connector/runs")
    parser.add_argument("--check", action="store_true", help="Compare exports without writing")
    args = parser.parse_args()
    try:
        outputs, summary = collect_outputs(args.source_code.resolve(), args.runs_root.resolve())
        if args.check:
            changed = [path.as_posix() for path, content in outputs.items()
                       if not (DEMO / path).is_file() or (DEMO / path).read_bytes() != content]
            if changed:
                raise ValueError("Exports differ: " + ", ".join(changed))
            summary["mode"] = "check"
        else:
            for path, content in outputs.items():
                destination = DEMO / path
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(content)
            summary["mode"] = "build"
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, f"Build stopped: {exc}\n")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
