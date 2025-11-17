import threading
import time
import math
import random
from typing import Callable


class Simulator(threading.Thread):
    """Simulates flow measurements in a background thread.

    Callback signature: fn(timestamp: float, value: float)
    """

    def __init__(self, callback: Callable[[float, float], None], interval: float = 0.1):
        super().__init__(daemon=True)
        self.callback = callback
        self.interval = interval
        self._stop_event = threading.Event()
        self._t0 = time.time()

    def run(self):
        while not self._stop_event.is_set():
            t = time.time() - self._t0
            # synthetic signal: baseline + slow drift + periodic fluctuations + noise
            baseline = 5.0
            drift = 0.02 * t
            periodic = 2.0 * math.sin(2 * math.pi * 0.2 * t)  # 0.2 Hz
            fast = 0.5 * math.sin(2 * math.pi * 2.0 * t)  # 2 Hz
            noise = random.normalvariate(0, 0.1)
            value = baseline + drift + periodic + fast + noise
            try:
                self.callback(time.time(), value)
            except Exception:
                pass
            time.sleep(self.interval)

    def stop(self):
        self._stop_event.set()
