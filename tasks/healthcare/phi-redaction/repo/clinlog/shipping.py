"""Batching and retry policy for shipping sanitised lines to the log platform.

Network I/O lives in the deployment wrapper; this module is pure so that the
policy can be unit tested.
"""

import gzip
from dataclasses import dataclass
from typing import Iterable, Iterator, List


@dataclass(frozen=True)
class BatchPolicy:
    max_lines: int = 500
    max_bytes: int = 512 * 1024


def batches(lines: Iterable[str], policy: BatchPolicy = BatchPolicy()) -> Iterator[List[str]]:
    batch: List[str] = []
    size = 0
    for line in lines:
        n = len(line.encode("utf-8")) + 1
        if batch and (len(batch) >= policy.max_lines or size + n > policy.max_bytes):
            yield batch
            batch, size = [], 0
        batch.append(line)
        size += n
    if batch:
        yield batch


def encode_batch(batch: List[str]) -> bytes:
    payload = ("\n".join(batch) + "\n").encode("utf-8")
    return gzip.compress(payload, mtime=0)


def backoff_seconds(attempt: int, base: float = 0.5, cap: float = 60.0) -> float:
    """Deterministic exponential backoff (jitter is added by the wrapper)."""
    if attempt < 0:
        raise ValueError("attempt must be >= 0")
    return min(cap, base * (2 ** attempt))


def should_retry(status: int) -> bool:
    return status == 429 or 500 <= status < 600
