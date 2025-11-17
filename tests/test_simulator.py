import time
from flowbench.simulator import Simulator


def test_simulator_runs_and_calls_back():
    called = []

    def cb(ts, v):
        called.append((ts, v))

    sim = Simulator(callback=cb, interval=0.01)
    sim.start()
    time.sleep(0.05)
    sim.stop()
    assert len(called) >= 1
