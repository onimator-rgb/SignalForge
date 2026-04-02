"""Tests for the portfolio report generator."""

from __future__ import annotations

import pytest

from app.ai_assistant.portfolio_report import (
    PositionSummary,
    RiskSnapshot,
    TradeSummary,
    generate_portfolio_report,
)


def _make_risk(**overrides: object) -> RiskSnapshot:
    defaults: dict[str, object] = dict(
        sharpe_ratio=1.5,
        sortino_ratio=1.8,
        max_drawdown_pct=10.0,
        profit_factor=1.6,
        win_rate=60.0,
        total_closed=10,
        wins=6,
        losses=4,
        avg_hold_hours=24.0,
        best_trade_pct=5.0,
        worst_trade_pct=-3.0,
    )
    defaults.update(overrides)
    return RiskSnapshot(**defaults)  # type: ignore[arg-type]


def _make_positions() -> list[PositionSummary]:
    return [
        PositionSummary("AAPL", 150.0, 160.0, 10, 6.67, "open"),
        PositionSummary("MSFT", 300.0, 310.0, 5, 3.33, "open"),
        PositionSummary("TSLA", 200.0, None, 8, None, "closed", "stop_loss", -5.0),
        PositionSummary("GOOG", 100.0, None, 12, None, "closed", "take_profit", 10.0),
        PositionSummary("AMZN", 120.0, None, 6, None, "closed", "take_profit", 7.5),
    ]


def _make_trades(n: int = 3) -> list[TradeSummary]:
    base = [
        TradeSummary("AAPL", "buy", 150.0, 10, 1500.0),
        TradeSummary("MSFT", "buy", 300.0, 5, 1500.0),
        TradeSummary("TSLA", "sell", 190.0, 8, 1520.0),
        TradeSummary("GOOG", "sell", 110.0, 12, 1320.0),
        TradeSummary("AMZN", "sell", 129.0, 6, 774.0),
        TradeSummary("META", "buy", 400.0, 3, 1200.0),
        TradeSummary("NFLX", "buy", 500.0, 2, 1000.0),
    ]
    return base[:n]


class TestAllSectionsPresent:
    def test_typical_portfolio_has_all_sections(self) -> None:
        report = generate_portfolio_report(
            positions=_make_positions(),
            risk=_make_risk(),
            recent_trades=_make_trades(),
            regime="bullish",
            current_cash=5000.0,
            initial_capital=10000.0,
        )
        assert report  # non-empty
        for header in [
            "PORTFOLIO SUMMARY",
            "OPEN POSITIONS",
            "RISK ASSESSMENT",
            "RECENT ACTIVITY",
            "REGIME COMMENTARY",
        ]:
            assert header in report


class TestPortfolioSummary:
    def test_numeric_formatting(self) -> None:
        report = generate_portfolio_report(
            positions=_make_positions(),
            risk=_make_risk(),
            recent_trades=[],
            regime="neutral",
            current_cash=5000.0,
            initial_capital=10000.0,
        )
        # total value = 5000 + (160*10 + 310*5) = 5000 + 3150 = 8150
        # total return = (8150 - 10000) / 10000 * 100 = -18.50%
        assert "-18.50%" in report
        assert "$5000.00" in report


class TestEmptyPositions:
    def test_no_positions(self) -> None:
        report = generate_portfolio_report(
            positions=[],
            risk=_make_risk(),
            recent_trades=[],
            regime="neutral",
            current_cash=10000.0,
            initial_capital=10000.0,
        )
        assert "No open positions" in report

    def test_all_closed(self) -> None:
        closed = [
            PositionSummary("TSLA", 200.0, None, 8, None, "closed", "stop_loss", -5.0),
        ]
        report = generate_portfolio_report(
            positions=closed,
            risk=_make_risk(),
            recent_trades=[],
            regime="neutral",
            current_cash=10000.0,
            initial_capital=10000.0,
        )
        assert "No open positions" in report


class TestRegimeCommentary:
    @pytest.mark.parametrize(
        "regime,expected_snippet",
        [
            ("bullish", "favorable conditions for maintaining positions"),
            ("bearish", "consider tightening stop-losses"),
            ("neutral", "maintain current strategy"),
        ],
    )
    def test_regime_produces_distinct_commentary(
        self, regime: str, expected_snippet: str
    ) -> None:
        report = generate_portfolio_report(
            positions=[],
            risk=_make_risk(),
            recent_trades=[],
            regime=regime,
            current_cash=10000.0,
            initial_capital=10000.0,
        )
        assert expected_snippet in report


