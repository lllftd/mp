"""
Realtime GEX via Futu OpenAPI (FutuOpenD).

What you get:
- Connect to FutuOpenD
- Fetch option chain for configured underlyings
- Subscribe to Level1 quotes for a limited subset of option contracts
- Every second aggregate GEX by strike and write `gex_live/data.json`
- Serve `gex_live/index.html` + `data.json` on a local HTTP server

Notes:
- Open Interest (OI) is usually NOT real-time. Treat it as the latest available snapshot (often daily).
- If IV is not provided by your chain/quote fields, this script will fall back to a simple IV solver (slower).
- SPX index options may not be available via Futu for some accounts/regions; use SPY as a fallback if needed.
"""

from __future__ import annotations

import argparse
import json
import math
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def bs_price(spot: float, strike: float, iv: float, t: float, r: float, q: float, opt_type: str) -> float:
    if spot <= 0 or strike <= 0 or iv <= 0 or t <= 0:
        return 0.0
    vsqrt = iv * math.sqrt(t)
    if vsqrt <= 0:
        return 0.0
    d1 = (math.log(spot / strike) + (r - q + 0.5 * iv * iv) * t) / vsqrt
    d2 = d1 - vsqrt
    if opt_type == "call":
        return spot * math.exp(-q * t) * _norm_cdf(d1) - strike * math.exp(-r * t) * _norm_cdf(d2)
    return strike * math.exp(-r * t) * _norm_cdf(-d2) - spot * math.exp(-q * t) * _norm_cdf(-d1)


def bs_gamma(spot: float, strike: float, iv: float, t: float, r: float = 0.0, q: float = 0.0) -> float:
    if spot <= 0 or strike <= 0 or iv <= 0 or t <= 0:
        return 0.0
    denom = iv * math.sqrt(t)
    if denom <= 0:
        return 0.0
    d1 = (math.log(spot / strike) + (r - q + 0.5 * iv * iv) * t) / denom
    return _norm_pdf(d1) / (spot * denom)


def solve_iv_newton(price: float, spot: float, strike: float, t: float, r: float, q: float, opt_type: str) -> Optional[float]:
    """
    Basic IV solver using Newton steps. Returns annualized IV as decimal, or None.
    """
    if price <= 0 or spot <= 0 or strike <= 0 or t <= 0:
        return None
    # initial guess
    iv = 0.30
    for _ in range(30):
        p = bs_price(spot, strike, iv, t, r, q, opt_type)
        # vega
        vsqrt = iv * math.sqrt(t)
        if vsqrt <= 0:
            return None
        d1 = (math.log(spot / strike) + (r - q + 0.5 * iv * iv) * t) / vsqrt
        vega = spot * math.exp(-q * t) * _norm_pdf(d1) * math.sqrt(t)
        if vega <= 1e-12:
            return None
        diff = p - price
        if abs(diff) < 1e-6:
            return float(iv)
        iv = iv - diff / vega
        if iv <= 1e-6 or iv > 5.0:
            iv = max(1e-6, min(5.0, iv))
    return float(iv)


def _normalize_type(x) -> Optional[str]:
    if x is None:
        return None
    s = str(x).strip().lower()
    if s in {"c", "call", "calls"}:
        return "call"
    if s in {"p", "put", "puts"}:
        return "put"
    return None


def _to_date(x) -> Optional[date]:
    if x is None:
        return None
    if isinstance(x, date) and not isinstance(x, datetime):
        return x
    if isinstance(x, datetime):
        return x.date()
    s = str(x).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    try:
        return pd.to_datetime(s).date()
    except Exception:
        return None


def _apply_sign(gex_raw: np.ndarray, opt_type: np.ndarray, sign_model: str) -> np.ndarray:
    if sign_model == "call_plus_put_minus":
        return np.where(opt_type == "call", gex_raw, -gex_raw)
    if sign_model == "dealer_short_all":
        return -np.abs(gex_raw)
    if sign_model == "no_sign":
        return np.abs(gex_raw)
    raise ValueError(f"Unknown sign_model: {sign_model}")


