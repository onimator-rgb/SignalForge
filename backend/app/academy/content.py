"""Static educational article definitions for the Academy module."""

from pydantic import BaseModel


class Article(BaseModel):
    slug: str
    title: str
    category: str  # 'indicators', 'strategies', 'risk', 'general'
    summary: str
    body: str


ARTICLES: list[Article] = [
    Article(
        slug="what-is-rsi",
        title="What Is RSI? Understanding the Relative Strength Index",
        category="indicators",
        summary="The Relative Strength Index (RSI) is a momentum oscillator that measures the speed and magnitude of price changes to identify overbought or oversold conditions.",
        body=(
            "## What Is RSI?\n\n"
            "The Relative Strength Index (RSI) is one of the most widely used "
            "technical indicators in trading. Developed by J. Welles Wilder Jr. "
            "in 1978, RSI measures the speed and magnitude of recent price changes "
            "to evaluate whether an asset is overbought or oversold.\n\n"
            "## How RSI-14 Works\n\n"
            "The standard RSI uses a 14-period lookback window (RSI-14). It "
            "compares the average gain to the average loss over those 14 periods "
            "and produces a value between 0 and 100. The formula normalises the "
            "ratio of average gains to average losses into this bounded range.\n\n"
            "## Overbought and Oversold Levels\n\n"
            "Traditionally, an RSI reading above 70 signals that an asset may be "
            "overbought — meaning the price has risen significantly and could be "
            "due for a pullback. Conversely, an RSI below 30 suggests the asset "
            "may be oversold and could be poised for a bounce. These thresholds "
            "are guidelines, not guarantees; in strong trends, RSI can remain "
            "elevated or depressed for extended periods.\n\n"
            "## Practical Tips\n\n"
            "Combine RSI with other indicators such as moving averages or volume "
            "analysis to confirm signals. Divergence between RSI and price — "
            "where price makes a new high but RSI does not — can be a powerful "
            "early warning of trend exhaustion."
        ),
    ),
    Article(
        slug="trailing-stops",
        title="How Trailing Stop-Losses Protect Your Profits",
        category="risk",
        summary="Trailing stop-losses automatically adjust upward with price, locking in gains while still giving a trade room to breathe.",
        body=(
            "## What Is a Trailing Stop?\n\n"
            "A trailing stop-loss is a dynamic order that follows the price of "
            "an asset as it moves in your favour. Unlike a fixed stop-loss, which "
            "stays at a set price, a trailing stop automatically adjusts upward "
            "(for long positions) as the market price increases, locking in "
            "profits along the way.\n\n"
            "## How It Works\n\n"
            "You set a trailing distance — either a fixed dollar amount or a "
            "percentage. As the price rises, the stop level rises with it, always "
            "maintaining that distance below the highest price reached. If the "
            "price then drops by the trailing amount, the stop triggers and your "
            "position is closed at or near that level.\n\n"
            "## Benefits\n\n"
            "Trailing stops remove the emotional difficulty of deciding when to "
            "sell. They let winners run while providing a safety net. This is "
            "especially valuable in volatile markets where sharp reversals can "
            "quickly erase unrealised gains.\n\n"
            "## Common Pitfalls\n\n"
            "Setting the trailing distance too tight can result in being stopped "
            "out by normal market noise. Too wide, and you may give back a large "
            "portion of profits before the stop triggers. Finding the right "
            "balance often involves analysing the asset's average true range (ATR)."
        ),
    ),
    Article(
        slug="dca-strategy",
        title="Dollar-Cost Averaging (DCA) Strategy Explained",
        category="strategies",
        summary="Dollar-cost averaging involves investing a fixed amount at regular intervals, reducing the impact of volatility on your average purchase price.",
        body=(
            "## What Is Dollar-Cost Averaging?\n\n"
            "Dollar-cost averaging (DCA) is an investment strategy where you "
            "invest a fixed amount of money at regular intervals — weekly, "
            "fortnightly, or monthly — regardless of the asset's current price. "
            "Over time, this approach smooths out the effects of short-term "
            "volatility on your overall cost basis.\n\n"
            "## Why DCA Works\n\n"
            "When prices are high, your fixed investment buys fewer units. When "
            "prices are low, the same amount buys more units. Over many periods, "
            "your average cost per unit tends to be lower than the average market "
            "price, because you naturally accumulate more shares when they are "
            "cheaper.\n\n"
            "## DCA vs Lump-Sum Investing\n\n"
            "Research shows that lump-sum investing outperforms DCA roughly "
            "two-thirds of the time, because markets tend to rise over the long "
            "term. However, DCA significantly reduces the risk of investing a "
            "large sum at a market peak. For risk-averse investors or those "
            "without a lump sum available, DCA is an excellent approach.\n\n"
            "## Implementing DCA\n\n"
            "Choose a fixed amount you can commit regularly. Select your target "
            "assets and set up automatic purchases on a schedule. The key is "
            "consistency — resist the urge to skip purchases when markets look "
            "uncertain, as those dips are exactly when DCA provides the most "
            "benefit."
        ),
    ),
    Article(
        slug="grid-bot-basics",
        title="Grid Bot Basics: Automated Trading at Price Intervals",
        category="strategies",
        summary="Grid bots place a series of buy and sell orders at predefined price intervals, profiting from sideways market oscillations.",
        body=(
            "## What Is a Grid Bot?\n\n"
            "A grid bot is an automated trading strategy that places a grid of "
            "buy and sell orders at regular price intervals above and below a "
            "set reference price. As the market oscillates, the bot buys low and "
            "sells high within the grid, capturing profits from each swing.\n\n"
            "## How Grid Trading Works\n\n"
            "You define an upper and lower price bound and the number of grid "
            "levels. The bot divides this range into equal intervals and places "
            "limit orders at each level. When a buy order fills, a corresponding "
            "sell order is placed one grid level above. When that sell fills, a "
            "new buy order is placed back at the lower level.\n\n"
            "## Ideal Market Conditions\n\n"
            "Grid bots perform best in ranging or sideways markets where the "
            "price bounces between support and resistance. In strong trending "
            "markets, a grid bot can accumulate losing positions on the wrong "
            "side of the trend. Careful range selection is critical.\n\n"
            "## Configuration Tips\n\n"
            "Start with a wider grid spacing in volatile assets and tighter "
            "spacing in stable ones. Always set stop-losses beyond the grid "
            "boundaries to limit downside risk. Backtest your grid parameters "
            "on historical data before deploying with real capital."
        ),
    ),
    Article(
        slug="risk-management-101",
        title="Risk Management 101: Position Sizing, Stop Losses, and Diversification",
        category="risk",
        summary="Effective risk management combines position sizing, stop-loss orders, and diversification to protect your capital from large drawdowns.",
        body=(
            "## Why Risk Management Matters\n\n"
            "No trading strategy wins every time. Risk management is what keeps "
            "you in the game when trades go against you. Without it, a single "
            "bad trade or a streak of losses can wipe out months of gains or "
            "even your entire account.\n\n"
            "## Position Sizing\n\n"
            "Position sizing determines how much capital to allocate to each "
            "trade. A common rule is to risk no more than 1-2% of your total "
            "portfolio on any single trade. This means if your stop-loss would "
            "result in a 5% loss on the position, your position size should be "
            "no more than 20-40% of your portfolio.\n\n"
            "## Stop-Loss Orders\n\n"
            "A stop-loss order automatically closes a position when the price "
            "moves against you by a predetermined amount. Always place stop "
            "losses before entering a trade — never adjust them further away "
            "from your entry price hoping the market will recover. Trailing "
            "stops can protect profits on winning trades.\n\n"
            "## Diversification\n\n"
            "Spreading your capital across different assets, sectors, and "
            "strategies reduces the impact of any single failure. Correlation "
            "matters: assets that move together provide less diversification "
            "benefit than uncorrelated ones. Aim for a balanced portfolio that "
            "does not depend on any single market or thesis being correct."
        ),
    ),
]


def get_articles(category: str | None = None) -> list[Article]:
    """Return all articles, optionally filtered by category."""
    if category is None:
        return list(ARTICLES)
    return [a for a in ARTICLES if a.category == category]


def get_article_by_slug(slug: str) -> Article | None:
    """Return a single article by slug, or None if not found."""
    for article in ARTICLES:
        if article.slug == slug:
            return article
    return None
