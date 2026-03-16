"""Database writer module: pool creation and batched document insertion."""
import logging
import os
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


def create_pool(config_path: str = "config.yaml"):
    """Create an oracledb connection pool from a YAML config file.

    Returns the pool on success, or None if the config file is missing
    or pool creation fails.
    """
    if not os.path.exists(config_path):
        logger.warning("Config file not found: %s", config_path)
        return None

    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)

        import oracledb

        home = str(Path.home())
        wallet_dir = config.get("WALLET_DIR", "")
        if wallet_dir:
            os.environ["TNS_ADMIN"] = f"{home}/{wallet_dir}"

        db = config["db"]
        pool = oracledb.create_pool(
            user=db["username"],
            password=db["password"],
            dsn=db["dsn"],
            min=1,
            max=4,
            increment=1,
        )
        logger.info("Connection pool created successfully.")
        return pool
    except Exception as e:
        logger.error("Failed to create pool: %s", e)
        return None


class BatchedDBWriter:
    """Buffers telemetry packets and flushes to Oracle DB in batches."""

    def __init__(self, pool, batch_size: int = 60, collection_name: str = "telemetry_packets"):
        self.pool = pool
        self.batch_size = batch_size
        self.collection_name = collection_name
        self._buffer: list[dict] = []
        self.total_flushed: int = 0

    @property
    def pending(self) -> int:
        return len(self._buffer)

    def add(self, document: dict):
        self._buffer.append(document)
        if len(self._buffer) >= self.batch_size:
            self.flush()

    def flush(self):
        if not self._buffer:
            return
        if self.pool is None:
            self._buffer.clear()
            return
        conn = self.pool.acquire()
        try:
            soda = conn.getSodaDatabase()
            coll = soda.createCollection(self.collection_name)
            for doc in self._buffer:
                coll.insertOne(doc)
            conn.commit()
            self.total_flushed += len(self._buffer)
            logger.debug("Flushed %d documents to %s", len(self._buffer), self.collection_name)
        except Exception as e:
            logger.error("DB flush failed: %s", e)
        finally:
            self.pool.release(conn)
            self._buffer.clear()

    def save_document(self, collection_name: str, document: dict):
        if self.pool is None:
            return
        conn = self.pool.acquire()
        try:
            soda = conn.getSodaDatabase()
            coll = soda.createCollection(collection_name)
            coll.insertOne(document)
            conn.commit()
        except Exception as e:
            logger.error("DB save failed for %s: %s", collection_name, e)
        finally:
            self.pool.release(conn)
