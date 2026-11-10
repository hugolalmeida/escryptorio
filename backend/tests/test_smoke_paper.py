"""Testes offline do isolamento operacional; nunca acessam a Bybit."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

path = Path(__file__).resolve().parents[2] / "scripts" / "smoke_paper.py"
spec = importlib.util.spec_from_file_location("smoke_paper", path)
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


def test_default_diagnostic_creates_new_isolated_db_without_network(monkeypatch, tmp_path):
    monkeypatch.setattr(smoke.tempfile, "tempdir", str(tmp_path))
    monkeypatch.setenv("CRYPTOLAB_DATABASE", str(tmp_path / "protected.sqlite3"))
    monkeypatch.setenv("PAPER_SIMULATION_ENABLED", "false")
    monkeypatch.setenv("LIVE_TRADING_ENABLED", "false")
    monkeypatch.setattr(smoke.subprocess, "run", lambda *a, **k: pytest.fail("rede proibida"))
    result = smoke.run()
    assert result["result"] == "NOT_RUN" and result["fill"] == "NOT_RUN"
    assert result["integrity"]["valid"] and Path(result["database"]).is_file()
    assert not (tmp_path / "protected.sqlite3").exists()
    assert smoke.os.environ["CRYPTOLAB_DATABASE"] == str(tmp_path / "protected.sqlite3")


def test_worker_failure_does_not_create_wallet_or_fill(monkeypatch, tmp_path):
    monkeypatch.setattr(smoke.tempfile, "tempdir", str(tmp_path))
    monkeypatch.setenv("PAPER_SIMULATION_ENABLED", "false")
    monkeypatch.setenv("LIVE_TRADING_ENABLED", "false")
    monkeypatch.setattr(smoke.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=1))
    result = smoke.run(public=True, activate=True)
    assert result["result"] == "FAILED" and result["fill"] == "NOT_RUN"
    assert smoke.PaperExecutor(Path(result["database"])).verify_integrity()["wallets"] == 0


@pytest.mark.parametrize("flag", ["PAPER_SIMULATION_ENABLED", "LIVE_TRADING_ENABLED"])
def test_guards_before_creating_database(monkeypatch, tmp_path, flag):
    monkeypatch.setattr(smoke.tempfile, "tempdir", str(tmp_path))
    monkeypatch.setenv("PAPER_SIMULATION_ENABLED", "false")
    monkeypatch.setenv("LIVE_TRADING_ENABLED", "false")
    monkeypatch.setenv(flag, "true")
    with pytest.raises(ValueError):
        smoke.run(public=True)
    assert not list(tmp_path.iterdir())


def test_activation_requires_public_opt_in(monkeypatch):
    monkeypatch.setenv("PAPER_SIMULATION_ENABLED", "false")
    monkeypatch.setenv("LIVE_TRADING_ENABLED", "false")
    with pytest.raises(ValueError, match="PUBLIC_COLLECTION_REQUIRED"):
        smoke.run(activate=True)
