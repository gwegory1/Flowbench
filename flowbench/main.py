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
        self.resize(1100, 720)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        layout = QtWidgets.QVBoxLayout(central)

        # Top: readout + controls
        top = QtWidgets.QWidget()
        top_l = QtWidgets.QHBoxLayout(top)

        # Readout card
        card = QtWidgets.QFrame()
        card.setFrameShape(QtWidgets.QFrame.Box)
        card.setStyleSheet("background: #071227; border: 1px solid #0d3240; border-radius: 0px; padding: 12px;")
        card_l = QtWidgets.QVBoxLayout(card)
        self.readout = QtWidgets.QLabel('---')
        self.readout.setObjectName('readout')
        rfont = QtGui.QFont('Consolas', 44, QtGui.QFont.Weight.Bold)
        self.readout.setFont(rfont)
        self.readout.setStyleSheet('color: #00e676;')
        self.unit_label = QtWidgets.QLabel('L/min')
        self.unit_label.setStyleSheet('color: #9aa7b1;')
        card_l.addWidget(self.readout)
        card_l.addWidget(self.unit_label)

        # Controls (vertical)
        ctrl = QtWidgets.QWidget()
        ctrl_l = QtWidgets.QVBoxLayout(ctrl)
        ctrl_l.setSpacing(8)
        btn_start = QtWidgets.QPushButton('Start')
        btn_stop = QtWidgets.QPushButton('Stop')
        btn_record = QtWidgets.QPushButton('Record')
        btn_start.setObjectName('btnStart')
        btn_stop.setObjectName('btnStop')
        btn_record.setObjectName('btnRecord')
        ctrl_l.addWidget(btn_start)
        ctrl_l.addWidget(btn_stop)
        ctrl_l.addWidget(btn_record)

        # small builder controls
        gb_widget = QtWidgets.QWidget()
        gb_layout = QtWidgets.QHBoxLayout(gb_widget)
        self.resolution_spin = QtWidgets.QDoubleSpinBox()
        self.resolution_spin.setRange(0.001, 1000.0)
        self.resolution_spin.setValue(1.0)
        self.resolution_unit = QtWidgets.QComboBox()
        self.resolution_unit.addItems(['s', 'mm'])
        self.resolution_spin.setSuffix(' s')
        self.slots_spin = QtWidgets.QSpinBox()
        self.slots_spin.setRange(1, 200)
        self.slots_spin.setValue(12)
        btn_setup_slots = QtWidgets.QPushButton('Setup Slots')
        gb_layout.addWidget(QtWidgets.QLabel('Resolution:'))
        gb_layout.addWidget(self.resolution_spin)
        gb_layout.addWidget(self.resolution_unit)
        gb_layout.addWidget(QtWidgets.QLabel('Slots:'))
        gb_layout.addWidget(self.slots_spin)
        gb_layout.addWidget(btn_setup_slots)

        top_l.addWidget(card, 1)
        top_l.addWidget(ctrl)
        top_l.addStretch()
        top_l.addWidget(gb_widget)

        layout.addWidget(top)

        # Middle: plot (70%) and builder (30%)
        middle = QtWidgets.QWidget()
        middle_l = QtWidgets.QHBoxLayout(middle)
        middle_l.setContentsMargins(0, 0, 0, 0)
        middle_l.setSpacing(12)

        self.plot = LivePlotWidget()
        middle_l.addWidget(self.plot, 7)

        builder = QtWidgets.QGroupBox('Manual Graph Builder')
        builder_layout = QtWidgets.QVBoxLayout(builder)
        builder.setMinimumWidth(480)
        builder.setMaximumWidth(520)
        middle_l.addWidget(builder, 3)

        layout.addWidget(middle)

        # Table inside builder - larger so fewer scrolls
        self.table = QtWidgets.QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels([f'X ({self.resolution_unit.currentText()})', 'Value'])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        self.table.setMinimumHeight(380)
        self.table.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        builder_layout.addWidget(self.table)

        # Action buttons
        actions = QtWidgets.QWidget()
        actions_l = QtWidgets.QVBoxLayout(actions)
        actions_l.setSpacing(6)
        btn_add_current = QtWidgets.QPushButton('Add Current to Selected')
        btn_add_next = QtWidgets.QPushButton('Add Current to Next')
        btn_build = QtWidgets.QPushButton('Build Graph')
        btn_clear = QtWidgets.QPushButton('Clear Builder')
        btn_save = QtWidgets.QPushButton('Save Builder')
        btn_load = QtWidgets.QPushButton('Load Builder')
        btn_export_svg = QtWidgets.QPushButton('Export SVG')
        actions_l.addWidget(btn_add_current)
        actions_l.addWidget(btn_add_next)
        actions_l.addWidget(btn_build)
        actions_l.addWidget(btn_clear)
        actions_l.addWidget(btn_save)
        actions_l.addWidget(btn_load)
        actions_l.addWidget(btn_export_svg)
        builder_layout.addWidget(actions)

        # Overlay controls
        overlay_row = QtWidgets.QHBoxLayout()
        self.overlay_checkbox = QtWidgets.QCheckBox('Overlay (keep existing)')
        btn_save_overlay = QtWidgets.QPushButton('Save as Overlay')
        btn_remove_overlay = QtWidgets.QPushButton('Remove Overlay')
        overlay_row.addWidget(self.overlay_checkbox)
        overlay_row.addWidget(btn_save_overlay)
        overlay_row.addWidget(btn_remove_overlay)
        builder_layout.addLayout(overlay_row)

        # overlays list
        self.overlay_list = QtWidgets.QListWidget()
        self.overlay_list.setMaximumHeight(140)
        builder_layout.addWidget(self.overlay_list)

        # internal overlay storage
        # store tuples: (label, xs, ys, color)
        self._overlays = []
        # simple color palette for overlays and manual builds (contrasting retro colors)
        self._color_palette = ['#ff3864', '#1a73e8', '#f9a825', '#00e676', '#9b59b6', '#ff6f00', '#00bcd4']
        # index for assigning next color to a manual build or overlay
        self._next_color_idx = 0

        # state
        self._sim = None
        self._lock = threading.Lock()
        self._recording = False
        self._recorded = []
        self._last_value = None

        # hook up buttons
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
        btn_save_overlay.clicked.connect(self.save_overlay)
        btn_remove_overlay.clicked.connect(self.remove_overlay)
        self.overlay_list.itemDoubleClicked.connect(self.toggle_overlay)

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
            # pick a color for this series
            color = self._color_palette[self._next_color_idx % len(self._color_palette)]
            self._next_color_idx += 1
            # if overlay checkbox is set, don't clear existing plot
            clear = not self.overlay_checkbox.isChecked()
            self.plot.plot_series(xs, ys, clear=clear, label='Manual Build', color=color, symbolBrush=color)

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

    # Overlay utilities
    def save_overlay(self):
        # read current table into xs/ys and add to overlay list with a label
        xs = []
        ys = []
        for i in range(self.table.rowCount()):
            xi = self.table.item(i, 0)
            yi = self.table.item(i, 1)
            if xi is None or yi is None:
                continue
            try:
                x = float(xi.text())
                y = float(yi.text())
            except Exception:
                continue
            xs.append(x)
            ys.append(y)
        if not xs:
            QtWidgets.QMessageBox.information(self, 'No data', 'Builder has no valid data to save as overlay.')
            return
        idx = len(self._overlays)
        color = self._color_palette[idx % len(self._color_palette)]
        label = f'Overlay {idx + 1}'
        self._overlays.append((label, xs, ys, color))
        item = QtWidgets.QListWidgetItem(label)
        # make the list item show the color as a small swatch
        item.setData(QtCore.Qt.UserRole, color)
        item.setForeground(QtGui.QBrush(QtGui.QColor(color)))
        self.overlay_list.addItem(item)

    def remove_overlay(self):
        item = self.overlay_list.currentItem()
        if not item:
            return
        idx = self.overlay_list.row(item)
        self.overlay_list.takeItem(idx)
        try:
            del self._overlays[idx]
        except Exception:
            pass
        # replot remaining overlays
        self._replot_overlays()

    def toggle_overlay(self, item):
        # double-click: plot that overlay alone (clearing others)
        idx = self.overlay_list.row(item)
        if idx < 0 or idx >= len(self._overlays):
            return
        _, xs, ys, color = self._overlays[idx]
        self.plot.plot_series(xs, ys, clear=True, label=item.text(), color=color, symbolBrush=color)

    def _replot_overlays(self):
        # clear then plot all overlays
        self.plot.clear()
        for label, xs, ys, color in self._overlays:
            self.plot.plot_series(xs, ys, clear=False, label=label, color=color, symbolBrush=color)


