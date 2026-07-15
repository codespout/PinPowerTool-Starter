from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QFrame, QSpacerItem, QSizePolicy, QScrollArea
from PySide6.QtCore import Qt
from src.modules.theme_manager import ThemeManager

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PinPowerTool")
        self.setGeometry(100, 100, 1100, 800) # Slightly larger default
        
        self.theme_manager = ThemeManager()
        self.setup_ui()
        self.apply_theme()

    def setup_ui(self):
        # Main container
        main_widget = QWidget()
        main_widget.setObjectName("MainContainer")
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(240)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(0, 20, 0, 20)
        sidebar_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # Logo
        import os
        from PySide6.QtGui import QPixmap
        logo_label = QLabel()
        logo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'assets', 'logo_transparent.png')
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            scaled_pixmap = pixmap.scaled(120, 120, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(scaled_pixmap)
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logo_label.setObjectName("LogoLabel")
            sidebar_layout.addWidget(logo_label)
        else:
            logo_title = QLabel("PIN POWER")
            logo_title = QLabel("PIN POWER")
            logo_title.setObjectName("LogoTitle")
            logo_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sidebar_layout.addWidget(logo_title)

        # Sidebar buttons with icons (Unicode)
        self.btn_dashboard = QPushButton("🏠  Dashboard")
        self.btn_accounts = QPushButton("👥  Accounts")
        self.btn_gather = QPushButton("🔍  Gather Pins")
        self.btn_automation = QPushButton("⚙️  Automation")
        self.btn_relationship = QPushButton("🤝  Relationship")
        self.btn_repurposer = QPushButton("♻️  Repurposer")
        self.btn_settings = QPushButton("🛠️  Settings")
        
        self.all_buttons = [self.btn_dashboard, self.btn_accounts, self.btn_gather, 
                           self.btn_automation, self.btn_relationship, self.btn_repurposer, self.btn_settings]

        for btn in self.all_buttons:
            sidebar_layout.addWidget(btn)

        # Bottom stretch to push toggle down
        sidebar_layout.addStretch()

        # Theme Toggle Button
        self.btn_theme_toggle = QPushButton("🌙  Dark Mode")
        self.btn_theme_toggle.setObjectName("ThemeToggle")
        self.btn_theme_toggle.clicked.connect(self.toggle_theme)
        sidebar_layout.addWidget(self.btn_theme_toggle)

        # Content Area with Scroll
        self.content_scroll = QScrollArea()
        self.content_scroll.setWidgetResizable(True)
        self.content_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.content_scroll.setObjectName("ContentScroll")
        
        self.content_area = QWidget()
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(20, 20, 20, 20)
        
        self.content_scroll.setWidget(self.content_area)
        
        # Add to main layout
        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(self.content_scroll)

        # Connect buttons
        self.btn_dashboard.clicked.connect(self.show_dashboard)
        self.btn_accounts.clicked.connect(self.show_accounts)
        self.btn_gather.clicked.connect(self.show_gather)
        self.btn_automation.clicked.connect(self.show_automation)
        self.btn_relationship.clicked.connect(self.show_relationship)
        self.btn_repurposer.clicked.connect(self.show_repurposer)
        self.btn_settings.clicked.connect(self.show_settings)

        # Show dashboard by default
        self.show_dashboard()

    def apply_theme(self):
        self.setStyleSheet(self.theme_manager.get_style())

    def toggle_theme(self):
        is_dark = self.theme_manager.toggle_theme()
        self.btn_theme_toggle.setText("🌙  Dark Mode" if is_dark else "☀️  Light Mode")
        self.apply_theme()
        # Refresh current view to ensure theme applies to child widgets
        self.refresh_current_view()

    def refresh_current_view(self):
        # Re-trigger current button click to redraw content with new theme
        for btn in self.all_buttons:
            if btn.property("active") == True:
                btn.click()
                break

    def set_active_button(self, active_btn):
        """Highlight the active button in the sidebar using QSS property."""
        for btn in self.all_buttons:
            btn.setProperty("active", False)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        
        active_btn.setProperty("active", True)
        active_btn.style().unpolish(active_btn)
        active_btn.style().polish(active_btn)
    
    def clear_content(self):
        for i in reversed(range(self.content_layout.count())): 
            item = self.content_layout.itemAt(i)
            if item.widget():
                item.widget().setParent(None)

    def show_dashboard(self):
        self.set_active_button(self.btn_dashboard)
        self.clear_content()
        from src.ui.dashboard_ui import DashboardUI
        self.content_layout.addWidget(DashboardUI())

    def show_accounts(self):
        self.set_active_button(self.btn_accounts)
        self.clear_content()
        from src.ui.account_manager_ui import AccountManagerUI
        self.content_layout.addWidget(AccountManagerUI())

    def show_gather(self):
        self.set_active_button(self.btn_gather)
        self.clear_content()
        from src.ui.gather_ui import GatherUI
        self.content_layout.addWidget(GatherUI())

    def show_automation(self):
        self.set_active_button(self.btn_automation)
        self.clear_content()
        from src.ui.automation_ui import AutomationUI
        self.content_layout.addWidget(AutomationUI())

    def show_relationship(self):
        self.set_active_button(self.btn_relationship)
        self.clear_content()
        from src.ui.dm_ui import DMUI
        self.content_layout.addWidget(DMUI())

    def show_repurposer(self):
        self.set_active_button(self.btn_repurposer)
        self.clear_content()
        from src.ui.repurposer_ui import RepurposerUI
        repurposer = RepurposerUI()
        repurposer.request_upload.connect(self.handle_upload_request)
        self.content_layout.addWidget(repurposer)
        
    def handle_upload_request(self, file_path, title):
        self.show_automation()
        # The new widget is now at index 0
        if self.content_layout.count() > 0:
            automation_ui = self.content_layout.itemAt(0).widget()
            if hasattr(automation_ui, 'open_repin_upload'):
                automation_ui.open_repin_upload(file_path, title)

    def show_settings(self):
        self.set_active_button(self.btn_settings)
        self.clear_content()
        from src.ui.settings_ui import SettingsUI
        self.content_layout.addWidget(SettingsUI())
