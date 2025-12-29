"""
GEX (Gamma Exposure) tool

Purpose:
- Compute GEX aggregated by strike from an option chain (CSV/Excel)
- Report the strike with max positive GEX and max negative GEX

One common definition (default uses a 1% underlying move):
    gamma = N'(d1) / (S * iv * sqrt(T))
    GEX_1% = gamma * S^2 * move_frac * OI * multiplier

Sign is convention-dependent; this tool supports:
  - call_plus_put_minus: calls positive, puts negative (common public approximation)
  - dealer_short_all: assume dealers are net short all options => all negative
  - no_sign: absolute value only (strength)
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import pandas as pd


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def bs_gamma(spot: float, strike: float, iv: float, t: float, r: float = 0.0, q: float = 0.0) -> float:
    """
    Black-Scholes gamma (per 1 underlying unit), for European options.
    """
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
        # Try common formats
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%d/%m/%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                pass
        # Last resort: pandas parser
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
    # Some feeds use 1/-1
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
    dte = _pick_first_existing(df, ("dte", "days_to_exp", "days_to_expiration", "ttm_days", "剩余天数"))
    expiration = _pick_first_existing(df, ("expiration", "expiry", "exp", "maturity", "到期日"))

    missing = [name for name, col in [("strike", strike), ("type", opt_type), ("iv", iv), ("oi", oi)] if col is None]
    if missing:
        raise ValueError(
            "Cannot infer required columns: "
            + ", ".join(missing)
            + ". Please specify explicitly, e.g. --col-strike STRIKE --col-type TYPE --col-iv IV --col-oi OI"
        )

    if dte is None and expiration is None:
        raise ValueError("Need either DTE or expiration date column: provide --col-dte or --col-expiration (or let the tool infer).")

    return Columns(strike=strike, opt_type=opt_type, iv=iv, oi=oi, dte=dte, expiration=expiration)


def compute_gex_by_strike(
    df: pd.DataFrame,
    spot: float,
    asof: date,
    cols: Columns,
    r: float,
    q: float,
    multiplier: float,
    move_frac: float,
    sign_model: str,
) -> pd.DataFrame:
    out = df.copy()

    out["_strike"] = pd.to_numeric(out[cols.strike], errors="coerce")
    out["_iv"] = pd.to_numeric(out[cols.iv], errors="coerce")
    out["_oi"] = pd.to_numeric(out[cols.oi], errors="coerce").fillna(0.0)
    out["_type"] = out[cols.opt_type].apply(_normalize_type)

    if cols.dte:
        out["_t"] = pd.to_numeric(out[cols.dte], errors="coerce") / 365.0
    else:
        exp_dates = out[cols.expiration].apply(_to_date)
        out["_t"] = exp_dates.apply(lambda d: ((d - asof).days / 365.0) if d else np.nan)

    # clean
    out = out.dropna(subset=["_strike", "_iv", "_t", "_type"])
    out = out[(out["_strike"] > 0) & (out["_iv"] > 0) & (out["_t"] > 0)]

    def _row_gamma(row) -> float:
        return bs_gamma(float(spot), float(row["_strike"]), float(row["_iv"]), float(row["_t"]), r=r, q=q)

    out["_gamma"] = out.apply(_row_gamma, axis=1)
    out["_gex_raw"] = out["_gamma"] * (spot**2) * float(move_frac) * out["_oi"] * float(multiplier)

    if sign_model == "call_plus_put_minus":
        out["_gex"] = np.where(out["_type"] == "call", out["_gex_raw"], -out["_gex_raw"])
    elif sign_model == "dealer_short_all":
        out["_gex"] = -np.abs(out["_gex_raw"])
    elif sign_model == "no_sign":
        out["_gex"] = np.abs(out["_gex_raw"])
    else:
        raise ValueError(f"未知 sign_model: {sign_model}")

    out["_strike_round"] = out["_strike"].round(10)
    g = out.groupby("_strike_round", as_index=False)["_gex"].sum().rename(columns={"_strike_round": "strike", "_gex": "gex"})

    # For visibility: also show call/put split under call_plus_put_minus (even if user selected another model)
    call_mask = out["_type"] == "call"
    put_mask = out["_type"] == "put"
    call_split = out.loc[call_mask].groupby("_strike_round")["_gex_raw"].sum()
    put_split = out.loc[put_mask].groupby("_strike_round")["_gex_raw"].sum()
    g["call_gex_raw"] = g["strike"].map(call_split).fillna(0.0)
    g["put_gex_raw"] = g["strike"].map(put_split).fillna(0.0)

    g = g.sort_values("strike").reset_index(drop=True)
    return g


def _read_chain(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(str(path))
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    return pd.read_csv(path)


def main() -> int:
    ap = argparse.ArgumentParser(description="GEX tool: aggregate by strike and find max positive/negative GEX")
    ap.add_argument("--file", required=True, help="Option chain file path (CSV or Excel)")
    ap.add_argument("--spot", required=True, type=float, help="Underlying spot price S")
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
    ap.add_argument("--top", type=int, default=10, help="Print top N positive/negative strikes")
    ap.add_argument("--out", default=None, help="Optional: write aggregated results to CSV")

    # Column overrides
    ap.add_argument("--col-strike", default=None, help="Column name for strike")
    ap.add_argument("--col-type", default=None, help="Column name for option type (C/P or call/put)")
    ap.add_argument("--col-iv", default=None, help="Column name for implied vol (annualized decimal, e.g. 0.25)")
    ap.add_argument("--col-oi", default=None, help="Column name for open interest (OI)")
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
            dte=args.col_dte,
            expiration=args.col_expiration,
        )
        if cols.dte is None and cols.expiration is None:
            cols = Columns(
                strike=cols.strike,
                opt_type=cols.opt_type,
                iv=cols.iv,
                oi=cols.oi,
                dte=infer_columns(df).dte,
                expiration=infer_columns(df).expiration,
            )
    else:
        cols = infer_columns(df)

    g = compute_gex_by_strike(
        df=df,
        spot=args.spot,
        asof=asof,
        cols=cols,
        r=args.r,
        q=args.q,
        multiplier=args.multiplier,
        move_frac=args.move_frac,
        sign_model=args.sign_model,
    )

    if g.empty:
        print("No usable rows. Check IV/T (DTE/expiration), type values, and column mapping; IV and T must be > 0.")
        return 2

    max_pos = g.loc[g["gex"].idxmax()]
    max_neg = g.loc[g["gex"].idxmin()]

    print(f"asof={asof} spot={args.spot} r={args.r} q={args.q} move_frac={args.move_frac} multiplier={args.multiplier}")
    print(f"sign_model={args.sign_model}")
    print()
    print(f"Max positive GEX: strike={max_pos['strike']}  gex={max_pos['gex']:.6g}")
    print(f"Max negative GEX: strike={max_neg['strike']}  gex={max_neg['gex']:.6g}")
    print()

    topn = max(1, int(args.top))
    pos = g.sort_values("gex", ascending=False).head(topn)
    neg = g.sort_values("gex", ascending=True).head(topn)

    pd.set_option("display.width", 160)
    pd.set_option("display.max_columns", 50)
    print(f"Top {topn} positive GEX (by strike):")
    print(pos[["strike", "gex", "call_gex_raw", "put_gex_raw"]].to_string(index=False))
    print()
    print(f"Top {topn} negative GEX (by strike):")
    print(neg[["strike", "gex", "call_gex_raw", "put_gex_raw"]].to_string(index=False))

    if args.out:
        out_path = Path(args.out)
        g.to_csv(out_path, index=False, encoding="utf-8-sig")
        print()
        print(f"Wrote: {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


