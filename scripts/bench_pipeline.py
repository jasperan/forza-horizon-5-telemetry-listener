"""Micro-benchmark for the per-packet hot path (no game, no database needed).

Measures:
  * decode: raw 324-byte FH5 datagram -> telemetry dict (TelemetryHub.process_packet)
  * flush:  BatchedDBWriter.flush() of 60 documents against a mocked SODA pool,
            counting the driver calls that would each be a DB round trip.

Run: uv run python scripts/bench_pipeline.py
"""
import random
import struct
import sys
import timeit
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data_packet import ForzaDataPacket  # noqa: E402
from src.db_writer import BatchedDBWriter  # noqa: E402
from src.telemetry_hub import TelemetryHub  # noqa: E402


def synthetic_packet(seed: int = 0) -> bytes:
    """Build a realistic FH5 datagram: 232 sled bytes, 12 FH5 bytes, 79 dash bytes, 1 pad."""
    rng = random.Random(seed)
    values = []
    for code in ForzaDataPacket.dash_format[1:]:
        if code == "f":
            values.append(rng.uniform(-100, 100))
        elif code in "iI":
            values.append(rng.randint(0, 1000))
        elif code == "H":
            values.append(rng.randint(0, 50))
        elif code == "B":
            values.append(rng.randint(0, 255))
        else:  # b
            values.append(rng.randint(-127, 127))
    values[0] = 1  # is_race_on
    body = struct.pack(ForzaDataPacket.dash_format, *values)
    return body[:232] + bytes(12) + body[232:] + b"\x00"


class FakeDriver:
    """Minimal stand-in for an oracledb pool/connection/SODA collection.

    Each method is a no-op that only counts calls, so the timing reflects the
    Python-side cost of the writer; every counted call is a DB round trip in
    production, which comes on top of these numbers.
    """

    def __init__(self):
        self.calls = dict.fromkeys(
            ["acquire", "getSodaDatabase", "createCollection", "openCollection",
             "insertOne", "insertMany", "commit", "release"], 0)

    def _hit(self, name):
        self.calls[name] += 1
        return self

    def acquire(self):
        return self._hit("acquire")

    def release(self, conn):
        self._hit("release")

    def getSodaDatabase(self):
        return self._hit("getSodaDatabase")

    def createCollection(self, name):
        return self._hit("createCollection")

    def openCollection(self, name):
        return self._hit("openCollection")

    def insertOne(self, doc):
        self._hit("insertOne")

    def insertMany(self, docs):
        self._hit("insertMany")

    def commit(self):
        self._hit("commit")


def bench_decode(n: int = 20000, repeat: int = 5) -> float:
    hub = TelemetryHub()
    packets = [synthetic_packet(i) for i in range(64)]
    best = min(
        timeit.repeat(
            lambda: [hub.process_packet(packets[i & 63]) for i in range(n)],
            number=1,
            repeat=repeat,
        )
    )
    return best / n * 1e6  # us per packet


def bench_flush(batches: int = 200, batch_size: int = 60, repeat: int = 5):
    hub = TelemetryHub()
    docs = [hub.process_packet(synthetic_packet(i)) for i in range(batch_size)]
    pool = FakeDriver()
    writer = BatchedDBWriter(pool=pool, batch_size=batch_size)

    def run():
        for _ in range(batches):
            for d in docs:
                writer.add(d)

    best = min(timeit.repeat(run, number=1, repeat=repeat))
    total_batches = batches * repeat
    per_batch = {k: v / total_batches for k, v in pool.calls.items()}
    return best / batches * 1e6, per_batch  # us per 60-doc batch (fake driver)


if __name__ == "__main__":
    us = bench_decode()
    print(f"decode: {us:.2f} us/packet ({1e6 / us:,.0f} packets/s)")
    us_flush, per_batch = bench_flush()
    print(f"add+flush (fake driver): {us_flush:.1f} us per 60-doc batch")
    print("driver calls per 60-doc batch:",
          ", ".join(f"{k}={v:g}" for k, v in per_batch.items()))
