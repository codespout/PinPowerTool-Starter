from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QRadioButton, QButtonGroup, QSpinBox, 
    QComboBox, QFileDialog, QTextEdit, QProgressBar, QGroupBox
)
from PySide6.QtCore import Signal as pyqtSignal, Qt
import os

class DownloaderUI(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)

        # Mode Selection
        mode_group = QGroupBox("Target Source")
        mode_layout = QHBoxLayout()
        self.radio_search = QRadioButton("🔍 Search Term")
        self.radio_links = QRadioButton("🔗 Specific Pin Links")
        self.radio_search.setChecked(True)
        
        self.mode_btn_group = QButtonGroup()
        self.mode_btn_group.addButton(self.radio_search)
        self.mode_btn_group.addButton(self.radio_links)
        
        mode_layout.addWidget(self.radio_search)
        mode_layout.addWidget(self.radio_links)
        mode_layout.addStretch()
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        # Inputs Card
        input_group = QGroupBox("Search Query / URLs")
        input_layout = QVBoxLayout()
        
        self.input_stack = QWidget()
        self.stack_layout = QVBoxLayout(self.input_stack)
        self.stack_layout.setContentsMargins(0, 0, 0, 0)
        
        # Search Input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter search term (e.g., 'luxury cars')")
        self.stack_layout.addWidget(self.search_input)
        
        # Links Input (Hidden by default)
        self.links_input = QTextEdit()
        self.links_input.setPlaceholderText("Paste pin URLs here (one per line)")
        self.links_input.setVisible(False)
        self.stack_layout.addWidget(self.links_input)
        
        input_layout.addWidget(self.input_stack)
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

        # Connect radio buttons to switch inputs
        self.radio_search.toggled.connect(self.toggle_inputs)

        # Settings Card
        settings_group = QGroupBox("Configuration")
        settings_vbox = QVBoxLayout()
        settings_layout = QHBoxLayout()
        
        # Count
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 1000)
        self.count_spin.setValue(10)
        self.count_spin.setPrefix("Maximum Pins: ")
        self.count_spin.setMinimumWidth(150)
        settings_layout.addWidget(self.count_spin)
        
        # Renaming
        self.rename_combo = QComboBox()
        self.rename_combo.addItems(["Original ID", "Number Sequence", "Pin Title", "Custom"])
        self.rename_combo.currentTextChanged.connect(self.toggle_custom_rename)
        
        settings_layout.addWidget(QLabel("Filename Pattern:"))
        settings_layout.addWidget(self.rename_combo)
        
        self.custom_rename_input = QLineEdit()
        self.custom_rename_input.setPlaceholderText("Pattern (e.g. mypin_{id})")
        self.custom_rename_input.setVisible(False)
        settings_layout.addWidget(self.custom_rename_input)
        
        settings_vbox.addLayout(settings_layout)

        # Output Folder
        folder_layout = QHBoxLayout()
        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText("Select destination folder...")
        self.browse_btn = QPushButton("📁 Browse")
        self.browse_btn.setMinimumHeight(40)
        self.browse_btn.clicked.connect(self.browse_folder)
        
        folder_layout.addWidget(self.folder_input)
        folder_layout.addWidget(self.browse_btn)
        settings_vbox.addLayout(folder_layout)
        
        settings_group.setLayout(settings_vbox)
        layout.addWidget(settings_group)

        # Action Buttons
        btn_group = QGroupBox("Execution")
        execution_layout = QVBoxLayout()
        
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("🚀 Start Download")
        self.start_btn.setMinimumHeight(45)
        self.start_btn.clicked.connect(self.start_download)
        
        self.stop_btn = QPushButton("🛑 Stop")
        self.stop_btn.setMinimumHeight(45)
        self.stop_btn.clicked.connect(self.stop_download)
        self.stop_btn.setEnabled(False)
        
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        execution_layout.addLayout(btn_layout)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimumHeight(20)
        execution_layout.addWidget(self.progress_bar)
        
        btn_group.setLayout(execution_layout)
        layout.addWidget(btn_group)

        # Log
        log_group = QGroupBox("Activity Log")
        log_layout = QVBoxLayout()
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setPlaceholderText("Download events will be logged here...")
        log_layout.addWidget(self.log_area)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        layout.addStretch()

    def toggle_inputs(self):
        is_search = self.radio_search.isChecked()
        self.search_input.setVisible(is_search)
        self.links_input.setVisible(not is_search)
        self.count_spin.setEnabled(is_search) # Count only applies to search

    def toggle_custom_rename(self, text):
        self.custom_rename_input.setVisible(text == "Custom")

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.folder_input.setText(folder)

    def log(self, message):
        self.log_area.append(message)

    def start_download(self):
        # Validation
        folder = self.folder_input.text()
        if not folder or not os.path.exists(folder):
            self.log("Error: Please select a valid output folder.")
            return

        mode = "search" if self.radio_search.isChecked() else "links"
        data = ""
        if mode == "search":
            data = self.search_input.text().strip()
            if not data:
                self.log("Error: Please enter a search term.")
                return
        else:
            data = self.links_input.toPlainText().strip()
            if not data:
                self.log("Error: Please enter pin links.")
                return

        renaming = self.rename_combo.currentText()
        custom_pattern = ""
        if renaming == "Custom":
            custom_pattern = self.custom_rename_input.text().strip()
            if not custom_pattern:
                self.log("Error: Please enter a custom renaming pattern.")
                return

        # Disable UI
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        
        # Start Worker
        self.log(f"Starting download in {mode} mode...")
        
        from src.modules.downloader import DownloaderWorker
        
        self.worker = DownloaderWorker(
            mode,
            data,
            folder,
            self.count_spin.value(),
            renaming,
            custom_pattern
        )
        self.worker.log_signal.connect(self.log)
        self.worker.progress_signal.connect(self.progress_bar.setValue)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()

    def stop_download(self):
        if self.worker:
            self.worker.stop()
            self.log("Stopping...")
            self.stop_btn.setEnabled(False)

    def on_finished(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.log("Download task finished.")
