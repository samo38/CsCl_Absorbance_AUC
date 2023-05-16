from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTableWidgetItem,
                               QPushButton, QFileDialog, QMessageBox, QTableWidget, QHeaderView, QCheckBox)
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


def get_n_dict_items(x: dict):
    counter = 0
    for _ in x.items():
        counter += 1
    return counter


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
        self.index_matrix = None
        self.absorbance = list()
        self.integral = dict()
        self.run_id = None
        self.cell = dict()
        self.cell_minmax = dict()
        self.wavelength = dict()
        self.scan = dict()
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

        self.tw_lamda = QTableWidget()
        self.tw_lamda.setColumnCount(1)
        self.tw_lamda.setRowCount(0)
        self.tw_lamda.setHorizontalHeaderLabels(["Lamda"])
        self.tw_lamda.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tw_lamda.verticalHeader().setVisible(False)

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
        self.tw_cell.cellClicked.connect(self.update_lambda)
        self.tw_lamda.cellClicked.connect(self.update_scan)
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
        self.clear_data()
        search_str = os.path.join(directory, "*.ra*")
        glob_list = glob.glob(search_str)
        wavelength_list = list()
        cell_list = list()
        scan_list = list()
        for i in range(len(glob_list)):
            fpath = glob_list[i]
            file_info = get_file_info(os.path.split(fpath)[1])
            if len(file_info) == 0:
                continue
            file_parsed = parse_file(fpath)
            if len(file_parsed) == 0:
                continue
            run_id, cell, scan, wavelength = file_info[0], file_info[1], file_info[2], file_info[3]
            x_vals, y_vals = file_parsed[0], file_parsed[1]
            if self.run_id is None:
                self.run_id = run_id
            else:
                if self.run_id != run_id:
                    QMessageBox.warning(self, "Error!", f"More than one run ID found:\n{self.run_id}\n{run_id}")
                    self.clear_data()
                    return
            if wavelength not in wavelength_list:
                wavelength_list.append(wavelength)
            if cell not in cell_list:
                cell_list.append(cell)
            if scan not in scan_list:
                scan_list.append(scan)
            abs_data = dict()
            abs_data["x_values"] = x_vals
            abs_data["y_values"] = y_vals
            abs_data["cell"] = cell
            abs_data["wavelength"] = wavelength
            abs_data["scan"] = scan
            abs_data["state"] = True
            abs_data["min_id"] = 0
            abs_data["max_id"] = np.size(x_vals)
            self.absorbance.append(abs_data)

        cell_list.sort()
        wavelength_list.sort()
        scan_list.sort()
        n_cell = len(cell_list)
        n_wavelength = len(wavelength_list)
        n_scans = len(scan_list)

        self.index_matrix = np.ones([n_cell, n_wavelength, n_scans], dtype=np.int32) * -1
        for i in range(n_cell):
            self.cell[cell_list[i]] = i
            self.cell_minmax[cell_list[i]] = [None, None]
            self.integral[cell_list[i]] = None

        for i in range(n_wavelength):
            self.wavelength[wavelength_list[i]] = i

        for i in range(n_scans):
            self.scan[scan_list[i]] = i

        for i in range(len(self.absorbance)):
            abs_data = self.absorbance[i]
            cell = abs_data.get("cell")
            wavelength = abs_data.get("wavelength")
            scan = abs_data.get("scan")
            id_cell = self.cell.get(cell)
            id_wavelength = self.wavelength.get(wavelength)
            id_scan = self.scan.get(scan)
            self.index_matrix[id_cell, id_wavelength, id_scan] = i
        self.pb_region.setEnabled(True)
        self.pb_integral.setEnabled(True)
        self.set_cell_table()

    @Slot()
    def report(self):
        cell_list = []
        data_list = []
        n_row_list = []
        for key, val in self.integral.items():
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

    @Slot(int, int)
    def update_lambda(self, row, col):
        cell_id = self.get_item_id(self.tw_cell.item(row, col), "cell")
        wavelength_scan_mat = self.index_matrix[cell_id]
        bool_vec = np.any(wavelength_scan_mat >= 0, axis=1)
        wavelength_ids = np.where(bool_vec)[0]
        wavelength_list = []
        for i in wavelength_ids:
            for key, value in self.wavelength.items():
                if value == i:
                    wavelength_list.append(key)
                    break
        wavelength_list.sort()

        self.tw_lamda.cellClicked.disconnect(self.update_scan)
        self.tw_lamda.clear()
        self.tw_lamda.setRowCount(len(wavelength_list))
        row = 0
        for wavelength in wavelength_list:
            item = QTableWidgetItem(str(wavelength))
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.tw_lamda.setItem(row, 0, item)
            row += 1
        self.tw_lamda.setHorizontalHeaderLabels(["Lambda"])
        self.tw_lamda.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tw_lamda.cellClicked.connect(self.update_scan)
        if row > 0:
            self.tw_lamda.setCurrentCell(0, 0)
            self.update_scan(0, 0)

    @Slot(int, int)
    def update_scan(self, row, col):
        cell_id = self.get_item_id(self.tw_cell.currentItem(), "cell")
        wavelength_id = self.get_item_id(self.tw_lamda.item(row, col), "lambda")
        bool_vec = self.index_matrix[cell_id, wavelength_id] >= 0
        scan_ids = np.where(bool_vec)[0]
        scan_list = []
        for i in scan_ids:
            for key, value in self.scan.items():
                if value == i:
                    scan_list.append(key)
                    break
        scan_list.sort()

        self.tw_scan.cellClicked.disconnect(self.update_scan_state)
        self.tw_scan.clear()
        self.tw_scan.setRowCount(len(scan_list))
        row = 0
        for scan in scan_list:
            scan_id = self.scan.get(scan)
            abs_id = self.index_matrix[cell_id, wavelength_id, scan_id]
            state = self.absorbance[abs_id].get("state")
            item = QTableWidgetItem(str(scan))
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
        self.plot_profile()

    @Slot(int, int)
    def update_scan_state(self, row, col):
        cell_id = self.get_item_id(self.tw_cell.currentItem(), "cell")
        wavelength_id = self.get_item_id(self.tw_lamda.currentItem(), "lambda")
        item = self.tw_scan.item(row, col)
        scan_id = self.get_item_id(item, "scan")
        abs_id = self.index_matrix[cell_id, wavelength_id, scan_id]
        if item.checkState() == Qt.CheckState.Checked:
            self.absorbance[abs_id]["state"] = True
        else:
            self.absorbance[abs_id]["state"] = False
        self.plot_profile()

    @Slot(bool)
    def update_region(self, checked):
        if checked:
            self.pb_region.setText("Apply")
            self.pb_region.setStyleSheet(u"background-color: rgb(143, 240, 164);")
            self.pick_region(1)
        else:
            self.pb_region.setText("Set Region")
            self.pb_region.setStyleSheet(u"background-color: rgb(249, 240, 107);")
            self.pick_region(0)

    @Slot()
    def plot_integral(self):
        self.figure_area.clear()
        self.figure_area.addLegend()
        shape = self.index_matrix.shape
        n_cell = shape[0]
        n_wavelength = shape[1]
        n_scan = shape[2]
        for i in range(n_cell):
            cell_item = self.tw_cell.item(i, 0)
            cell_key = int(cell_item.text())
            [min_x, max_x] = self.cell_minmax.get(cell_key)
            if min_x is None or max_x is None:
                continue
            wavelength_vec = []
            integral_vec = []
            std_vec = []
            for j in range(n_wavelength):
                int_list = []
                for k in range(n_scan):
                    abs_id = self.index_matrix[i, j, k]
                    if abs_id < 0:
                        continue
                    abs_data = self.absorbance[abs_id]
                    x_val = abs_data.get("x_values")
                    y_val = abs_data.get("y_values")
                    state = abs_data.get("state")
                    min_id = abs_data.get("min_id")
                    max_id = abs_data.get("max_id")
                    if not state:
                        continue
                    area = np.trapz(y_val[min_id: max_id], x_val[min_id: max_id])
                    int_list.append(area)
                lambda_key = -1
                for key, val in self.wavelength.items():
                    if val == j:
                        lambda_key = key
                        break
                if lambda_key != -1:
                    wavelength_vec.append(lambda_key)
                    int_list = np.array(int_list, dtype=np.float32)
                    integral_vec.append(np.mean(int_list))
                    std_vec.append(np.std(int_list))
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
            self.integral[cell_key] = cell_integral

            pen = pyqtgraph.mkPen(color=self.colors[i % len(self.colors)], width=2)
            self.figure_area.plot(wavelength_vec, integral_vec, pen=pen, name=str(cell_key))

    def clear_data(self):
        self.index_matrix = None
        self.absorbance.clear()
        self.run_id = None
        self.integral.clear()
        self.cell.clear()
        self.cell_minmax.clear()
        self.wavelength.clear()
        self.scan.clear()

    def get_item_id(self, item, item_type):
        key = int(item.text())
        if item_type == "cell":
            return self.cell.get(key)
        elif item_type == "lambda":
            return self.wavelength.get(key)
        elif item_type == "scan":
            return self.scan.get(key)
        else:
            return None

    def plot_profile(self, all_lambdas=False):
        cell_id = self.get_item_id(self.tw_cell.currentItem(), "cell")
        wavelength_id = self.get_item_id(self.tw_lamda.currentItem(), "lambda")
        if all_lambdas:
            abs_ids = self.index_matrix[cell_id][:][-1]
        else:
            abs_ids = []
            for i in range(self.tw_scan.rowCount()):
                item = self.tw_scan.item(i, 0)
                scan_id = self.get_item_id(item, "scan")
                abs_ids.append(self.index_matrix[cell_id, wavelength_id, scan_id])

        self.figure_scans.clear()

        if all_lambdas:
            flag_title = 0
        else:
            flag_title = 1
        for index in abs_ids:
            if index < 0:
                continue
            abs_data = self.absorbance[index]
            if not abs_data.get("state"):
                continue
            min_id = abs_data.get("min_id")
            max_id = abs_data.get("max_id")
            x_vals = abs_data.get("x_values")[min_id: max_id]
            y_vals = abs_data.get("y_values")[min_id: max_id]
            if flag_title == 0:
                cell = abs_data.get("cell")
                self.figure_scans.setTitle(title=f"Cell {cell}")
                flag_title = -1
            elif flag_title == 1:
                cell = abs_data.get("cell")
                wavelength = abs_data.get("wavelength")
                self.figure_scans.setTitle(title=f"Cell {cell} at {wavelength} (nm)")
                flag_title = -1

            pen = pyqtgraph.mkPen(color='magenta', width=2)
            curve = self.figure_scans.plot(pen=pen)
            curve.setData(x_vals, y_vals)

    def set_cell_table(self):
        self.tw_cell.cellClicked.disconnect(self.update_lambda)
        self.tw_cell.clear()
        self.tw_cell.setRowCount(get_n_dict_items(self.cell))
        row = 0
        for cell in self.cell.keys():
            item = QTableWidgetItem(str(cell))
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.tw_cell.setItem(row, 0, item)
            row += 1
        self.tw_cell.setHorizontalHeaderLabels(["Cell"])
        self.tw_cell.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tw_cell.cellClicked.connect(self.update_lambda)
        if row > 0:
            self.tw_cell.setCurrentCell(0, 0)
            self.update_lambda(0, 0)

    def pick_region(self, state: int):
        cell_key = int(self.tw_cell.currentItem().text())
        if state == 1:  # connect picker
            self.plot_profile(all_lambdas=True)
            [min_x, max_x] = self.cell_minmax.get(cell_key)
            if min_x is None or max_x is None:
                min_x = 5.8
                max_x = 7.2
            self.region_picker.setRegion([min_x, max_x])
            self.figure_scans.addItem(self.region_picker)
        elif state == 0:  # accept and close picker
            [min_val, max_val] = self.region_picker.getRegion()
            self.cell_minmax[cell_key] = [min_val, max_val]
            self.apply_region()
            self.plot_profile()

    def apply_region(self):
        cell_item = self.tw_cell.currentItem()
        cell_key = int(cell_item.text())
        cell_id = self.get_item_id(cell_item, "cell")
        [min_x, max_x] = self.cell_minmax.get(cell_key)
        index_matrix = self.index_matrix[cell_id]
        n_wvl, n_scn = index_matrix.shape[0], index_matrix.shape[1]
        for i in range(n_wvl):
            for j in range(n_scn):
                abs_id = index_matrix[i, j]
                if abs_id < 0:
                    continue
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
