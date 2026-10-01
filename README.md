# Market Book dashboard demo

A static, read-only copy of the
[Market Book Connector](https://github.com/egemen-candir/market-book-connector)
dashboard. Live at [marketbook.teodinlabs.com](https://marketbook.teodinlabs.com/).

It shows the 50 recorded runs of the blind-batch study (published in the main
repository's `study/` folder) plus one recorded run of the golden example. The
run labels match the case IDs in `study/results.csv`.

There is no server and no model call: every result is a saved run. New
evaluations are disabled. To analyse your own commentary, run the dashboard
locally by following the main repository's README.

## How it was built

`build/build_static_demo.py` exports each recorded run with the published
dashboard's own view builder, so every view is what the local dashboard shows
for that run. `build/apply_demo_frontend.py` adapts the published front end for
static hosting: relative file paths, saved files instead of server requests, a
demo banner, and a disabled Run button. The run list is `build/demo_runs.json`.

Rebuilding needs a checkout of the main repository with its Python dependencies
and the recorded run folders, which are not part of the public repositories:

```bash
python build/build_static_demo.py --source-code /path/to/market-book-connector --runs-root /path/to/runs
python build/apply_demo_frontend.py --source-code /path/to/market-book-connector
```

## Local preview

```bash
python3 -m http.server 8800 --bind 127.0.0.1
```

Then open `http://127.0.0.1:8800/`.
