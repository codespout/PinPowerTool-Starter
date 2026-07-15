from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QSpinBox, QRadioButton, QButtonGroup,
                             QLineEdit, QTextEdit, QFileDialog, QComboBox, QCheckBox,
                             QDialog, QTableWidget, QTableWidgetItem, QHeaderView, 
                             QDialogButtonBox, QMessageBox, QGroupBox)
from PySide6.QtCore import QThread, Signal as pyqtSignal, Qt
from src.database import get_db_connection
from src.modules.actions import PinterestAutomation
import time
import os
import json
from datetime import datetime
from src.modules.settings_helper import AutomationSettings

class RotationBoardsDialog(QDialog):
    """Dialog to map accounts to specific boards for rotation."""
    def __init__(self, accounts, current_mapping=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Rotation Boards")
        self.setMinimumWidth(600)
        self.accounts = accounts
        self.mapping = current_mapping or {}
        self.combos = {} # {account_id: QComboBox}
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        label = QLabel("Specify the target board for each account in rotation:")
        label.setStyleSheet("font-weight: bold; margin-bottom: 5px;")
        layout.addWidget(label)
        
        self.table = QTableWidget(len(self.accounts), 3)
        self.table.setHorizontalHeaderLabels(["Account Email", "Board Name", "Actions"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        
        for i, acc in enumerate(self.accounts):
            acc_id = acc['id']
            # Email (Read-only)
            email_item = QTableWidgetItem(acc['email'])
            email_item.setFlags(email_item.flags() ^ Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 0, email_item)
            
            # Board Name (QComboBox)
            combo = QComboBox()
            combo.setEditable(True)
            self.combos[acc_id] = combo
            
            # Load boards from DB
            boards = []
            if acc['boards']:
                try:
                    boards = json.loads(acc['boards'])
                except: pass
            
            if boards:
                combo.addItems(boards)
            else:
                combo.addItem("Default Board")
                
            # Set current value if in mapping
            current_val = self.mapping.get(str(acc_id), "")
            if current_val:
                index = combo.findText(current_val)
                if index >= 0:
                    combo.setCurrentIndex(index)
                else:
                    combo.setCurrentText(current_val)
            
            self.table.setCellWidget(i, 1, combo)
            
            # Refresh Button
            btn_refresh = QPushButton("🔄 Refresh")
            btn_refresh.setMinimumHeight(30)
            btn_refresh.clicked.connect(lambda checked, a=acc, c=combo: self.refresh_account_boards(a, c))
            self.table.setCellWidget(i, 2, btn_refresh)
            
        layout.addWidget(self.table)
        
        note = QLabel("Note: If left empty, the main 'Pin to Board' selection will be used.")
        note.setStyleSheet("font-style: italic; margin-top: 5px;")
        layout.addWidget(note)
        
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        
    def refresh_account_boards(self, account, combo):
        """Fetch boards for a single account and update DB/UI."""
        try:
            combo.clear()
            combo.addItem("Fetching...")
            combo.repaint()
            
            # Load cookies
            cookies = None
            if account['cookies']:
                try:
                    import json
                    cookies = json.loads(account['cookies'])
                except: pass
            
            # Get proxy
            proxy_dict = None
            if account['proxy']:
                parts = account['proxy'].split(':')
                if len(parts) >= 2:
                    proxy_dict = {'server': f"http://{parts[0]}:{parts[1]}"}
                    if len(parts) >= 4:
                        proxy_dict['username'] = parts[2]
                        proxy_dict['password'] = parts[3]
            
            # Use temporary automation instance
            automation = PinterestAutomation(headless=True, proxy=proxy_dict)
            if automation.start_browser(cookies=cookies):
                boards = automation.get_my_boards()
                automation.stop_browser()
                
                combo.clear()
                if boards:
                    # Save to DB
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("UPDATE accounts SET boards = ? WHERE id = ?", (json.dumps(boards), account['id']))
                    conn.commit()
                    conn.close()
                    
                    combo.addItems(boards)
                    QMessageBox.information(self, "Success", f"Fetched {len(boards)} boards for {account['email']}")
                else:
                    combo.addItem("Default Board")
                    QMessageBox.warning(self, "Warning", f"No boards found for {account['email']}")
            else:
                combo.clear()
                combo.addItem("Default Board")
                QMessageBox.critical(self, "Error", f"Failed to start browser for {account['email']}")
                
        except Exception as e:
            combo.clear()
            combo.addItem("Default Board")
            QMessageBox.critical(self, "Error", f"Error: {e}")

    def get_mapping(self):
        mapping = {}
        for acc_id, combo in self.combos.items():
            board_name = combo.currentText().strip()
            if board_name:
                mapping[str(acc_id)] = board_name
        return mapping


class RepinWorker(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(int)
    
    def __init__(self, mode, board_name, limit, auto_like=False, image_files=None, title_template="", description_template="", link_template="", tags="", upload_delay_min=5, upload_delay_max=10, rotation_options=None):
        super().__init__()
        self.mode = mode  # 'repin' or 'upload'
        self.orig_board_name = board_name
        self.board_name = board_name
        self.limit = limit
        self.auto_like = auto_like
        self.image_files = image_files  # List of image file paths
        self.title_template = title_template
        self.description_template = description_template
        self.link_template = link_template
        self.tags = tags
        self.upload_delay_min = upload_delay_min
        self.upload_delay_max = upload_delay_max
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
            account_id = self.current_account['id']
            
            # Set account-specific board if rotation is enabled and mapping exists
            if self.rotation_options.get('enabled') and 'boards' in self.rotation_options:
                # Boards dict keys are stringified IDs from JSON
                self.board_name = self.rotation_options['boards'].get(str(account_id), self.orig_board_name)
            else:
                self.board_name = self.orig_board_name

            self.log_signal.emit(f"\n🔄 [Account {account_index % len(accounts) + 1}/{len(accounts)}] Switching to: {email}")
            if self.rotation_options.get('enabled'):
                self.log_signal.emit(f"  → Target Board: {self.board_name}")
            
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
            if self.mode == 'repin':
                batch_processed = self.do_repin(batch_limit)
            else:
                batch_processed = self.do_upload(batch_limit, total_processed)
            
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
    
    def do_repin(self, batch_limit):
        """Repin gathered pins to selected board."""
        # Log active filters
        filter_summary = self.auto_settings.get_filter_summary()
        self.log_signal.emit(f"Active filters: {filter_summary}")
        self.log_signal.emit("")
        
        self.log_signal.emit("Fetching pins to repin from database...")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        # Fetch more pins than limit to account for filtering
        cursor.execute("SELECT pin_url FROM gathered_pins LIMIT ?", (batch_limit * 10,))
        pins = cursor.fetchall()
        conn.close()
        
        if not pins:
            self.log_signal.emit("No gathered pins found in database")
            return 0
        
        self.log_signal.emit(f"Found {len(pins)} pins, will repin up to {batch_limit} in this session")
        
        # Get username for skip own pins check
        account_username = self.current_account['email'].split('@')[0] if self.current_account and self.current_account['email'] else ""
        
        processed = 0
        skipped = 0
        
        for pin in pins:
            if not self.is_running or processed >= batch_limit:
                break
            
            pin_url = pin['pin_url']
            
            try:
                # Extract pin data for filtering
                self.log_signal.emit(f"\n[{processed+1}/{batch_limit}] Processing: {pin_url}")
                self.log_signal.emit("  → Extracting pin data...")
                
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
                
                self.log_signal.emit(f"  → Repinning to board '{self.board_name}'...")
                if self.auto_like:
                    self.log_signal.emit("  → Auto-like enabled")
                
                # Smart Skip: Provide skip check callback for DB fallback after UI check
                account_id = self.current_account['id']
                def db_skip_check(url):
                    return self.auto_settings.is_pin_repinned(account_id, url)
                
                result = self.automation.repin_pin(pin_url, self.board_name, self.auto_like, skip_check=db_skip_check)
                
                success = False
                msg = ""
                is_already_done = False
                
                if isinstance(result, tuple):
                    success, msg = result
                    if "Already" in msg:
                        is_already_done = True
                else:
                    success = result
                    msg = "Repinned successfully" if success else "Failed to repin"
                
                if success:
                    if not is_already_done:
                        processed += 1
                        # Increment action count for breaks only for actual actions
                        self.auto_settings.increment_action_count()
                    
                    self.log_signal.emit(f"  ✓ {msg} ({processed}/{batch_limit})")
                    
                    # Save to history if it was a real action OR if UI check caught it
                    if "DB" not in msg:
                        try:
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            cursor.execute("INSERT OR IGNORE INTO repin_history (account_id, pin_url, board_name) VALUES (?, ?, ?)",
                                         (account_id, pin_url, self.board_name))
                            conn.commit()
                            conn.close()
                        except Exception as e:
                            print(f"Error saving to repin_history: {e}")

                    
                    # Check if we should take a break
                    should_break, duration = self.auto_settings.should_take_break()
                    if should_break:
                        self.log_signal.emit(f"")
                        self.log_signal.emit(f"⏸ Taking a {duration}s break...")
                        time.sleep(duration)
                        self.log_signal.emit(f"⏵ Resuming automation")
                        self.log_signal.emit(f"")
                else:
                    self.log_signal.emit(f"  ✗ {msg}")
                
                # Apply delay
                if processed < batch_limit:
                    delay = self.auto_settings.get_random_delay()
                    self.log_signal.emit(f"  ⏱ Waiting {delay}s...")
                    time.sleep(delay)
                
            except Exception as e:
                self.log_signal.emit(f"Error repinning: {e}")
        
        return processed
    
    def do_upload(self, batch_limit, total_processed):
        """Upload pins from selected image files."""
        if not self.image_files or len(self.image_files) == 0:
            self.log_signal.emit("Error: No image files selected")
            return 0
        
        self.log_signal.emit(f"Will upload up to {batch_limit} images in this session")
        
        processed = 0
        # Start from the offset of total_processed
        for image_path in self.image_files[total_processed:]:
            if not self.is_running or processed >= batch_limit:
                break
            
            try:
                # Generate title, description and link from templates
                filename = os.path.basename(image_path)
                filename_no_ext = os.path.splitext(filename)[0]
                
                title = self.title_template.replace('{filename}', filename_no_ext) if self.title_template else filename_no_ext
                description = self.description_template.replace('{filename}', filename_no_ext) if self.description_template else ""
                link = self.link_template.replace('{filename}', filename_no_ext) if self.link_template else ""
                
                self.log_signal.emit(f"Uploading: {filename}")
                self.log_signal.emit(f"  Title: {title}")
                if self.tags:
                    self.log_signal.emit(f"  Tags: {self.tags}")
                
                # Upload with tags
                if self.automation.upload_pin(image_path, self.board_name, title, description, link, self.tags):
                    processed += 1
                    self.log_signal.emit(f"✓ Uploaded {filename} ({processed}/{batch_limit})")
                else:
                    self.log_signal.emit(f"✗ Failed to upload {filename}")
                
                # Configurable random delay between uploads
                if processed < batch_limit and self.is_running:
                    import random
                    delay = random.randint(self.upload_delay_min, self.upload_delay_max)
                    self.log_signal.emit(f"Waiting {delay} seconds before next upload...")
                    time.sleep(delay)
                
            except Exception as e:
                self.log_signal.emit(f"Error uploading: {e}")
        
        return processed
    
    def stop(self):
        self.is_running = False


class AutoRepinUI(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.selected_files = []  # Store selected image files
        self.rotation_boards = {} # {account_id: board_name} mapping
        self.setup_ui()
        
        # Check if there's an existing worker and restore its state
        from src.modules.automation_manager import AutomationManager
        manager = AutomationManager()
        existing_worker = manager.get_worker('repin')
        
        if existing_worker and manager.is_worker_running('repin'):
            self.log("✓ Reconnected to running task")
            self.worker = existing_worker
            
            # Restore buffered logs
            buffered_logs = manager.get_logs('repin')
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
        
        # Load saved boards from DB on startup
        self.load_saved_boards()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)
        
        # Mode Selection
        mode_group = QGroupBox("Select Mode")
        mode_layout = QVBoxLayout()
        
        self.bg_mode = QButtonGroup()
        self.rb_repin = QRadioButton("♻️ Repin from Gathered Pins")
        self.rb_upload = QRadioButton("📤 Upload New Pins from Folder")
        self.rb_repin.setChecked(True)
        
        self.bg_mode.addButton(self.rb_repin, 0)
        self.bg_mode.addButton(self.rb_upload, 1)
        
        mode_btns_layout = QHBoxLayout()
        mode_btns_layout.addWidget(self.rb_repin)
        mode_btns_layout.addWidget(self.rb_upload)
        mode_btns_layout.addStretch()
        
        mode_layout.addLayout(mode_btns_layout)
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)
        
        # Board Selection Card
        board_group = QGroupBox("Target Board")
        board_layout = QHBoxLayout()
        lbl_board = QLabel("Pin to Board:")
        lbl_board = QLabel("Pin to Board:")
        self.cmb_boards = QComboBox()
        self.cmb_boards.setMinimumWidth(200)
        btn_refresh = QPushButton("🔄 Refresh")
        btn_refresh.setMinimumHeight(40)
        btn_refresh.clicked.connect(self.load_boards)
        
        board_layout.addWidget(lbl_board)
        board_layout.addWidget(self.cmb_boards)
        board_layout.addWidget(btn_refresh)
        board_layout.addStretch()
        
        board_group.setLayout(board_layout)
        layout.addWidget(board_group)
        
        # Repin Mode Options
        self.repin_widget = QWidget()
        repin_layout = QVBoxLayout(self.repin_widget)
        repin_layout.setContentsMargins(10, 0, 10, 0)
        
        # Auto-Like Option
        self.chk_auto_like = QCheckBox("❤️ Also like pins after saving")
        self.chk_auto_like.setChecked(False)
        repin_layout.addWidget(self.chk_auto_like)
        
        info_label = QLabel("Pins will be repinned from the gathered results list.")
        info_label = QLabel("Pins will be repinned from the gathered results list.")
        info_label.setObjectName("InfoLabel")
        repin_layout.addWidget(info_label)
        
        layout.addWidget(self.repin_widget)
        
        # Upload Mode Options
        self.upload_widget = QWidget()
        upload_main_layout = QVBoxLayout(self.upload_widget)
        upload_main_layout.setContentsMargins(0, 10, 0, 10)
        
        # Create scroll area for upload options
        from PySide6.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidgetResizable(True)
        scroll.setObjectName("ContentScroll")
        
        # Content widget for scroll area
        scroll_content = QWidget()
        upload_layout = QVBoxLayout(scroll_content)
        
        # File selection
        files_layout = QHBoxLayout()
        lbl_files = QLabel("Images:")
        lbl_files.setStyleSheet("font-weight: bold;")
        self.inp_files = QLineEdit()
        self.inp_files.setPlaceholderText("Select image files...")
        self.inp_files.setReadOnly(True)
        btn_browse = QPushButton("📁 Browse Files...")
        btn_browse.setMinimumHeight(40)
        btn_browse.clicked.connect(self.browse_files)
        
        files_layout.addWidget(lbl_files)
        files_layout.addWidget(self.inp_files)
        files_layout.addWidget(btn_browse)
        
        upload_layout.addLayout(files_layout)
        
        # Title template
        lbl_title = QLabel("Title Template:")
        lbl_title.setStyleSheet("margin-top: 10px;")
        upload_layout.addWidget(lbl_title)
        
        self.inp_title = QLineEdit()
        self.inp_title.setPlaceholderText("Use {filename} to insert image name, e.g. Amazing {filename}")
        upload_layout.addWidget(self.inp_title)
        
        # Description template
        lbl_desc = QLabel("Description Template (optional):")
        lbl_desc.setStyleSheet("margin-top: 10px;")
        upload_layout.addWidget(lbl_desc)
        
        self.txt_description = QTextEdit()
        self.txt_description.setPlaceholderText("Use {filename} to insert image name\ne.g. Check out {filename}! #pinterest")
        self.txt_description.setMaximumHeight(80)
        upload_layout.addWidget(self.txt_description)
        
        # Tags/Keywords
        lbl_tags = QLabel("Tags/Keywords (optional):")
        lbl_tags.setStyleSheet("margin-top: 10px;")
        upload_layout.addWidget(lbl_tags)
        
        self.inp_tags = QLineEdit()
        self.inp_tags.setPlaceholderText("Comma-separated tags, e.g. #inspiration, #design, #diy")
        upload_layout.addWidget(self.inp_tags)
        
        # Link template
        lbl_link = QLabel("Link/Destination URL (optional):")
        lbl_link.setStyleSheet("margin-top: 10px;")
        upload_layout.addWidget(lbl_link)
        
        self.inp_link = QLineEdit()
        self.inp_link.setPlaceholderText("e.g. https://mywebsite.com/{filename}")
        upload_layout.addWidget(self.inp_link)
        
        # Upload delay configuration
        delay_layout = QHBoxLayout()
        lbl_delay = QLabel("Wait between uploads:")
        lbl_delay.setStyleSheet("margin-top: 10px;")
        
        self.spin_delay_min = QSpinBox()
        self.spin_delay_min.setRange(1, 300)
        self.spin_delay_min.setValue(5)
        self.spin_delay_min.setSuffix(" sec (min)")
        
        lbl_to = QLabel("to")
        
        self.spin_delay_max = QSpinBox()
        self.spin_delay_max.setRange(1, 300)
        self.spin_delay_max.setValue(10)
        self.spin_delay_max.setSuffix(" sec (max)")
        
        delay_layout.addWidget(lbl_delay)
        delay_layout.addWidget(self.spin_delay_min)
        delay_layout.addWidget(lbl_to)
        delay_layout.addWidget(self.spin_delay_max)
        delay_layout.addStretch()
        
        upload_layout.addLayout(delay_layout)
        
        # Add scroll content to scroll area
        scroll.setWidget(scroll_content)
        upload_main_layout.addWidget(scroll)
        
        layout.addWidget(self.upload_widget)
        self.upload_widget.hide()
        
        # Configuration Card
        settings_group = QGroupBox("Configuration")
        settings_layout = QVBoxLayout()

        # Account Rotation
        lbl_rot_title = QLabel("Account Rotation (Multi-Account)")
        lbl_rot_title.setStyleSheet("font-weight: bold;")
        settings_layout.addWidget(lbl_rot_title)
        
        rotation_controls = QHBoxLayout()
        self.chk_rotation = QCheckBox("Enable Rotation")
        self.chk_rotation.setToolTip("Cycles through all active accounts in Account Manager")
        
        self.btn_manage_boards = QPushButton("⚙️ Manage Rotation Boards")
        self.btn_manage_boards.setMinimumHeight(40)
        self.btn_manage_boards.clicked.connect(self.manage_rotation_boards)
        
        lbl_switch = QLabel("Switch after:")
        lbl_switch.setStyleSheet("margin-left: 15px;")
        
        self.spin_rotation_limit = QSpinBox()
        self.spin_rotation_limit.setRange(1, 1000)
        self.spin_rotation_limit.setValue(10)
        lbl_actions = QLabel("actions")
        
        rotation_controls.addWidget(self.chk_rotation)
        rotation_controls.addWidget(self.btn_manage_boards)
        rotation_controls.addWidget(lbl_switch)
        rotation_controls.addWidget(self.spin_rotation_limit)
        rotation_controls.addWidget(lbl_actions)
        rotation_controls.addStretch()
        
        settings_layout.addLayout(rotation_controls)
        
        # Quantity
        settings_layout.addSpacing(10)
        quantity_layout = QHBoxLayout()
        lbl_quantity = QLabel("Total to process:")
        lbl_quantity = QLabel("Total to process:")
        self.spin_limit = QSpinBox()
        self.spin_limit.setRange(1, 500)
        self.spin_limit.setValue(50)
        lbl_pins = QLabel("pins")
        
        quantity_layout.addWidget(lbl_quantity)
        quantity_layout.addWidget(self.spin_limit)
        quantity_layout.addWidget(lbl_pins)
        quantity_layout.addStretch()
        
        settings_layout.addLayout(quantity_layout)
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
        self.rb_repin.toggled.connect(self.on_mode_changed)
        self.rb_upload.toggled.connect(self.on_mode_changed)
    
    def manage_rotation_boards(self):
        """Show dialog to map boards to accounts for rotation."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM accounts WHERE is_selected = 1 ORDER BY id ASC")
        accounts = cursor.fetchall()
        conn.close()
        
        if not accounts:
            QMessageBox.warning(self, "Warning", "No active accounts selected in Account Manager.")
            return
            
        dialog = RotationBoardsDialog(accounts, self.rotation_boards, self)
        if dialog.exec():
            self.rotation_boards = dialog.get_mapping()
            self.log(f"Updated rotation board mappings for {len(self.rotation_boards)} accounts")

    def on_mode_changed(self):
        if self.rb_repin.isChecked():
            self.repin_widget.show()
            self.upload_widget.hide()
            self.btn_start.setText("Start Repinning")
        else:
            self.repin_widget.hide()
            self.upload_widget.show()
            self.btn_start.setText("Start Uploading")
    
    def browse_files(self):
        """Let user select multiple image files to upload."""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Image Files",
            "",
            "Images (*.jpg *.jpeg *.png *.gif *.webp);;All Files (*.*)"
        )
        if files:
            self.selected_files = files
            self.inp_files.setText(f"{len(files)} image(s) selected")
            self.log(f"Selected {len(files)} image file(s)")

    def prepare_upload(self, file_path, title):
        """Prepare UI for a single file upload from Repurposer."""
        if not os.path.exists(file_path):
            return
            
        self.rb_upload.setChecked(True)
        self.selected_files = [file_path]
        self.inp_files.setText("1 image(s) selected")
        
        # Pre-fill title template if provided
        if title:
            # Escape braces if they exist to avoid format errors, or just set it as a literal
            # The worker uses .replace('{filename}', ...) so if we put the full title here, 
            # we should make sure it doesn't get messed up. 
            # Actually, standard title is fine.
            self.inp_title.setText(title)
        
        # Clear other fields to be safe or leave defaults
        self.log(f"Prepared upload for: {os.path.basename(file_path)}")
    
    def load_saved_boards(self):
        """Load boards from DB for the current account."""
        self.cmb_boards.clear()
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT boards FROM accounts WHERE is_selected = 1 LIMIT 1")
            row = cursor.fetchone()
            conn.close()
            
            if row and row['boards']:
                boards = json.loads(row['boards'])
                if boards:
                    self.cmb_boards.addItems(boards)
                    return True
        except: pass
        
        # Fallback
        self.cmb_boards.addItems(["Main Board", "Ideas", "Inspiration"])
        return False

    def load_boards(self):
        """Load user's boards from Pinterest account and save to DB."""
        self.cmb_boards.clear()
        self.cmb_boards.addItem("Loading boards...")
        self.cmb_boards.repaint()
        
        try:
            # Get active account
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM accounts WHERE is_selected = 1 LIMIT 1")
            account = cursor.fetchone()
            conn.close()
            
            if not account:
                self.cmb_boards.clear()
                self.cmb_boards.addItems(["Main Board", "Ideas", "Inspiration"])
                self.log("No active account, showing default boards")
                return
            
            # Load cookies
            cookies = None
            if account['cookies']:
                try:
                    import json
                    cookies = json.loads(account['cookies'])
                except: pass
            
            # Get proxy
            proxy_dict = None
            if account['proxy']:
                parts = account['proxy'].split(':')
                if len(parts) >= 2:
                    proxy_dict = {'server': f"http://{parts[0]}:{parts[1]}"}
                    if len(parts) >= 4:
                        proxy_dict['username'] = parts[2]
                        proxy_dict['password'] = parts[3]
            
            # Create temporary automation instance
            automation = PinterestAutomation(headless=True, proxy=proxy_dict)
            if automation.start_browser(cookies=cookies):
                boards = automation.get_my_boards()
                automation.stop_browser()
                
                self.cmb_boards.clear()
                if boards:
                    # Save to DB
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("UPDATE accounts SET boards = ? WHERE id = ?", (json.dumps(boards), account['id']))
                    conn.commit()
                    conn.close()
                    
                    self.cmb_boards.addItems(boards)
                    self.log(f"Loaded {len(boards)} boards from Pinterest and saved to database")
                else:
                    self.cmb_boards.addItems(["Main Board", "Ideas", "Inspiration"])
                    self.log("Could not fetch boards, showing defaults")
            else:
                self.cmb_boards.clear()
                self.cmb_boards.addItems(["Main Board", "Ideas", "Inspiration"])
                self.log("Browser failed to start, showing defaults")
                
        except Exception as e:
            self.cmb_boards.clear()
            self.cmb_boards.addItems(["Main Board", "Ideas", "Inspiration"])
            self.log(f"Error loading boards: {e}")
    
    def start_automation(self):
        mode = 'repin' if self.rb_repin.isChecked() else 'upload'
        board_name = self.cmb_boards.currentText()
        limit = self.spin_limit.value()
        auto_like = self.chk_auto_like.isChecked() if mode == 'repin' else False
        
        if not board_name:
            self.log("Error: Please select a board")
            return
        
        image_files = None
        title_template = ""
        description_template = ""
        link_template = ""
        tags = ""
        upload_delay_min = 5
        upload_delay_max = 10
        
        if mode == 'upload':
            if not self.selected_files or len(self.selected_files) == 0:
                self.log("Error: Please select image files")
                return
            image_files = self.selected_files
            title_template = self.inp_title.text().strip()
            description_template = self.txt_description.toPlainText().strip()
            link_template = self.inp_link.text().strip()
            tags = self.inp_tags.text().strip()
            upload_delay_min = self.spin_delay_min.value()
            upload_delay_max = self.spin_delay_max.value()
            
            # Validate delay range
            if upload_delay_min > upload_delay_max:
                self.log("Error: Minimum delay cannot be greater than maximum delay")
                return
        
        self.txt_logs.clear()
        self.log(f"Starting {mode} automation...")
        
        # Register worker with AutomationManager for persistence
        from src.modules.automation_manager import AutomationManager
        manager = AutomationManager()
        
        # Prepare rotation options
        rotation_options = {
            'enabled': self.chk_rotation.isChecked(),
            'limit': self.spin_rotation_limit.value(),
            'boards': self.rotation_boards
        }
        
        self.worker = RepinWorker(
            mode, board_name, limit, 
            auto_like=auto_like, 
            image_files=image_files,
            title_template=title_template,
            description_template=description_template,
            link_template=link_template,
            tags=tags,
            upload_delay_min=upload_delay_min,
            upload_delay_max=upload_delay_max,
            rotation_options=rotation_options
        )
        manager.register_worker('repin', self.worker)
        
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
        mode = 'repinned' if self.rb_repin.isChecked() else 'uploaded'
        self.log(f"\n✓ Automation complete. {mode.capitalize()} {count} pins.")

    def add_to_schedule(self):
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QDateTimeEdit, QSpinBox, QDialogButtonBox
        from PySide6.QtCore import QDateTime
        import json
        
        # Validation
        mode = 'repin' if self.rb_repin.isChecked() else 'upload'
        board_name = self.cmb_boards.currentText()
        if not board_name:
            self.log("Error: Please select a board first")
            return
            
        dialog = QDialog(self)
        dialog.setWindowTitle("Schedule Task")
        dialog.setFixedWidth(300)
        d_layout = QVBoxLayout(dialog)
        
        d_layout.addWidget(QLabel("Start Time:"))
        dt_edit = QDateTimeEdit(QDateTime.currentDateTime().addSecs(600)) # Default 10 mins from now
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
        interval_spin.setValue(2)  # Default 2 minutes
        d_layout.addWidget(interval_spin)
        
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        d_layout.addWidget(btns)
        
        if dialog.exec():
            start_time = dt_edit.dateTime().toPyDateTime()
            repeat_count = repeat_spin.value()
            interval_mins = interval_spin.value()
            
            # Gather Payload
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM accounts WHERE is_selected = 1 LIMIT 1")
            account = cursor.fetchone()
            
            if not account:
                self.log("Error: No active account")
                conn.close()
                return

            import datetime
            current_time = start_time
            
            tasks_created = 0
            for i in range(repeat_count):
                payload = {
                    'board_name': board_name,
                    'limit': self.spin_limit.value(),
                    'auto_like': self.chk_auto_like.isChecked(),
                    'mode': mode
                }
                
                if mode == 'upload':
                    if not self.selected_files:
                        self.log("Error: No files selected for upload")
                        return
                    # For upload batch, we schedule separate tasks or 1 task?
                    # Let's schedule 1 task that handles the batch limit
                    payload['image_files'] = self.selected_files
                    payload['title_tmpl'] = self.inp_title.text()
                    payload['desc_tmpl'] = self.txt_description.toPlainText()
                    payload['link_tmpl'] = self.inp_link.text()
                    payload['tags'] = self.inp_tags.text()
                
                
                # Convert datetime to string format for consistent DB storage
                scheduled_time_str = current_time.strftime('%Y-%m-%d %H:%M:%S')
                
                cursor.execute("""
                    INSERT INTO scheduled_actions (account_id, action_type, target_data, scheduled_time, status)
                    VALUES (?, ?, ?, ?, 'pending')
                """, (account['id'], mode, json.dumps(payload), scheduled_time_str))
                
                current_time = current_time + datetime.timedelta(minutes=interval_mins)
                tasks_created += 1
                
            conn.commit()
            conn.close()
            self.log(f"✓ Scheduled {tasks_created} task(s) starting {start_time}")

    
    def log(self, message):
        self.txt_logs.append(message)
