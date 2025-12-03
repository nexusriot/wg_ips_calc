#!/usr/bin/env python3
"""
PyQt5 GUI for WireGuard AllowedIPs calculator.
"""
import sys
import os
import json
import platform
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QTextEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QMessageBox,
    QListWidget,
    QListWidgetItem,
    QDialog,
    QAction,
    QMainWindow
)
from PyQt5.QtCore import Qt

from wg_ips_core import calculate_allowed_ips, VERSION



def get_config_dir(app_name: str = "wg_allowed_ips") -> str:
    """
    Return a per-user config directory, depending on OS.

    Linux:   ~/.config/<app_name>
    macOS:   ~/Library/Application Support/<app_name>
    Windows: %APPDATA%\<app_name> (fallback: ~\<app_name>)
    """
    home = os.path.expanduser("~")
    system = platform.system()

    if system == "Windows":
        base = os.environ.get("APPDATA", home)
        cfg = os.path.join(base, app_name)
    elif system == "Darwin":
        base = os.path.join(home, "Library", "Application Support")
        cfg = os.path.join(base, app_name)
    else:
        base = os.environ.get("XDG_CONFIG_HOME", os.path.join(home, ".config"))
        cfg = os.path.join(base, app_name)

    os.makedirs(cfg, exist_ok=True)
    return cfg


class HistoryWindow(QDialog):
    def __init__(self, history, load_callback, parent=None):
        """
        history: list of dict entries
        load_callback: function(entry_dict) -> None
        """
        super().__init__(parent)
        self.setWindowTitle("Calculation History")
        self.resize(600, 400)

        self.setWindowModality(Qt.WindowModal)

        self.history = history
        self.load_callback = load_callback

        layout = QVBoxLayout()
        self.list = QListWidget()

        self.list.setFrameShape(self.list.Box)
        self.list.setLineWidth(1)
        self.list.setStyleSheet("QListWidget { border: 2px solid #777; }")

        self.list.itemDoubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.list)

        btn_layout = QHBoxLayout()

        self.btn_load = QPushButton("Load Selected")
        self.btn_clear = QPushButton("Clear History")
        self.btn_close = QPushButton("Close")

        self.btn_load.clicked.connect(self.on_load_clicked)
        self.btn_clear.clicked.connect(self.on_clear_clicked)
        self.btn_close.clicked.connect(self.close)

        btn_layout.addWidget(self.btn_load)
        btn_layout.addWidget(self.btn_clear)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_close)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

        self.populate(self.history)

    def showEvent(self, event):
        super().showEvent(event)
        self.center_on_parent()

    def center_on_parent(self):
        parent = self.parentWidget()
        if not parent:
            return

        self.adjustSize()

        pg = parent.geometry()
        sg = self.geometry()

        x = pg.x() + (pg.width() - sg.width()) // 2
        y = pg.y() + (pg.height() - sg.height()) // 2
        self.move(max(0, x), max(0, y))

    def populate(self, history):
        self.history = history
        self.list.clear()

        for entry in reversed(self.history):
            ts = entry.get("timestamp", "")
            allowed = entry.get("allowed", "").replace("\n", " ")
            disallowed = entry.get("disallowed", "").replace("\n", " ")

            summary_allowed = (allowed[:60] + "...") if len(allowed) > 60 else allowed
            summary_disallowed = (
                disallowed[:60] + "..." if len(disallowed) > 60 else disallowed
            )

            text = f"[{ts}]  A: {summary_allowed} | D: {summary_disallowed}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, entry)
            self.list.addItem(item)

    def get_selected_entry(self):
        item = self.list.currentItem()
        if not item:
            return None
        return item.data(Qt.UserRole)

    def on_item_double_clicked(self, item: QListWidgetItem):
        entry = item.data(Qt.UserRole)
        if entry and self.load_callback:
            self.load_callback(entry)
            self.close()

    def on_load_clicked(self):
        entry = self.get_selected_entry()
        if not entry:
            QMessageBox.information(
                self, "No selection", "Please select a history entry first."
            )
            return
        if self.load_callback:
            self.load_callback(entry)
        self.close()

    def on_clear_clicked(self):
        if QMessageBox.question(
            self,
            "Clear History",
            "Clear history?",
            QMessageBox.Yes | QMessageBox.No,
        ) != QMessageBox.Yes:
            return

        self.history.clear()

        if hasattr(self.parentWidget(), "save_history"):
            self.parentWidget().save_history()
        # Update visible
        self.populate(self.history)


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About WireGuard AllowedIPs Calculator")
        self.resize(350, 190)
        self.setWindowModality(Qt.WindowModal)

        layout = QVBoxLayout()

        lbl_title = QLabel("<b>WireGuard AllowedIPs Calculator %s </b>" % VERSION)
        lbl_title.setAlignment(Qt.AlignCenter)

        lbl_text = QLabel(
            """
            <p></p>
            <p>Small helper tool to calculate WireGuard <code>AllowedIPs</code></p>
            <p>Project
              <a href="https://github.com/nexusriot/wg_allowed_ips">
                 home   </a>
            </p>
            """
        )
        lbl_text.setWordWrap(True)
        lbl_text.setTextFormat(Qt.RichText)
        lbl_text.setOpenExternalLinks(True)

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.close)

        layout.addWidget(lbl_title)
        layout.addWidget(lbl_text)
        layout.addStretch()
        layout.addWidget(btn_close, alignment=Qt.AlignRight)

        self.setLayout(layout)


