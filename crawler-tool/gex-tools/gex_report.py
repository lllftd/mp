"""
Generate a dark-themed HTML dashboard similar to common GEX charts:
- Horizontal bars by strike (positive/negative)
- Sidebar metrics: Zero Gamma, Major Positive/Negative, Net GEX
- Toggle windows: 0DTE / Next day / <=90DTE (requires DTE or expiration)

No extra Python deps required (uses Plotly via CDN in the generated HTML).
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def bs_gamma(spot: float, strike: float, iv: float, t: float, r: float = 0.0, q: float = 0.0) -> float:
    if spot <= 0 or strike <= 0 or iv <= 0 or t <= 0:
        return 0.0
    denom = iv * math.sqrt(t)
    if denom <= 0:
        return 0.0
    d1 = (math.log(spot / strike) + (r - q + 0.5 * iv * iv) * t) / denom
    return _norm_pdf(d1) / (spot * denom)


def _to_date(x) -> Optional[date]:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    if isinstance(x, date) and not isinstance(x, datetime):
        return x
    if isinstance(x, datetime):
        return x.date()
    if isinstance(x, str):
        s = x.strip()
        if not s:
            return None
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%d/%m/%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                pass
        try:
            return pd.to_datetime(s).date()
        except Exception:
            return None
    return None


def _normalize_type(x: str) -> Optional[str]:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    s = str(x).strip().lower()
    if s in {"c", "call", "calls"}:
        return "call"
    if s in {"p", "put", "puts"}:
        return "put"
    if s in {"1", "+1"}:
        return "call"
    if s in {"-1"}:
        return "put"
    return None


@dataclass(frozen=True)
class Columns:
    strike: str
    opt_type: str
    iv: str
    oi: str
    volume: Optional[str] = None
    dte: Optional[str] = None
    expiration: Optional[str] = None


def _pick_first_existing(df: pd.DataFrame, candidates: Tuple[str, ...]) -> Optional[str]:
    lower_map = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in lower_map:
            return lower_map[cand.lower()]
    return None


def infer_columns(df: pd.DataFrame) -> Columns:
    strike = _pick_first_existing(df, ("strike", "k", "行权价"))
    opt_type = _pick_first_existing(df, ("type", "option_type", "cp", "right", "putcall", "call_put", "看涨看跌"))
    iv = _pick_first_existing(df, ("iv", "implied_vol", "implied_volatility", "vol", "sigma", "隐含波动率"))
    oi = _pick_first_existing(df, ("open_interest", "oi", "openinterest", "持仓量"))
    volume = _pick_first_existing(df, ("volume", "volm", "成交量"))
    dte = _pick_first_existing(df, ("dte", "days_to_exp", "days_to_expiration", "ttm_days", "剩余天数"))
    expiration = _pick_first_existing(df, ("expiration", "expiry", "exp", "maturity", "到期日"))

    missing = [name for name, col in [("strike", strike), ("type", opt_type), ("iv", iv), ("oi", oi)] if col is None]
    if missing:
        raise ValueError(
            "Cannot infer required columns: "
            + ", ".join(missing)
            + ". Please specify explicitly (e.g. --col-strike STRIKE --col-type TYPE --col-iv IV --col-oi OI)."
        )
    if dte is None and expiration is None:
        raise ValueError("Need either DTE or expiration date column: provide --col-dte or --col-expiration (or let the tool infer).")
    return Columns(strike=strike, opt_type=opt_type, iv=iv, oi=oi, volume=volume, dte=dte, expiration=expiration)


def _read_chain(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(str(path))
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    return pd.read_csv(path)


def _prep_rows(
    df: pd.DataFrame,
    spot: float,
    asof: date,
    cols: Columns,
    r: float,
    q: float,
) -> pd.DataFrame:
    out = df.copy()
    out["_strike"] = pd.to_numeric(out[cols.strike], errors="coerce")
    out["_iv"] = pd.to_numeric(out[cols.iv], errors="coerce")
    out["_oi"] = pd.to_numeric(out[cols.oi], errors="coerce").fillna(0.0)
    out["_type"] = out[cols.opt_type].apply(_normalize_type)
    if cols.volume:
        out["_vol"] = pd.to_numeric(out[cols.volume], errors="coerce").fillna(0.0)
    else:
        out["_vol"] = 0.0

    if cols.dte:
        dte_days = pd.to_numeric(out[cols.dte], errors="coerce")
    else:
        exp_dates = out[cols.expiration].apply(_to_date)
        dte_days = exp_dates.apply(lambda d: (d - asof).days if d else np.nan)
    out["_dte_days"] = dte_days
    out["_t"] = out["_dte_days"] / 365.0

    out = out.dropna(subset=["_strike", "_iv", "_t", "_type", "_dte_days"])
    out = out[(out["_strike"] > 0) & (out["_iv"] > 0) & (out["_t"] > 0) & (out["_dte_days"] >= 0)]

    def _row_gamma(row) -> float:
        return bs_gamma(float(spot), float(row["_strike"]), float(row["_iv"]), float(row["_t"]), r=r, q=q)

    out["_gamma"] = out.apply(_row_gamma, axis=1)
    out["_strike_round"] = out["_strike"].round(10)
    return out


def _apply_sign(gex_raw: np.ndarray, opt_type: np.ndarray, sign_model: str) -> np.ndarray:
    if sign_model == "call_plus_put_minus":
        return np.where(opt_type == "call", gex_raw, -gex_raw)
    if sign_model == "dealer_short_all":
        return -np.abs(gex_raw)
    if sign_model == "no_sign":
        return np.abs(gex_raw)
    raise ValueError(f"Unknown sign_model: {sign_model}")


def gex_by_strike(
    rows: pd.DataFrame,
    spot: float,
    multiplier: float,
    move_frac: float,
    sign_model: str,
    weight_col: str,
) -> pd.DataFrame:
    """
    weight_col: '_oi' or '_vol'
    """
    gex_raw = rows["_gamma"].to_numpy() * (spot**2) * float(move_frac) * rows[weight_col].to_numpy() * float(multiplier)
    gex = _apply_sign(gex_raw, rows["_type"].to_numpy(), sign_model)
    tmp = rows[["_strike_round"]].copy()
    tmp["_gex"] = gex
    g = tmp.groupby("_strike_round", as_index=False)["_gex"].sum().rename(columns={"_strike_round": "strike", "_gex": "gex"})
    return g.sort_values("strike").reset_index(drop=True)


def total_gex_for_spot(
    rows: pd.DataFrame,
    spot: float,
    r: float,
    q: float,
    multiplier: float,
    move_frac: float,
    sign_model: str,
    weight_col: str,
) -> float:
    # recompute gamma under this spot
    strikes = rows["_strike"].to_numpy(dtype=float)
    ivs = rows["_iv"].to_numpy(dtype=float)
    ts = rows["_t"].to_numpy(dtype=float)
    types = rows["_type"].to_numpy()
    weights = rows[weight_col].to_numpy(dtype=float)

    gammas = np.array([bs_gamma(float(spot), float(k), float(iv), float(t), r=r, q=q) for k, iv, t in zip(strikes, ivs, ts)], dtype=float)
    gex_raw = gammas * (spot**2) * float(move_frac) * weights * float(multiplier)
    gex = _apply_sign(gex_raw, types, sign_model)
    return float(np.nansum(gex))


def find_zero_gamma(
    rows: pd.DataFrame,
    r: float,
    q: float,
    multiplier: float,
    move_frac: float,
    sign_model: str,
    weight_col: str,
    grid: Optional[np.ndarray] = None,
) -> Optional[float]:
    if rows.empty:
        return None
    if grid is None:
        kmin = float(rows["_strike"].min())
        kmax = float(rows["_strike"].max())
        if not (math.isfinite(kmin) and math.isfinite(kmax)) or kmin <= 0 or kmax <= 0 or kmax <= kmin:
            return None
        grid = np.linspace(kmin, kmax, 200)

    vals = np.array(
        [total_gex_for_spot(rows, float(s), r=r, q=q, multiplier=multiplier, move_frac=move_frac, sign_model=sign_model, weight_col=weight_col) for s in grid],
        dtype=float,
    )
    # Find sign change
    signs = np.sign(vals)
    for i in range(1, len(grid)):
        if signs[i] == 0:
            return float(grid[i])
        if signs[i - 1] == 0:
            return float(grid[i - 1])
        if signs[i] != signs[i - 1]:
            # linear interpolation
            x0, x1 = float(grid[i - 1]), float(grid[i])
            y0, y1 = float(vals[i - 1]), float(vals[i])
            if y1 == y0:
                return x0
            return x0 + (0 - y0) * (x1 - x0) / (y1 - y0)
    return None


def _subset_windows(rows: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    dte = rows["_dte_days"].astype(int)
    return {
        "0DTE": rows.loc[dte == 0].copy(),
        "NEXT": rows.loc[dte == 1].copy(),
        "90D": rows.loc[dte <= 90].copy(),
    }


def _metrics(rows: pd.DataFrame, spot: float, r: float, q: float, multiplier: float, move_frac: float, sign_model: str) -> Dict:
    # OI-based
    g_oi = gex_by_strike(rows, spot=spot, multiplier=multiplier, move_frac=move_frac, sign_model=sign_model, weight_col="_oi")
    net_oi = float(g_oi["gex"].sum()) if not g_oi.empty else 0.0
    maj_pos_oi = float(g_oi.loc[g_oi["gex"].idxmax(), "strike"]) if not g_oi.empty else None
    maj_neg_oi = float(g_oi.loc[g_oi["gex"].idxmin(), "strike"]) if not g_oi.empty else None
    zero_oi = find_zero_gamma(rows, r=r, q=q, multiplier=multiplier, move_frac=move_frac, sign_model=sign_model, weight_col="_oi")

    # Volume-based (if present)
    has_vol = rows["_vol"].sum() > 0
    g_vol = gex_by_strike(rows, spot=spot, multiplier=multiplier, move_frac=move_frac, sign_model=sign_model, weight_col="_vol") if has_vol else pd.DataFrame()
    net_vol = float(g_vol["gex"].sum()) if has_vol and not g_vol.empty else None
    maj_pos_vol = float(g_vol.loc[g_vol["gex"].idxmax(), "strike"]) if has_vol and not g_vol.empty else None
    maj_neg_vol = float(g_vol.loc[g_vol["gex"].idxmin(), "strike"]) if has_vol and not g_vol.empty else None

    return {
        "has_volume": bool(has_vol),
        "oi": {"zero_gamma": zero_oi, "major_positive": maj_pos_oi, "major_negative": maj_neg_oi, "net_gex": net_oi, "series": g_oi.to_dict(orient="list")},
        "vol": {"major_positive": maj_pos_vol, "major_negative": maj_neg_vol, "net_gex": net_vol, "series": (g_vol.to_dict(orient="list") if has_vol else None)},
    }


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>GEX Dashboard</title>
  <script src="https://cdn.plot.ly/plotly-2.30.0.min.js"></script>
  <style>
    :root{
      --bg:#0b1220;
      --panel:#0f1a2b;
      --panel2:#0c1626;
      --text:#e7edf6;
      --muted:#9fb0c6;
      --green:#2ecc71;
      --red:#ff3b30;
      --yellow:#f1c40f;
      --border:rgba(255,255,255,0.08);
      --grid:rgba(255,255,255,0.10);
    }
    html,body{height:100%; margin:0; background:var(--bg); color:var(--text); font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial;}
    .wrap{display:flex; gap:16px; height:100vh; box-sizing:border-box; padding:16px;}
    .main{flex: 1 1 auto; background:linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.00)); border:1px solid var(--border); border-radius:10px; padding:12px;}
    .side{width:360px; min-width:320px; background:var(--panel); border:1px solid var(--border); border-radius:10px; padding:14px; display:flex; flex-direction:column; gap:14px;}
    .row{display:flex; gap:10px; align-items:center;}
    .title{font-weight:700; letter-spacing:0.3px;}
    .box{background:var(--panel2); border:1px solid var(--border); border-radius:10px; padding:12px;}
    .label{color:var(--muted); font-size:12px; margin-bottom:6px;}
    select,button,input[type=range]{background:rgba(255,255,255,0.05); color:var(--text); border:1px solid var(--border); border-radius:8px; padding:10px 12px;}
    button{cursor:pointer;}
    .btns{display:flex; gap:10px;}
    .btn{flex:1; text-align:center; font-weight:600;}
    .btn.active{background:rgba(56,139,253,0.85); border-color:rgba(56,139,253,0.9);}
    .metric{display:flex; justify-content:space-between; gap:10px; padding:6px 0; border-bottom:1px dashed rgba(255,255,255,0.07);}
    .metric:last-child{border-bottom:none;}
    .k{color:var(--muted);}
    .v{font-variant-numeric: tabular-nums;}
    .v.green{color:var(--green);}
    .v.red{color:var(--red);}
    .v.yellow{color:var(--yellow);}
    #chart{height: calc(100vh - 60px); }
    .small{font-size:12px; color:var(--muted);}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="main">
      <div id="chart"></div>
    </div>
    <div class="side">
      <div class="box">
        <div class="label">Stock</div>
        <div class="row">
          <select id="stockSelect" style="flex:1"></select>
        </div>
        <div class="btns" style="margin-top:10px;">
          <button class="btn active" id="btn0dte">0DTE</button>
          <button class="btn" id="btnNext">NEXT</button>
          <button class="btn" id="btn90d">90D</button>
        </div>
      </div>

      <div class="box">
        <div class="title">Update</div>
        <div class="metric"><div class="k">Time</div><div class="v" id="mTime"></div></div>
        <div class="metric"><div class="k">Spot</div><div class="v" id="mSpot"></div></div>
      </div>

      <div class="box" id="volBox">
        <div class="title">Volume</div>
        <div class="metric"><div class="k">Zero Gamma</div><div class="v yellow" id="vZero"></div></div>
        <div class="metric"><div class="k">Major Positive</div><div class="v green" id="vPos"></div></div>
        <div class="metric"><div class="k">Major Negative</div><div class="v red" id="vNeg"></div></div>
        <div class="metric"><div class="k">Net GEX</div><div class="v" id="vNet"></div></div>
      </div>

      <div class="box">
        <div class="title">Open Interest</div>
        <div class="metric"><div class="k">Zero Gamma</div><div class="v yellow" id="oiZero"></div></div>
        <div class="metric"><div class="k">Major Positive</div><div class="v green" id="oiPos"></div></div>
        <div class="metric"><div class="k">Major Negative</div><div class="v red" id="oiNeg"></div></div>
        <div class="metric"><div class="k">Net GEX</div><div class="v" id="oiNet"></div></div>
      </div>

      <div class="box">
        <div class="title">Scale</div>
        <div class="row">
          <input id="scale" type="range" min="0.2" max="3" step="0.1" value="1" style="flex:1" />
          <div class="small" style="width:52px; text-align:right;"><span id="scaleVal">1.0</span>x</div>
        </div>
        <div class="small" style="margin-top:8px;">Sign model: <span id="signModel"></span></div>
      </div>
    </div>
  </div>

  <script>
    const DATA = __DATA_JSON__;

    function fmt(x){
      if (x === null || x === undefined || Number.isNaN(x)) return "-";
      if (Math.abs(x) >= 1000) return x.toFixed(1);
      return x.toFixed(2);
    }
    function fmtInt(x){
      if (x === null || x === undefined || Number.isNaN(x)) return "-";
      return String(Math.round(x));
    }
    function setActive(btnId){
      ["btn0dte","btnNext","btn90d"].forEach(id=>{
        document.getElementById(id).classList.toggle("active", id === btnId);
      });
    }
    function pickWindow(winKey){
      return {
        "0DTE": "0DTE",
        "NEXT": "NEXT",
        "90D": "90D"
      }[winKey];
    }

    function buildBars(series, scale){
      const strikes = series.strike;
      const gex = series.gex.map(v => v * scale);
      const pos = gex.map(v => Math.max(0, v));
      const neg = gex.map(v => Math.min(0, v));
      return {strikes, pos, neg, gex};
    }

    function render(stockKey, winKey){
      const stock = DATA.stocks[stockKey];
      const win = stock.windows[winKey];
      const scale = parseFloat(document.getElementById("scale").value || "1");
      document.getElementById("scaleVal").innerText = scale.toFixed(1);

      document.getElementById("mTime").innerText = stock.time;
      document.getElementById("mSpot").innerText = fmt(stock.spot);
      document.getElementById("signModel").innerText = stock.sign_model;

      // OI metrics
      document.getElementById("oiZero").innerText = fmt(win.metrics.oi.zero_gamma);
      document.getElementById("oiPos").innerText = fmt(win.metrics.oi.major_positive);
      document.getElementById("oiNeg").innerText = fmt(win.metrics.oi.major_negative);
      document.getElementById("oiNet").innerText = fmt(win.metrics.oi.net_gex);
      document.getElementById("oiNet").className = "v " + (win.metrics.oi.net_gex >= 0 ? "green" : "red");

      // Volume metrics (optional)
      const volBox = document.getElementById("volBox");
      if (win.metrics.has_volume && win.metrics.vol && win.metrics.vol.net_gex !== null){
        volBox.style.display = "block";
        // For volume we don't compute zero-gamma by default, show "-" to match typical dashboards.
        document.getElementById("vZero").innerText = "-";
        document.getElementById("vPos").innerText = fmt(win.metrics.vol.major_positive);
        document.getElementById("vNeg").innerText = fmt(win.metrics.vol.major_negative);
        document.getElementById("vNet").innerText = fmt(win.metrics.vol.net_gex);
        document.getElementById("vNet").className = "v " + (win.metrics.vol.net_gex >= 0 ? "green" : "red");
      } else {
        volBox.style.display = "none";
      }

      const bars = buildBars(win.metrics.oi.series, scale);

      const traceNeg = {
        type: "bar",
        orientation: "h",
        y: bars.strikes,
        x: bars.neg,
        name: "Negative",
        marker: {color: "#ff3b30"},
        hovertemplate: "strike=%{y}<br>gex=%{x:.2f}<extra></extra>"
      };
      const tracePos = {
        type: "bar",
        orientation: "h",
        y: bars.strikes,
        x: bars.pos,
        name: "Positive",
        marker: {color: "#2ecc71"},
        hovertemplate: "strike=%{y}<br>gex=%{x:.2f}<extra></extra>"
      };

      const spotLine = {
        type: "scatter",
        mode: "lines",
        x: [Math.min(...bars.gex) * 1.05, Math.max(...bars.gex) * 1.05],
        y: [stock.spot, stock.spot],
        line: {color: "rgba(255,255,255,0.45)", width: 1, dash:"dash"},
        hoverinfo: "skip",
        showlegend: false
      };

      const layout = {
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        barmode: "overlay",
        margin: {l: 60, r: 10, t: 10, b: 40},
        xaxis: {
          zeroline: true,
          zerolinecolor: "rgba(255,255,255,0.25)",
          gridcolor: "rgba(255,255,255,0.10)",
          tickfont: {color: "rgba(255,255,255,0.70)"},
        },
        yaxis: {
          autorange: true,
          gridcolor: "rgba(255,255,255,0.06)",
          tickfont: {color: "rgba(255,255,255,0.70)"},
        },
        showlegend: false,
      };

      // Plotly can't directly put a horizontal line at y=spot when y is categorical (strike axis).
      // We'll just render bars and add an annotation for spot instead.
      const ann = {
        x: 0,
        y: stock.spot,
        xref: "paper",
        yref: "y",
        text: "spot " + fmt(stock.spot),
        showarrow: false,
        font: {color: "rgba(255,255,255,0.85)", size: 12},
        bgcolor: "rgba(255,255,255,0.10)",
        bordercolor: "rgba(255,255,255,0.20)",
        borderwidth: 1,
        borderpad: 4,
      };
      layout.annotations = [ann];

      Plotly.react("chart", [traceNeg, tracePos], layout, {displayModeBar:false, responsive:true});
    }

    // Init UI
    const stockSelect = document.getElementById("stockSelect");
    Object.keys(DATA.stocks).forEach(k=>{
      const opt = document.createElement("option");
      opt.value = k;
      opt.textContent = k;
      stockSelect.appendChild(opt);
    });
    stockSelect.value = DATA.default_stock;

    let currentWin = "0DTE";
    function rerender(){
      render(stockSelect.value, currentWin);
    }

    document.getElementById("btn0dte").onclick = ()=>{ currentWin="0DTE"; setActive("btn0dte"); rerender(); };
    document.getElementById("btnNext").onclick = ()=>{ currentWin="NEXT"; setActive("btnNext"); rerender(); };
    document.getElementById("btn90d").onclick = ()=>{ currentWin="90D"; setActive("btn90d"); rerender(); };
    stockSelect.onchange = rerender;
    document.getElementById("scale").oninput = rerender;

    rerender();
  </script>
</body>
</html>
"""


