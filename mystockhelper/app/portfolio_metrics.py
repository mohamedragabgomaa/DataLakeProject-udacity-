from __future__ import annotations

from .config import PORTFOLIO, WATCHLIST


def position_metrics(ticker, current_price, total_value=None):
    pos = PORTFOLIO.get(ticker)
    if not pos or current_price is None:
        return None
    shares = float(pos["shares"])
    avg_cost = float(pos["avg_cost"])
    cost = shares * avg_cost
    value = shares * current_price
    pnl = value - cost
    pnl_pct = (pnl / cost * 100.0) if cost else None
    weight = (value / total_value * 100.0) if total_value else None
    return {
        "shares": shares,
        "avg_cost": avg_cost,
        "cost": cost,
        "value": value,
        "pnl": pnl,
        "pnl_pct": pnl_pct,
        "weight_pct": weight,
    }


def portfolio_totals(prices):
    total_cost = 0.0
    total_value = 0.0
    for ticker in WATCHLIST:
        pos = PORTFOLIO.get(ticker)
        if not pos:
            continue
        shares = float(pos["shares"])
        avg_cost = float(pos["avg_cost"])
        total_cost += shares * avg_cost
        price = prices.get(ticker)
        if price is not None:
            total_value += shares * price
    pnl = total_value - total_cost if total_cost else None
    pnl_pct = (pnl / total_cost * 100.0) if pnl is not None and total_cost else None
    return {
        "total_cost": total_cost,
        "total_value": total_value,
        "pnl": pnl,
        "pnl_pct": pnl_pct,
    }
