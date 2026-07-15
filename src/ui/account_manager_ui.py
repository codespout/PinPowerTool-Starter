from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, 
                             QMessageBox, QCheckBox, QAbstractItemView, QGroupBox)
from PySide6.QtCore import Qt
from src.database import get_db_connection
from src.modules.actions import PinterestAutomation
import json

class AccountManagerUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.load_accounts()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)

        # Title
        lbl_title = QLabel("👥 Account Manager")
        lbl_title.setObjectName("HeaderTitle")
        layout.addWidget(lbl_title)

        # Input Form Card
        add_group = QGroupBox("Add New Account")
        form_layout = QVBoxLayout()
        
        row1 = QHBoxLayout()
        self.txt_email = QLineEdit()
        self.txt_email.setPlaceholderText("Email Address")
        
        self.txt_password = QLineEdit()
        self.txt_password.setPlaceholderText("Pinterest Password")
        self.txt_password.setEchoMode(QLineEdit.EchoMode.Password)
        
        self.chk_show_pass = QCheckBox("Show")
        self.chk_show_pass.stateChanged.connect(self.toggle_password)
        
        row1.addWidget(self.txt_email)
        row1.addWidget(self.txt_password)
        row1.addWidget(self.chk_show_pass)
        form_layout.addLayout(row1)
        
        row2 = QHBoxLayout()
        self.txt_proxy = QLineEdit()
        self.txt_proxy.setPlaceholderText("Proxy Configuration (ip:port:user:pass) - Optional")
        
        self.btn_add = QPushButton("🚀 Add & Verify Connection")
        self.btn_add.setMinimumHeight(40)
        self.btn_add.clicked.connect(self.add_account)
        
        row2.addWidget(self.txt_proxy)
        row2.addWidget(self.btn_add)
        form_layout.addLayout(row2)
        
        add_group.setLayout(form_layout)
        layout.addWidget(add_group)

        # Table Card
        table_group = QGroupBox("Connected Accounts")
        table_layout = QVBoxLayout()
        
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Name", "Email", "Type", "Status", "Proxy", "Active"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setMinimumHeight(200) # Reduced to allow more flexibility
        table_layout.addWidget(self.table)
        
        # Action Buttons
        action_layout = QHBoxLayout()
        self.btn_set_active = QPushButton("⭐ Toggle Active State")
        self.btn_set_active.setMinimumHeight(40)
        self.btn_set_active.clicked.connect(self.set_active_account)
        
        self.btn_delete = QPushButton("🗑️ Delete Account")
        self.btn_delete.setMinimumHeight(40)
        self.btn_delete.clicked.connect(self.delete_account)
        
        action_layout.addWidget(self.btn_set_active)
        action_layout.addWidget(self.btn_delete)
        table_layout.addLayout(action_layout)
        
        table_group.setLayout(table_layout)
        layout.addWidget(table_group)

    def toggle_password(self, state):
        if state == 2: # Checked
            self.txt_password.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.txt_password.setEchoMode(QLineEdit.EchoMode.Password)

    def load_accounts(self):
        self.table.setRowCount(0)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email, account_type, status, proxy, is_selected FROM accounts")
        accounts = cursor.fetchall()
        conn.close()

        for row in accounts:
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)
            
            # Name
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(row['name'] or 'Unknown')))
            # Email
            self.table.setItem(row_idx, 1, QTableWidgetItem(row['email']))
            # Type
            self.table.setItem(row_idx, 2, QTableWidgetItem(row['account_type']))
            # Status
            self.table.setItem(row_idx, 3, QTableWidgetItem(row['status']))
            # Proxy
            self.table.setItem(row_idx, 4, QTableWidgetItem(row['proxy'] or 'None'))
            # Active
            active_item = QTableWidgetItem("YES" if row['is_selected'] else "NO")
            if row['is_selected']:
                active_item.setBackground(Qt.GlobalColor.green)
            self.table.setItem(row_idx, 5, active_item)
            
            # Store ID in hidden data
            self.table.item(row_idx, 0).setData(Qt.ItemDataRole.UserRole, row['id'])

    def add_account(self):
        email = self.txt_email.text().strip()
        password = self.txt_password.text().strip()
        proxy_str = self.txt_proxy.text().strip()
        
        if not email or not password:
            QMessageBox.warning(self, "Error", "Email and Password are required.")
            return

        # Parse Proxy
        proxy_dict = None
        if proxy_str:
            parts = proxy_str.split(':')
            if len(parts) >= 2:
                proxy_dict = {'server': f"http://{parts[0]}:{parts[1]}"}
                if len(parts) >= 4:
                    proxy_dict['username'] = parts[2]
                    proxy_dict['password'] = parts[3]
        
        # Verify Login
        self.btn_add.setEnabled(False)
        self.btn_add.setText("Verifying...")
        # Force UI update
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()

        automation = PinterestAutomation(headless=False, proxy=proxy_dict)
        result = automation.verify_login(email, password)
        
        if result['success']:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Deactivate others if this is the first one? No, user sets active manually.
            
            cursor.execute("""
                INSERT INTO accounts (email, password, proxy, status, cookies, account_type, name)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (email, password, proxy_str, 'Active', json.dumps(result['cookies']), result['account_type'], result['name']))
            
            conn.commit()
            conn.close()
            
            self.txt_email.clear()
            self.txt_password.clear()
            self.txt_proxy.clear()
            self.load_accounts()
            QMessageBox.information(self, "Success", f"Account verified and added!\nType: {result['account_type']}")
        else:
            QMessageBox.critical(self, "Verification Failed", result['message'])
            
        self.btn_add.setEnabled(True)
        self.btn_add.setText("Add & Verify")

    def set_active_account(self):
        selected_items = self.table.selectedItems()
        if not selected_items:
            return
            
        row = selected_items[0].row()
        account_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        
        # Get current state
        current_state_text = self.table.item(row, 5).text()
        new_state = 1 if current_state_text == "NO" else 0
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Toggle selected
        cursor.execute("UPDATE accounts SET is_selected = ? WHERE id = ?", (new_state, account_id))
        
        conn.commit()
        conn.close()
        self.load_accounts()

    def delete_account(self):
        selected_items = self.table.selectedItems()
        if not selected_items:
            return
            
        row = selected_items[0].row()
        account_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        
        confirm = QMessageBox.question(self, "Confirm", "Are you sure you want to delete this account?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if confirm == QMessageBox.StandardButton.Yes:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
            conn.commit()
            conn.close()
            self.load_accounts()