def build_data_payload(
    name: str,
    df: pd.DataFrame,
    spot: float,
    asof: date,
    r: float,
    q: float,
    multiplier: float,
    move_frac: float,
    sign_model: str,
    cols: Columns,
) -> Dict:
    rows = _prep_rows(df, spot=spot, asof=asof, cols=cols, r=r, q=q)
    windows = _subset_windows(rows)
    win_payload = {}
    for key, sub in windows.items():
        win_payload[key] = {
            "metrics": _metrics(sub, spot=spot, r=r, q=q, multiplier=multiplier, move_frac=move_frac, sign_model=sign_model),
            "count": int(len(sub)),
        }

    return {
        "spot": float(spot),
        "time": datetime.now().strftime("%m-%d %H:%M:%S"),
        "sign_model": sign_model,
        "windows": win_payload,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate a GEX HTML dashboard (similar to common GEX bar charts).")
    ap.add_argument("--file", required=True, help="Option chain file path (CSV or Excel)")
    ap.add_argument("--spot", required=True, type=float, help="Underlying spot price S")
    ap.add_argument("--stock", default="TICKER", help="Label for the dashboard (e.g. QQQ)")
    ap.add_argument("--asof", default=None, help="As-of date (YYYY-MM-DD), default: today")
    ap.add_argument("--r", type=float, default=0.0, help="Risk-free rate r (annualized, decimal)")
    ap.add_argument("--q", type=float, default=0.0, help="Dividend yield q (annualized, decimal)")
    ap.add_argument("--multiplier", type=float, default=100.0, help="Contract multiplier (equity options typically 100)")
    ap.add_argument("--move-frac", type=float, default=0.01, help="Underlying move fraction, default 1%% = 0.01")
    ap.add_argument(
        "--sign-model",
        default="call_plus_put_minus",
        choices=("call_plus_put_minus", "dealer_short_all", "no_sign"),
        help="Sign convention for GEX",
    )
    ap.add_argument("--out", default="gex_dashboard.html", help="Output HTML file")

    # Column overrides
    ap.add_argument("--col-strike", default=None, help="Column name for strike")
    ap.add_argument("--col-type", default=None, help="Column name for option type (C/P or call/put)")
    ap.add_argument("--col-iv", default=None, help="Column name for implied vol (annualized decimal, e.g. 0.25)")
    ap.add_argument("--col-oi", default=None, help="Column name for open interest (OI)")
    ap.add_argument("--col-volume", default=None, help="Column name for volume (optional)")
    ap.add_argument("--col-dte", default=None, help="Column name for days-to-expiration (DTE, numeric)")
    ap.add_argument("--col-expiration", default=None, help="Column name for expiration date")

    args = ap.parse_args()

    asof = _to_date(args.asof) if args.asof else date.today()
    if asof is None:
        raise ValueError("Cannot parse --asof; please use YYYY-MM-DD")

    df = _read_chain(Path(args.file))

    if args.col_strike and args.col_type and args.col_iv and args.col_oi:
        cols = Columns(
            strike=args.col_strike,
            opt_type=args.col_type,
            iv=args.col_iv,
            oi=args.col_oi,
            volume=args.col_volume,
            dte=args.col_dte,
            expiration=args.col_expiration,
        )
        if cols.dte is None and cols.expiration is None:
            inferred = infer_columns(df)
            cols = Columns(
                strike=cols.strike,
                opt_type=cols.opt_type,
                iv=cols.iv,
                oi=cols.oi,
                volume=cols.volume or inferred.volume,
                dte=inferred.dte,
                expiration=inferred.expiration,
            )
    else:
        cols = infer_columns(df)
        if args.col_volume:
            cols = Columns(
                strike=cols.strike,
                opt_type=cols.opt_type,
                iv=cols.iv,
                oi=cols.oi,
                volume=args.col_volume,
                dte=cols.dte,
                expiration=cols.expiration,
            )

    payload = {
        "default_stock": args.stock,
        "stocks": {args.stock: build_data_payload(args.stock, df, spot=args.spot, asof=asof, r=args.r, q=args.q, multiplier=args.multiplier, move_frac=args.move_frac, sign_model=args.sign_model, cols=cols)},
    }
    html = HTML_TEMPLATE.replace("__DATA_JSON__", json.dumps(payload, ensure_ascii=True))
    out_path = Path(args.out)
    out_path.write_text(html, encoding="utf-8")
    print(f"Wrote: {out_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


