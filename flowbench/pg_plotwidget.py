from PySide6 import QtWidgets, QtCore, QtGui
from PySide6 import QtSvg
import pyqtgraph as pg
import collections


class PGPlotWidget(QtWidgets.QWidget):
    """A lightweight PyQtGraph-based plot widget with a similar API to the
    existing LivePlotWidget: add_point, plot_series, clear, export_svg.
    """

    def __init__(self, max_points: int = 1000, parent=None):
        super().__init__(parent)
        self.max_points = max_points
        self.times = collections.deque(maxlen=max_points)
        self.values = collections.deque(maxlen=max_points)
        self._t0 = None

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Configure PyQtGraph appearance to match the dark blue/green theme
        pg.setConfigOptions(background='#071227', foreground='#8fe6c7', antialias=True)
        self.plotw = pg.PlotWidget()
        self.plotw.setBackground('#071227')
        self.plotw.showGrid(x=True, y=True, alpha=0.25)
        self.plotw.getAxis('left').setPen(pg.mkPen('#8fe6c7'))
        self.plotw.getAxis('bottom').setPen(pg.mkPen('#8fe6c7'))
        self.plotw.getAxis('left').setTextPen(pg.mkPen('#cfeef5'))
        self.plotw.getAxis('bottom').setTextPen(pg.mkPen('#cfeef5'))

        self._curve = self.plotw.plot([], [], pen=pg.mkPen('#00e676', width=2))
        layout.addWidget(self.plotw)

    def add_point(self, timestamp: float, value: float):
        if not self.times:
            self._t0 = timestamp
        self.times.append(timestamp - self._t0)
        self.values.append(value)
        # PyQtGraph is efficient with lists
        self._curve.setData(list(self.times), list(self.values))

    def plot_series(self, x_vals, y_vals, clear=True, label=None, color: str = None, symbolBrush: str = None):
        """Plot a series. Optional `color` and `symbolBrush` let callers pick colors for overlays.

        Parameters:
        - color: hex color string for the line (defaults to blue)
        - symbolBrush: hex color string for marker fill (defaults to teal)
        """
        if clear:
            self.plotw.clear()
        pen_color = color or '#1a73e8'
        marker_brush = symbolBrush or '#66ffda'
        pen = pg.mkPen(pen_color, width=2)
        self.plotw.plot(x_vals, y_vals, pen=pen, symbol='o', symbolBrush=marker_brush)
        if label:
            self.plotw.setTitle(label, color='#8fe6c7')

    def clear(self):
        self.times.clear()
        self.values.clear()
        self.plotw.clear()
        self._curve = self.plotw.plot([], [], pen=pg.mkPen('#00e676', width=2))

    def export_svg(self, path: str):
        """Export the current plot to an SVG file using QSvgGenerator.
        This renders the widget into an SVG; results are vector and will
        capture the visuals produced by the widget.
        """
        gen = QtSvg.QSvgGenerator()
        gen.setFileName(path)
        size = self.plotw.size()
        gen.setSize(size)
        gen.setViewBox(self.plotw.rect())
        gen.setTitle('FlowBench Export')
        painter = QtGui.QPainter()
        painter.begin(gen)
        # Render the PlotWidget into the SVG painter
        self.plotw.render(painter)
        painter.end()
