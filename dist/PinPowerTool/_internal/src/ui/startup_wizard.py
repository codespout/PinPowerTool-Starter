from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QCheckBox, 
                             QPushButton, QComboBox, QHBoxLayout, QFrame)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
import json
import os

class StartupWizard(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to PinPowerTool")
        self.setFixedSize(500, 400)
        self.config_path = "config.json"
        
        # Load existing icon if available
        logo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'assets', 'logo.png')
        if os.path.exists(logo_path):
            self.setWindowIcon(QIcon(logo_path))
            
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Header
        lbl_title = QLabel("Welcome to PinPowerTool")
        lbl_title.setStyleSheet("font-size: 24px; font-weight: bold; color: #333;")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_title)
        
        lbl_desc = QLabel("Let's set up a few things before we get started with your automation journey.")
        lbl_desc.setWordWrap(True)
        lbl_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_desc.setStyleSheet("color: #666; font-size: 14px;")
        layout.addWidget(lbl_desc)
        
        # Divider
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)
        
        # Options
        options_layout = QVBoxLayout()
        options_layout.setSpacing(15)
        
        # Browser Type Preference
        browser_layout = QHBoxLayout()
        lbl_browser = QLabel("Preferred Browser:")
        self.cmb_browser = QComboBox()
        self.cmb_browser.addItems(["Chrome", "Firefox", "Edge"])
        browser_layout.addWidget(lbl_browser)
        browser_layout.addWidget(self.cmb_browser)
        options_layout.addLayout(browser_layout)
        
        # Dark Mode
        self.chk_dark_mode = QCheckBox("Enable Dark Mode (Recommended)")
        self.chk_dark_mode.setChecked(True)
        options_layout.addWidget(self.chk_dark_mode)
        
        # Auto-Minimize
        self.chk_minimize = QCheckBox("Minimize to Tray on Close")
        self.chk_minimize.setChecked(True)
        options_layout.addWidget(self.chk_minimize)
        
        layout.addLayout(options_layout)
        
        layout.addStretch()
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_start = QPushButton("Get Started 🚀")
        btn_start.setMinimumHeight(45)
        btn_start.setStyleSheet("""
            QPushButton {
                background-color: #E60023;
                color: white;
                font-weight: bold;
                border-radius: 5px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #ad081b;
            }
        """)
        btn_start.clicked.connect(self.save_and_start)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_start)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
        
    def save_and_start(self):
        # Save preferences
        config = {
            "browser_type": self.cmb_browser.currentText().lower(),
            "theme": "dark" if self.chk_dark_mode.isChecked() else "light",
            "minimize_to_tray": self.chk_minimize.isChecked(),
            "first_run": False
        }
        
        try:
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")
            
        self.accept()
