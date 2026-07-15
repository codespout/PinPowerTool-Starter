from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, 
                             QMessageBox, QDialog, QAbstractItemView, QMenu, QTextEdit, QGroupBox)
from PySide6.QtCore import Qt, QTimer, Signal as pyqtSignal
from PySide6.QtGui import QAction
from src.database import get_db_connection
from datetime import datetime
import json

class SchedulerUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        
        # Auto-refresh timer for table
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.load_schedule)
        self.timer.start(5000) # Refresh every 5 seconds
        
        # Use a single-shot timer to load initial data
        QTimer.singleShot(100, self.load_schedule)
        
        # Connect to SchedulerWorker logs
        QTimer.singleShot(200, self.connect_to_scheduler_worker)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)
        
        # Header Card
        header_group = QGroupBox("Task Management")
        header_vbox = QVBoxLayout()
        header_layout = QHBoxLayout()
        title_label = QLabel("Scheduled Tasks & Automation Queue")
        title_label.setObjectName("HeaderTitle")
        
        self.btn_refresh = QPushButton("🔄 Refresh Queue")
        self.btn_refresh.setMinimumHeight(40)
        self.btn_refresh.clicked.connect(self.load_schedule)
        
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_refresh)
        header_vbox.addLayout(header_layout)
        header_group.setLayout(header_vbox)
        layout.addWidget(header_group)
        
        # Table Card
        table_group = QGroupBox("Active & Upcoming Tasks")
        table_layout = QVBoxLayout()
        
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["ID", "Account", "Action", "Target", "Scheduled Time", "Status", "Log"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        
        # Adjust column widths
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        
        table_layout.addWidget(self.table)
        table_group.setLayout(table_layout)
        layout.addWidget(table_group)
        
        # Footer Action Buttons
        footer_group = QGroupBox("Queue Actions")
        footer_layout = QHBoxLayout()
        
        self.btn_pause = QPushButton("⏸ Pause Queue") 
        self.btn_pause.setMinimumHeight(40)
        self.btn_pause.setEnabled(False)
        
        self.btn_clear_completed = QPushButton("🧹 Clear History")
        self.btn_clear_completed.setMinimumHeight(40)
        self.btn_clear_completed.clicked.connect(self.clear_completed_tasks)
        
        self.btn_delete = QPushButton("🗑 Delete Selected")
        self.btn_delete.setMinimumHeight(40)
        self.btn_delete.clicked.connect(self.delete_selected_task)
        
        footer_layout.addWidget(self.btn_pause)
        footer_layout.addStretch()
        footer_layout.addWidget(self.btn_clear_completed)
        footer_layout.addWidget(self.btn_delete)
        
        footer_group.setLayout(footer_layout)
        layout.addWidget(footer_group)
        
        # Live Execution Log
        log_group = QGroupBox("Scheduler Live Log")
        log_layout = QVBoxLayout()
        
        self.txt_logs = QTextEdit()
        self.txt_logs.setReadOnly(True)
        self.txt_logs.setMinimumHeight(120)
        self.txt_logs.setPlaceholderText("Execution events will appear here...")
        log_layout.addWidget(self.txt_logs)
        
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        layout.addStretch()

    def load_schedule(self):
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            query = """
                SELECT s.id, a.email, s.action_type, s.target_data, s.scheduled_time, s.status, s.log_output 
                FROM scheduled_actions s
                LEFT JOIN accounts a ON s.account_id = a.id
                ORDER BY s.scheduled_time ASC
            """
            cursor.execute(query)
            tasks = cursor.fetchall()
            conn.close()
            
            self.table.setRowCount(0)
            
            for row_idx, task in enumerate(tasks):
                self.table.insertRow(row_idx)
                
                # Parse Target Data 
                target_str = "..."
                try:
                    data = json.loads(task['target_data'])
                    if task['action_type'] == 'repin':
                        target_str = f"Board: {data.get('board_name')}"
                    elif task['action_type'] == 'upload':
                        target_str = f"File: {data.get('title')}"
                except:
                    target_str = str(task['target_data'])[:20]

                self.table.setItem(row_idx, 0, QTableWidgetItem(str(task['id'])))
                self.table.setItem(row_idx, 1, QTableWidgetItem(str(task['email'])))
                self.table.setItem(row_idx, 2, QTableWidgetItem(str(task['action_type']).capitalize()))
                self.table.setItem(row_idx, 3, QTableWidgetItem(target_str))
                self.table.setItem(row_idx, 4, QTableWidgetItem(str(task['scheduled_time'])))
                
                status_item = QTableWidgetItem(display_status(task['status']))
                if task['status'] == 'completed':
                    status_item.setData(Qt.ItemDataRole.UserRole, "completed")
                elif task['status'] == 'failed':
                    status_item.setData(Qt.ItemDataRole.UserRole, "failed")
                elif task['status'] == 'pending':
                    status_item.setData(Qt.ItemDataRole.UserRole, "pending")
                elif task['status'] == 'processing':
                    status_item.setData(Qt.ItemDataRole.UserRole, "processing")
                    
                self.table.setItem(row_idx, 5, status_item)
                self.table.setItem(row_idx, 6, QTableWidgetItem(str(task['log_output'] or "")))

        except Exception as e:
            print(f"Error loading schedule: {e}")

    def show_context_menu(self, position):
        menu = QMenu()
        delete_action = QAction("Delete Task", self)
        delete_action.triggered.connect(self.delete_selected_task)
        menu.addAction(delete_action)
        menu.exec(self.table.viewport().mapToGlobal(position))

    def delete_selected_task(self):
        rows = sorted(set(index.row() for index in self.table.selectedIndexes()))
        if not rows:
            return
            
        confirm = QMessageBox.question(self, "Confirm Delete", 
                                      f"Delete {len(rows)} selected task(s)?",
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if confirm == QMessageBox.StandardButton.Yes:
            conn = get_db_connection()
            cursor = conn.cursor()
            for row in rows:
                task_id = self.table.item(row, 0).text()
                cursor.execute("DELETE FROM scheduled_actions WHERE id = ?", (task_id,))
            conn.commit()
            conn.close()
            self.load_schedule()

    def clear_completed_tasks(self):
        confirm = QMessageBox.question(self, "Confirm Clear", 
                                      "Delete all completed/failed tasks from history?",
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if confirm == QMessageBox.StandardButton.Yes:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM scheduled_actions WHERE status IN ('completed', 'failed', 'cancelled')")
            conn.commit()
            conn.close()
            self.load_schedule()
    
    def connect_to_scheduler_worker(self):
        """Connect to SchedulerWorker to receive execution logs."""
        try:
            from src.modules.automation_manager import AutomationManager
            manager = AutomationManager()
            scheduler_worker = manager.get_worker('scheduler')
            
            if scheduler_worker:
                # Restore existing logs
                buffered_logs = manager.get_logs('scheduler')
                for log_line in buffered_logs:
                    self.txt_logs.append(log_line)
                
                # Connect to future logs
                try:
                    scheduler_worker.log_signal.connect(self.log)
                except:
                    pass  # Already connected
        except Exception as e:
            print(f"Error connecting to scheduler: {e}")
    
    def log(self, message):
        """Add log message to the display."""
        self.txt_logs.append(message)

def display_status(status):
    if status == 'pending': return '⏳ Pending'
    if status == 'processing': return '⚙ Processing'
    if status == 'completed': return '✓ Completed'
    if status == 'failed': return '✗ Failed'
    if status == 'cancelled': return '⊘ Cancelled'
    return status
