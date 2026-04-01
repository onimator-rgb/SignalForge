"""Portfolio trading rules — entry/exit criteria for demo positions."""

# ── Position sizing ──────────────────────────────
INITIAL_CAPITAL = 1000.00
MAX_POSITION_PCT = 0.20        # max 20% of equity per position
MAX_OPEN_POSITIONS = 5
MIN_CASH_RESERVE_PCT = 0.10    # keep at least 10% cash
MIN_POSITION_USD = 10.00       # minimum viable position

# ── Entry criteria ───────────────────────────────
MIN_SCORE_FOR_ENTRY = 65       # recommendation score threshold
ALLOWED_CONFIDENCE = {"medium", "high"}
BLOCKED_RISK = {"high"}        # don't enter high risk
COOLDOWN_HOURS = 24            # hours after closing before re-entering same asset
DAILY_DRAWDOWN_LIMIT_PCT = 5.0 # halt entries when equity drops >5% intraday

# ── Exit criteria ────────────────────────────────
STOP_LOSS_PCT = -0.08          # -8%
TAKE_PROFIT_PCT = 0.15         # +15%
MAX_HOLD_HOURS = 72            # 3 days max hold
