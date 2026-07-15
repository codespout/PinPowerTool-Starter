from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget
from src.ui.auto_follow_ui import AutoFollowUI
from src.ui.auto_comment_ui import AutoCommentUI
from src.ui.auto_repin_ui import AutoRepinUI

class AutomationUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Tabbed Interface
        self.tabs = QTabWidget()
        
        # Add automation tabs with icons
        self.auto_follow_tab = AutoFollowUI()
        self.tabs.addTab(self.auto_follow_tab, "👤 Auto-Follow")
        
        self.auto_comment_tab = AutoCommentUI()
        self.tabs.addTab(self.auto_comment_tab, "💬 Auto-Comment")
        
        self.auto_repin_tab = AutoRepinUI()
        self.tabs.addTab(self.auto_repin_tab, "📌 Auto-Repin")
        
        # Add Downloader Tab
        from src.ui.downloader_ui import DownloaderUI
        self.tabs.addTab(DownloaderUI(), "📥 Downloader") 
        
        # Add Scheduler Tab
        from src.ui.scheduler_ui import SchedulerUI
        self.tabs.addTab(SchedulerUI(), "📅 Scheduler")
        
        layout.addWidget(self.tabs)

    def open_repin_upload(self, file_path, title):
        """Switch to Repin tab and prepare upload."""
        self.tabs.setCurrentWidget(self.auto_repin_tab)
        self.auto_repin_tab.prepare_upload(file_path, title)