def _gex_by_strike(rows: pd.DataFrame, spot: float, r: float, q: float, multiplier: float, move_frac: float, sign_model: str) -> pd.DataFrame:
    # Ensure IV exists; if not, try to solve from mid price
    iv = rows["iv"].to_numpy(dtype=float)
    need = ~np.isfinite(iv) | (iv <= 0)
    if need.any():
        mids = rows["mid"].to_numpy(dtype=float)
        strikes = rows["strike"].to_numpy(dtype=float)
        ts = rows["t"].to_numpy(dtype=float)
        types = rows["type"].to_numpy()
        iv_solved = iv.copy()
        for i in np.where(need)[0]:
            iv_i = solve_iv_newton(float(mids[i]), float(spot), float(strikes[i]), float(ts[i]), float(r), float(q), str(types[i]))
            if iv_i is not None:
                iv_solved[i] = iv_i
        iv = iv_solved

    gammas = np.array([bs_gamma(float(spot), float(k), float(v), float(t), r=r, q=q) for k, v, t in zip(rows["strike"], iv, rows["t"])], dtype=float)
    gex_raw = gammas * (spot**2) * float(move_frac) * rows["oi"].to_numpy(dtype=float) * float(multiplier)
    gex = _apply_sign(gex_raw, rows["type"].to_numpy(), sign_model)
    tmp = pd.DataFrame({"strike": rows["strike_round"].to_numpy(), "gex": gex})
    g = tmp.groupby("strike", as_index=False)["gex"].sum().sort_values("strike").reset_index(drop=True)
    return g


def _total_gex_for_spot(rows: pd.DataFrame, spot: float, r: float, q: float, multiplier: float, move_frac: float, sign_model: str) -> float:
    g = _gex_by_strike(rows, spot=spot, r=r, q=q, multiplier=multiplier, move_frac=move_frac, sign_model=sign_model)
    return float(g["gex"].sum()) if not g.empty else 0.0


def _find_zero_gamma(rows: pd.DataFrame, r: float, q: float, multiplier: float, move_frac: float, sign_model: str) -> Optional[float]:
    if rows.empty:
        return None
    kmin = float(rows["strike"].min())
    kmax = float(rows["strike"].max())
    if not (math.isfinite(kmin) and math.isfinite(kmax)) or kmax <= kmin:
        return None
    grid = np.linspace(kmin, kmax, 160)
    vals = np.array([_total_gex_for_spot(rows, float(s), r=r, q=q, multiplier=multiplier, move_frac=move_frac, sign_model=sign_model) for s in grid], dtype=float)
    signs = np.sign(vals)
    for i in range(1, len(grid)):
        if signs[i] == 0:
            return float(grid[i])
        if signs[i - 1] == 0:
            return float(grid[i - 1])
        if signs[i] != signs[i - 1]:
            x0, x1 = float(grid[i - 1]), float(grid[i])
            y0, y1 = float(vals[i - 1]), float(vals[i])
            if y1 == y0:
                return x0
            return x0 + (0 - y0) * (x1 - x0) / (y1 - y0)
    return None


def _metrics(rows: pd.DataFrame, spot: float, r: float, q: float, multiplier: float, move_frac: float, sign_model: str) -> Dict:
    g = _gex_by_strike(rows, spot=spot, r=r, q=q, multiplier=multiplier, move_frac=move_frac, sign_model=sign_model)
    if g.empty:
        return {"has_volume": False, "oi": {"zero_gamma": None, "major_positive": None, "major_negative": None, "net_gex": 0.0, "series": {"strike": [], "gex": []}}}
    net = float(g["gex"].sum())
    maj_pos = float(g.loc[g["gex"].idxmax(), "strike"])
    maj_neg = float(g.loc[g["gex"].idxmin(), "strike"])
    zero = _find_zero_gamma(rows, r=r, q=q, multiplier=multiplier, move_frac=move_frac, sign_model=sign_model)
    return {
        "has_volume": False,
        "oi": {"zero_gamma": zero, "major_positive": maj_pos, "major_negative": maj_neg, "net_gex": net, "series": g.to_dict(orient="list")},
    }


