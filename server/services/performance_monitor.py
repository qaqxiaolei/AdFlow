import time
from typing import Dict


class PerformanceMonitor:
    def __init__(self):
        self._timings: Dict[str, list] = {}

    def start(self, key: str):
        self._timings[key] = [time.time(), None]

    def end(self, key: str) -> float:
        if key in self._timings:
            start_time = self._timings[key][0]
            elapsed = time.time() - start_time
            self._timings[key][1] = elapsed
            return elapsed
        return 0.0

    def get_timing(self, key: str) -> float:
        return self._timings.get(key, [0, 0])[1] or 0.0

    def log_timings(self, session_id: str):
        timings_str = ", ".join(f"{k}: {v[1]:.2f}s" for k, v in self._timings.items() if v[1])
        print(f"⏱️ Session {session_id} 性能统计: {timings_str}")


performance_monitor = PerformanceMonitor()