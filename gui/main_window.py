# gui/main_window.py
import os
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QFileDialog,
                             QProgressBar, QTextEdit, QMessageBox, QTabWidget,
                             QComboBox)
from PyQt5.QtGui import QFont

from config import MATCH_METHODS, DEFAULT_METHOD
from workers.match_worker import WorkerMatch
from workers.upscale_worker import WorkerUpscale


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dino Crisis 2: Обработка масок и фонов")
        self.setGeometry(100, 100, 800, 600)

        tabs = QTabWidget()
        self.setCentralWidget(tabs)

        tab1 = QWidget()
        tabs.addTab(tab1, "Сопоставление")
        self.setup_tab1(tab1)

        tab2 = QWidget()
        tabs.addTab(tab2, "Генерация x4")
        self.setup_tab2(tab2)

        self.worker = None

    # ------------------------------------------------------------------
    # Вкладка 1
    # ------------------------------------------------------------------
    def setup_tab1(self, parent):
        layout = QVBoxLayout(parent)

        # Директория с фонами
        bg_layout = QHBoxLayout()
        bg_layout.addWidget(QLabel("Фоны (оригинал):"))
        self.bg_edit = QLineEdit()
        bg_layout.addWidget(self.bg_edit)
        self.bg_btn = QPushButton("Обзор...")
        self.bg_btn.clicked.connect(self.select_bg_dir)
        bg_layout.addWidget(self.bg_btn)
        layout.addLayout(bg_layout)

        # Директория с масками
        mask_layout = QHBoxLayout()
        mask_layout.addWidget(QLabel("Маски (оригинал):"))
        self.mask_edit = QLineEdit()
        mask_layout.addWidget(self.mask_edit)
        self.mask_btn = QPushButton("Обзор...")
        self.mask_btn.clicked.connect(self.select_mask_dir)
        mask_layout.addWidget(self.mask_btn)
        layout.addLayout(mask_layout)

        # Выбор метода сравнения
        method_layout = QHBoxLayout()
        method_layout.addWidget(QLabel("Метод сравнения:"))
        self.method_combo = QComboBox()
        for display_name in MATCH_METHODS.keys():
            self.method_combo.addItem(display_name)
        # Устанавливаем метод по умолчанию
        default_display = [k for k, v in MATCH_METHODS.items() if v == DEFAULT_METHOD][0]
        self.method_combo.setCurrentText(default_display)
        method_layout.addWidget(self.method_combo)
        method_layout.addStretch()
        layout.addLayout(method_layout)

        # Выходной CSV
        out_layout = QHBoxLayout()
        out_layout.addWidget(QLabel("Результат CSV:"))
        self.out_edit = QLineEdit("result.csv")
        out_layout.addWidget(self.out_edit)
        self.out_btn = QPushButton("Сохранить как...")
        self.out_btn.clicked.connect(self.select_output_file)
        out_layout.addWidget(self.out_btn)
        layout.addLayout(out_layout)

        # Кнопка запуска
        self.start_btn1 = QPushButton("Старт")
        self.start_btn1.clicked.connect(self.start_matching)
        layout.addWidget(self.start_btn1)

        # Прогресс-бар и лог
        self.progress1 = QProgressBar()
        layout.addWidget(self.progress1)
        self.log1 = QTextEdit()
        self.log1.setReadOnly(True)
        self.log1.setFont(QFont("Courier", 9))
        layout.addWidget(self.log1)

    def select_bg_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Выберите директорию с оригинальными фонами")
        if dir_path:
            self.bg_edit.setText(dir_path)

    def select_mask_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Выберите директорию с оригинальными масками")
        if dir_path:
            self.mask_edit.setText(dir_path)

    def select_output_file(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Сохранить результат как",
                                                   "result.csv", "CSV (*.csv)")
        if file_path:
            self.out_edit.setText(file_path)

    def start_matching(self):
        bg_dir = self.bg_edit.text().strip()
        mask_dir = self.mask_edit.text().strip()
        out_file = self.out_edit.text().strip()
        method_display = self.method_combo.currentText()
        method = MATCH_METHODS.get(method_display, DEFAULT_METHOD)

        if not bg_dir or not os.path.isdir(bg_dir):
            QMessageBox.warning(self, "Ошибка", "Укажите существующую директорию с фонами.")
            return
        if not mask_dir or not os.path.isdir(mask_dir):
            QMessageBox.warning(self, "Ошибка", "Укажите существующую директорию с масками.")
            return
        if not out_file:
            out_file = "result.csv"
            self.out_edit.setText(out_file)

        self.start_btn1.setEnabled(False)
        self.progress1.setValue(0)
        self.log1.clear()

        self.worker = WorkerMatch(bg_dir, mask_dir, out_file, method)
        self.worker.progress.connect(self.progress1.setValue)
        self.worker.log.connect(self.log1.append)
        self.worker.finished.connect(self.on_match_finished)
        self.worker.start()

    def on_match_finished(self, success, message):
        self.start_btn1.setEnabled(True)
        self.log1.append(message)
        if success:
            QMessageBox.information(self, "Готово", message)
        else:
            QMessageBox.critical(self, "Ошибка", message)
        self.worker = None

    # ------------------------------------------------------------------
    # Вкладка 2 (без изменений)
    # ------------------------------------------------------------------
    def setup_tab2(self, parent):
        layout = QVBoxLayout(parent)

        up_layout = QHBoxLayout()
        up_layout.addWidget(QLabel("Фоны (x4):"))
        self.upscale_bg_edit = QLineEdit()
        up_layout.addWidget(self.upscale_bg_edit)
        self.upscale_bg_btn = QPushButton("Обзор...")
        self.upscale_bg_btn.clicked.connect(self.select_upscale_bg_dir)
        up_layout.addWidget(self.upscale_bg_btn)
        layout.addLayout(up_layout)

        csv_layout = QHBoxLayout()
        csv_layout.addWidget(QLabel("CSV результат:"))
        self.csv_edit = QLineEdit()
        csv_layout.addWidget(self.csv_edit)
        self.csv_btn = QPushButton("Обзор...")
        self.csv_btn.clicked.connect(self.select_csv_file)
        csv_layout.addWidget(self.csv_btn)
        layout.addLayout(csv_layout)

        orig_mask_layout = QHBoxLayout()
        orig_mask_layout.addWidget(QLabel("Оригинальные маски:"))
        self.orig_mask_edit = QLineEdit()
        orig_mask_layout.addWidget(self.orig_mask_edit)
        self.orig_mask_btn = QPushButton("Обзор...")
        self.orig_mask_btn.clicked.connect(self.select_orig_mask_dir)
        orig_mask_layout.addWidget(self.orig_mask_btn)
        layout.addLayout(orig_mask_layout)

        out_mask_layout = QHBoxLayout()
        out_mask_layout.addWidget(QLabel("Сохранить маски в:"))
        self.out_mask_edit = QLineEdit()
        out_mask_layout.addWidget(self.out_mask_edit)
        self.out_mask_btn = QPushButton("Обзор...")
        self.out_mask_btn.clicked.connect(self.select_output_mask_dir)
        out_mask_layout.addWidget(self.out_mask_btn)
        layout.addLayout(out_mask_layout)

        self.start_btn2 = QPushButton("Генерировать")
        self.start_btn2.clicked.connect(self.start_upscale)
        layout.addWidget(self.start_btn2)

        self.progress2 = QProgressBar()
        layout.addWidget(self.progress2)
        self.log2 = QTextEdit()
        self.log2.setReadOnly(True)
        self.log2.setFont(QFont("Courier", 9))
        layout.addWidget(self.log2)

    def select_upscale_bg_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Выберите директорию с увеличенными фонами (x4)")
        if dir_path:
            self.upscale_bg_edit.setText(dir_path)

    def select_csv_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Выберите CSV файл с результатами",
                                                   "", "CSV (*.csv)")
        if file_path:
            self.csv_edit.setText(file_path)

    def select_orig_mask_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Выберите директорию с оригинальными масками")
        if dir_path:
            self.orig_mask_edit.setText(dir_path)

    def select_output_mask_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Выберите директорию для сохранения новых масок")
        if dir_path:
            self.out_mask_edit.setText(dir_path)

    def start_upscale(self):
        up_dir = self.upscale_bg_edit.text().strip()
        csv_path = self.csv_edit.text().strip()
        orig_mask_dir = self.orig_mask_edit.text().strip()
        out_dir = self.out_mask_edit.text().strip()

        if not up_dir or not os.path.isdir(up_dir):
            QMessageBox.warning(self, "Ошибка", "Укажите существующую директорию с увеличенными фонами.")
            return
        if not csv_path or not os.path.isfile(csv_path):
            QMessageBox.warning(self, "Ошибка", "Укажите существующий CSV файл.")
            return
        if not orig_mask_dir or not os.path.isdir(orig_mask_dir):
            QMessageBox.warning(self, "Ошибка", "Укажите существующую директорию с оригинальными масками.")
            return
        if not out_dir:
            out_dir = "upscaled_masks"
            self.out_mask_edit.setText(out_dir)
        os.makedirs(out_dir, exist_ok=True)

        self.start_btn2.setEnabled(False)
        self.progress2.setValue(0)
        self.log2.clear()

        self.worker = WorkerUpscale(up_dir, csv_path, orig_mask_dir, out_dir)
        self.worker.progress.connect(self.progress2.setValue)
        self.worker.log.connect(self.log2.append)
        self.worker.finished.connect(self.on_upscale_finished)
        self.worker.start()

    def on_upscale_finished(self, success, message):
        self.start_btn2.setEnabled(True)
        self.log2.append(message)
        if success:
            QMessageBox.information(self, "Готово", message)
        else:
            QMessageBox.critical(self, "Ошибка", message)
        self.worker = None