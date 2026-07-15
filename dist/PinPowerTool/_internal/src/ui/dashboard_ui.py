from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QComboBox, QPushButton, QDateEdit, QTableWidget,
                             QTableWidgetItem, QHeaderView, QGroupBox, QGridLayout, QFrame)
from PySide6.QtCore import Qt, QDate
from src.database import get_db_connection
import json

class DashboardUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.load_accounts()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)
        
        # Header
        # Header Card
        header_group = QGroupBox("Performance Overview")
        header_vbox = QVBoxLayout()
        lbl_title = QLabel("Analytics & Insights")
        lbl_title.setObjectName("HeaderTitle")
        header_vbox.addWidget(lbl_title)
        
        # Controls
        controls_layout = QHBoxLayout()
        
        # Account selector
        lbl_account = QLabel("Account:")
        self.cmb_account = QComboBox()
        self.cmb_account.setMinimumWidth(250)
        self.cmb_account.setMinimumHeight(40)
        
        # Date range
        lbl_from = QLabel("From:")
        lbl_from.setStyleSheet("font-weight: bold;")
        self.date_from = QDateEdit()
        self.date_from.setMinimumHeight(40)
        self.date_from.setDate(QDate.currentDate().addDays(-30))
        self.date_from.setCalendarPopup(True)
        
        lbl_to = QLabel("To:")
        lbl_to.setStyleSheet("font-weight: bold;")
        self.date_to = QDateEdit()
        self.date_to.setMinimumHeight(40)
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setCalendarPopup(True)
        
        # Refresh button
        btn_refresh = QPushButton("🔄 Refresh Analytics")
        btn_refresh.setMinimumHeight(45)
        btn_refresh.clicked.connect(self.refresh_analytics)
        
        controls_layout.addWidget(lbl_account)
        controls_layout.addWidget(self.cmb_account)
        controls_layout.addSpacing(20)
        controls_layout.addWidget(lbl_from)
        controls_layout.addWidget(self.date_from)
        controls_layout.addSpacing(10)
        controls_layout.addWidget(lbl_to)
        controls_layout.addWidget(self.date_to)
        controls_layout.addSpacing(20)
        controls_layout.addWidget(btn_refresh)
        controls_layout.addStretch()
        
        header_vbox.addLayout(controls_layout)
        header_group.setLayout(header_vbox)
        layout.addWidget(header_group)
        
        # Summary Cards
        summary_group = QGroupBox("Key Metrics")
        summary_layout = QGridLayout()
        
        # Create metric cards
        self.lbl_followers = self.create_metric_card("Gathered Users", "0")
        self.lbl_following = self.create_metric_card("Following", "0")
        self.lbl_pins = self.create_metric_card("Gathered Pins", "0")
        self.lbl_boards = self.create_metric_card("Boards", "0")
        
        summary_layout.addWidget(self.lbl_followers, 0, 0)
        summary_layout.addWidget(self.lbl_following, 0, 1)
        summary_layout.addWidget(self.lbl_pins, 0, 2)
        summary_layout.addWidget(self.lbl_boards, 0, 3)
        
        summary_group.setLayout(summary_layout)
        layout.addWidget(summary_group)
        layout.addSpacing(20)
        
        # Activity History Table
        history_group = QGroupBox("Recent Automation Activity")
        history_layout = QVBoxLayout()
        
        self.table_history = QTableWidget()
        self.table_history.setColumnCount(4)
        self.table_history.setHorizontalHeaderLabels(["Date", "Action Type", "Count", "Status"])
        self.table_history.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_history.verticalHeader().setVisible(False)
        self.table_history.setMinimumHeight(200)
        
        history_layout.addWidget(self.table_history)
        history_group.setLayout(history_layout)
        layout.addWidget(history_group)
        
        # Footer Credits
        lbl_credits = QLabel("Powered by Suporter")
        lbl_credits.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_credits.setStyleSheet("color: #666; font-size: 10px; margin-top: 10px;")
        layout.addWidget(lbl_credits)
        
        layout.addStretch()
    
    def create_metric_card(self, label, value):
        """Create a metric card widget."""
        frame = QFrame()
        frame.setObjectName("MetricCard")
        frame.setMinimumHeight(100)
        
        card_layout = QVBoxLayout(frame)
        card_layout.setContentsMargins(15, 15, 15, 15)
        
        lbl_value = QLabel(value)
        lbl_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_value.setObjectName(f"value_{label}")
        lbl_value.setProperty("class", "MetricValue")
        
        lbl_title = QLabel(label)
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_title.setProperty("class", "MetricLabel")
        
        card_layout.addWidget(lbl_value)
        card_layout.addWidget(lbl_title)
        
        return frame
    
    def load_accounts(self):
        """Load accounts into dropdown."""
        self.cmb_account.clear()
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, email FROM accounts")
            accounts = cursor.fetchall()
            conn.close()
            
            for account in accounts:
                self.cmb_account.addItem(account['email'], account['id'])
                
            if self.cmb_account.count() > 0:
                self.refresh_analytics()
        except Exception as e:
            print(f"Error loading accounts: {e}")
    
    def refresh_analytics(self):
        """Refresh analytics data for selected account and date range."""
        if self.cmb_account.count() == 0:
            return
        
        account_id = self.cmb_account.currentData()
        if not account_id:
            return
        
        date_from = self.date_from.date().toString("yyyy-MM-dd")
        date_to = self.date_to.date().toString("yyyy-MM-dd")
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Get activity summary from database
            # Count gathered pins
            cursor.execute("SELECT COUNT(*) as count FROM gathered_pins")
            pin_count = cursor.fetchone()
            if pin_count:
                self.update_metric("Gathered Pins", str(pin_count['count']))
            
            # Count gathered users
            cursor.execute("SELECT COUNT(*) as count FROM gathered_users")
            user_count = cursor.fetchone()
            if user_count:
                self.update_metric("Gathered Users", str(user_count['count']))
            
            # Following and Boards would require Pinterest API
            self.update_metric("Following", "N/A")
            self.update_metric("Boards", "N/A")
            
            # Show sample activity in table
            self.table_history.setRowCount(0)
            
            # Add sample data based on actual database
            from datetime import datetime
            sample_activities = [
                (datetime.now().strftime("%Y-%m-%d"), "Pins Gathered", str(pin_count['count'] if pin_count else 0), "Complete"),
                (datetime.now().strftime("%Y-%m-%d"), "Users Gathered", str(user_count['count'] if user_count else 0), "Complete"),
            ]
            
            for activity in sample_activities:
                row = self.table_history.rowCount()
                self.table_history.insertRow(row)
                for col, value in enumerate(activity):
                    item = QTableWidgetItem(str(value))
                    self.table_history.setItem(row, col, item)
            
            conn.close()
            
        except Exception as e:
            print(f"Error refreshing analytics: {e}")
            import traceback
            traceback.print_exc()
    
    def update_metric(self, label, value):
        """Update a metric card value."""
        for child in self.findChildren(QLabel):
            if child.objectName() == f"value_{label}":
                child.setText(str(value))
                break
