import threading
import json
import time
import os
from .simulator import Simulator

import webview
import logging
from collections import deque


class WebBridge:
    def __init__(self):
        self.window = None
        self._sim = None
        self._recording = False
        # queue samples to avoid calling evaluate_js directly from the simulator
        self._queue = deque()
        self._dispatch_running = True
        self._dispatch_thread = threading.Thread(target=self._dispatch_loop, daemon=True)
        self._dispatch_thread.start()
        # only dispatch samples after the web UI reports loaded
        self._ready = False
        # simple lock to avoid reentrant API calls from JS
        self._api_lock = threading.Lock()

    def send_sample(self, ts, value):
        # enqueue sample; dispatcher will deliver to the web UI thread
        self._queue.append((ts, value))

    def _dispatch_loop(self):
        while self._dispatch_running:
            if not self._queue:
                time.sleep(0.01)
                continue
            ts, value = self._queue.popleft()
            # do not attempt to call evaluate_js until the page has fully loaded
            if not self.window or not self._ready:
                # re-enqueue and back off
                self._queue.appendleft((ts, value))
                time.sleep(0.05)
                continue
            payload = json.dumps({'timestamp': ts, 'value': value})
            try:
                # evaluate_js can execute JS which may call back into Python; running
                # from a separate thread avoids deep recursive Python<->JS call stacks.
                self.window.evaluate_js(f'window.onSample({payload})')
            except Exception:
                # swallow and continue
                pass

    # API called from JS via pywebview
    def start(self):
        with self._api_lock:
            if self._sim is not None:
                return
            self._sim = Simulator(callback=lambda t, v: self.send_sample(t, v), interval=0.05)
            self._sim.start()

    def stop(self):
        with self._api_lock:
            if self._sim is None:
                return
            self._sim.stop()
            self._sim = None

    def toggle_record(self):
        with self._api_lock:
            self._recording = not self._recording
            return self._recording

    # persistence APIs
    def save_builder(self, json_rows: str):
        """Save builder CSV provided as JSON array of [x,y] pairs."""
        try:
            rows = json.loads(json_rows)
        except Exception:
            return False
        # Persist to package-local file to avoid calling file-dialog APIs
        fname = os.path.join(os.path.dirname(__file__), 'builder.csv')
        try:
            with open(fname, 'w', newline='') as f:
                import csv
                w = csv.writer(f)
                w.writerow(['x', 'value'])
                for r in rows:
                    w.writerow([r[0], r[1]])
            return True
        except Exception:
            return False

    def load_builder(self):
        """Open a builder CSV and return JSON rows to JS."""
        fname = os.path.join(os.path.dirname(__file__), 'builder.csv')
        if not os.path.exists(fname):
            return '[]'
        try:
            import csv
            rows = []
            with open(fname, 'r', newline='') as f:
                r = csv.reader(f)
                hdr = next(r, None)
                for row in r:
                    x = row[0] if len(row) > 0 else ''
                    y = row[1] if len(row) > 1 else ''
                    rows.append([x, y])
            return json.dumps(rows)
        except Exception:
            return '[]'

    def save_svg(self, data_url: str):
        """Save an SVG data URL (data:image/svg+xml;base64,...) passed from JS."""
        # strip prefix
        try:
            prefix = 'data:image/svg+xml;'
            if data_url.startswith(prefix):
                # may be base64 or utf-8; let webview callers send directly as utf-8
                content = data_url.split(',', 1)[1]
            else:
                content = data_url
        except Exception:
            return False
        fname = os.path.join(os.path.dirname(__file__), 'exported_plot.svg')
        try:
            # if content is base64, decode; otherwise write as-is
            import base64
            try:
                raw = base64.b64decode(content)
                with open(fname, 'wb') as f:
                    f.write(raw)
            except Exception:
                with open(fname, 'w', encoding='utf-8') as f:
                    f.write(content)
            return True
        except Exception:
            return False


def run_web_app():
    bridge = WebBridge()
    html_path = os.path.join(os.path.dirname(__file__), 'web_ui', 'index.html')
    # pass bridge as js_api so JS can call Python methods via window.pywebview.api
    # reduce pywebview verbosity
    logging.getLogger('pywebview').setLevel(logging.WARNING)
    window = webview.create_window('FlowBench (Web)', html_path, js_api=bridge, width=1000, height=700)
    # mark bridge.window only once the loaded event fires to avoid evaluate_js race
    def _on_loaded():
        bridge.window = window
        bridge._ready = True
    try:
        window.events.loaded += _on_loaded
    except Exception:
        # if events API is unavailable, fall back to immediate assignment
        bridge.window = window
        bridge._ready = True
    # prefer quieter startup; debug=True produces a lot of developer output
    webview.start(debug=False)


if __name__ == '__main__':
    run_web_app()
