from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QRadioButton, QButtonGroup, QSpinBox,
                             QCheckBox, QComboBox, QTextEdit, QMessageBox, QGroupBox)
from PySide6.QtCore import QThread, Signal as pyqtSignal, Qt
from src.database import get_db_connection
from src.modules.actions import PinterestAutomation
import time
import json
from datetime import datetime, timedelta
from src.modules.settings_helper import AutomationSettings

class FollowWorker(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(int)  # Number of users processed
    
    def __init__(self, mode, limit, unfollow_options=None, rotation_options=None):
        super().__init__()
        self.mode = mode  # 'follow' or 'unfollow'
        self.limit = limit
        self.unfollow_options = unfollow_options or {}
        self.rotation_options = rotation_options or {'enabled': False, 'limit': 10}
        self.is_running = True
        
        # Load automation settings
        self.auto_settings = AutomationSettings()
        
        # We'll initialize automation inside run() for rotation support
        self.automation = None
        self.current_account = None
    
    def get_selected_accounts(self):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM accounts WHERE is_selected = 1 ORDER BY id ASC")
        accounts = cursor.fetchall()
        conn.close()
        return accounts
    
    def run(self):
        accounts = self.get_selected_accounts()
        if not accounts:
            self.log_signal.emit("Error: No active accounts selected in Account Manager")
            self.finished_signal.emit(0)
            return

        total_processed = 0
        account_index = 0
        
        while self.is_running and total_processed < self.limit:
            self.current_account = accounts[account_index % len(accounts)]
            email = self.current_account['email']
            
            self.log_signal.emit(f"\n🔄 [Account {account_index % len(accounts) + 1}/{len(accounts)}] Switching to: {email}")
            
            # Configure automation for current account
            account_proxy = self.current_account['proxy']
            proxy_dict = self.auto_settings.get_proxy_config(account_proxy)
            self.automation = PinterestAutomation(headless=False, proxy=proxy_dict)
            
            # Load cookies
            cookies = None
            if self.current_account['cookies']:
                try:
                    cookies = json.loads(self.current_account['cookies'])
                except:
                    pass
            
            # Start browser
            if not self.automation.start_browser(cookies=cookies):
                self.log_signal.emit(f"Error: Failed to start browser for {email}")
                # Try next account instead of failing entirely
                account_index += 1
                if account_index >= len(accounts) and not self.rotation_options['enabled']:
                     break
                continue
            
            # Ensure logged in
            if not self.automation.ensure_logged_in(email, self.current_account['password']):
                self.log_signal.emit(f"Error: Login failed for {email}")
                self.automation.stop_browser()
                account_index += 1
                if account_index >= len(accounts) and not self.rotation_options['enabled']:
                     break
                continue
            
            # Save fresh cookies
            try:
                fresh_cookies = self.automation.context.cookies()
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE accounts SET cookies = ? WHERE id = ?", 
                              (json.dumps(fresh_cookies), self.current_account['id']))
                conn.commit()
                conn.close()
            except: pass

            # Human Warmup if enabled
            self.auto_settings.reload_settings()
            if self.auto_settings.settings.get('warmup_enabled'):
                duration = self.auto_settings.settings.get('warmup_duration', 5)
                self.automation.human_warmup(duration_mins=duration, log_signal=self.log_signal)
            
            # Determine how many to do with THIS account
            rotation_limit = self.rotation_options['limit'] if self.rotation_options['enabled'] else self.limit
            batch_limit = min(rotation_limit, self.limit - total_processed)
            
            self.log_signal.emit(f"  → Goal for this session: {batch_limit} actions")
            
            batch_processed = 0
            if self.mode == 'follow':
                batch_processed = self.do_follow(batch_limit)
            else:
                batch_processed = self.do_unfollow(batch_limit)
            
            total_processed += batch_processed
            
            # Close browser for this account
            self.automation.stop_browser()
            
            if not self.is_running or total_processed >= self.limit:
                break
                
            if self.rotation_options['enabled']:
                self.log_signal.emit(f"\n♻ Finished batch for {email}. Rotating account...")
                account_index += 1
                time.sleep(5) # Small buffer between rotations
            else:
                # If rotation not enabled, we just finish with the first account
                break

        self.finished_signal.emit(total_processed)
    
    def do_follow(self, batch_limit):
        """Follow users from gathered database."""
        # Log active filters
        filter_summary = self.auto_settings.get_filter_summary()
        self.log_signal.emit(f"Active filters: {filter_summary}")
        self.log_signal.emit("")
        
        self.log_signal.emit("Fetching users to follow from database...")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        # Fetch more users than limit to account for filtering
        cursor.execute("SELECT user_url, username FROM gathered_users LIMIT ?", (batch_limit * 10,))
        users = cursor.fetchall()
        conn.close()
        
        if not users:
            self.log_signal.emit("No gathered users found in database")
            return 0
        
        self.log_signal.emit(f"Found {len(users)} users, will follow up to {batch_limit} in this session")
        
        processed = 0
        skipped = 0
        
        for user in users:
            if not self.is_running or processed >= batch_limit:
                break
            
            user_url = user['user_url']
            username = user['username'] if user['username'] else user_url.rstrip('/').split('/')[-1]
            
            try:
                # Check if we should skip this user based on filters
                # We need to scrape user data first if filters are active
                # This adds overhead, so we only do it if filters are enabled
                
                # Check if any user filters are active
                has_active_filters = (
                    self.auto_settings.settings.get("filter_followers_mode", 0) != 0 or
                    self.auto_settings.settings.get("filter_following_mode", 0) != 0 or
                    self.auto_settings.settings.get("filter_user_pins_mode", 0) != 0
                )
                
                if has_active_filters:
                    self.log_signal.emit(f"Analyzing user: {username}")
                    user_data = self.automation.get_user_details(user_url)
                    
                    if not user_data:
                        self.log_signal.emit(f"  ⚠ Could not get details for {username}, skipping")
                        skipped += 1
                        continue
                        
                    should_skip, reason = self.auto_settings.should_skip_user(user_data)
                    if should_skip:
                        self.log_signal.emit(f"  ⊗ Skipped: {reason}")
                        skipped += 1
                        continue
                
                self.log_signal.emit(f"Following: {username}")
                
                # Smart Skip: Provide skip check callback for DB fallback after UI check
                account_id = self.current_account['id']
                def db_skip_check(url):
                    return self.auto_settings.is_user_followed(account_id, url)
                
                result = self.automation.follow_user(user_url, skip_check=db_skip_check)
                
                success = False
                msg = ""
                is_already_done = False
                
                if isinstance(result, tuple):
                    success, msg = result
                    if "Already" in msg:
                        is_already_done = True
                else:
                    success = result
                    msg = "Following successfully" if success else "Failed to follow"
                
                if success:
                    if not is_already_done:
                        processed += 1
                        # Increment action count for breaks only for actual actions
                        self.auto_settings.increment_action_count()
                    
                    # Save to followed_users table with account_id
                    if "DB" not in msg:
                        try:
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            cursor.execute(
                                "INSERT OR IGNORE INTO followed_users (account_id, user_url, username, followed_date) VALUES (?, ?, ?, ?)",
                                (account_id, user_url, username, datetime.now())
                            )
                            conn.commit()
                            conn.close()
                        except Exception as e:
                            print(f"Error saving to followed_users: {e}")
                    
                    self.log_signal.emit(f"  ✓ {msg} ({processed}/{batch_limit})")
                    
                    # Check if we should take a break
                    should_break, duration = self.auto_settings.should_take_break()
                    if should_break:
                        self.log_signal.emit(f"")
                        self.log_signal.emit(f"⏸ Taking a {duration}s break...")
                        time.sleep(duration)
                        self.log_signal.emit(f"⏵ Resuming automation")
                        self.log_signal.emit(f"")
                else:
                    self.log_signal.emit(f"  ✗ Failed to follow {username}")
                
                # Apply delay
                if processed < batch_limit:
                    delay = self.auto_settings.get_random_delay()
                    self.log_signal.emit(f"  ⏱ Waiting {delay}s...")
                    time.sleep(delay)
                
            except Exception as e:
                self.log_signal.emit(f"Error following {username}: {e}")
        
        return processed
    
    def do_unfollow(self, batch_limit):
        """Unfollow users with smart filtering."""
        self.log_signal.emit("Fetching users to unfollow...")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Build query based on options
        query = "SELECT user_url, username, followed_date FROM followed_users WHERE account_id = ?"
        params = [self.current_account['id']]
        
        # Filter by date
        if self.unfollow_options.get('exclude_recent'):
            days = self.unfollow_options.get('exclude_days', 7)
            cutoff_date = datetime.now() - timedelta(days=days)
            query += " AND followed_date < ?"
            params.append(cutoff_date)
        
        query += " LIMIT ?"
        params.append(batch_limit * 10)
        
        cursor.execute(query, params)
        users = cursor.fetchall()
        conn.close()
        
        if not users:
            self.log_signal.emit("No users found matching filter criteria")
            return 0
        
        self.log_signal.emit(f"Found {len(users)} users, will unfollow up to {batch_limit} in this session")
        
        processed = 0
        for user in users:
            if not self.is_running or processed >= batch_limit:
                break
            
            user_url = user['user_url']
            username = user['username']
            
            # Check if following back (if option enabled)
            if self.unfollow_options.get('only_not_following_back'):
                try:
                    self.log_signal.emit(f"Checking if {username} follows back...")
                    if self.automation.check_if_following_back(user_url):
                        self.log_signal.emit(f"  ⊘ Skipping {username} (follows you back)")
                        continue
                except Exception as e:
                    self.log_signal.emit(f"Warning: Could not check follow status for {username}")
            
            try:
                self.log_signal.emit(f"Unfollowing: {username}")
                
                if self.automation.unfollow_user(user_url):
                    processed += 1
                    
                    # Remove from followed_users table
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM followed_users WHERE user_url = ?", (user_url,))
                    conn.commit()
                    conn.close()
                    
                    self.log_signal.emit(f"  ✓ Unfollowed {username} ({processed}/{batch_limit})")
                    
                    # Increment action count for breaks
                    self.auto_settings.increment_action_count()
                    
                    # Check if we should take a break
                    should_break, duration = self.auto_settings.should_take_break()
                    if should_break:
                        self.log_signal.emit(f"")
                        self.log_signal.emit(f"⏸ Taking a {duration}s break...")
                        time.sleep(duration)
                        self.log_signal.emit(f"⏵ Resuming automation")
                        self.log_signal.emit(f"")
                else:
                    self.log_signal.emit(f"  ✗ Failed to unfollow {username}")
                
                # Apply delay
                if processed < batch_limit:
                    delay = self.auto_settings.get_random_delay()
                    self.log_signal.emit(f"  ⏱ Waiting {delay}s...")
                    time.sleep(delay)
                
            except Exception as e:
                self.log_signal.emit(f"Error unfollowing {username}: {e}")
        
        return processed
    
    def stop(self):
        self.is_running = False


