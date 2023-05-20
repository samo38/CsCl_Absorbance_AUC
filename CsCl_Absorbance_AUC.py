from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTableWidgetItem,
                               QPushButton, QFileDialog, QMessageBox, QTableWidget, QHeaderView, QAbstractItemView)
from PySide6.QtCore import (Qt, Slot, Signal)
from PySide6.QtGui import QColor
import numpy as np
import pyqtgraph
import sys
import os
import glob


def str2float(x):
    try:
        return float(x)
    except ValueError:
        return None


def dict_keys_list(x: dict):
    keys = []
    for k in x.keys():
        keys.append(k)
    keys.sort()
    return keys


def parse_file(file_path):
    with open(file_path) as fid:
        lines = fid.readlines()
    if len(lines) < 3:
        return []
    x_values = []
    y_values = []
    min_x = 5.8
    max_x = 7.2
    for i in range(2, len(lines)):
        lsp = lines[i].split()
        if len(lsp) == 3:
            x = str2float(lsp[0])
            y = str2float(lsp[1])
            if x is not None and y is not None:
                # x_r = round(x, 3)
                if min_x <= x <= max_x:
                    x_values.append(x)
                    y_values.append(y)
    if len(x_values) > 0 and len(y_values) > 0:
        return np.array(x_values, dtype=np.float32), np.array(y_values, dtype=np.float32)
    else:
        return []


def get_file_info(f_name: str):
    dot_sp = f_name.split(".")
    if len(dot_sp) != 2 or len(dot_sp[1]) != 3:
        return []
    if dot_sp[1][0: 2] != "ra" and dot_sp[1][0: 2] != "ri":
        return []
    dash_sp = dot_sp[0].split("-")
    if len(dash_sp) != 7:
        return []
    run_id = dash_sp[0]
    cell = int(dash_sp[2][1:])
    scan = int(dash_sp[3][1:])
    wavelength = int(dash_sp[4][1: 4])
    return run_id, cell, scan, wavelength


def compare_x_array(arr1: np.array, arr2: np.array):
    len_chk = len(arr1) == len(arr2)
    i_chk = round(arr1[0], 3) == round(arr2[0], 3)
    f_chk = round(arr1[-1], 3) == round(arr2[-1], 3)
    if len_chk and i_chk and f_chk:
        return True
    else:
        return False


class MainWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(600, 400)
        self.setWindowTitle("Beckman Absorbance Analysis")
        self.absorbance = list()
        self.cell_wavelength_scan = dict()
        self.cell_integral = dict()
        self.run_id = None
        self.cell_minmax = dict()
        self.curve_list = dict()
        self.cell_last_scans = dict()
        self.current_cell = 0
        self.current_wavelengths = list()
        self.colors = [
            QColor(255, 255, 255),    # White
            QColor(255, 0, 0),        # Red
            QColor(0, 255, 0),        # Lime
            QColor(0, 0, 255),        # Blue
            QColor(255, 255, 0),      # Yellow
            QColor(0, 255, 255),      # Cyan
            QColor(255, 0, 255),      # Magenta
            QColor(192, 192, 192),    # Silver
            QColor(128, 128, 128),    # Gray
            QColor(128, 128, 0),      # Olive
            QColor(0, 128, 0),        # Green
            QColor(128, 0, 128),      # Purple
        ]

        self.pb_load = QPushButton("Load")
        self.pb_report = QPushButton("Report")

        lyt_load = QHBoxLayout()
        lyt_load.setContentsMargins(0, 0, 0, 0)
        lyt_load.setSpacing(2)
        lyt_load.addWidget(self.pb_load)
        lyt_load.addWidget(self.pb_report)
        lyt_load.addStretch(1)

        self.tw_cell = QTableWidget()
        self.tw_cell.setColumnCount(1)
        self.tw_cell.setRowCount(0)
        self.tw_cell.setHorizontalHeaderLabels(["Cell"])
        self.tw_cell.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tw_cell.verticalHeader().setVisible(False)
        self.tw_cell.setSelectionMode(QAbstractItemView.SingleSelection)

        self.tw_lamda = QTableWidget()
        self.tw_lamda.setColumnCount(1)
        self.tw_lamda.setRowCount(0)
        self.tw_lamda.setHorizontalHeaderLabels(["Lamda"])
        self.tw_lamda.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tw_lamda.verticalHeader().setVisible(False)
        # self.tw_lamda.setSelectionMode(QAbstractItemView.ExtendedSelection)

        self.tw_scan = QTableWidget()
        self.tw_scan.setColumnCount(1)
        self.tw_scan.setRowCount(0)
        self.tw_scan.setHorizontalHeaderLabels(["Scan"])
        self.tw_scan.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tw_scan.verticalHeader().setVisible(False)

        lyt_tables = QHBoxLayout()
        lyt_tables.setContentsMargins(0, 0, 0, 0)
        lyt_tables.setSpacing(1)
        lyt_tables.addWidget(self.tw_cell)
        lyt_tables.addWidget(self.tw_lamda)
        lyt_tables.addWidget(self.tw_scan)

        lyt_left = QVBoxLayout()
        lyt_left.setContentsMargins(0, 0, 0, 0)
        lyt_left.addLayout(lyt_load)
        lyt_left.addLayout(lyt_tables)
        lyt_left.setSpacing(5)

        plt_win = pyqtgraph.GraphicsLayoutWidget()
        self.figure_scans = plt_win.addPlot(title="Scans")
        self.figure_scans.getAxis("bottom").setLabel(text="Radial Points (cm)")
        self.figure_scans.getAxis("left").setLabel(text="Absorbance")
        self.figure_area = plt_win.addPlot(title="Integral")
        self.figure_area.getAxis("bottom").setLabel(text="Wavelength (nm)")
        self.figure_area.getAxis("left").setLabel(text="Total Absorbance")

        pen = pyqtgraph.mkPen(color='w', width=3)
        self.region_picker = pyqtgraph.LinearRegionItem(pen=pen)

        self.pb_region = QPushButton("Set Region")
        self.pb_region.setCheckable(True)
        self.pb_region.setStyleSheet(u"background-color: rgb(249, 240, 107);")
        self.pb_region.setMaximumWidth(150)
        self.pb_region.setDisabled(True)

        self.pb_integral = QPushButton("Calculate Integral(s)")
        self.pb_integral.setStyleSheet(u"background-color: rgb(249, 240, 107);")
        self.pb_integral.setDisabled(True)

        lyt_reg_int = QHBoxLayout()
        lyt_reg_int.setContentsMargins(0, 0, 0, 0)
        lyt_reg_int.addWidget(self.pb_region)
        lyt_reg_int.addStretch(1)
        lyt_reg_int.addWidget(self.pb_integral)

        lyt_right = QVBoxLayout()
        lyt_right.setContentsMargins(0, 0, 0, 0)
        lyt_right.setSpacing(1)
        lyt_right.addLayout(lyt_reg_int)
        lyt_right.addWidget(plt_win)

        lyt_main = QHBoxLayout()
        lyt_main.setContentsMargins(1, 1, 1, 1)
        lyt_main.addLayout(lyt_left, 1)
        lyt_main.addLayout(lyt_right, 3)
        lyt_main.setSpacing(2)

        self.setLayout(lyt_main)

        self.pb_load.clicked.connect(self.load_data)
        self.tw_cell.currentItemChanged.connect(self.update_tw_lambda)
        self.tw_lamda.itemSelectionChanged.connect(self.update_tw_scan)
        self.tw_scan.cellClicked.connect(self.update_scan_state)
        self.pb_region.clicked.connect(self.update_region)
        self.pb_integral.clicked.connect(self.plot_integral)
        self.pb_report.clicked.connect(self.report)

    @Slot()
    def load_data(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Directory",
                                                     os.path.expanduser('~'), QFileDialog.ShowDirsOnly)
        if len(directory) == 0:
            return

        search_str = os.path.join(directory, "*.ra*")
        glob_list = glob.glob(search_str)
        absorbance = []
        run_id = None
        for i in range(len(glob_list)):
            fpath = glob_list[i]
            file_info = get_file_info(os.path.split(fpath)[1])
            if len(file_info) == 0:
                continue
            file_parsed = parse_file(fpath)
            if len(file_parsed) == 0:
                continue
            run_id_c, cell, scan, wavelength = file_info[0], file_info[1], file_info[2], file_info[3]
            x_vals, y_vals = file_parsed[0], file_parsed[1]
            if run_id is None:
                run_id = run_id_c
            else:
                if run_id != run_id_c:
                    QMessageBox.warning(self, "Error!", f"More than one run ID found:\n{self.run_id}\n{run_id}")
                    return
            abs_data = dict()
            abs_data["x_values"] = x_vals
            abs_data["y_values"] = y_vals
            abs_data["cell"] = cell
            abs_data["wavelength"] = wavelength
            abs_data["scan"] = scan
            abs_data["state"] = True
            abs_data["min_id"] = 0
            abs_data["max_id"] = np.size(x_vals)
            absorbance.append(abs_data)

        if len(absorbance) == 0:
            QMessageBox.warning(self, "Warning!", "No 'RA' files found!")
            return
        self.clear_data()
        self.run_id = run_id
        self.absorbance = absorbance
        for abs_id in range(len(absorbance)):
            abs_data = absorbance[abs_id]
            cell = abs_data.get("cell")
            wavelength = abs_data.get("wavelength")
            scan = abs_data.get("scan")
            wavelength_scan_list = self.cell_wavelength_scan.get(cell)
            if wavelength_scan_list is None:
                wavelength_scan_list = dict()
            scan_list = wavelength_scan_list.get(wavelength)
            if scan_list is None:
                scan_list = dict()
            scan_list[scan] = abs_id
            wavelength_scan_list[wavelength] = scan_list
            self.cell_wavelength_scan[cell] = wavelength_scan_list
            self.absorbance.append(abs_data)

        for cell, wavelength_scan in self.cell_wavelength_scan.items():
            self.cell_minmax[cell] = [None, None]
            self.cell_integral[cell] = None

            last_scans = []
            for wavelength, scan in wavelength_scan.items():
                last_key = -100
                for key in scan.keys():
                    last_key = max(key, last_key)
                last_scans.append(scan.get(last_key))
            self.cell_last_scans[cell] = last_scans

        self.pb_region.setEnabled(True)
        self.pb_integral.setEnabled(True)
        self.set_tw_cell()

    @Slot()
    def report(self):
        cell_list = []
        data_list = []
        n_row_list = []
        for key, val in self.cell_integral.items():
            if val is None:
                continue
            cell_list.append(key)
            data_list.append(val)
            n_row_list.append(len(val[0]))
        n_cell = len(cell_list)
        if n_cell == 0:
            QMessageBox.warning(self, "Warning", "Integral profiles not found!")
            return
        ft = QFileDialog.getSaveFileName(self, "Save CSV File", os.path.expanduser('~'), "*.csv")
        file_name = ft[0]
        if len(file_name) == 0:
            return

        temp_name = file_name.lower()
        if not temp_name.endswith(".csv"):
            file_name += ".csv"
        header = True
        with open(file_name, 'w') as fid:
            row = 0
            while True:
                if header:
                    line = ""
                    for i in range(n_cell):
                        line += f"Cell_{cell_list[i]}_lambda,Cell_{cell_list[i]}_OD,"
                        line += f"Cell_{cell_list[i]}_STD"
                        if i == n_cell - 1:
                            line += "\n"
                        else:
                            line += ","
                    header = False
                    fid.write(line)
                has_data = False
                line = ""
                for i in range(n_cell):
                    if row >= n_row_list[i]:
                        has_data = has_data or False
                        line += ",,"
                    else:
                        has_data = has_data or True
                        data = data_list[i]
                        line += f"{data[0][row]},{data[1][row]},{data[2][row]}"
                    if i == n_cell - 1:
                        line += "\n"
                    else:
                        line += ","
                if has_data:
                    fid.write(line)
                    row += 1
                else:
                    break

    @Slot(object, object)
    def update_tw_lambda(self, c_item, p_item):
        cell = int(c_item.text())
        self.current_cell = cell
        self.current_wavelengths.clear()
        wavelength_list = dict_keys_list(self.cell_wavelength_scan.get(cell))
        self.tw_lamda.itemSelectionChanged.disconnect(self.update_tw_scan)
        self.tw_lamda.clear()
        self.tw_lamda.setRowCount(len(wavelength_list))
        for i in range(len(wavelength_list)):
            item = QTableWidgetItem(str(wavelength_list[i]))
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.tw_lamda.setItem(i, 0, item)
        self.tw_lamda.setHorizontalHeaderLabels(["Lambda"])
        self.tw_lamda.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tw_lamda.itemSelectionChanged.connect(self.update_tw_scan)
        if len(wavelength_list) > 0:
            self.tw_lamda.setCurrentCell(0, 0)

    @Slot()
    def update_tw_scan(self):
        cell = self.current_cell
        # wavelength_scan_list = self.cell_wavelength_scan.get(cell)
        wavelength_list = [int(item.text()) for item in self.tw_lamda.selectedItems()]
        if len(wavelength_list) == 0:
            row = self.tw_lamda.currentRow()
            wavelength_list = [int(self.tw_lamda.item(row, 0).text())]
        self.current_wavelengths = wavelength_list
        if len(wavelength_list) == 1:
            wavelength = int(wavelength_list[0])
            scan_list = dict_keys_list(self.cell_wavelength_scan.get(cell).get(wavelength))
            self.tw_scan.cellClicked.disconnect(self.update_scan_state)
            self.tw_scan.clear()
            self.tw_scan.setRowCount(len(scan_list))
            row = 0
            scan_dict = self.cell_wavelength_scan.get(cell).get(wavelength)
            for i in range(len(scan_list)):
                abs_id = scan_dict.get(scan_list[i])
                state = self.absorbance[abs_id].get("state")
                item = QTableWidgetItem(str(scan_list[i]))
                item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                if state:
                    item.setCheckState(Qt.CheckState.Checked)
                else:
                    item.setCheckState(Qt.CheckState.Unchecked)
                self.tw_scan.setItem(row, 0, item)
                row += 1
            self.tw_scan.setHorizontalHeaderLabels(["Scan"])
            self.tw_scan.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
            self.tw_scan.cellClicked.connect(self.update_scan_state)
        else:
            self.tw_scan.cellClicked.disconnect(self.update_scan_state)
            self.tw_scan.clear()
            self.tw_scan.setRowCount(0)
            self.tw_scan.setHorizontalHeaderLabels(["Scan"])
            self.tw_scan.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
            self.tw_scan.cellClicked.connect(self.update_scan_state)
        self.plot_scans()

    @Slot(int, int)
    def update_scan_state(self, row, col):
        cell = self.current_cell
        wavelength = self.current_wavelengths[0]
        item = self.tw_scan.item(row, col)
        scan = int(item.text())
        abs_id = self.cell_wavelength_scan.get(cell).get(wavelength).get(scan)
        if item.checkState() == Qt.CheckState.Checked:
            self.absorbance[abs_id]["state"] = True
        else:
            self.absorbance[abs_id]["state"] = False
        self.plot_scans()

    @Slot(bool)
    def update_region(self, checked):
        if checked:
            self.pb_region.setText("Apply")
            self.pb_region.setStyleSheet(u"background-color: rgb(143, 240, 164);")
            self.pick_region(1)
            self.pb_load.setDisabled(True)
            self.pb_report.setDisabled(True)
            self.tw_scan.setDisabled(True)
            self.tw_lamda.setDisabled(True)
            self.tw_scan.setDisabled(True)
        else:
            self.pb_region.setText("Set Region")
            self.pb_region.setStyleSheet(u"background-color: rgb(249, 240, 107);")
            self.pick_region(0)
            self.pb_load.setEnabled(True)
            self.pb_report.setEnabled(True)
            self.tw_scan.setEnabled(True)
            self.tw_lamda.setEnabled(True)
            self.tw_scan.setEnabled(True)

    @Slot()
    def plot_integral(self):
        self.figure_area.clear()
        self.figure_area.addLegend()
        counter = -1
        for cell in self.cell_wavelength_scan.keys():
            counter += 1
            [min_x, max_x] = self.cell_minmax.get(cell)
            if min_x is None or max_x is None:
                continue
            wavelength_vec = []
            integral_vec = []
            std_vec = []
            for wavelength in self.cell_wavelength_scan.get(cell).keys():
                int_list = []
                for abs_id in self.cell_wavelength_scan.get(cell).get(wavelength).values():
                    abs_data = self.absorbance[abs_id]
                    state = abs_data.get("state")
                    if not state:
                        continue
                    x_val = abs_data.get("x_values")
                    y_val = abs_data.get("y_values")
                    min_id = abs_data.get("min_id")
                    max_id = abs_data.get("max_id")
                    area = np.trapz(y_val[min_id: max_id], x_val[min_id: max_id])
                    int_list.append(area)
                if len(int_list) == 0:
                    continue
                wavelength_vec.append(wavelength)
                int_list = np.array(int_list, dtype=np.float32)
                integral_vec.append(np.mean(int_list))
                std_vec.append(np.std(int_list))

            if len(wavelength_vec) == 0:
                self.cell_integral[cell] = None
                continue
            wavelength_vec = np.array(wavelength_vec, dtype=np.float32)
            integral_vec = np.array(integral_vec, dtype=np.float32)
            std_vec = np.array(std_vec, dtype=np.float32)
            argsort = np.argsort(wavelength_vec)
            cell_integral = list()
            wavelength_vec = wavelength_vec[argsort]
            integral_vec = integral_vec[argsort]
            std_vec = std_vec[argsort]
            cell_integral.append(wavelength_vec)
            cell_integral.append(integral_vec)
            cell_integral.append(std_vec)
            self.cell_integral[cell] = cell_integral

            pen = pyqtgraph.mkPen(color=self.colors[counter % len(self.colors)], width=2)
            self.figure_area.plot(wavelength_vec, integral_vec, pen=pen, name=str(cell))

    def clear_data(self):
        self.absorbance.clear()
        self.cell_wavelength_scan.clear()
        self.cell_integral.clear()
        self.run_id = None
        self.cell_minmax.clear()
        self.curve_list.clear()
        self.cell_last_scans.clear()
        self.current_cell = 0
        self.current_wavelengths.clear()

    def plot_last_scans(self):
        cell = self.current_cell
        last_scans = self.cell_last_scans.get(cell)
        self.figure_scans.clear()
        pen = pyqtgraph.mkPen(color='yellow', width=1)
        for abs_id in last_scans:
            abs_data = self.absorbance[abs_id]
            min_id = abs_data.get("min_id")
            max_id = abs_data.get("max_id")
            x_vals = abs_data.get("x_values")[min_id: max_id]
            y_vals = abs_data.get("y_values")[min_id: max_id]
            cell = abs_data.get("cell")
            self.figure_scans.setTitle(title=f"Cell {cell}")
            curve = self.figure_scans.plot(pen=pen)
            curve.setData(x_vals, y_vals)

    def plot_scans(self):
        self.figure_scans.clear()
        cell = self.current_cell
        wavelength_keys = self.current_wavelengths
        if len(wavelength_keys) == 1:
            flag_title = "SINGLE"
        else:
            flag_title = "MULTIPLE"
        pen = pyqtgraph.mkPen(color='magenta', width=1)

        wavelength_scan = self.cell_wavelength_scan.get(cell)
        for wavelength in wavelength_keys:
            for scan, abs_id in wavelength_scan.get(wavelength).items():
                abs_data = self.absorbance[abs_id]
                if not abs_data.get("state"):
                    continue
                min_id = abs_data.get("min_id")
                max_id = abs_data.get("max_id")
                x_vals = abs_data.get("x_values")[min_id: max_id]
                y_vals = abs_data.get("y_values")[min_id: max_id]
                cell = abs_data.get("cell")
                if flag_title == "SINGLE":
                    wavelength = abs_data.get("wavelength")
                    self.figure_scans.setTitle(title=f"Cell {cell} at {wavelength} (nm)")
                    flag_title = ""
                elif flag_title == "MULTIPLE":
                    self.figure_scans.setTitle(title=f"Cell {cell}, multiple wavelengths")
                    flag_title = ""
                curve = self.figure_scans.plot(pen=pen)
                curve.setData(x_vals, y_vals)

    def set_tw_cell(self):
        self.tw_cell.currentItemChanged.disconnect(self.update_tw_lambda)
        self.tw_cell.clear()
        cell_list = dict_keys_list(self.cell_wavelength_scan)
        self.tw_cell.setRowCount(len(cell_list))
        for i in range(len(cell_list)):
            item = QTableWidgetItem(str(cell_list[i]))
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.tw_cell.setItem(i, 0, item)
        self.tw_cell.setHorizontalHeaderLabels(["Cell"])
        self.tw_cell.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tw_cell.currentItemChanged.connect(self.update_tw_lambda)
        if len(cell_list) > 0:
            self.tw_cell.setCurrentCell(0, 0)

    def pick_region(self, state: int):
        cell = self.current_cell
        if state == 1:  # connect picker
            self.plot_last_scans()
            [min_x, max_x] = self.cell_minmax.get(cell)
            if min_x is None or max_x is None:
                min_x = 5.8
                max_x = 7.2
            self.region_picker.setRegion([min_x, max_x])
            self.figure_scans.addItem(self.region_picker)
        elif state == 0:  # accept and close picker
            [min_val, max_val] = self.region_picker.getRegion()
            self.cell_minmax[cell] = [min_val, max_val]
            self.apply_region()
            self.plot_scans()

    def apply_region(self):
        cell = self.current_cell
        [min_x, max_x] = self.cell_minmax.get(cell)
        wavelength_scan = self.cell_wavelength_scan.get(cell)
        for wavelength, scan in wavelength_scan.items():
            for abs_id in scan.values():
                abs_data = self.absorbance[abs_id]
                x_val = abs_data.get("x_values")
                trim_b = np.logical_and(x_val >= min_x, x_val <= max_x)
                trim_ids = np.where(trim_b)[0]
                if len(trim_ids) < 10:
                    min_id = 0
                    max_id = len(x_val)
                else:
                    min_id = trim_ids[0]
                    max_id = trim_ids[-1]
                self.absorbance[abs_id]["min_id"] = min_id
                self.absorbance[abs_id]["max_id"] = max_id


if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
