from PySide6 import QtWidgets
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import collections
import time

# Color palette matching dark blue/green aesthetic
BG_COLOR = '#071227'      # main background
PLOT_BG = '#081722'       # plot panel background
AXIS_COLOR = '#8fe6c7'    # axis labels/ticks
GRID_COLOR = '#063346'
LINE_COLORS = ['#00e676', '#1a73e8', '#9be9c9', '#66ffda', '#7ee7ff']


class LivePlotWidget(QtWidgets.QWidget):
    def __init__(self, max_points: int = 1000, parent=None):
        super().__init__(parent)
        self.fig = Figure(figsize=(5, 3), facecolor=BG_COLOR)
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111, facecolor=PLOT_BG)
        # style axes and labels to be vibrant on dark background
        self.ax.tick_params(colors=AXIS_COLOR, which='both')
        for spine in self.ax.spines.values():
            spine.set_color(AXIS_COLOR)
        self.ax.xaxis.label.set_color(AXIS_COLOR)
        self.ax.yaxis.label.set_color(AXIS_COLOR)
        self.ax.title.set_color(AXIS_COLOR)
        self.ax.set_xlabel('Time (s)')
        self.ax.set_ylabel('Flow')
        self.ax.grid(True, color=GRID_COLOR)

        self.times = collections.deque(maxlen=max_points)
        self.values = collections.deque(maxlen=max_points)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.canvas)
        self.setLayout(layout)

        # main live line (use vibrant first color)
        self._line, = self.ax.plot([], [], '-', lw=1.5, color=LINE_COLORS[0])
        self._color_index = 0

    def add_point(self, timestamp: float, value: float):
        # convert timestamp to relative seconds from first sample
        if not self.times:
            self._t0 = timestamp
        self.times.append(timestamp - self._t0)
        self.values.append(value)
        self._update_plot()

    def _update_plot(self):
        self._line.set_data(self.times, self.values)
        if self.times:
            self.ax.set_xlim(max(0, self.times[0]), self.times[-1])
            ymin = min(self.values)
            ymax = max(self.values)
            margin = (ymax - ymin) * 0.1 if ymax > ymin else 0.5
            self.ax.set_ylim(ymin - margin, ymax + margin)
        # ensure legend/labels keep color styling
        self.ax.title.set_color(AXIS_COLOR)
        self.canvas.draw_idle()

    def plot_series(self, x_vals, y_vals, clear=True, label=None):
        """Plot a full series of x and y values. If clear, replace existing data."""
        if clear:
            self.ax.cla()
            # reapply styling after clear
            self.ax.set_facecolor(PLOT_BG)
            self.ax.tick_params(colors=AXIS_COLOR, which='both')
            for spine in self.ax.spines.values():
                spine.set_color(AXIS_COLOR)
            self.ax.xaxis.label.set_color(AXIS_COLOR)
            self.ax.yaxis.label.set_color(AXIS_COLOR)
            self.ax.title.set_color(AXIS_COLOR)
            self.ax.set_xlabel('X')
            self.ax.set_ylabel('Flow')
            self.ax.grid(True, color=GRID_COLOR)
        # choose a vibrant color cyclically
        self._color_index = (self._color_index + 1) % len(LINE_COLORS)
        color = LINE_COLORS[self._color_index]
        self.ax.plot(x_vals, y_vals, marker='o', linestyle='-', color=color)
        if label:
            self.ax.set_title(label)
        self.canvas.draw_idle()

    def clear(self):
        """Clear the plot area."""
        self.times.clear()
        self.values.clear()
        self.ax.cla()
        self.ax.set_xlabel('Time (s)')
        self.ax.set_ylabel('Flow')
        self.ax.grid(True)
        self._line, = self.ax.plot([], [], '-', lw=1, color=LINE_COLORS[0])
        self.canvas.draw_idle()

    def export_svg(self, path: str):
        """Export the current figure to an SVG file at the given path."""
        # ensure background is preserved in export
        self.fig.savefig(path, format='svg', facecolor=self.fig.get_facecolor())
