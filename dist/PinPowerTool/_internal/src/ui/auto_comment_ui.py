from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QSpinBox, QCheckBox, QTextEdit, 
                             QDialog, QListWidget, QLineEdit, QMessageBox, QGroupBox)
from PySide6.QtCore import QThread, Signal as pyqtSignal, Qt
from src.database import get_db_connection
from src.modules.actions import PinterestAutomation
import time
import random
import json
from datetime import datetime, timedelta
from src.modules.settings_helper import AutomationSettings

class CommentTemplatesDialog(QDialog):
    """Dialog for managing comment templates."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Comment Templates")
        self.setMinimumWidth(400)
        self.setMinimumHeight(300)
        self.setup_ui()
        self.load_templates()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # List of templates
        lbl = QLabel("Templates List:")
        lbl = QLabel("Templates List:")
        lbl.setObjectName("SectionTitle")
        layout.addWidget(lbl)
        
        self.list_templates = QListWidget()
        layout.addWidget(self.list_templates)
        
        # Add new template
        add_group = QGroupBox("Add New Template")
        add_layout = QHBoxLayout()
        self.inp_new_comment = QLineEdit()
        self.inp_new_comment.setPlaceholderText("Type new comment template here...")
        
        btn_add = QPushButton("➕ Add")
        btn_add.setMinimumHeight(40)
        btn_add.clicked.connect(self.add_template)
        
        add_layout.addWidget(self.inp_new_comment)
        add_layout.addWidget(btn_add)
        add_group.setLayout(add_layout)
        layout.addWidget(add_group)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        btn_delete = QPushButton("🗑️ Delete Selected")
        btn_delete.setMinimumHeight(40)
        btn_delete.clicked.connect(self.delete_template)
        
        btn_close = QPushButton("✖ Close")
        btn_close.setMinimumHeight(40)
        btn_close.clicked.connect(self.accept)
        
        btn_layout.addWidget(btn_delete)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)
    
    def load_templates(self):
        """Load templates from database."""
        self.list_templates.clear()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, comment_text FROM comment_templates WHERE is_active = 1")
        templates = cursor.fetchall()
        conn.close()
        
        for template in templates:
            self.list_templates.addItem(f"{template['comment_text']} (ID: {template['id']})")
    
    def add_template(self):
        """Add new comment template."""
        comment = self.inp_new_comment.text().strip()
        if not comment:
            QMessageBox.warning(self, "Error", "Please enter a comment")
            return
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO comment_templates (comment_text) VALUES (?)", (comment,))
        conn.commit()
        conn.close()
        
        self.inp_new_comment.clear()
        self.load_templates()
    
    def delete_template(self):
        """Delete selected template."""
        current_item = self.list_templates.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Error", "Please select a template to delete")
            return
        
        # Extract ID from item text
        text = current_item.text()
        template_id = int(text.split("ID: ")[-1].rstrip(")"))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM comment_templates WHERE id = ?", (template_id,))
        conn.commit()
        conn.close()
        
        self.load_templates()


class CommentWorker(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(int)
    
    def __init__(self, limit, skip_recent_days, follow_after_comment, rotation_options=None):
        super().__init__()
        self.limit = limit
        self.skip_recent_days = skip_recent_days
        self.follow_after_comment = follow_after_comment
        self.rotation_options = rotation_options or {'enabled': False, 'limit': 10}
        self.is_running = True
        
        # Load automation settings first
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
            
            batch_processed = self.do_comment(batch_limit)
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
    
    def do_comment(self, batch_limit):
        """Comment on gathered pins."""
        # Log active filters
        filter_summary = self.auto_settings.get_filter_summary()
        self.log_signal.emit(f"Active filters: {filter_summary}")
        self.log_signal.emit("")
        
        # Load comment templates
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT comment_text FROM comment_templates WHERE is_active = 1")
        templates = cursor.fetchall()
        
        if not templates:
            self.log_signal.emit("Error: No comment templates found. Please add templates first.")
            conn.close()
            return 0
        
        comment_texts = [t['comment_text'] for t in templates]
        self.log_signal.emit(f"Loaded {len(comment_texts)} comment templates")
        
        # Load gathered pins
        # Fetch more pins than limit to account for filtering
        cursor.execute("SELECT pin_url FROM gathered_pins LIMIT ?", (batch_limit * 10,))
        pins = cursor.fetchall()
        conn.close()
        
        if not pins:
            self.log_signal.emit("No gathered pins found in database")
            return 0
        
        self.log_signal.emit(f"Found {len(pins)} pins, will comment on up to {batch_limit} in this session")
        
        # Get username for skip own pins check
        account_username = self.current_account['email'].split('@')[0] if self.current_account and self.current_account['email'] else ""
        
        # Calculate cutoff date for recent comments
        cutoff_date = datetime.now() - timedelta(days=self.skip_recent_days)
        
        processed = 0
        skipped = 0
        
        for pin in pins:
            if not self.is_running or processed >= batch_limit:
                break
            
            pin_url = pin['pin_url']
            
            try:
                # Extract pin data for filtering
                self.log_signal.emit(f"Analyzing pin: {pin_url}")
                
                pin_data = self.automation.get_pin_data(pin_url)
                if not pin_data:
                    self.log_signal.emit("  ⚠ Could not extract pin data, skipping")
                    skipped += 1
                    continue
                
                # Apply filters and skip checks
                should_skip, reason = self.auto_settings.should_skip_pin(pin_data, account_username)
                
                if should_skip:
                    self.log_signal.emit(f"  ⊗ Skipped: {reason}")
                    skipped += 1
                    continue
                
                # Extract pin owner (username from URL pattern or scraped data)
                pin_owner = pin_data.get('author')
                if not pin_owner:
                     # Fallback to getting owner if not in pin_data (though get_pin_data should have it)
                     pin_owner = self.get_pin_owner(pin_url)
                
                if not pin_owner:
                    self.log_signal.emit(f"  ⊘ Could not determine owner for {pin_url}")
                    continue
                
                # Check if we commented on this user recently (Account specific)
                account_id = self.current_account['id']
                if self.skip_recent_days > 0:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cutoff_date_str = cutoff_date.strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute(
                        "SELECT COUNT(*) as count FROM commented_pins WHERE account_id = ? AND pin_owner = ? AND commented_date > ?",
                        (account_id, pin_owner, cutoff_date_str)
                    )
                    result = cursor.fetchone()
                    recent_comment_count = result['count'] if result else 0
                    conn.close()
                    
                    if recent_comment_count > 0:
                        self.log_signal.emit(f"  ⊘ Skipping {pin_owner} (this account commented recently)")
                        continue
                
                # Pick random comment
                comment = random.choice(comment_texts)
                
                self.log_signal.emit(f"  → Commenting on pin by {pin_owner}...")
                
                if self.automation.comment_on_pin(pin_url, comment):
                    processed += 1
                    
                    # Save to database
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO commented_pins (account_id, pin_url, pin_owner, comment_text, commented_date) VALUES (?, ?, ?, ?, ?)",
                        (account_id, pin_url, pin_owner, comment, datetime.now())
                    )
                    conn.commit()
                    conn.close()
                    
                    self.log_signal.emit(f"  ✓ Commented: \"{comment}\" ({processed}/{batch_limit})")
                    
                    # Follow user if option enabled
                    if self.follow_after_comment:
                        user_url = f"https://www.pinterest.com/{pin_owner}/"
                        self.log_signal.emit(f"  Following {pin_owner}...")
                        if self.automation.follow_user(user_url):
                            self.log_signal.emit(f"  ✓ Followed {pin_owner}")
                        time.sleep(2)
                        
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
                    self.log_signal.emit(f"  ✗ Failed to comment on pin")
                
                # Apply delay
                if processed < batch_limit:
                    delay = self.auto_settings.get_random_delay()
                    self.log_signal.emit(f"  ⏱ Waiting {delay}s...")
                    time.sleep(delay)
                
            except Exception as e:
                self.log_signal.emit(f"Error processing pin: {e}")
                import traceback
                traceback.print_exc()
    
    def get_pin_owner(self, pin_url):
        """Navigate to pin and extract owner username."""
        try:
            self.automation.page.goto(pin_url, timeout=30000, wait_until="domcontentloaded")
            time.sleep(3)
            
            # Scroll to load content
            self.automation.page.evaluate("window.scrollTo(0, 300)")
            time.sleep(1)
            
            # Try to find owner information using multiple methods
            
            # Method 1: Look for profile link with data-test-id
            try:
                print("Trying to find pin owner - Method 1: data-test-id")
                owner_link = self.automation.page.query_selector('a[data-test-id="creator-profile-link"]')
                if owner_link:
                    href = owner_link.get_attribute('href')
                    if href and '?' not in href:  # Avoid query parameters
                        username = href.rstrip('/').split('/')[-1]
                        if username and username not in ['pin', 'search', 'ideas', 'today', 'explore']:
                            print(f"Found owner via Method 1: {username}")
                            return username
            except Exception as e:
                print(f"Method 1 failed: {e}")
            
            # Method 2: Look for links that contain username pattern
            try:
                print("Trying to find pin owner - Method 2: Link pattern")
                all_links = self.automation.page.query_selector_all('a[href^="/"]')
                for link in all_links:
                    href = link.get_attribute('href') or ''
                    # Clean username pattern: /username/ (no special chars)
                    if href.startswith('/') and href.count('/') >= 2:
                        parts = href.strip('/').split('/')
                        potential_username = parts[0]
                        
                        # Validate username
                        if (potential_username and 
                            '?' not in potential_username and
                            '=' not in potential_username and
                            potential_username not in ['pin', 'search', 'ideas', 'today', 'explore', '_', '_saved', '_created'] and
                            len(potential_username) > 2 and
                            not potential_username.startswith('_')):
                            print(f"Found owner via Method 2: {potential_username}")
                            return potential_username
            except Exception as e:
                print(f"Method 2 failed: {e}")
            
            # Method 3: Look in page title or meta tags
            try:
                print("Trying to find pin owner - Method 3: Page metadata")
                title = self.automation.page.title()
                # Pinterest titles often have pattern: "Description - Username | Pinterest"
                if '|' in title:
                    before_pipe = title.split('|')[0]
                    if '-' in before_pipe:
                        username = before_pipe.split('-')[-1].strip()
                        if username and len(username) > 2:
                            print(f"Found owner via Method 3: {username}")
                            return username
            except Exception as e:
                print(f"Method 3 failed: {e}")
            
            print("Could not extract pin owner from page")
            return None
            
        except Exception as e:
            print(f"Error getting pin owner: {e}")
            return None
    
    def stop(self):
        self.is_running = False


class AutoCommentUI(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.setup_ui()
        
        # Check if there's an existing worker and restore its state
        from src.modules.automation_manager import AutomationManager
        manager = AutomationManager()
        existing_worker = manager.get_worker('comment')
        
        if existing_worker and manager.is_worker_running('comment'):
            self.log("✓ Reconnected to running task")
            self.worker = existing_worker
            
            # Restore buffered logs
            buffered_logs = manager.get_logs('comment')
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
        
        # Info Card
        info_group = QGroupBox("Comment Automation")
        info_layout = QVBoxLayout()
        info_label = QLabel("Comment on gathered pins using rotating templates to drive engagement.")
        info_label = QLabel("Comment on gathered pins using rotating templates to drive engagement.")
        info_label.setObjectName("InfoLabel")
        info_layout.addWidget(info_label)
        
        # Comment Templates Button
        btn_templates = QPushButton("📝 Manage Comment Templates")
        btn_templates.setMinimumHeight(45)
        btn_templates.clicked.connect(self.show_templates_dialog)
        info_layout.addWidget(btn_templates)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # Settings Card
        settings_group = QGroupBox("Task Configuration")
        settings_layout = QVBoxLayout()

        # Quantity
        quantity_layout = QHBoxLayout()
        quantity_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        lbl_quantity = QLabel("Total pins to comment:")
        lbl_quantity = QLabel("Total pins to comment:")
        self.spin_limit = QSpinBox()
        self.spin_limit.setRange(1, 500)
        self.spin_limit.setValue(200)
        lbl_pins = QLabel("pins")
        
        quantity_layout.addWidget(lbl_quantity)
        quantity_layout.addWidget(self.spin_limit)
        quantity_layout.addWidget(lbl_pins)
        quantity_layout.addStretch()
        
        settings_layout.addLayout(quantity_layout)
        
        # Skip recent option
        skip_layout = QHBoxLayout()
        skip_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.chk_skip_recent = QCheckBox("Skip pins from any user I've commented on in the last")
        self.chk_skip_recent.setChecked(True)
        self.spin_skip_days = QSpinBox()
        self.spin_skip_days.setRange(1, 365)
        self.spin_skip_days.setValue(30)
        lbl_days = QLabel("days")
        
        skip_layout.addWidget(self.chk_skip_recent)
        skip_layout.addWidget(self.spin_skip_days)
        skip_layout.addWidget(lbl_days)
        skip_layout.addStretch()
        
        settings_layout.addLayout(skip_layout)
        
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
        
        # Follow after comment option
        self.chk_follow = QCheckBox("🤝 Follow user after commenting")
        self.chk_follow.setChecked(False)
        settings_layout.addSpacing(5)
        settings_layout.addWidget(self.chk_follow)
        
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
    
    def show_templates_dialog(self):
        dialog = CommentTemplatesDialog(self)
        dialog.exec()
    
    def start_automation(self):
        limit = self.spin_limit.value()
        skip_days = self.spin_skip_days.value() if self.chk_skip_recent.isChecked() else 0
        follow_after = self.chk_follow.isChecked()
        
        self.txt_logs.clear()
        self.log("Starting comment automation...")
        
        # Register worker with AutomationManager for persistence
        from src.modules.automation_manager import AutomationManager
        manager = AutomationManager()
        
        # Prepare rotation options
        rotation_options = {
            'enabled': self.chk_rotation.isChecked(),
            'limit': self.spin_rotation_limit.value()
        }
        
        self.worker = CommentWorker(limit, skip_days, follow_after, rotation_options)
        manager.register_worker('comment', self.worker)
        
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
        self.log(f"\n✓ Automation complete. Commented on {count} pins.")
    
    def add_to_schedule(self):
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QDateTimeEdit, QSpinBox, QDialogButtonBox
        from PySide6.QtCore import QDateTime
        import json
        import datetime
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Schedule Comment Task")
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
                    'limit': self.spin_limit.value(),
                    'skip_recent_days': self.spin_skip_days.value() if self.chk_skip_recent.isChecked() else 0,
                    'follow_after_comment': self.chk_follow.isChecked()
                }
                
                scheduled_time_str = current_time.strftime('%Y-%m-%d %H:%M:%S')
                
                cursor.execute("""
                    INSERT INTO scheduled_actions (account_id, action_type, target_data, scheduled_time, status)
                    VALUES (?, ?, ?, ?, 'pending')
                """, (account['id'], 'comment', json.dumps(payload), scheduled_time_str))
                
                current_time = current_time + datetime.timedelta(minutes=interval_mins)
                tasks_created += 1
                
            conn.commit()
            conn.close()
            self.log(f"✓ Scheduled {tasks_created} comment task(s) starting {start_time}")

    
    def log(self, message):
        self.txt_logs.append(message)