@dataclass
class LiveConfig:
    host: str
    port: int
    out_dir: Path
    http_port: int
    sign_model: str
    r: float
    q: float
    multiplier: float
    move_frac: float
    refresh_chain_sec: int
    refresh_calc_sec: float
    strike_band_pct: float
    max_strikes_per_exp: int


class _QuoteStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.quotes: Dict[str, Dict[str, float]] = {}

    def update_from_df(self, df: pd.DataFrame) -> None:
        """
        Expect columns like: code, last_price, bid_price, ask_price, implied_volatility, volume, open_interest ...
        We'll store what we can.
        """
        if df is None or df.empty:
            return
        cols = {c.lower(): c for c in df.columns}
        code_col = cols.get("code") or cols.get("security_code") or cols.get("symbol")
        if not code_col:
            return

        def _col(*names: str) -> Optional[str]:
            for n in names:
                if n in cols:
                    return cols[n]
            return None

        last_c = _col("last_price", "last", "price")
        bid_c = _col("bid_price", "bid")
        ask_c = _col("ask_price", "ask")
        iv_c = _col("implied_volatility", "iv")
        vol_c = _col("volume", "vol")
        oi_c = _col("open_interest", "oi")

        with self._lock:
            for _, row in df.iterrows():
                code = str(row[code_col])
                rec = self.quotes.get(code, {})
                if last_c:
                    rec["last"] = float(row[last_c]) if pd.notna(row[last_c]) else rec.get("last", float("nan"))
                if bid_c:
                    rec["bid"] = float(row[bid_c]) if pd.notna(row[bid_c]) else rec.get("bid", float("nan"))
                if ask_c:
                    rec["ask"] = float(row[ask_c]) if pd.notna(row[ask_c]) else rec.get("ask", float("nan"))
                if iv_c:
                    rec["iv"] = float(row[iv_c]) if pd.notna(row[iv_c]) else rec.get("iv", float("nan"))
                if vol_c:
                    rec["volume"] = float(row[vol_c]) if pd.notna(row[vol_c]) else rec.get("volume", float("nan"))
                if oi_c:
                    rec["oi"] = float(row[oi_c]) if pd.notna(row[oi_c]) else rec.get("oi", float("nan"))
                self.quotes[code] = rec

    def get(self, code: str) -> Dict[str, float]:
        with self._lock:
            return dict(self.quotes.get(code, {}))


def _serve_directory(directory: Path, port: int) -> ThreadingHTTPServer:
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(directory), **kwargs)

        def log_message(self, fmt: str, *args) -> None:
            return

    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd


def _default_underlyings() -> List[str]:
    # Futu symbol format usually like US.AAPL
    return ["US.QQQ", "US.IWM", "US.MSFT", "US.TSLA", "US.GOOG", "US.AAPL", "US.META", "US.AMZN", "US.NVDA", "US.SPX"]


