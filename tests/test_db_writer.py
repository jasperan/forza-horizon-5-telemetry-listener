"""Tests for BatchedDBWriter - buffering and flushing behavior."""
from unittest.mock import MagicMock

from src.db_writer import BatchedDBWriter


def test_buffer_fills_before_flush():
    writer = BatchedDBWriter(pool=None, batch_size=3)
    writer.add({"speed": 50.0})
    writer.add({"speed": 60.0})
    assert writer.pending == 2
    assert writer.total_flushed == 0


def test_buffer_auto_flushes_at_batch_size():
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_soda = MagicMock()
    mock_coll = MagicMock()
    mock_pool.acquire.return_value = mock_conn
    mock_conn.getSodaDatabase.return_value = mock_soda
    mock_soda.createCollection.return_value = mock_coll
    writer = BatchedDBWriter(pool=mock_pool, batch_size=2, collection_name="test")
    writer.add({"speed": 50.0})
    writer.add({"speed": 60.0})
    assert writer.pending == 0
    assert writer.total_flushed == 2
    mock_coll.insertMany.assert_called_once_with([{"speed": 50.0}, {"speed": 60.0}])
    mock_coll.insertOne.assert_not_called()
    mock_conn.commit.assert_called_once()


def test_noop_when_no_pool():
    writer = BatchedDBWriter(pool=None, batch_size=2)
    writer.add({"speed": 50.0})
    writer.add({"speed": 60.0})
    writer.add({"speed": 70.0})
    assert writer.total_flushed == 0


def test_manual_flush():
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_soda = MagicMock()
    mock_coll = MagicMock()
    mock_pool.acquire.return_value = mock_conn
    mock_conn.getSodaDatabase.return_value = mock_soda
    mock_soda.createCollection.return_value = mock_coll
    writer = BatchedDBWriter(pool=mock_pool, batch_size=100, collection_name="test")
    writer.add({"speed": 50.0})
    writer.flush()
    assert writer.pending == 0
    assert writer.total_flushed == 1
