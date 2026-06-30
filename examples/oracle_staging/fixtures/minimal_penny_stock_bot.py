from __future__ import annotations


WATCHLIST = ["TESTA", "TESTB"]
AI_COUNCIL_OUTBOX_DIR = "ai_council_outbox"


def analyze_signals(ticker):
    """Fixture-only signal analyzer. This does not call a broker API."""
    if ticker != "TESTA":
        return None
    return {
        "signals": ["RSI_DIP", "VOLUME_EXPLOSION"],
        "is_combo": True,
        "current_price": 0.82,
        "rsi": 68,
        "volume_ratio": 5.2,
        "gap_pct": 7.1,
        "recent_momentum_pct": 0.018,
        "signal_score": 3.1,
        "vwap": 0.8,
        "breakout_ok": True,
    }


def calc_position_size(cash_usd, is_combo, current_price, signal_score=0.0):
    return 100


def place_order(cfg, token, base_url, ticker, side, qty, price):
    """Unsafe insertion point fixture. Do not add export hooks inside this function."""
    return False, "fixture_no_order_execution"


def check_exits(positions, cfg, token, base_url, today_trades, today_pnl_usd, cooldown=None):
    """Unsafe insertion point fixture. No order logic is executed here."""
    return positions, today_trades, today_pnl_usd


def force_close_all(positions, cfg, token, base_url, today_trades, today_pnl_usd, cooldown=None):
    """Unsafe insertion point fixture. No order logic is executed here."""
    return positions, today_trades, today_pnl_usd


def scan_and_enter(positions, cfg, token, base_url, cash_usd, today_trades, today_pnl_usd, cooldown=None):
    """Fixture scan loop with a safe candidate hook point before the order function."""
    combo_signals = []
    single_signals = []

    for ticker in WATCHLIST:
        result = analyze_signals(ticker)
        if result:
            entry = {"ticker": ticker, **result}
            # Safe insertion candidate: export the entry to an outbox here.
            if result["is_combo"]:
                combo_signals.append(entry)
            else:
                single_signals.append(entry)

    candidates = combo_signals + single_signals
    for candidate in candidates:
        ticker = candidate["ticker"]
        current_price = candidate["current_price"]
        signals = candidate["signals"]
        signal_score = candidate.get("signal_score", 0.0)
        qty = calc_position_size(cash_usd, candidate["is_combo"], current_price, signal_score)
        if qty <= 0:
            continue
        signal_label = "+".join(signals)
        buy_price = current_price * 1.005
        # Unsafe boundary: export hooks must stay before this call.
        ok, result_msg = place_order(cfg, token, base_url, ticker, "BUY", qty, buy_price)
        if ok:
            positions[ticker] = {
                "qty": qty,
                "avg_price": current_price,
                "signal_type": signal_label,
                "signal_score": signal_score,
            }
    return positions, today_trades, today_pnl_usd
