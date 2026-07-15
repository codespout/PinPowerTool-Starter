import sys
import json
import random
import time
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTextEdit, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QGroupBox, QLineEdit, QCheckBox, QComboBox, 
                             QProgressBar, QTabWidget, QMessageBox, QScrollArea)
from PySide6.QtCore import Qt, QThread, Signal as pyqtSignal
from src.database import get_db_connection
from src.modules.actions import PinterestAutomation
from src.modules.settings_manager import SettingsManager

class DMWorker(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, account_ids, templates, settings):
        super().__init__()
        self.account_ids = account_ids
        self.templates = templates
        self.settings = settings
        self.is_running = True

    def run(self):
        try:
            self.log_signal.emit("Starting Relationship Builder Process...")
            
            for account_id in self.account_ids:
                if not self.is_running: break
                
                # Fetch account info
                conn = get_db_connection()
                account = conn.execute('SELECT * FROM accounts WHERE id = ?', (account_id,)).fetchone()
                conn.close()
                
                if not account: continue
                
                self.log_signal.emit(f"Processing Account: {account['email']}")
                
                # Load existing cookies
                cookies = None
                if account['cookies']:
                    try:
                        cookies = json.loads(account['cookies'])
                    except:
                        pass
                
                automation = PinterestAutomation(proxy=account['proxy'])
                automation.start_browser(cookies=cookies)
                
                if not automation.ensure_logged_in(account['email'], account['password']):
                    self.log_signal.emit(f"✗ Login failed for {account['email']}")
                    automation.stop_browser()
                    continue
                
                # Save fresh cookies
                try:
                    fresh_cookies = automation.context.cookies()
                    conn_update = get_db_connection()
                    conn_update.execute('UPDATE accounts SET cookies = ? WHERE id = ?', 
                                      (json.dumps(fresh_cookies), account_id))
                    conn_update.commit()
                    conn_update.close()
                except:
                    pass
                
                # Step 1: Scan Notifications
                self.log_signal.emit("Scanning notifications for recent engagements...")
                engagements = automation.get_latest_engagements(limit=20)
                
                if not engagements:
                    self.log_signal.emit("No new engagements found to build relationships with.")
                    automation.stop_browser()
                    continue
                
                self.log_signal.emit(f"Found {len(engagements)} potential fans!")
                
                sent_count = 0
                max_dms = self.settings.get('max_dms_per_account', 5)
                
                for fan in engagements:
                    if not self.is_running: break
                    if sent_count >= max_dms:
                        self.log_signal.emit(f"Limit reached for {account['email']} ({max_dms} DMs)")
                        break
                        
                    user_url = fan.get('url')
                    username = fan.get('username', 'there')
                    interaction_type = fan.get('type') # follow, save, like, etc.
                    
                    # Check if already messaged for this reason
                    if self.has_already_messaged(account_id, user_url, interaction_type):
                        self.log_signal.emit(f"Skipping {username} - Already messaged for {interaction_type}")
                        continue
                    
                    # Select template based on type
                    template = self.templates.get(interaction_type, self.templates.get('general', ''))
                    if not template:
                        self.log_signal.emit(f"No template found for {interaction_type}. Skipping.")
                        continue
                        
                    self.log_signal.emit(f"Using '{interaction_type}' template...")
                    message = template.replace('{username}', username)
                    
                    self.log_signal.emit(f"Sending message to {username}...")
                    status = automation.send_direct_message(user_url, message)
                    
                    if status == True:
                        self.save_dm_history(account_id, user_url, interaction_type, message)
                        self.log_signal.emit(f"✓ Message sent to {username}")
                        sent_count += 1
                        # Human random delay
                        wait_time = random.randint(self.settings.get('min_delay', 30), self.settings.get('max_delay', 60))
                        self.log_signal.emit(f"Waiting {wait_time}s before next interaction...")
                        time.sleep(wait_time)
                    elif status == "restricted":
                        self.log_signal.emit(f"⚠️ {username} has a restricted profile (Contact only). Skipping.")
                        # Still save to history so we don't try again for this specific interaction?
                        # user_url + interaction_type is our uniqueness constraint.
                        # If we skip, we skip.
                        self.save_dm_history(account_id, user_url, interaction_type, "[RESTRICTED]")
                    else:
                        self.log_signal.emit(f"✗ Failed to message {username}")
                
                automation.stop_browser()
                self.log_signal.emit(f"Finished processing {account['email']}")
            
            self.finished_signal.emit(True, "Process completed successfully")
            
        except Exception as e:
            self.log_signal.emit(f"Error in DM worker: {str(e)}")
            self.finished_signal.emit(False, str(e))

    def has_already_messaged(self, account_id, user_url, interaction_type):
        conn = get_db_connection()
        res = conn.execute('SELECT 1 FROM sent_dms WHERE account_id = ? AND receiver_url = ? AND interaction_type = ?', 
                          (account_id, user_url, interaction_type)).fetchone()
        conn.close()
        return res is not None

    def save_dm_history(self, account_id, user_url, interaction_type, message):
        conn = get_db_connection()
        conn.execute('INSERT INTO sent_dms (account_id, receiver_url, interaction_type, message) VALUES (?, ?, ?, ?)',
                    (account_id, user_url, interaction_type, message))
        conn.commit()
        conn.close()

    def stop(self):
        self.is_running = False

