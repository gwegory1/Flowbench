import sys
import threading
import csv
from PySide6 import QtWidgets, QtCore, QtGui
from .simulator import Simulator
from .pg_plotwidget import PGPlotWidget as LivePlotWidget


class MainWindow(QtWidgets.QMainWindow):
    """Main application window for FlowBench."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle('FlowBench')
        self.resize(1000, 700)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        layout = QtWidgets.QVBoxLayout(central)

        # Top panel: readout card and controls
        top = QtWidgets.QWidget()
        top_l = QtWidgets.QHBoxLayout(top)

        # Readout card (vibrant, high-contrast)
        card = QtWidgets.QFrame()
        card.setFrameShape(QtWidgets.QFrame.Box)
        card.setStyleSheet('background: #0b1220; border-radius: 8px; padding: 12px;')
        card_l = QtWidgets.QVBoxLayout(card)
        self.readout = QtWidgets.QLabel('---')
        self.readout.setObjectName('readout')
        rfont = QtGui.QFont('Segoe UI', 36, QtGui.QFont.Weight.Black)
        self.readout.setFont(rfont)
        self.readout.setStyleSheet('color: #00e676;')
        self.unit_label = QtWidgets.QLabel('L/min')
        self.unit_label.setStyleSheet('color: #9aa7b1;')
        card_l.addWidget(self.readout)
        card_l.addWidget(self.unit_label)

        # Controls
        ctrl = QtWidgets.QWidget()
        ctrl_l = QtWidgets.QHBoxLayout(ctrl)
        btn_start = QtWidgets.QPushButton('Start')
        btn_stop = QtWidgets.QPushButton('Stop')
        btn_record = QtWidgets.QPushButton('Record')
        ctrl_l.addWidget(btn_start)
        ctrl_l.addWidget(btn_stop)
        ctrl_l.addWidget(btn_record)

        # manual graph builder controls
        gb_widget = QtWidgets.QWidget()
        gb_layout = QtWidgets.QHBoxLayout(gb_widget)
        self.resolution_spin = QtWidgets.QDoubleSpinBox()
        self.resolution_spin.setRange(0.001, 1000.0)
        self.resolution_spin.setValue(1.0)
        self.resolution_unit = QtWidgets.QComboBox()
        self.resolution_unit.addItems(['s', 'mm'])
        # default unit is seconds
        self.resolution_spin.setSuffix(' s')
        self.slots_spin = QtWidgets.QSpinBox()
        self.slots_spin.setRange(1, 1000)
        self.slots_spin.setValue(10)
        btn_setup_slots = QtWidgets.QPushButton('Setup Slots')
        gb_layout.addWidget(QtWidgets.QLabel('Resolution:'))
        gb_layout.addWidget(self.resolution_spin)
        gb_layout.addWidget(self.resolution_unit)
        gb_layout.addWidget(QtWidgets.QLabel('Slots:'))
        gb_layout.addWidget(self.slots_spin)
        gb_layout.addWidget(btn_setup_slots)

        top_l.addWidget(card)
        top_l.addWidget(ctrl)
        top_l.addStretch()
        top_l.addWidget(gb_widget)

        layout.addWidget(top)

        # Plot
        self.plot = LivePlotWidget()
        layout.addWidget(self.plot, 1)

        # Manual graph builder area (table + actions)
        builder = QtWidgets.QGroupBox('Manual Graph Builder')
        builder_layout = QtWidgets.QVBoxLayout(builder)

        self.table = QtWidgets.QTableWidget(0, 2)
        # show unit in X header
        self.table.setHorizontalHeaderLabels([f'X ({self.resolution_unit.currentText()})', 'Value'])
        self.table.horizontalHeader().setStretchLastSection(True)
        builder_layout.addWidget(self.table)

        actions = QtWidgets.QWidget()
        actions_l = QtWidgets.QHBoxLayout(actions)
        btn_add_current = QtWidgets.QPushButton('Add Current to Selected')
        btn_add_next = QtWidgets.QPushButton('Add Current to Next')
        btn_build = QtWidgets.QPushButton('Build Graph')
        btn_clear = QtWidgets.QPushButton('Clear Builder')
        btn_save = QtWidgets.QPushButton('Save Builder')
        btn_load = QtWidgets.QPushButton('Load Builder')
        btn_export_svg = QtWidgets.QPushButton('Export SVG')
        actions_l.addWidget(btn_add_current)
        actions_l.addWidget(btn_add_next)
        actions_l.addStretch()
        actions_l.addWidget(btn_save)
        actions_l.addWidget(btn_load)
        actions_l.addWidget(btn_build)
        actions_l.addWidget(btn_clear)
        actions_l.addWidget(btn_export_svg)
        builder_layout.addWidget(actions)

        layout.addWidget(builder)

        # state
        self._sim = None
        self._lock = threading.Lock()
        self._recording = False
        self._recorded = []
        self._last_value = None

        btn_start.clicked.connect(self.start)
        btn_stop.clicked.connect(self.stop)
        btn_record.clicked.connect(self.toggle_record)
        btn_setup_slots.clicked.connect(self.setup_slots)
        self.resolution_unit.currentIndexChanged.connect(self._on_unit_changed)
        btn_add_current.clicked.connect(self.add_current_to_selected)
        btn_add_next.clicked.connect(self.add_current_to_next)
        btn_build.clicked.connect(self.build_graph_from_table)
        btn_clear.clicked.connect(self.clear_builder)
        btn_save.clicked.connect(self.save_builder)
        btn_load.clicked.connect(self.load_builder)
        btn_export_svg.clicked.connect(self.export_svg)

    def export_svg(self):
        """Export the current displayed plot to an SVG file."""
        fname = QtWidgets.QFileDialog.getSaveFileName(self, 'Export plot to SVG', 'plot.svg', 'SVG Files (*.svg)')[0]
        if not fname:
            return
        try:
            self.plot.export_svg(fname)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Export failed', f'Could not export SVG:\n{e}')

    @QtCore.Slot()
    def start(self):
        if self._sim is not None:
            return
        self._sim = Simulator(callback=self.handle_sample, interval=0.05)
        self._sim.start()

    @QtCore.Slot()
    def stop(self):
        if self._sim is None:
            return
        self._sim.stop()
        self._sim = None

    @QtCore.Slot()
    def toggle_record(self):
        self._recording = not self._recording
        if self._recording:
            self._recorded = []
        else:
            fname = QtWidgets.QFileDialog.getSaveFileName(self, 'Save recording', 'recording.csv', 'CSV Files (*.csv)')[0]
            if fname:
                with open(fname, 'w', newline='') as f:
                    w = csv.writer(f)
                    w.writerow(['timestamp', 'value'])
                    w.writerows(self._recorded)

    def handle_sample(self, timestamp: float, value: float):
        # called from simulator thread; forward to GUI thread via singleShot
        self._last_value = (timestamp, value)
        QtCore.QTimer.singleShot(0, lambda: self._handle_sample_gui(*self._last_value))

    @QtCore.Slot(float, float)
    def _handle_sample_gui(self, timestamp: float, value: float):
        # update readout
        self.readout.setText(f"{value:0.3f}")
        self.plot.add_point(timestamp, value)
        if self._recording:
            self._recorded.append((timestamp, value))

    # Manual graph builder helpers
    def setup_slots(self):
        slots = int(self.slots_spin.value())
        resolution = float(self.resolution_spin.value())
        unit = self.resolution_unit.currentText()
        self.table.setRowCount(slots)
        for i in range(slots):
            # X values represent multiples of resolution in chosen unit
            x_item = QtWidgets.QTableWidgetItem(f"{i * resolution:0.3f}")
            x_item.setFlags(x_item.flags() & ~QtCore.Qt.ItemIsEditable)
            self.table.setItem(i, 0, x_item)
            self.table.setItem(i, 1, QtWidgets.QTableWidgetItem(''))

    def _on_unit_changed(self):
        # update resolution suffix and X header label
        unit = self.resolution_unit.currentText()
        self.resolution_spin.setSuffix(f' {unit}')
        hdr = f'X ({unit})'
        self.table.setHorizontalHeaderLabels([hdr, 'Value'])

    def add_current_to_selected(self):
        sel = self.table.selectedItems()
        if not sel:
            return
        row = sel[0].row()
        if self._last_value is None:
            return
        _, v = self._last_value
        self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(f"{v:0.3f}"))

    def add_current_to_next(self):
        if self._last_value is None:
            return
        _, v = self._last_value
        rows = self.table.rowCount()
        for i in range(rows):
            it = self.table.item(i, 1)
            if it is None or it.text().strip() == '':
                self.table.setItem(i, 1, QtWidgets.QTableWidgetItem(f"{v:0.3f}"))
                return

    def build_graph_from_table(self):
        xs = []
        ys = []
        for i in range(self.table.rowCount()):
            xi_it = self.table.item(i, 0)
            yi_it = self.table.item(i, 1)
            if xi_it is None or yi_it is None:
                continue
            try:
                x = float(xi_it.text())
                y = float(yi_it.text())
            except Exception:
                continue
            xs.append(x)
            ys.append(y)
        if xs and ys:
            self.plot.plot_series(xs, ys, clear=True, label='Manual Build')

    def clear_builder(self):
        self.table.setRowCount(0)
        self.plot.clear()

    def save_builder(self):
        fname = QtWidgets.QFileDialog.getSaveFileName(self, 'Save builder', 'builder.csv', 'CSV Files (*.csv)')[0]
        if not fname:
            return
        rows = self.table.rowCount()
        with open(fname, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['x', 'value'])
            for i in range(rows):
                xi = self.table.item(i, 0)
                yi = self.table.item(i, 1)
                x = xi.text() if xi is not None else ''
                y = yi.text() if yi is not None else ''
                w.writerow([x, y])

    def load_builder(self):
        fname = QtWidgets.QFileDialog.getOpenFileName(self, 'Load builder', '', 'CSV Files (*.csv)')[0]
        if not fname:
            return
        with open(fname, 'r', newline='') as f:
            r = csv.reader(f)
            hdr = next(r, None)
            rows = list(r)
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            x = row[0] if len(row) > 0 else ''
            y = row[1] if len(row) > 1 else ''
            xi = QtWidgets.QTableWidgetItem(x)
            xi.setFlags(xi.flags() & ~QtCore.Qt.ItemIsEditable)
            self.table.setItem(i, 0, xi)
            self.table.setItem(i, 1, QtWidgets.QTableWidgetItem(y))


def main(argv):
    app = QtWidgets.QApplication(list(argv))
    # Minimalist futuristic dark blue/green theme
    stylesheet = """
    QWidget { background: #071227; color: #cfeef5; font-family: 'Segoe UI', Arial, sans-serif; }
    QFrame { background: transparent; }
    QGroupBox { border: 1px solid #0d3240; margin-top: 8px; border-radius: 6px; }
    QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; color: #8fe6c7; }
    QLabel#readout { color: #00e676; }
    QLabel { color: #cfeef5; }
    QPushButton { background: #083148; border: 1px solid #12536b; padding: 6px 10px; border-radius: 6px; color: #cfeef5; }
    QPushButton:hover { background: #0b4a63; }
    QPushButton:pressed { background: #063342; }
    QTableWidget { background: #081722; gridline-color: #063346; }
    QHeaderView::section { background: #062433; color: #9be9c9; border: none; padding: 6px; }
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { background: #051827; border: 1px solid #0b3b4a; padding: 4px; color: #cfeef5; }
    QScrollBar:vertical { background: #061a24; width: 10px; }
    """
    app.setStyleSheet(stylesheet)
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