def main() -> int:
    ap = argparse.ArgumentParser(description="Realtime GEX via Futu OpenAPI (FutuOpenD) + local live dashboard.")
    ap.add_argument("--host", default="127.0.0.1", help="FutuOpenD host")
    ap.add_argument("--port", type=int, default=11111, help="FutuOpenD port")
    ap.add_argument("--http-port", type=int, default=8000, help="Local HTTP server port")
    ap.add_argument("--out-dir", default=str(Path(__file__).with_name("gex_live")), help="Output dir (contains index.html and data.json)")
    ap.add_argument("--symbols", default=",".join(_default_underlyings()), help="Comma-separated underlyings (e.g. US.QQQ,US.IWM,US.AAPL)")
    ap.add_argument("--sign-model", default="call_plus_put_minus", choices=("call_plus_put_minus", "dealer_short_all", "no_sign"))
    ap.add_argument("--r", type=float, default=0.0)
    ap.add_argument("--q", type=float, default=0.0)
    ap.add_argument("--multiplier", type=float, default=100.0)
    ap.add_argument("--move-frac", type=float, default=0.01, help="Underlying move fraction, default 1%% = 0.01")
    ap.add_argument("--refresh-chain-sec", type=int, default=60, help="Refresh option chain every N seconds")
    ap.add_argument("--refresh-calc-sec", type=float, default=1.0, help="Recompute/write dashboard every N seconds")
    ap.add_argument("--strike-band-pct", type=float, default=0.10, help="Only keep strikes within +/-pct of spot (e.g. 0.10 = 10%%)")
    ap.add_argument("--max-strikes-per-exp", type=int, default=40, help="Cap strikes per expiration to limit subscriptions")

    args = ap.parse_args()

    cfg = LiveConfig(
        host=args.host,
        port=args.port,
        out_dir=Path(args.out_dir),
        http_port=args.http_port,
        sign_model=args.sign_model,
        r=args.r,
        q=args.q,
        multiplier=args.multiplier,
        move_frac=args.move_frac,
        refresh_chain_sec=args.refresh_chain_sec,
        refresh_calc_sec=args.refresh_calc_sec,
        strike_band_pct=args.strike_band_pct,
        max_strikes_per_exp=args.max_strikes_per_exp,
    )
    cfg.out_dir.mkdir(parents=True, exist_ok=True)
    data_path = cfg.out_dir / "data.json"
    index_path = cfg.out_dir / "index.html"

    # Ensure index.html exists (tracked in repo); if not, guide the user.
    if not index_path.exists():
        raise FileNotFoundError(f"Missing {index_path}. Ensure `crawler-tool/app/scripts/gex_live/index.html` exists.")

    httpd = _serve_directory(cfg.out_dir, cfg.http_port)
    print(f"Live dashboard: http://127.0.0.1:{cfg.http_port}/")

    try:
        from futu import OpenQuoteContext, SubType, StockQuoteHandlerBase
    except Exception as e:
        raise RuntimeError("Missing futu-api. Install: pip install futu-api") from e

    symbols = [s.strip() for s in str(args.symbols).split(",") if s.strip()]
    if not symbols:
        raise ValueError("No symbols provided.")

    store = _QuoteStore()

    class QuoteHandler(StockQuoteHandlerBase):
        def on_recv_rsp(self, rsp_pb):
            ret, df = super().on_recv_rsp(rsp_pb)
            if ret != 0:
                return ret, df
            store.update_from_df(df)
            return ret, df

    quote_ctx = OpenQuoteContext(host=cfg.host, port=cfg.port)
    quote_ctx.set_handler(QuoteHandler())

    # subscribe to underlying quotes
    quote_ctx.subscribe(symbols, [SubType.QUOTE], is_first_push=True)

    # state
    chain_rows: Dict[str, pd.DataFrame] = {}
    option_codes: Dict[str, List[str]] = {}

    def _get_spot(sym: str) -> Optional[float]:
        q = store.get(sym)
        v = q.get("last")
        if v is None or not math.isfinite(v) or v <= 0:
            return None
        return float(v)

    def _fetch_chain(sym: str, asof: date) -> pd.DataFrame:
        """
        Attempt to fetch option chain via Futu API.
        Different SDK versions may have different fields; we normalize later.
        """
        if not hasattr(quote_ctx, "get_option_chain"):
            raise RuntimeError("Your futu-api does not expose get_option_chain(); please upgrade futu-api.")
        start = asof.strftime("%Y-%m-%d")
        end = (asof + timedelta(days=90)).strftime("%Y-%m-%d")
        ret, df = quote_ctx.get_option_chain(sym, start_date=start, end_date=end)
        if ret != 0:
            raise RuntimeError(f"get_option_chain failed for {sym}: {df}")
        return df

    def _normalize_chain(sym: str, df: pd.DataFrame, asof: date, spot: float) -> pd.DataFrame:
        """
        Normalize to columns:
          code, strike, type, exp, dte_days, oi, iv, bid, ask, last, mid
        """
        if df is None or df.empty:
            return pd.DataFrame()
        cols = {c.lower(): c for c in df.columns}

        def _col(*names: str) -> Optional[str]:
            for n in names:
                if n in cols:
                    return cols[n]
            return None

        code_c = _col("code", "option_code", "security_code")
        strike_c = _col("strike_price", "strike", "k")
        type_c = _col("option_type", "type", "call_put", "put_call")
        exp_c = _col("expiration_date", "expiry_date", "expire_date", "expiration", "expiry")
        dte_c = _col("dte", "days_to_expiration", "days_to_expiry")
        oi_c = _col("open_interest", "oi")
        iv_c = _col("implied_volatility", "iv")

        if not code_c or not strike_c or not type_c:
            # Dump columns to help user map/upgrade SDK
            raise RuntimeError(f"Unexpected option chain schema for {sym}. Columns: {list(df.columns)}")

        out = pd.DataFrame()
        out["code"] = df[code_c].astype(str)
        out["strike"] = pd.to_numeric(df[strike_c], errors="coerce")
        out["type"] = df[type_c].apply(_normalize_type)
        if exp_c:
            out["exp"] = df[exp_c].apply(_to_date)
        else:
            out["exp"] = None
        if dte_c:
            out["dte_days"] = pd.to_numeric(df[dte_c], errors="coerce")
        else:
            out["dte_days"] = out["exp"].apply(lambda d: (d - asof).days if d else np.nan)

        out["oi"] = pd.to_numeric(df[oi_c], errors="coerce").fillna(0.0) if oi_c else 0.0
        out["iv"] = pd.to_numeric(df[iv_c], errors="coerce") if iv_c else np.nan

        # merge last known quotes (bid/ask/last/iv/oi)
        bids, asks, lasts, ivs, ois = [], [], [], [], []
        for c in out["code"]:
            q = store.get(c)
            bids.append(q.get("bid", float("nan")))
            asks.append(q.get("ask", float("nan")))
            lasts.append(q.get("last", float("nan")))
            ivs.append(q.get("iv", float("nan")))
            ois.append(q.get("oi", float("nan")))
        out["bid"] = bids
        out["ask"] = asks
        out["last"] = lasts
        # Prefer quote IV if chain IV missing
        out["iv"] = out["iv"].where(np.isfinite(out["iv"]) & (out["iv"] > 0), np.array(ivs, dtype=float))
        # Prefer quote OI if chain OI missing (rare)
        out["oi"] = out["oi"].where(np.isfinite(out["oi"]) & (out["oi"] >= 0), np.array(ois, dtype=float))

        out["mid"] = np.where(np.isfinite(out["bid"]) & np.isfinite(out["ask"]) & (out["bid"] > 0) & (out["ask"] > 0), (out["bid"] + out["ask"]) / 2.0, out["last"])

        out = out.dropna(subset=["strike", "type", "dte_days"])
        out = out[(out["strike"] > 0) & (out["dte_days"] >= 0)]

        # Filter strikes near spot
        lo = float(spot) * (1.0 - float(cfg.strike_band_pct))
        hi = float(spot) * (1.0 + float(cfg.strike_band_pct))
        out = out[(out["strike"] >= lo) & (out["strike"] <= hi)]

        # Cap strikes per expiration (pick closest-to-spot)
        out["strike_dist"] = (out["strike"] - float(spot)).abs()
        out["exp_key"] = out["dte_days"].fillna(999999).astype(int)
        out = out.sort_values(["exp_key", "strike_dist"])
        out = out.groupby("exp_key", as_index=False).head(int(cfg.max_strikes_per_exp))

        out["t"] = out["dte_days"] / 365.0
        out["strike_round"] = out["strike"].round(10)
        out = out[(out["t"] > 0)]
        return out.reset_index(drop=True)

    last_chain_ts = 0.0
    last_calc_ts = 0.0
    asof = date.today()

    while True:
        now = time.time()
        # refresh option chain and subscriptions
        if now - last_chain_ts >= float(cfg.refresh_chain_sec):
            last_chain_ts = now
            for sym in symbols:
                spot = _get_spot(sym)
                if not spot:
                    continue
                try:
                    raw_chain = _fetch_chain(sym, asof=asof)
                    norm = _normalize_chain(sym, raw_chain, asof=asof, spot=float(spot))
                    chain_rows[sym] = norm
                    codes = sorted(set(norm["code"].tolist()))
                    option_codes[sym] = codes
                except Exception as e:
                    print(f"[WARN] chain {sym}: {e}")
                    chain_rows[sym] = pd.DataFrame()
                    option_codes[sym] = []

            # subscribe to option quotes for all symbols (union)
            all_codes = sorted(set(c for codes in option_codes.values() for c in codes))
            if all_codes:
                try:
                    quote_ctx.subscribe(all_codes, [SubType.QUOTE], is_first_push=True)
                except Exception as e:
                    print(f"[WARN] subscribe options: {e}")

        # compute dashboard JSON
        if now - last_calc_ts >= float(cfg.refresh_calc_sec):
            last_calc_ts = now
            payload = {"default_stock": symbols[0] if symbols else None, "stocks": {}}
            ts_str = datetime.now().strftime("%m-%d %H:%M:%S")
            for sym in symbols:
                spot = _get_spot(sym)
                if not spot:
                    continue
                rows = chain_rows.get(sym)
                if rows is None or rows.empty:
                    continue

                # Update IV/OI/mid from latest quotes (fast refresh)
                bids, asks, lasts, ivs, ois = [], [], [], [], []
                for c in rows["code"]:
                    q = store.get(c)
                    bids.append(q.get("bid", float("nan")))
                    asks.append(q.get("ask", float("nan")))
                    lasts.append(q.get("last", float("nan")))
                    ivs.append(q.get("iv", float("nan")))
                    ois.append(q.get("oi", float("nan")))
                rows2 = rows.copy()
                rows2["bid"] = bids
                rows2["ask"] = asks
                rows2["last"] = lasts
                rows2["iv"] = rows2["iv"].where(np.isfinite(rows2["iv"]) & (rows2["iv"] > 0), np.array(ivs, dtype=float))
                rows2["oi"] = rows2["oi"].where(np.isfinite(rows2["oi"]) & (rows2["oi"] >= 0), np.array(ois, dtype=float))
                rows2["mid"] = np.where(np.isfinite(rows2["bid"]) & np.isfinite(rows2["ask"]) & (rows2["bid"] > 0) & (rows2["ask"] > 0), (rows2["bid"] + rows2["ask"]) / 2.0, rows2["last"])

                # windows
                dte = rows2["dte_days"].astype(int)
                windows = {
                    "0DTE": rows2.loc[dte == 0].copy(),
                    "NEXT": rows2.loc[dte == 1].copy(),
                    "90D": rows2.loc[dte <= 90].copy(),
                }
                win_payload = {}
                for key, sub in windows.items():
                    win_payload[key] = {"metrics": _metrics(sub, spot=float(spot), r=cfg.r, q=cfg.q, multiplier=cfg.multiplier, move_frac=cfg.move_frac, sign_model=cfg.sign_model), "count": int(len(sub))}

                payload["stocks"][sym] = {"spot": float(spot), "time": ts_str, "sign_model": cfg.sign_model, "windows": win_payload}

            data_path.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")

        time.sleep(0.05)


if __name__ == "__main__":
    raise SystemExit(main())


