"""Tests for db_writer module - pool creation and config loading."""
import os
import tempfile
from unittest.mock import patch, MagicMock

import pytest
import yaml


def test_db_connection_loads_config():
    """Mock oracledb, create a temp config.yaml, verify create_pool reads it correctly."""
    config = {
        "db": {
            "username": "testuser",
            "password": "testpass",
            "dsn": "testdsn_high",
        },
        "WALLET_DIR": "wallets/test_wallet",
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config, f)
        tmp_path = f.name

    try:
        mock_pool = MagicMock()
        with patch("oracledb.create_pool", return_value=mock_pool) as mock_create:
            from src.db_writer import create_pool

            pool = create_pool(tmp_path)

            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args
            assert call_kwargs.kwargs["user"] == "testuser"
            assert call_kwargs.kwargs["password"] == "testpass"
            assert call_kwargs.kwargs["dsn"] == "testdsn_high"
            assert call_kwargs.kwargs["min"] == 1
            assert call_kwargs.kwargs["max"] == 4
            assert pool is mock_pool
    finally:
        os.unlink(tmp_path)


def test_db_connection_returns_none_when_no_config():
    """Verify create_pool returns None for nonexistent config."""
    from src.db_writer import create_pool

    result = create_pool("/nonexistent/path/config.yaml")
    assert result is None