class DMUI(QWidget):
    def __init__(self):
        super().__init__()
        self.settings_manager = SettingsManager()
        self.setup_ui()
        self.load_accounts()
        self.load_saved_settings()

    def setup_ui(self):
        main_vbox = QVBoxLayout(self)
        
        # Scroll Area Setup
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        
        self.scroll_content = QWidget()
        layout = QVBoxLayout(self.scroll_content)
        
        # 🟢 TOP: Account Selection
        self.account_group = QGroupBox("Target Accounts")
        self.account_group.setMinimumHeight(200) # Reduced to allow scrollability
        acc_layout = QVBoxLayout()
        
        btn_acc_layout = QHBoxLayout()
        self.btn_select_all = QPushButton("Select All")
        self.btn_deselect_all = QPushButton("Deselect All")
        self.btn_select_all.clicked.connect(self.select_all_accounts)
        self.btn_deselect_all.clicked.connect(self.deselect_all_accounts)
        btn_acc_layout.addWidget(self.btn_select_all)
        btn_acc_layout.addWidget(self.btn_deselect_all)
        btn_acc_layout.addStretch()
        acc_layout.addLayout(btn_acc_layout)

        self.account_table = QTableWidget(0, 3)
        self.account_table.setHorizontalHeaderLabels(["", "Account", "Status"])
        self.account_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.account_table.setMinimumHeight(200)
        self.account_table.setColumnWidth(0, 30)
        acc_layout.addWidget(self.account_table)
        self.account_group.setLayout(acc_layout)
        layout.addWidget(self.account_group)

        # 🔵 MIDDLE: Multi-Scenario Templates
        template_group = QGroupBox("Personalized Message Templates")
        temp_layout = QVBoxLayout()
        
        self.tabs = QTabWidget()
        
        # Scenario 1: New Follower
        self.tab_follow = QWidget()
        follow_layout = QVBoxLayout()
        follow_layout.addWidget(QLabel("Message for New Followers:"))
        self.txt_follow_temp = QTextEdit()
        self.txt_follow_temp.setPlaceholderText("Hi {username}, thanks for the follow! I love your boards...")
        follow_layout.addWidget(self.txt_follow_temp)
        self.tab_follow.setLayout(follow_layout)
        
        # Scenario 2: Pin Saver
        self.tab_save = QWidget()
        save_layout = QVBoxLayout()
        save_layout.addWidget(QLabel("Message for Pin Savers:"))
        self.txt_save_temp = QTextEdit()
        self.txt_save_temp.setPlaceholderText("Hey {username}, saw you saved my pin! Glad you liked it...")
        save_layout.addWidget(self.txt_save_temp)
        self.tab_save.setLayout(save_layout)
        
        # Scenario 3: Pin Liker
        self.tab_like = QWidget()
        like_layout = QVBoxLayout()
        like_layout.addWidget(QLabel("Message for Pin Likers:"))
        self.txt_like_temp = QTextEdit()
        self.txt_like_temp.setPlaceholderText("Hi {username}, thanks for liking my content! Check out...")
        like_layout.addWidget(self.txt_like_temp)
        self.tab_like.setLayout(like_layout)
        
        self.tabs.addTab(self.tab_follow, "New Follower")
        self.tabs.addTab(self.tab_save, "Pin Saver")
        self.tabs.addTab(self.tab_like, "Pin Liker")
        
        temp_layout.addWidget(self.tabs)
        
        btn_temp_layout = QHBoxLayout()
        btn_temp_layout.addStretch()
        self.btn_save_settings = QPushButton("💾 Save All Settings")
        self.btn_save_settings.setFixedWidth(200)
        self.btn_save_settings.clicked.connect(self.save_templates)
        btn_temp_layout.addWidget(self.btn_save_settings)
        temp_layout.addLayout(btn_temp_layout)
        
        temp_layout.addWidget(QLabel("Tip: Use {username} for personalization."))
        template_group.setLayout(temp_layout)
        layout.addWidget(template_group)

        # 🛡️ SAFETY GUIDELINES
        safety_group = QGroupBox("⚠️ Safety Guidelines & Account Risk")
        safety_layout = QVBoxLayout()
        safety_info = QLabel(
            "<div>"
            "<p><b>Direct Messaging (DM) is a high-risk activity.</b> Pinterest is very sensitive to automated messaging. "
            "Follow these rules to protect your account:</p>"
            "<ul>"
            "<li><b>Keep Limits Low:</b> Do not exceed 5-15 DMs per day per account.</li>"
            "<li><b>Randomize Delays:</b> Use at least 30-120 seconds between messages.</li>"
            "<li><b>Non-Promotional:</b> Your first message should be friendly and non-salesy. Avoid links.</li>"
            "<li><b>Vary Your Text:</b> Use different templates and the <b>{username}</b> tag.</li>"
            "<li><b>Aged Accounts:</b> Only use this feature on accounts at least 30 days old.</li>"
            "</ul>"
            "</div>"
        )
        safety_info.setWordWrap(True)
        safety_layout.addWidget(safety_info)
        safety_group.setLayout(safety_layout)
        layout.addWidget(safety_group)

        # 🟡 BOTTOM: Settings & Execution
        exec_layout = QHBoxLayout()
        
        settings_group = QGroupBox("Safety Settings")
        set_layout = QVBoxLayout()
        
        limit_layout = QHBoxLayout()
        limit_layout.addWidget(QLabel("DMs per Account:"))
        self.sb_limit = QLineEdit("5")
        self.sb_limit.setFixedWidth(50)
        limit_layout.addWidget(self.sb_limit)
        set_layout.addLayout(limit_layout)
        
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("Delay (s):"))
        self.sb_min_delay = QLineEdit("30")
        self.sb_min_delay.setFixedWidth(40)
        self.sb_max_delay = QLineEdit("60")
        self.sb_max_delay.setFixedWidth(40)
        delay_layout.addWidget(self.sb_min_delay)
        delay_layout.addWidget(QLabel("-"))
        delay_layout.addWidget(self.sb_max_delay)
        set_layout.addLayout(delay_layout)
        
        settings_group.setLayout(set_layout)
        exec_layout.addWidget(settings_group)
        
        self.btn_start = QPushButton("🚀 Start Building Relationships")
        self.btn_start.setFixedHeight(80)
        self.btn_start.clicked.connect(self.start_process)
        exec_layout.addWidget(self.btn_start)
        
        layout.addLayout(exec_layout)

        # 🔴 LOGS
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("Activity Log...")
        layout.addWidget(self.log_output)
        
        # Finalize Scroll Area
        self.scroll.setWidget(self.scroll_content)
        main_vbox.addWidget(self.scroll)

    def load_accounts(self):
        try:
            conn = get_db_connection()
            accounts = conn.execute('SELECT id, email FROM accounts').fetchall()
            conn.close()
            
            self.account_table.setRowCount(len(accounts))
            self.account_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            
            for i, account in enumerate(accounts):
                # Native Checkable Item
                chk_item = QTableWidgetItem()
                chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                chk_item.setCheckState(Qt.CheckState.Unchecked)
                self.account_table.setItem(i, 0, chk_item)
                
                email_item = QTableWidgetItem(account['email'])
                email_item.setData(Qt.ItemDataRole.UserRole, account['id'])
                self.account_table.setItem(i, 1, email_item)
                
                self.account_table.setItem(i, 2, QTableWidgetItem("Ready"))
            
            # Allow toggling by clicking anywhere in the row
            self.account_table.cellClicked.connect(self.toggle_row_check)
                
        except Exception as e:
            print(f"Error loading accounts: {e}")

    def load_saved_settings(self):
        """Load templates and safety settings from database."""
        try:
            templates = self.settings_manager.get_setting('dm_templates')
            if templates:
                self.txt_follow_temp.setPlainText(templates.get('follow', ''))
                self.txt_save_temp.setPlainText(templates.get('save', ''))
                self.txt_like_temp.setPlainText(templates.get('like', ''))
            
            safety = self.settings_manager.get_setting('dm_safety')
            if safety:
                self.sb_limit.setText(str(safety.get('limit', 5)))
                self.sb_min_delay.setText(str(safety.get('min_delay', 30)))
                self.sb_max_delay.setText(str(safety.get('max_delay', 60)))
        except Exception as e:
            print(f"Error loading DM settings: {e}")

    def save_templates(self, show_msg=True):
        """Persist current UI values to settings database."""
        try:
            templates = {
                'follow': self.txt_follow_temp.toPlainText().strip(),
                'save': self.txt_save_temp.toPlainText().strip(),
                'like': self.txt_like_temp.toPlainText().strip()
            }
            safety = {
                'limit': int(self.sb_limit.text()),
                'min_delay': int(self.sb_min_delay.text()),
                'max_delay': int(self.sb_max_delay.text())
            }
            self.settings_manager.set_setting('dm_templates', templates)
            self.settings_manager.set_setting('dm_safety', safety)
            if show_msg:
                QMessageBox.information(self, "Success", "Settings saved successfully!")
            return True
        except Exception as e:
            if show_msg:
                QMessageBox.critical(self, "Error", f"Failed to save settings: {e}")
            return False

    def select_all_accounts(self):
        for i in range(self.account_table.rowCount()):
            item = self.account_table.item(i, 0)
            if item: item.setCheckState(Qt.CheckState.Checked)

    def deselect_all_accounts(self):
        for i in range(self.account_table.rowCount()):
            item = self.account_table.item(i, 0)
            if item: item.setCheckState(Qt.CheckState.Unchecked)

    def toggle_row_check(self, row, column):
        # If user clicked the checkbox column, let the native handler work
        # If they clicked email or status columns, toggle the check manually
        if column > 0:
            item = self.account_table.item(row, 0)
            if item:
                new_state = Qt.CheckState.Checked if item.checkState() == Qt.CheckState.Unchecked else Qt.CheckState.Unchecked
                item.setCheckState(new_state)

    def log(self, text):
        self.log_output.append(text)

    def start_process(self):
        selected_ids = []
        for i in range(self.account_table.rowCount()):
            chk_item = self.account_table.item(i, 0)
            if chk_item and chk_item.checkState() == Qt.CheckState.Checked:
                acc_id = self.account_table.item(i, 1).data(Qt.ItemDataRole.UserRole)
                selected_ids.append(acc_id)
        
        if not selected_ids:
            QMessageBox.warning(self, "Warning", "Please select at least one account.")
            return
            
        # Save before starting
        if not self.save_templates(show_msg=False):
            return

        templates = self.settings_manager.get_setting('dm_templates')
        safety = self.settings_manager.get_setting('dm_safety')
        
        if not any(templates.values()):
            QMessageBox.warning(self, "Warning", "Please enter at least one message template.")
            return

        settings = {
            'max_dms_per_account': safety.get('limit', 5),
            'min_delay': safety.get('min_delay', 30),
            'max_delay': safety.get('max_delay', 60)
        }
        
        self.btn_start.setEnabled(False)
        self.btn_start.setText("Working...")
        
        self.worker = DMWorker(selected_ids, templates, settings)
        self.worker.log_signal.connect(self.log)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()

    def on_finished(self, success, message):
        self.btn_start.setEnabled(True)
        self.btn_start.setText("🚀 Start Building Relationships")
        if success:
            QMessageBox.information(self, "Success", "DM process finished.")
        else:
            QMessageBox.critical(self, "Error", f"Process aborted: {message}")
