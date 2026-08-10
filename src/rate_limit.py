import threading
import time


class RateLimiter:
    """Token bucket, capacity and refill both = rpm. Thread-safe.

    Allows a burst of `rpm` calls, then enforces a continuous
    rpm/60-per-second refill. rpm <= 0 disables limiting.
    """

    def __init__(self, rpm: int) -> None:
        self.rpm = rpm
        self.capacity = float(rpm)
        self.tokens = float(rpm)
        self.updated = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self) -> None:
        if self.rpm <= 0:
            return
        while True:
            with self.lock:
                now = time.monotonic()
                self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.rpm / 60.0)
                self.updated = now
                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return
                wait = (1.0 - self.tokens) * 60.0 / self.rpm
            time.sleep(wait)