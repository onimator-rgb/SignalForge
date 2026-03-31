"""Portfolio service — manages demo positions based on recommendations."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.assets.service import get_latest_price
from app.logging_config import get_logger
from app.portfolio.models import Portfolio, PortfolioPosition, PortfolioTransaction
from app.portfolio.rules import (
    COOLDOWN_HOURS, INITIAL_CAPITAL, MAX_OPEN_POSITIONS,
    MIN_CASH_RESERVE_PCT, MIN_POSITION_USD,
)
from app.recommendations.models import Recommendation
from app.strategy.profiles import get_active_profile
from app.strategy.regime import calculate_regime, get_regime_position_multiplier, get_regime_score_adjustment

log = get_logger(__name__)


async def get_or_create_portfolio(db: AsyncSession) -> Portfolio:
    """Get the default demo portfolio, creating it if needed."""
    result = await db.execute(
        select(Portfolio).where(Portfolio.is_active.is_(True)).limit(1)
    )
    portfolio = result.scalar_one_or_none()
    if not portfolio:
        portfolio = Portfolio(
            name="Demo Portfolio",
            initial_capital=INITIAL_CAPITAL,
            current_cash=INITIAL_CAPITAL,
        )
        db.add(portfolio)
        await db.flush()
        log.info("portfolio.created", id=str(portfolio.id), capital=INITIAL_CAPITAL)
    return portfolio


async def evaluate_portfolio(db: AsyncSession) -> dict:
    """Main portfolio cycle: check exits, then check entries. Returns summary."""
    portfolio = await get_or_create_portfolio(db)
    now = datetime.now(timezone.utc)

    closed = await _check_exits(db, portfolio, now)
    opened = await _check_entries(db, portfolio, now)

    await db.flush()
    portfolio.updated_at = now
    await db.commit()

    if closed or opened:
        log.info("portfolio.evaluate_done", closed=closed, opened=opened,
                 cash=float(portfolio.current_cash))
    return {"closed": closed, "opened": opened}


async def manual_close_position(db: AsyncSession, position_id: uuid.UUID) -> dict:
    """Manually close a demo position at current market price."""
    portfolio = await get_or_create_portfolio(db)
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(PortfolioPosition).where(
            PortfolioPosition.id == position_id,
            PortfolioPosition.portfolio_id == portfolio.id,
            PortfolioPosition.status == "open",
        )
    )
    pos = result.scalar_one_or_none()
    if not pos:
        raise ValueError("Position not found or already closed")

    price_data = await get_latest_price(db, pos.asset_id)
    if not price_data:
        raise ValueError("Cannot get current price for this asset")

    await _close_position(db, portfolio, pos, price_data.close, "manual", now)
    await db.commit()

    log.info("portfolio.manual_close_done", position_id=str(position_id))
    return {"status": "closed", "exit_price": price_data.close}


# ── Exit logic ────────────────────────────────────

async def _check_exits(db: AsyncSession, portfolio: Portfolio, now: datetime) -> int:
    from app.portfolio.exits import evaluate_exit, update_position_state

    profile = get_active_profile()
    regime_data = await calculate_regime(db)
    regime = regime_data["regime"]

    result = await db.execute(
        select(PortfolioPosition).where(
            PortfolioPosition.portfolio_id == portfolio.id,
            PortfolioPosition.status == "open",
        )
    )
    positions = list(result.scalars().all())
    closed = 0

    for pos in positions:
        price_data = await get_latest_price(db, pos.asset_id)
        if not price_data:
            continue

        current_price = price_data.close

        # Update position state (peak, trailing, break-even)
        update_position_state(pos, current_price, profile, regime)

        # Get current recommendation for signal deterioration check
        rec_res = await db.execute(
            select(Recommendation.score, Recommendation.recommendation_type)
            .where(Recommendation.asset_id == pos.asset_id, Recommendation.status == "active")
            .limit(1)
        )
        rec_row = rec_res.one_or_none()
        rec_score = float(rec_row.score) if rec_row else None
        rec_type = rec_row.recommendation_type if rec_row else None

        # Evaluate exit rules
        reason, exit_ctx = evaluate_exit(
            pos, current_price, profile, regime,
            rec_score=rec_score, rec_type=rec_type, now=now,
        )

        if reason:
            pos.exit_context = exit_ctx
            await _close_position(db, portfolio, pos, current_price, reason, now)
            closed += 1

        await db.flush()

    return closed


async def _close_position(
    db: AsyncSession, portfolio: Portfolio, pos: PortfolioPosition,
    exit_price: float, reason: str, now: datetime,
) -> None:
    qty = float(pos.quantity)
    exit_value = round(exit_price * qty, 2)
    entry_value = float(pos.entry_value_usd)
    pnl_usd = round(exit_value - entry_value, 2)
    pnl_pct = round((exit_price - float(pos.entry_price)) / float(pos.entry_price) * 100, 4)

    pos.exit_price = exit_price
    pos.exit_value_usd = exit_value
    pos.closed_at = now
    pos.close_reason = reason
    pos.realized_pnl_usd = pnl_usd
    pos.realized_pnl_pct = pnl_pct
    pos.status = "closed"

    portfolio.current_cash = float(portfolio.current_cash) + exit_value

    tx = PortfolioTransaction(
        portfolio_id=portfolio.id,
        position_id=pos.id,
        tx_type="sell",
        asset_id=pos.asset_id,
        price=exit_price,
        quantity=qty,
        value_usd=exit_value,
        executed_at=now,
    )
    db.add(tx)

    asset_res = await db.execute(select(Asset.symbol).where(Asset.id == pos.asset_id))
    symbol = asset_res.scalar_one_or_none() or "?"
    log.info(
        "portfolio.position_closed",
        symbol=symbol, reason=reason,
        entry=float(pos.entry_price), exit=exit_price,
        pnl_usd=pnl_usd, pnl_pct=pnl_pct,
    )


# ── Entry logic ───────────────────────────────────

async def _check_entries(db: AsyncSession, portfolio: Portfolio, now: datetime) -> int:
    from app.portfolio.models import EntryDecision
    from app.portfolio.trailing_buy import start_trailing, update_trailing

    # Load strategy profile + regime
    profile = get_active_profile()
    regime_data = await calculate_regime(db)
    regime = regime_data["regime"]
    score_adj = get_regime_score_adjustment(regime)
    pos_mult = get_regime_position_multiplier(regime)

    effective_threshold = profile.candidate_buy_threshold - score_adj
    effective_position_pct = profile.max_position_pct * pos_mult
    allowed_confidence = {"medium", "high"} if profile.min_confidence == "medium" else {"high"}
    blocked_risk = set() if profile.allow_high_risk else {"high"}

    log.debug("portfolio.profile_applied",
              profile=profile.name, regime=regime,
              threshold=effective_threshold, position_pct=round(effective_position_pct, 3))

    open_count_res = await db.execute(
        select(func.count()).where(
            PortfolioPosition.portfolio_id == portfolio.id,
            PortfolioPosition.status == "open",
        )
    )
    open_count = open_count_res.scalar_one()
    if open_count >= MAX_OPEN_POSITIONS:
        return 0

    open_assets_res = await db.execute(
        select(PortfolioPosition.asset_id).where(
            PortfolioPosition.portfolio_id == portfolio.id,
            PortfolioPosition.status == "open",
        )
    )
    open_asset_ids = set(r[0] for r in open_assets_res.all())

    cooldown_since = now - timedelta(hours=COOLDOWN_HOURS)
    cooldown_res = await db.execute(
        select(PortfolioPosition.asset_id).where(
            PortfolioPosition.portfolio_id == portfolio.id,
            PortfolioPosition.status == "closed",
            PortfolioPosition.closed_at >= cooldown_since,
        )
    )
    cooldown_asset_ids = set(r[0] for r in cooldown_res.all())
    blocked_ids = open_asset_ids | cooldown_asset_ids

    # ── Phase 0: Process pending trailing buys ────────────
    ready_to_buy: list[tuple[uuid.UUID, uuid.UUID]] = []  # (asset_id, recommendation_id)
    pending_trail_asset_ids: set[uuid.UUID] = set()

    pending_trails_res = await db.execute(
        select(EntryDecision).where(
            EntryDecision.stage == "trailing_buy",
            EntryDecision.status == "pending",
        )
    )
    pending_trails = list(pending_trails_res.scalars().all())

    for trail in pending_trails:
        pending_trail_asset_ids.add(trail.asset_id)
        price_data = await get_latest_price(db, trail.asset_id)
        if not price_data:
            continue

        if not trail.context_data or not trail.recommendation_id:
            continue

        action, updated_ctx = update_trailing(trail.context_data, price_data.close, now)

        if action == "buy":
            trail.status = "allowed"
            trail.reason_text = f"trailing_buy_triggered at {price_data.close}"
            trail.context_data = updated_ctx
            ready_to_buy.append((trail.asset_id, trail.recommendation_id))
            log.info("portfolio.trailing_buy_triggered",
                     asset_id=str(trail.asset_id), price=price_data.close,
                     lowest=updated_ctx["lowest_price"])
        elif action == "expired":
            trail.status = "blocked"
            trail.reason_codes = ["trail_expired"]
            trail.reason_text = "Trailing buy expired without bounce"
            trail.context_data = updated_ctx
            log.info("portfolio.trailing_buy_expired", asset_id=str(trail.asset_id))
        else:
            # continue trailing — update lowest_price
            trail.context_data = updated_ctx

        await db.flush()

    recs_res = await db.execute(
        select(Recommendation)
        .where(
            Recommendation.status == "active",
            Recommendation.recommendation_type == "candidate_buy",
            Recommendation.score >= effective_threshold,
            Recommendation.confidence.in_(allowed_confidence),
            ~Recommendation.risk_level.in_(blocked_risk) if blocked_risk else True,
        )
        .order_by(Recommendation.score.desc())
    )
    candidates = list(recs_res.scalars().all())

    opened = 0
    equity = await _compute_equity(db, portfolio)

    from app.portfolio.protections import check_protections

    # Phase 1: Filter candidates through protections + confirmations
    from app.portfolio.confirmations import check_confirmations
    from app.portfolio.ranking import compute_ranking
    from app.indicators.service import get_indicators
    from app.recommendations.service import _get_volume_context

    viable = []  # [(rec, asset_class, symbol, price_data, ranking)]

    for rec in candidates:
        if rec.asset_id in blocked_ids:
            continue

        # Skip assets that already have a pending trailing buy
        if rec.asset_id in pending_trail_asset_ids:
            continue

        asset_info = await db.execute(
            select(Asset.asset_class, Asset.symbol).where(Asset.id == rec.asset_id)
        )
        row = asset_info.one_or_none()
        if not row:
            continue
        ac, sym = row.asset_class, row.symbol

        # Protections
        allowed, prot_type, prot_reason = await check_protections(
            db, portfolio.id, rec.asset_id, ac, regime, now
        )
        if not allowed:
            await _record_decision(db, rec, ac, "blocked", "protections",
                                   [prot_type], prot_reason, {}, regime, profile.name, now)
            continue

        # Confirmations
        ind = await get_indicators(db, rec.asset_id, sym, interval="1h")
        price_data = await get_latest_price(db, rec.asset_id)
        change_24h = price_data.change_24h_pct if price_data else None
        avg_vol, latest_vol = await _get_volume_context(db, rec.asset_id, "1h")

        conf = check_confirmations(
            indicators=ind, change_24h_pct=change_24h,
            avg_volume=avg_vol, latest_volume=latest_vol,
            rec_generated_at=rec.generated_at, asset_class=ac,
            regime=regime, now=now,
        )
        if not conf["allowed"]:
            await _record_decision(db, rec, ac, "blocked", "confirmations",
                                   conf["reason_codes"], conf["reason_text"],
                                   conf["context"], regime, profile.name, now)
            continue

        # Compute ranking
        from app.anomalies.models import AnomalyEvent
        anom_cnt = (await db.execute(
            select(func.count()).where(AnomalyEvent.asset_id == rec.asset_id, AnomalyEvent.is_resolved.is_(False))
        )).scalar_one()
        signal_age = (now - rec.generated_at).total_seconds() / 3600

        ranking = compute_ranking(
            rec_score=float(rec.score), confidence=rec.confidence,
            risk_level=rec.risk_level, asset_class=ac, regime=regime,
            signal_age_hours=signal_age, anomaly_count=anom_cnt,
            indicators=ind, change_24h_pct=change_24h,
        )

        if ranking["allocation_multiplier"] <= 0:
            await _record_decision(db, rec, ac, "blocked", "ranking",
                                   ["rank_too_low"], f"Ranking {ranking['ranking_score']:.0f} below entry tier",
                                   ranking, regime, profile.name, now)
            continue

        viable.append((rec, ac, sym, price_data, ranking))

    # Phase 1b: Create trailing buy entries for new viable candidates
    for rec, ac, sym, price_data, ranking in viable:
        if not price_data:
            continue

        current_price = price_data.close
        trail_ctx = start_trailing(
            current_price, profile.trailing_buy_bounce_pct,
            profile.trailing_buy_max_hours, now,
        )

        decision = EntryDecision(
            asset_id=rec.asset_id,
            recommendation_id=rec.id,
            status="pending",
            stage="trailing_buy",
            reason_codes=["trailing_buy_started"],
            reason_text=f"Trailing buy started at {current_price}",
            context_data=trail_ctx,
            regime=regime,
            profile=profile.name,
        )
        db.add(decision)
        pending_trail_asset_ids.add(rec.asset_id)

        log.info("portfolio.trailing_buy_started",
                 symbol=sym, price=current_price,
                 bounce_pct=profile.trailing_buy_bounce_pct,
                 max_hours=profile.trailing_buy_max_hours)

    await db.flush()

    # Phase 2: Process ready_to_buy from trailing buys that triggered
    slots_available = MAX_OPEN_POSITIONS - open_count

    for asset_id, recommendation_id in ready_to_buy:
        if opened >= slots_available:
            break

        # Load the recommendation for this trailing buy
        rec_res = await db.execute(
            select(Recommendation).where(Recommendation.id == recommendation_id)
        )
        trail_rec = rec_res.scalar_one_or_none()
        if not trail_rec:
            continue

        if asset_id in blocked_ids:
            continue

        reserve = float(portfolio.initial_capital) * MIN_CASH_RESERVE_PCT
        available = float(portfolio.current_cash) - reserve
        if available < MIN_POSITION_USD:
            break

        price_data = await get_latest_price(db, asset_id)
        if not price_data:
            continue

        price = price_data.close

        max_size = equity * effective_position_pct
        size_usd = min(max_size, available)
        if size_usd < MIN_POSITION_USD:
            break

        quantity = size_usd / price

        pos = PortfolioPosition(
            portfolio_id=portfolio.id,
            asset_id=asset_id,
            recommendation_id=recommendation_id,
            entry_price=price,
            quantity=quantity,
            entry_value_usd=round(size_usd, 2),
            opened_at=now,
            stop_loss_price=round(price * (1 + profile.stop_loss_pct), 8),
            take_profit_price=round(price * (1 + profile.take_profit_pct), 8),
            max_hold_until=now + timedelta(hours=profile.max_hold_hours),
        )
        db.add(pos)
        await db.flush()

        tx = PortfolioTransaction(
            portfolio_id=portfolio.id,
            position_id=pos.id,
            tx_type="buy",
            asset_id=asset_id,
            price=price,
            quantity=quantity,
            value_usd=round(size_usd, 2),
            executed_at=now,
        )
        db.add(tx)

        portfolio.current_cash = float(portfolio.current_cash) - round(size_usd, 2)
        blocked_ids.add(asset_id)
        opened += 1

        asset_res = await db.execute(select(Asset.symbol).where(Asset.id == asset_id))
        symbol = asset_res.scalar_one_or_none() or "?"
        log.info(
            "portfolio.position_opened",
            symbol=symbol, price=price,
            quantity=round(quantity, 8), value_usd=round(size_usd, 2),
            score=float(trail_rec.score), entry_type="trailing_buy",
        )

    return opened


# ── Query helpers ─────────────────────────────────

async def _record_decision(
    db: AsyncSession, rec, asset_class: str,
    status: str, stage: str, reason_codes: list, reason_text: str,
    context: dict, regime: str, profile_name: str, now: datetime,
) -> None:
    """Record entry decision for diagnostics."""
    from app.portfolio.models import EntryDecision
    decision = EntryDecision(
        asset_id=rec.asset_id,
        recommendation_id=rec.id,
        status=status,
        stage=stage,
        reason_codes=reason_codes,
        reason_text=reason_text,
        context_data=context,
        regime=regime,
        profile=profile_name,
    )
    db.add(decision)
    await db.flush()


async def _compute_equity(db: AsyncSession, portfolio: Portfolio) -> float:
    result = await db.execute(
        select(PortfolioPosition).where(
            PortfolioPosition.portfolio_id == portfolio.id,
            PortfolioPosition.status == "open",
        )
    )
    positions = list(result.scalars().all())
    positions_value = 0.0
    for pos in positions:
        price_data = await get_latest_price(db, pos.asset_id)
        if price_data:
            positions_value += price_data.close * float(pos.quantity)
        else:
            positions_value += float(pos.entry_value_usd)
    return float(portfolio.current_cash) + positions_value


def _position_badges(pnl_pct: float, dist_stop_pct: float, dist_target_pct: float, hours_remaining: float) -> list[str]:
    """Compute state badges for an open position."""
    badges = []
    if pnl_pct > 0:
        badges.append("in_profit")
    elif pnl_pct < -1:
        badges.append("in_loss")
    if dist_stop_pct < 2:
        badges.append("near_stop")
    if dist_target_pct < 3:
        badges.append("near_target")
    if 0 < hours_remaining < 12:
        badges.append("expiring_soon")
    return badges


async def get_portfolio_summary(db: AsyncSession) -> dict:
    """Build full portfolio summary with rich position data."""
    portfolio = await get_or_create_portfolio(db)
    now = datetime.now(timezone.utc)

    # Open positions with current prices + recommendation data
    open_res = await db.execute(
        select(PortfolioPosition, Asset.symbol, Asset.asset_class,
               Recommendation.score.label("rec_score"),
               Recommendation.recommendation_type.label("rec_type"),
               Recommendation.rationale_summary.label("rec_rationale"),
               Recommendation.scoring_version.label("rec_version"))
        .join(Asset, PortfolioPosition.asset_id == Asset.id)
        .outerjoin(Recommendation, PortfolioPosition.recommendation_id == Recommendation.id)
        .where(
            PortfolioPosition.portfolio_id == portfolio.id,
            PortfolioPosition.status == "open",
        )
        .order_by(PortfolioPosition.opened_at.desc())
    )
    open_positions = []
    positions_value = 0.0
    for row in open_res.all():
        pos = row.PortfolioPosition
        price_data = await get_latest_price(db, pos.asset_id)
        current_price = price_data.close if price_data else float(pos.entry_price)
        current_value = current_price * float(pos.quantity)
        entry_price = float(pos.entry_price)
        unrealized_pnl = round(current_value - float(pos.entry_value_usd), 2)
        unrealized_pct = round((current_price / entry_price - 1) * 100, 4) if entry_price > 0 else 0
        positions_value += current_value

        # Timing
        hours_open = round((now - pos.opened_at).total_seconds() / 3600, 1)
        hours_remaining = round((pos.max_hold_until - now).total_seconds() / 3600, 1) if pos.max_hold_until else 0

        # Distances
        stop_price = float(pos.stop_loss_price) if pos.stop_loss_price else 0
        target_price = float(pos.take_profit_price) if pos.take_profit_price else 0
        dist_stop_pct = round(abs((current_price - stop_price) / entry_price * 100), 2) if entry_price > 0 else 99
        dist_target_pct = round(abs((target_price - current_price) / entry_price * 100), 2) if entry_price > 0 else 99

        badges = _position_badges(unrealized_pct, dist_stop_pct, dist_target_pct, hours_remaining)

        open_positions.append({
            "id": pos.id, "asset_id": pos.asset_id, "asset_symbol": row.symbol,
            "asset_class": row.asset_class,
            "entry_price": entry_price, "quantity": float(pos.quantity),
            "entry_value_usd": float(pos.entry_value_usd), "opened_at": pos.opened_at,
            "current_price": current_price, "current_value_usd": round(current_value, 2),
            "unrealized_pnl_usd": unrealized_pnl, "unrealized_pnl_pct": unrealized_pct,
            "stop_loss_price": stop_price, "take_profit_price": target_price,
            "dist_stop_pct": dist_stop_pct, "dist_target_pct": dist_target_pct,
            "max_hold_until": pos.max_hold_until,
            "hours_open": hours_open, "hours_remaining": hours_remaining,
            "peak_price": float(pos.peak_price) if pos.peak_price else None,
            "peak_pnl_pct": float(pos.peak_pnl_pct) if pos.peak_pnl_pct else None,
            "trailing_stop_price": float(pos.trailing_stop_price) if pos.trailing_stop_price else None,
            "break_even_armed": pos.break_even_armed,
            "badges": badges, "status": pos.status,
            "recommendation": {
                "id": str(pos.recommendation_id) if pos.recommendation_id else None,
                "score": float(row.rec_score) if row.rec_score else None,
                "type": row.rec_type,
                "rationale": row.rec_rationale,
                "scoring_version": row.rec_version,
            } if pos.recommendation_id else None,
        })

    # Closed positions
    closed_res = await db.execute(
        select(PortfolioPosition, Asset.symbol, Asset.asset_class,
               Recommendation.score.label("rec_score"),
               Recommendation.recommendation_type.label("rec_type"))
        .join(Asset, PortfolioPosition.asset_id == Asset.id)
        .outerjoin(Recommendation, PortfolioPosition.recommendation_id == Recommendation.id)
        .where(
            PortfolioPosition.portfolio_id == portfolio.id,
            PortfolioPosition.status == "closed",
        )
        .order_by(PortfolioPosition.closed_at.desc())
        .limit(20)
    )
    closed_positions = []
    for row in closed_res.all():
        pos = row.PortfolioPosition
        hold_hours = round((pos.closed_at - pos.opened_at).total_seconds() / 3600, 1) if pos.closed_at else None
        closed_positions.append({
            "id": pos.id, "asset_id": pos.asset_id, "asset_symbol": row.symbol,
            "asset_class": row.asset_class,
            "entry_price": float(pos.entry_price),
            "exit_price": float(pos.exit_price) if pos.exit_price else None,
            "entry_value_usd": float(pos.entry_value_usd),
            "exit_value_usd": float(pos.exit_value_usd) if pos.exit_value_usd else None,
            "realized_pnl_usd": float(pos.realized_pnl_usd) if pos.realized_pnl_usd else None,
            "realized_pnl_pct": float(pos.realized_pnl_pct) if pos.realized_pnl_pct else None,
            "opened_at": pos.opened_at, "closed_at": pos.closed_at,
            "hold_hours": hold_hours, "close_reason": pos.close_reason,
            "exit_context": pos.exit_context,
            "status": pos.status,
            "rec_score": float(row.rec_score) if row.rec_score else None,
            "rec_type": row.rec_type,
        })

    # Transactions
    tx_res = await db.execute(
        select(PortfolioTransaction, Asset.symbol)
        .join(Asset, PortfolioTransaction.asset_id == Asset.id)
        .where(PortfolioTransaction.portfolio_id == portfolio.id)
        .order_by(PortfolioTransaction.executed_at.desc())
        .limit(20)
    )
    transactions = [
        {
            "id": row.PortfolioTransaction.id, "tx_type": row.PortfolioTransaction.tx_type,
            "asset_id": row.PortfolioTransaction.asset_id, "asset_symbol": row.symbol,
            "price": float(row.PortfolioTransaction.price),
            "quantity": float(row.PortfolioTransaction.quantity),
            "value_usd": float(row.PortfolioTransaction.value_usd),
            "executed_at": row.PortfolioTransaction.executed_at,
        }
        for row in tx_res.all()
    ]

    # Stats
    cash = float(portfolio.current_cash)
    equity = cash + positions_value
    unrealized_total = sum(p["unrealized_pnl_usd"] for p in open_positions)
    total_return_pct = round((equity / float(portfolio.initial_capital) - 1) * 100, 2)

    all_closed_res = await db.execute(
        select(PortfolioPosition).where(
            PortfolioPosition.portfolio_id == portfolio.id,
            PortfolioPosition.status == "closed",
        )
    )
    all_closed = list(all_closed_res.scalars().all())
    wins = [p for p in all_closed if p.realized_pnl_usd and float(p.realized_pnl_usd) > 0]
    pnl_pcts = [float(p.realized_pnl_pct) for p in all_closed if p.realized_pnl_pct is not None]
    total_realized = sum(float(p.realized_pnl_usd) for p in all_closed if p.realized_pnl_usd)

    return {
        "stats": {
            "initial_capital": float(portfolio.initial_capital),
            "current_cash": cash,
            "equity": round(equity, 2),
            "unrealized_pnl": round(unrealized_total, 2),
            "total_return_pct": total_return_pct,
            "open_positions": len(open_positions),
            "closed_positions": len(all_closed),
            "total_trades": len(all_closed) + len(open_positions),
            "win_rate": round(len(wins) / len(all_closed) * 100, 1) if all_closed else None,
            "avg_return_pct": round(sum(pnl_pcts) / len(pnl_pcts), 2) if pnl_pcts else None,
            "best_trade_pct": round(max(pnl_pcts), 2) if pnl_pcts else None,
            "worst_trade_pct": round(min(pnl_pcts), 2) if pnl_pcts else None,
            "total_realized_pnl": round(total_realized, 2),
        },
        "open_positions": open_positions,
        "recent_closed": closed_positions,
        "recent_transactions": transactions,
    }
