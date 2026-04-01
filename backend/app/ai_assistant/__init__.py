"""AI assistant module — pure-logic advisory and reporting functions."""

from app.ai_assistant.portfolio_report import (
    PositionSummary,
    RiskSnapshot,
    TradeSummary,
    generate_portfolio_report,
)
from app.ai_assistant.strategy_advisor import StrategyRule, suggest_improvements

__all__ = [
    "PositionSummary",
    "RiskSnapshot",
    "TradeSummary",
    "generate_portfolio_report",
    "StrategyRule",
    "suggest_improvements",
]
