# GEX Tools (Gamma Exposure)

This folder contains a small toolkit to compute and visualize option Gamma Exposure (GEX).

## Files

- `gex_tool.py`
  - CLI tool: read an option chain (CSV/Excel), aggregate GEX by strike, and print max positive / max negative.
- `gex_report.py`
  - Generate a static HTML dashboard from a saved option chain file.
- `realtime_gex_futu.py`
  - Realtime dashboard via **Futu OpenAPI** (requires FutuOpenD running).
- `gex_live/`
  - Live dashboard frontend (`index.html`) + runtime data file (`data.json`).

## Install

From repo root:

```bash
pip install -r crawler-tool/requirements.txt
```

## Realtime (Futu)

1) Start **FutuOpenD** (and make sure your account has US options realtime quotes permission).

2) Run:

```bash
python crawler-tool/gex-tools/realtime_gex_futu.py
```

3) Open the dashboard:

- `http://127.0.0.1:8000/`

## Notes

- Open Interest (OI) is usually not tick-level; it is often updated daily. Real-time dashboards typically reuse the latest available OI snapshot and recompute GEX using real-time spot/quotes/IV.


