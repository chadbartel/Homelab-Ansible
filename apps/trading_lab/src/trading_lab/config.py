"""Application configuration powered by Pydantic Settings."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TradingLabSettings(BaseSettings):
    """Runtime settings loaded from environment variables with safe paper-trading defaults."""

    model_config = SettingsConfigDict(
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    # Database / TimescaleDB
    database_url: str = Field(
        default="sqlite:///./trading_lab.db",
        description="SQLAlchemy 2.0 connection URL (postgresql+psycopg://... in production).",
    )

    # Ollama LLM endpoint
    ollama_base_url: str = Field(default="http://ollama:11434")
    ollama_model: str = Field(default="huihui_ai/qwen3-abliterated:8b-v2")
    ollama_timeout_seconds: float = Field(default=120.0, gt=0.0)

    # Alpaca Paper Trading (optional; falls back to virtual ledger if unset)
    alpaca_api_key: str = Field(default="")
    alpaca_secret_key: str = Field(default="")
    alpaca_paper_base_url: str = Field(default="https://paper-api.alpaca.markets")
    paper_only: bool = Field(default=True)

    # Universe & benchmark
    ticker_allowlist: str = Field(default="AAPL,MSFT,NVDA,AMZN,GOOGL,SPY")
    benchmark_symbol: str = Field(default="SPY")
    lookback_bars: int = Field(default=90, ge=60, le=500)

    # Hard RiskGate guardrails
    max_position_pct: float = Field(default=0.05, gt=0.0, le=1.0)
    default_stop_loss_pct: float = Field(default=0.03, gt=0.0, lt=1.0)
    min_stop_loss_pct: float = Field(default=0.005, gt=0.0, lt=1.0)
    max_stop_loss_pct: float = Field(default=0.15, gt=0.0, lt=1.0)
    min_confidence: float = Field(default=0.55, ge=0.0, le=1.0)
    daily_drawdown_limit_pct: float = Field(default=0.03, gt=0.0, lt=1.0)
    initial_cash: float = Field(default=100000.0, gt=0.0)

    # Scheduler
    scheduler_enabled: bool = Field(default=True)
    scheduler_timezone: str = Field(default="America/New_York")
    scheduler_market_cron: str = Field(default="*/30 9-16 * * 1-5")
    scheduler_reflection_cron: str = Field(default="0 10 * * 6")

    # Filesystem paths (mounted under /mnt/ollama_storage/trading_lab on monolith)
    log_dir: str = Field(default="/app/logs")
    artifacts_dir: str = Field(default="/app/artifacts")

    @property
    def allowlist_symbols(self) -> list[str]:
        """Normalized, deduplicated list of allowed ticker symbols."""
        seen: set[str] = set()
        result: list[str] = []
        for raw in self.ticker_allowlist.split(","):
            sym = raw.strip().upper()
            if sym and sym not in seen:
                seen.add(sym)
                result.append(sym)
        return result

    @property
    def alpaca_configured(self) -> bool:
        """True only when both Alpaca API key and secret key are non-empty."""
        return bool(self.alpaca_api_key.strip() and self.alpaca_secret_key.strip())

    @property
    def execution_mode(self) -> str:
        """Active paper execution backend identifier."""
        return "alpaca_paper" if self.alpaca_configured else "virtual_ledger"