def main(argv):
    app = QtWidgets.QApplication(list(argv))
    # Retro 80s aesthetic: monospaced bold, square panels, sharp borders
    stylesheet = """
    QWidget { background: #071227; color: #cfeef5; font-family: 'Consolas', monospace; }
    QFrame { background: transparent; }
    QGroupBox { border: 2px solid #14424a; margin-top: 8px; border-radius: 0px; padding: 8px; }
    QGroupBox::title { subcontrol-origin: margin; left: 6px; padding: 0 4px; color: #00e676; font-weight: 700; }
    QLabel#readout { color: #00e676; font-weight: 900; }
    QLabel { color: #cfeef5; }
    QPushButton { background: #001f2a; border: 2px solid #0b5260; padding: 8px 10px; border-radius: 0px; color: #cfeef5; font-weight:700 }
    QPushButton:hover { background: #062c36; }
    QPushButton:pressed { background: #032025; }
    QTableWidget { background: #071827; gridline-color: #0b2e36; color: #cfeef5 }
    QHeaderView::section { background: #062433; color: #9be9c9; border: 1px solid #0c3942; padding: 6px; }
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { background: #06141a; border: 1px solid #0b3b4a; padding: 4px; color: #cfeef5; }
    QScrollBar:vertical { background: #061a24; width: 10px; }
    /* Improved QCheckBox indicator styling so checked state is visible */
    QCheckBox { color: #cfeef5; spacing: 6px; }
    QCheckBox::indicator { width: 16px; height: 16px; border: 2px solid #0b5260; border-radius: 2px; background: #06141a; }
    QCheckBox::indicator:unchecked { background: #06141a; border: 2px solid #0b5260; }
    QCheckBox::indicator:checked { background: #00e676; border: 2px solid #00e676; }
    QCheckBox::indicator:checked:hover { background: #32ff8a; }
    QCheckBox::indicator:disabled { background: #031216; border: 2px solid #04282b; }
    """
    app.setStyleSheet(stylesheet)
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
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

        super().__init__()
        self.setWindowTitle('FlowBench')
        self.resize(1000, 700)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        layout = QtWidgets.QVBoxLayout(central)

        # Top panel: readout card and controls
        top = QtWidgets.QWidget()
        top_l = QtWidgets.QHBoxLayout(top)

        # Readout card (retro square panel)
        card = QtWidgets.QFrame()
        card.setFrameShape(QtWidgets.QFrame.Box)
        card.setStyleSheet('background: #071227; border: 1px solid #0d3240; border-radius: 0px; padding: 12px;')
        card_l = QtWidgets.QVBoxLayout(card)
        self.readout = QtWidgets.QLabel('---')
        self.readout.setObjectName('readout')
        rfont = QtGui.QFont('IBM Plex Mono', 40, QtGui.QFont.Weight.Bold)
        self.readout.setFont(rfont)
        self.readout.setStyleSheet('color: #00e676;')
        self.unit_label = QtWidgets.QLabel('L/min')
        self.unit_label.setStyleSheet('color: #9aa7b1;')
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
                self.resize(1100, 720)

                central = QtWidgets.QWidget()
                self.setCentralWidget(central)

                layout = QtWidgets.QVBoxLayout(central)

                # Top: readout + controls
                top = QtWidgets.QWidget()
                top_l = QtWidgets.QHBoxLayout(top)

                # Readout card
                card = QtWidgets.QFrame()
                card.setFrameShape(QtWidgets.QFrame.Box)
                card.setStyleSheet("background: #071227; border: 1px solid #0d3240; border-radius: 0px; padding: 12px;")
                card_l = QtWidgets.QVBoxLayout(card)
                self.readout = QtWidgets.QLabel('---')
                self.readout.setObjectName('readout')
                rfont = QtGui.QFont('Consolas', 44, QtGui.QFont.Weight.Bold)
                self.readout.setFont(rfont)
                self.readout.setStyleSheet('color: #00e676;')
                self.unit_label = QtWidgets.QLabel('L/min')
                self.unit_label.setStyleSheet('color: #9aa7b1;')
                card_l.addWidget(self.readout)
                card_l.addWidget(self.unit_label)

                # Controls (vertical)
                ctrl = QtWidgets.QWidget()
                ctrl_l = QtWidgets.QVBoxLayout(ctrl)
                ctrl_l.setSpacing(8)
                btn_start = QtWidgets.QPushButton('Start')
                btn_stop = QtWidgets.QPushButton('Stop')
                btn_record = QtWidgets.QPushButton('Record')
                btn_start.setObjectName('btnStart')
                btn_stop.setObjectName('btnStop')
                btn_record.setObjectName('btnRecord')
                ctrl_l.addWidget(btn_start)
                ctrl_l.addWidget(btn_stop)
                ctrl_l.addWidget(btn_record)

                # small builder controls
                gb_widget = QtWidgets.QWidget()
                gb_layout = QtWidgets.QHBoxLayout(gb_widget)
                self.resolution_spin = QtWidgets.QDoubleSpinBox()
                self.resolution_spin.setRange(0.001, 1000.0)
                self.resolution_spin.setValue(1.0)
                self.resolution_unit = QtWidgets.QComboBox()
                self.resolution_unit.addItems(['s', 'mm'])
                self.resolution_spin.setSuffix(' s')
                self.slots_spin = QtWidgets.QSpinBox()
                self.slots_spin.setRange(1, 200)
                self.slots_spin.setValue(12)
                btn_setup_slots = QtWidgets.QPushButton('Setup Slots')
                gb_layout.addWidget(QtWidgets.QLabel('Resolution:'))
                gb_layout.addWidget(self.resolution_spin)
                gb_layout.addWidget(self.resolution_unit)
                gb_layout.addWidget(QtWidgets.QLabel('Slots:'))
                gb_layout.addWidget(self.slots_spin)
                gb_layout.addWidget(btn_setup_slots)

                top_l.addWidget(card, 1)
                top_l.addWidget(ctrl)
                top_l.addStretch()
                top_l.addWidget(gb_widget)

                layout.addWidget(top)

                # Middle: plot (70%) and builder (30%)
                middle = QtWidgets.QWidget()
                middle_l = QtWidgets.QHBoxLayout(middle)
                middle_l.setContentsMargins(0, 0, 0, 0)
                middle_l.setSpacing(12)

                self.plot = LivePlotWidget()
                middle_l.addWidget(self.plot, 7)

                builder = QtWidgets.QGroupBox('Manual Graph Builder')
                builder_layout = QtWidgets.QVBoxLayout(builder)
                builder.setMinimumWidth(480)
                builder.setMaximumWidth(520)
                middle_l.addWidget(builder, 3)

                layout.addWidget(middle)

                # Table inside builder - larger so fewer scrolls
                self.table = QtWidgets.QTableWidget(0, 2)
                self.table.setHorizontalHeaderLabels([f'X ({self.resolution_unit.currentText()})', 'Value'])
                self.table.horizontalHeader().setStretchLastSection(False)
                self.table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
                self.table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
                self.table.setMinimumHeight(380)
                self.table.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
                builder_layout.addWidget(self.table)

                # Action buttons
                actions = QtWidgets.QWidget()
                actions_l = QtWidgets.QVBoxLayout(actions)
                actions_l.setSpacing(6)
                btn_add_current = QtWidgets.QPushButton('Add Current to Selected')
                btn_add_next = QtWidgets.QPushButton('Add Current to Next')
                btn_build = QtWidgets.QPushButton('Build Graph')
                btn_clear = QtWidgets.QPushButton('Clear Builder')
                btn_save = QtWidgets.QPushButton('Save Builder')
                btn_load = QtWidgets.QPushButton('Load Builder')
                btn_export_svg = QtWidgets.QPushButton('Export SVG')
                actions_l.addWidget(btn_add_current)
                actions_l.addWidget(btn_add_next)
                actions_l.addWidget(btn_build)
                actions_l.addWidget(btn_clear)
                actions_l.addWidget(btn_save)
                actions_l.addWidget(btn_load)
                actions_l.addWidget(btn_export_svg)
                builder_layout.addWidget(actions)

                # Overlay controls
                overlay_row = QtWidgets.QHBoxLayout()
                self.overlay_checkbox = QtWidgets.QCheckBox('Overlay (keep existing)')
                btn_save_overlay = QtWidgets.QPushButton('Save as Overlay')
                btn_remove_overlay = QtWidgets.QPushButton('Remove Overlay')
                overlay_row.addWidget(self.overlay_checkbox)
                overlay_row.addWidget(btn_save_overlay)
                overlay_row.addWidget(btn_remove_overlay)
                builder_layout.addLayout(overlay_row)

                # overlays list
                self.overlay_list = QtWidgets.QListWidget()
                self.overlay_list.setMaximumHeight(140)
                builder_layout.addWidget(self.overlay_list)

                # internal overlay storage
                self._overlays = []

                # state
                self._sim = None
                self._lock = threading.Lock()
                self._recording = False
                self._recorded = []
                self._last_value = None

                # hook up buttons
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
                btn_save_overlay.clicked.connect(self.save_overlay)
                btn_remove_overlay.clicked.connect(self.remove_overlay)
                self.overlay_list.itemDoubleClicked.connect(self.toggle_overlay)

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
                    # if overlay checkbox is set, don't clear existing plot
                    clear = not self.overlay_checkbox.isChecked()
                    self.plot.plot_series(xs, ys, clear=clear, label='Manual Build')

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

            # Overlay utilities
            def save_overlay(self):
                # read current table into xs/ys and add to overlay list with a label
                xs = []
                ys = []
                for i in range(self.table.rowCount()):
                    xi = self.table.item(i, 0)
                    yi = self.table.item(i, 1)
                    if xi is None or yi is None:
                        continue
                    try:
                        x = float(xi.text())
                        y = float(yi.text())
                    except Exception:
                        continue
                    xs.append(x)
                    ys.append(y)
                if not xs:
                    QtWidgets.QMessageBox.information(self, 'No data', 'Builder has no valid data to save as overlay.')
                    return
                label = f'Overlay {len(self._overlays) + 1}'
                self._overlays.append((label, xs, ys))
                self.overlay_list.addItem(label)

            def remove_overlay(self):
                item = self.overlay_list.currentItem()
                if not item:
                    return
                idx = self.overlay_list.row(item)
                self.overlay_list.takeItem(idx)
                try:
                    del self._overlays[idx]
                except Exception:
                    pass
                # replot remaining overlays
                self._replot_overlays()

            def toggle_overlay(self, item):
                # double-click: plot that overlay alone (clearing others)
                idx = self.overlay_list.row(item)
                if idx < 0 or idx >= len(self._overlays):
                    return
                _, xs, ys = self._overlays[idx]
                self.plot.plot_series(xs, ys, clear=True, label=item.text())

            def _replot_overlays(self):
                # clear then plot all overlays
                self.plot.clear()
                for label, xs, ys in self._overlays:
                    self.plot.plot_series(xs, ys, clear=False, label=label)


        def main(argv):
            app = QtWidgets.QApplication(list(argv))
            # Retro 80s aesthetic: monospaced bold, square panels, sharp borders
            stylesheet = """
            QWidget { background: #071227; color: #cfeef5; font-family: 'Consolas', monospace; }
            QFrame { background: transparent; }
            QGroupBox { border: 2px solid #14424a; margin-top: 8px; border-radius: 0px; padding: 8px; }
            QGroupBox::title { subcontrol-origin: margin; left: 6px; padding: 0 4px; color: #00e676; font-weight: 700; }
            QLabel#readout { color: #00e676; font-weight: 900; }
            QLabel { color: #cfeef5; }
            QPushButton { background: #001f2a; border: 2px solid #0b5260; padding: 8px 10px; border-radius: 0px; color: #cfeef5; font-weight:700 }
            QPushButton:hover { background: #062c36; }
            QPushButton:pressed { background: #032025; }
            QTableWidget { background: #071827; gridline-color: #0b2e36; color: #cfeef5 }
            QHeaderView::section { background: #062433; color: #9be9c9; border: 1px solid #0c3942; padding: 6px; }
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { background: #06141a; border: 1px solid #0b3b4a; padding: 4px; color: #cfeef5; }
            QScrollBar:vertical { background: #061a24; width: 10px; }
            """
            app.setStyleSheet(stylesheet)
            w = MainWindow()
            w.show()
            return app.exec()


        if __name__ == '__main__':
            raise SystemExit(main(sys.argv))
