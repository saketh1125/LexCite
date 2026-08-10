import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.rate_limit import RateLimiter


def test_rate_limiter():
    limiter = RateLimiter(600)  # 10 req/s
    start = time.monotonic()
    for _ in range(600):
        limiter.acquire()  # burst is allowed up to capacity
    assert time.monotonic() - start < 2.0
    start = time.monotonic()
    limiter.acquire()  # bucket empty, must wait ~0.1s
    elapsed = time.monotonic() - start
    assert 0.05 <= elapsed <= 0.5, f"waited {elapsed:.3f}s"


def test_disabled_when_zero():
    limiter = RateLimiter(0)
    start = time.monotonic()
    for _ in range(100):
        limiter.acquire()
    assert time.monotonic() - start < 1.0


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok {name}")
    print("all rate limiter tests passed")