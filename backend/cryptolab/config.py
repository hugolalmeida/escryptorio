import os
from pathlib import Path

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
SYMBOLS = ("BTCUSDT", "ETHUSDT")
INTERVALS = {"15": 900, "60": 3600, "240": 14400, "D": 86400}


class Settings(BaseModel):
    database_path: Path = ROOT / "data" / "cryptolab.sqlite3"
    stale_after_seconds: int = Field(default=90, ge=30, le=300)
    poll_seconds: int = Field(default=15, ge=10, le=60)

    @classmethod
    def from_env(cls) -> "Settings":
        # Fail closed even if someone changes the deployment environment.
        if os.getenv("LIVE_TRADING_ENABLED", "false").lower() != "false":
            raise RuntimeError("Execução real indisponível: LIVE_TRADING_ENABLED deve ser false.")
        return cls(
            database_path=os.getenv("CRYPTOLAB_DATABASE", str(ROOT / "data" / "cryptolab.sqlite3")),
            stale_after_seconds=os.getenv("STALE_AFTER_SECONDS", "90"),
            poll_seconds=os.getenv("POLL_SECONDS", "15"),
        )