class AutoFollowUI(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.setup_ui()
        
        # Check if there's an existing worker and restore its state
        from src.modules.automation_manager import AutomationManager
        manager = AutomationManager()
        existing_worker = manager.get_worker('follow')
        
        if existing_worker and manager.is_worker_running('follow'):
            self.log("✓ Reconnected to running task")
            self.worker = existing_worker
            
            # Restore buffered logs
            buffered_logs = manager.get_logs('follow')
            for log_line in buffered_logs:
                self.txt_logs.append(log_line)
            
            # Reconnect signals
            try:
                self.worker.log_signal.connect(self.log)
                self.worker.finished_signal.connect(self.on_finished)
            except:
                pass  # Signal already connected
            
            # Update button states
            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(True)
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)
        
        # Mode Selection
        mode_group = QGroupBox("Select Mode")
        mode_layout = QVBoxLayout()
        
        self.bg_mode = QButtonGroup()
        self.rb_follow = QRadioButton("🏃 Follow New Users")
        self.rb_unfollow = QRadioButton("👤 Unfollow Users")
        self.rb_follow.setChecked(True)
        
        self.bg_mode.addButton(self.rb_follow, 0)
        self.bg_mode.addButton(self.rb_unfollow, 1)
        
        mode_btns_layout = QHBoxLayout()
        mode_btns_layout.addWidget(self.rb_follow)
        mode_btns_layout.addWidget(self.rb_unfollow)
        mode_btns_layout.addStretch()
        
        mode_layout.addLayout(mode_btns_layout)
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)
        
        # Follow Mode Options
        self.follow_widget = QWidget()
        follow_layout = QVBoxLayout(self.follow_widget)
        follow_layout.setContentsMargins(0, 0, 0, 0)
        
        info_label = QLabel("Users will be followed from the gathered results list.")
        info_label.setObjectName("InfoLabel")
        follow_layout.addWidget(info_label)
        
        layout.addWidget(self.follow_widget)
        
        # Unfollow Mode Options
        self.unfollow_widget = QWidget()
        unfollow_layout = QVBoxLayout(self.unfollow_widget)
        unfollow_layout.setContentsMargins(0, 0, 0, 0)
        
        self.chk_not_following_back = QCheckBox("Only unfollow users who aren't following me back")
        self.chk_not_following_back.setChecked(True)
        unfollow_layout.addWidget(self.chk_not_following_back)
        
        exclude_layout = QHBoxLayout()
        self.chk_exclude_recent = QCheckBox("Exclude users followed less than")
        self.chk_exclude_recent.setChecked(True)
        self.spin_exclude_days = QSpinBox()
        self.spin_exclude_days.setRange(1, 365)
        self.spin_exclude_days.setValue(7)
        lbl_days = QLabel("days ago")
        
        exclude_layout.addWidget(self.chk_exclude_recent)
        exclude_layout.addWidget(self.spin_exclude_days)
        exclude_layout.addWidget(lbl_days)
        exclude_layout.addStretch()
        
        unfollow_layout.addLayout(exclude_layout)
        layout.addWidget(self.unfollow_widget)
        self.unfollow_widget.hide()
        
        # Settings Card
        settings_group = QGroupBox("Configuration")
        settings_layout = QVBoxLayout()

        # Quantity
        quantity_layout = QHBoxLayout()
        quantity_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        lbl_quantity = QLabel("Total to process:")
        lbl_quantity = QLabel("Total to process:")
        self.spin_limit = QSpinBox()
        self.spin_limit.setRange(1, 500)
        self.spin_limit.setValue(100)
        lbl_users = QLabel("users")
        
        quantity_layout.addWidget(lbl_quantity)
        quantity_layout.addWidget(self.spin_limit)
        quantity_layout.addWidget(lbl_users)
        quantity_layout.addStretch()
        
        settings_layout.addLayout(quantity_layout)
        
        # Account Rotation
        settings_layout.addSpacing(10)
        lbl_rot_title = QLabel("Account Rotation (Multi-Account)")
        lbl_rot_title = QLabel("Account Rotation (Multi-Account)")
        lbl_rot_title.setObjectName("SectionTitle")
        settings_layout.addWidget(lbl_rot_title)
        
        rotation_controls = QHBoxLayout()
        rotation_controls.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.chk_rotation = QCheckBox("Enable Rotation")
        self.chk_rotation.setToolTip("Cycles through all active accounts in Account Manager")
        
        lbl_switch = QLabel("Switch account after:")
        lbl_switch = QLabel("Switch account after:")
        
        self.spin_rotation_limit = QSpinBox()
        self.spin_rotation_limit.setRange(1, 1000)
        self.spin_rotation_limit.setValue(10)
        lbl_actions = QLabel("actions")
        
        rotation_controls.addWidget(self.chk_rotation)
        rotation_controls.addWidget(lbl_switch)
        rotation_controls.addWidget(self.spin_rotation_limit)
        rotation_controls.addWidget(lbl_actions)
        rotation_controls.addStretch()
        
        settings_layout.addLayout(rotation_controls)
        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)
        
        # Action Buttons
        btn_group = QGroupBox("Execution")
        btn_layout = QHBoxLayout()
        
        self.btn_start = QPushButton("🚀 Run Now")
        self.btn_start.setMinimumHeight(45)
        self.btn_start.clicked.connect(self.start_automation)
        
        self.btn_schedule = QPushButton("📅 Add to Queue")
        self.btn_schedule.setMinimumHeight(45)
        self.btn_schedule.clicked.connect(self.add_to_schedule)
        
        self.btn_stop = QPushButton("🛑 Stop")
        self.btn_stop.setMinimumHeight(45)
        self.btn_stop.clicked.connect(self.stop_automation)
        self.btn_stop.setEnabled(False)
        
        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_schedule)
        btn_layout.addWidget(self.btn_stop)
        
        btn_group.setLayout(btn_layout)
        layout.addWidget(btn_group)
        
        # Logs
        log_group = QGroupBox("Activity Log")
        log_layout = QVBoxLayout()
        
        self.txt_logs = QTextEdit()
        self.txt_logs.setReadOnly(True)
        self.txt_logs.setMinimumHeight(150)
        self.txt_logs.setPlaceholderText("Automation events will be logged here...")
        log_layout.addWidget(self.txt_logs)
        
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        layout.addStretch()
        
        # Connect mode change
        self.rb_follow.toggled.connect(self.on_mode_changed)
        self.rb_unfollow.toggled.connect(self.on_mode_changed)
    
    def on_mode_changed(self):
        if self.rb_follow.isChecked():
            self.follow_widget.show()
            self.unfollow_widget.hide()
            self.btn_start.setText("Start Following")
        else:
            self.follow_widget.hide()
            self.unfollow_widget.show()
            self.btn_start.setText("Start Unfollowing")
    
    def start_automation(self):
        mode = 'follow' if self.rb_follow.isChecked() else 'unfollow'
        limit = self.spin_limit.value()
        
        # Prepare unfollow options
        unfollow_options = {}
        if mode == 'unfollow':
            unfollow_options = {
                'only_not_following_back': self.chk_not_following_back.isChecked(),
                'exclude_recent': self.chk_exclude_recent.isChecked(),
                'exclude_days': self.spin_exclude_days.value()
            }
        
        self.txt_logs.clear()
        self.log(f"Starting {'follow' if mode == 'follow' else 'unfollow'} automation...")
        
        # Register worker with AutomationManager for persistence
        from src.modules.automation_manager import AutomationManager
        manager = AutomationManager()
        
        # Prepare worker options
        rotation_options = {
            'enabled': self.chk_rotation.isChecked(),
            'limit': self.spin_rotation_limit.value()
        }
        
        self.worker = FollowWorker(mode, limit, unfollow_options, rotation_options)
        manager.register_worker('follow', self.worker)
        
        self.worker.log_signal.connect(self.log)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()
        
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
    
    def stop_automation(self):
        if self.worker:
            self.worker.stop()
            self.log("Stopping...")
    
    def on_finished(self, count):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        mode = 'followed' if self.rb_follow.isChecked() else 'unfollowed'
        self.log(f"\n✓ Automation complete. {mode.capitalize()} {count} users.")
    
    def add_to_schedule(self):
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QDateTimeEdit, QSpinBox, QDialogButtonBox
        from PySide6.QtCore import QDateTime
        import json
        import datetime
        
        mode = 'follow' if self.rb_follow.isChecked() else 'unfollow'
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Schedule {mode.capitalize()} Task")
        dialog.setFixedWidth(300)
        d_layout = QVBoxLayout(dialog)
        
        d_layout.addWidget(QLabel("Start Time:"))
        dt_edit = QDateTimeEdit(QDateTime.currentDateTime().addSecs(600))
        dt_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        d_layout.addWidget(dt_edit)
        
        d_layout.addWidget(QLabel("Repeat this task (times):"))
        repeat_spin = QSpinBox()
        repeat_spin.setRange(1, 100)
        repeat_spin.setValue(1)
        d_layout.addWidget(repeat_spin)
        
        d_layout.addWidget(QLabel("Interval between tasks (minutes):"))
        interval_spin = QSpinBox()
        interval_spin.setRange(1, 1440)
        interval_spin.setValue(2)
        d_layout.addWidget(interval_spin)
        
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        d_layout.addWidget(btns)
        
        if dialog.exec():
            start_time = dt_edit.dateTime().toPyDateTime()
            repeat_count = repeat_spin.value()
            interval_mins = interval_spin.value()
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM accounts WHERE is_selected = 1 LIMIT 1")
            account = cursor.fetchone()
            
            if not account:
                self.log("Error: No active account")
                conn.close()
                return

            current_time = start_time
            tasks_created = 0
            
            for i in range(repeat_count):
                payload = {
                    'mode': mode,
                    'limit': self.spin_limit.value()
                }
                
                if mode == 'unfollow':
                    payload['unfollow_options'] = {
                        'only_not_following_back': self.chk_not_following_back.isChecked(),
                        'exclude_recent': self.chk_exclude_recent.isChecked(),
                        'exclude_days': self.spin_exclude_days.value()
                    }
                
                scheduled_time_str = current_time.strftime('%Y-%m-%d %H:%M:%S')
                
                cursor.execute("""
                    INSERT INTO scheduled_actions (account_id, action_type, target_data, scheduled_time, status)
                    VALUES (?, ?, ?, ?, 'pending')
                """, (account['id'], 'follow', json.dumps(payload), scheduled_time_str))
                
                current_time = current_time + datetime.timedelta(minutes=interval_mins)
                tasks_created += 1
                
            conn.commit()
            conn.close()
            self.log(f"✓ Scheduled {tasks_created} {mode} task(s) starting {start_time}")

    
    def log(self, message):
        self.txt_logs.append(message)