class AllowedIPsCalculator(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.app_name = "wg_allowed_ips"
        self.config_dir = get_config_dir(self.app_name)
        self.config_path = os.path.join(self.config_dir, "config.json")
        self.history_path = os.path.join(self.config_dir, "history.json")
        self.history_limit = 200  # max entries to keep

        self.history = self.load_history()
        self.history_window = None
        self.about_dialog = None

        self.init_ui()
        self.load_window_config()

    def init_ui(self):
        self.setWindowTitle("WireGuard AllowedIPs Calculator")
        self.setMinimumSize(800, 600)

        # ---- Menu bar (native QMainWindow menu) ----
        menu_bar = self.menuBar()

        menu_file = menu_bar.addMenu("&File")
        act_exit = QAction("E&xit", self)
        act_exit.triggered.connect(self.close)
        menu_file.addAction(act_exit)

        menu_help = menu_bar.addMenu("&Help")
        act_about = QAction("&About", self)
        act_about.triggered.connect(self.on_about)
        menu_help.addAction(act_about)

        # ---- Central widget & layout ----
        central = QWidget(self)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # Allowed IPs input
        lbl_allowed = QLabel("Allowed IPs (comma or newline separated):")
        self.txt_allowed = QTextEdit()
        self.txt_allowed.setPlaceholderText("Example: 0.0.0.0/0, ::/0")

        # Disallowed IPs input
        lbl_disallowed = QLabel("Disallowed IPs (comma or newline separated):")
        self.txt_disallowed = QTextEdit()
        self.txt_disallowed.setPlaceholderText(
            "Example: 27.27.27.27, 10.27.0.27/32, 10.27.0.1"
        )

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.btn_calculate = QPushButton("Calculate")
        self.btn_calculate.clicked.connect(self.on_calculate)

        self.btn_copy = QPushButton("Copy Output to Clipboard")
        self.btn_copy.clicked.connect(self.on_copy_output)

        self.btn_history = QPushButton("History")
        self.btn_history.clicked.connect(self.on_show_history)

        btn_layout.addWidget(self.btn_calculate)
        btn_layout.addWidget(self.btn_copy)
        btn_layout.addWidget(self.btn_history)
        btn_layout.addStretch()

        lbl_output = QLabel("Resulting AllowedIPs:")
        self.txt_output = QPlainTextEdit()
        self.txt_output.setReadOnly(True)
        self.txt_output.setPlaceholderText(
            "Calculated output will appear here, e.g.\n"
            "AllowedIPs = 0.0.0.0/5, 8.0.0.0/7, ..."
        )
        main_layout.addWidget(lbl_allowed)
        main_layout.addWidget(self.txt_allowed)
        main_layout.addWidget(lbl_disallowed)
        main_layout.addWidget(self.txt_disallowed)
        main_layout.addLayout(btn_layout)
        main_layout.addWidget(lbl_output)
        main_layout.addWidget(self.txt_output)
        self.setCentralWidget(central)
        # Prefill example allowed (disallowed left empty)
        self.txt_allowed.setText("0.0.0.0/0, ::/0")

    def load_window_config(self):
        if not os.path.exists(self.config_path):
            return
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            return

        geom = cfg.get("geometry")
        if geom:
            try:
                x = int(geom.get("x", self.x()))
                y = int(geom.get("y", self.y()))
                w = int(geom.get("w", self.width()))
                h = int(geom.get("h", self.height()))
                self.setGeometry(x, y, w, h)
            except Exception:
                pass

    def save_window_config(self):
        cfg = {}
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            except Exception:
                cfg = {}

        geom = {
            "x": self.x(),
            "y": self.y(),
            "w": self.width(),
            "h": self.height(),
        }
        cfg["geometry"] = geom

        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
        except Exception:
            pass

    def load_history(self):
        if not os.path.exists(self.history_path):
            return []
        try:
            with open(self.history_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except Exception:
            pass
        return []

    def save_history(self):
        try:
            with open(self.history_path, "w", encoding="utf-8") as f:
                json.dump(self.history, f, indent=2)
        except Exception:
            pass

    def add_to_history(self, allowed_text, disallowed_text, result_text):
        entry = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "allowed": allowed_text,
            "disallowed": disallowed_text,
            "result": result_text,
        }
        self.history.append(entry)
        if len(self.history) > self.history_limit:
            self.history = self.history[-self.history_limit :]
        self.save_history()

        if self.history_window is not None:
            self.history_window.populate(self.history)

    def on_about(self):
        if self.about_dialog is None:
            self.about_dialog = AboutDialog(self)
        self.about_dialog.show()
        self.about_dialog.raise_()
        self.about_dialog.activateWindow()

    def on_show_history(self):
        if self.history_window is None:
            self.history_window = HistoryWindow(
                self.history, load_callback=self.load_from_history, parent=self
            )
        else:
            self.history_window.populate(self.history)

        self.history_window.show()
        self.history_window.raise_()
        self.history_window.activateWindow()

    def load_from_history(self, entry: dict):
        allowed = entry.get("allowed", "")
        disallowed = entry.get("disallowed", "")
        result = entry.get("result", "")

        self.txt_allowed.setPlainText(allowed)
        self.txt_disallowed.setPlainText(disallowed)
        self.txt_output.setPlainText(result)

    def on_calculate(self):
        allowed_text = self.txt_allowed.toPlainText()
        disallowed_text = self.txt_disallowed.toPlainText()

        try:
            result = calculate_allowed_ips(allowed_text, disallowed_text)
        except ValueError as e:
            QMessageBox.critical(self, "Input error", str(e))
            return
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Unexpected error during calculation:\n{e}"
            )
            return

        self.txt_output.setPlainText(result)
        self.add_to_history(allowed_text, disallowed_text, result)

    def on_copy_output(self):
        text = self.txt_output.toPlainText().strip()
        if not text:
            QMessageBox.information(
                self, "Nothing to copy", "Output field is empty, nothing to copy."
            )
            return
        QApplication.clipboard().setText(text)
        QMessageBox.information(self, "Copied", "Output copied to clipboard.")

    def closeEvent(self, event):
        self.save_window_config()
        if self.history_window is not None:
            self.history_window.close()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    win = AllowedIPsCalculator()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