class TestSharpeInterpretation:
    def test_excellent(self) -> None:
        report = generate_portfolio_report(
            positions=[], risk=_make_risk(sharpe_ratio=2.5),
            recent_trades=[], regime="neutral",
            current_cash=10000.0, initial_capital=10000.0,
        )
        assert "excellent" in report

    def test_good(self) -> None:
        report = generate_portfolio_report(
            positions=[], risk=_make_risk(sharpe_ratio=1.5),
            recent_trades=[], regime="neutral",
            current_cash=10000.0, initial_capital=10000.0,
        )
        assert "good" in report

    def test_poor(self) -> None:
        report = generate_portfolio_report(
            positions=[], risk=_make_risk(sharpe_ratio=-0.5),
            recent_trades=[], regime="neutral",
            current_cash=10000.0, initial_capital=10000.0,
        )
        assert "poor" in report

    def test_none(self) -> None:
        report = generate_portfolio_report(
            positions=[], risk=_make_risk(sharpe_ratio=None),
            recent_trades=[], regime="neutral",
            current_cash=10000.0, initial_capital=10000.0,
        )
        assert "N/A" in report


class TestMaxDrawdown:
    def test_critical(self) -> None:
        report = generate_portfolio_report(
            positions=[], risk=_make_risk(max_drawdown_pct=30.0),
            recent_trades=[], regime="neutral",
            current_cash=10000.0, initial_capital=10000.0,
        )
        assert "critical" in report

    def test_warning(self) -> None:
        report = generate_portfolio_report(
            positions=[], risk=_make_risk(max_drawdown_pct=20.0),
            recent_trades=[], regime="neutral",
            current_cash=10000.0, initial_capital=10000.0,
        )
        assert "warning" in report

    def test_acceptable(self) -> None:
        report = generate_portfolio_report(
            positions=[], risk=_make_risk(max_drawdown_pct=10.0),
            recent_trades=[], regime="neutral",
            current_cash=10000.0, initial_capital=10000.0,
        )
        assert "acceptable" in report


class TestProfitFactor:
    def test_above_one(self) -> None:
        report = generate_portfolio_report(
            positions=[], risk=_make_risk(profit_factor=1.8),
            recent_trades=[], regime="neutral",
            current_cash=10000.0, initial_capital=10000.0,
        )
        assert "gains outweigh losses" in report

    def test_below_one(self) -> None:
        report = generate_portfolio_report(
            positions=[], risk=_make_risk(profit_factor=0.7),
            recent_trades=[], regime="neutral",
            current_cash=10000.0, initial_capital=10000.0,
        )
        assert "losses outweigh gains" in report

    def test_none(self) -> None:
        report = generate_portfolio_report(
            positions=[], risk=_make_risk(profit_factor=None),
            recent_trades=[], regime="neutral",
            current_cash=10000.0, initial_capital=10000.0,
        )
        assert "N/A" in report


class TestZeroInitialCapital:
    def test_no_crash(self) -> None:
        report = generate_portfolio_report(
            positions=_make_positions(),
            risk=_make_risk(),
            recent_trades=[],
            regime="neutral",
            current_cash=0.0,
            initial_capital=0.0,
        )
        assert "PORTFOLIO SUMMARY" in report
        assert "0.00%" in report


class TestRecentTradesTruncation:
    def test_truncates_to_five(self) -> None:
        trades = _make_trades(7)
        report = generate_portfolio_report(
            positions=[], risk=_make_risk(),
            recent_trades=trades, regime="neutral",
            current_cash=10000.0, initial_capital=10000.0,
        )
        # 7 trades provided, only 5 should appear
        activity_section = report.split("RECENT ACTIVITY")[1].split("REGIME COMMENTARY")[0]
        trade_lines = [l for l in activity_section.strip().splitlines() if l.strip().startswith(("BUY", "SELL"))]
        assert len(trade_lines) == 5

    def test_no_trades(self) -> None:
        report = generate_portfolio_report(
            positions=[], risk=_make_risk(),
            recent_trades=[], regime="neutral",
            current_cash=10000.0, initial_capital=10000.0,
        )
        assert "No recent trades" in report
