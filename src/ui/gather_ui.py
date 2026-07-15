from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QTextEdit, QTabWidget, QRadioButton, QButtonGroup, 
                             QSpinBox, QProgressBar, QMessageBox, QComboBox, QGroupBox, QScrollArea)
from PySide6.QtCore import Qt, QThread, Signal as pyqtSignal
from src.modules.actions import PinterestAutomation
from src.modules.filters import FilterModule
from src.database import get_db_connection
import json

class GatherWorker(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(list)
    
    def __init__(self, mode, keyword, limit, source_type='search', trend_options=None):
        super().__init__()
        self.mode = mode # 'pins' or 'users'
        self.keyword = keyword
        self.limit = limit
        self.source_type = source_type  # 'search', 'user', 'followers', 'following', 'trends'
        self.trend_options = trend_options or {} # {'country': 'US', 'interest': 'ALL'}
        
        # Fetch Active Account
        self.account = self.get_active_account()
        
        # Load automation settings first
        from src.modules.settings_helper import AutomationSettings
        self.auto_settings = AutomationSettings()
        
        # Configure Proxy
        proxy_dict = None
        
        # Check Global Settings Proxy first
        use_global_proxy = self.auto_settings.settings.get("use_proxy", False)
        if use_global_proxy:
            host = self.auto_settings.settings.get("proxy_host", "").strip()
            port = self.auto_settings.settings.get("proxy_port", "").strip()
            user = self.auto_settings.settings.get("proxy_user", "").strip()
            pwd = self.auto_settings.settings.get("proxy_pass", "").strip()
            
            if host and port:
                self.log_signal.emit(f"DEBUG: Using Global Proxy settings: {host}:{port}")
                proxy_dict = {'server': f"http://{host}:{port}"}
                if user and pwd:
                    proxy_dict['username'] = user
                    proxy_dict['password'] = pwd
            else:
                self.log_signal.emit("WARNING: Global Proxy enabled but Host/Port missing.")

        # Fallback to Account Proxy if Global not used/invalid
        if not proxy_dict and self.account and self.account['proxy']:
            raw_proxy = self.account['proxy']
            self.log_signal.emit(f"DEBUG: Found proxy string in Account DB: '{raw_proxy}'")
            
            p_str = raw_proxy.strip()
            p_str = p_str.replace('http://', '').replace('https://', '')
            
            parts = p_str.split(':')
            if len(parts) >= 2:
                proxy_dict = {'server': f"http://{parts[0]}:{parts[1]}"}
                if len(parts) >= 4:
                    proxy_dict['username'] = parts[2]
                    proxy_dict['password'] = parts[3]
                self.log_signal.emit(f"DEBUG: Parsed Account proxy: {parts[0]}:***")
            else:
                self.log_signal.emit(f"WARNING: Account proxy string invalid.")
        
        if not proxy_dict:
             self.log_signal.emit("DEBUG: No proxy configured (Global or Account).")

        disable_images = self.auto_settings.settings.get("disable_images", False)
        
        self.automation = PinterestAutomation(headless=False, proxy=proxy_dict, disable_images=disable_images)
        self.filters = FilterModule()
        
        self.is_running = True

    def get_active_account(self):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM accounts WHERE is_selected = 1 LIMIT 1")
        account = cursor.fetchone()
        conn.close()
        return account

    def run(self):
        if not self.account:
            self.log_signal.emit("Error: No active account selected. Please select an account in the Accounts tab.")
            self.finished_signal.emit([])
            return

        self.log_signal.emit(f"Starting gather {self.mode} for '{self.keyword}' using account: {self.account['email']}...")
        
        # Load cookies if available
        cookies = None
        if self.account['cookies']:
            try:
                cookies = json.loads(self.account['cookies'])
            except Exception as e:
                self.log_signal.emit(f"Warning: Failed to parse cookies: {e}")
                
        # Start browser with cookies
        if not self.automation.start_browser(cookies=cookies):
            self.log_signal.emit("Error: Failed to start browser")
            self.finished_signal.emit([])
            return
        
        # Ensure user is logged in
        self.log_signal.emit("Verifying login status...")
        if not self.automation.ensure_logged_in(self.account['email'], self.account['password']):
            self.log_signal.emit("Error: Failed to login. Please check your credentials.")
            self.automation.stop_browser()
            self.finished_signal.emit([])
            return
        
        # Save cookies after successful login
        try:
            fresh_cookies = self.automation.context.cookies()
            cookies_json = json.dumps(fresh_cookies)
            
            # Update database with fresh cookies
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE accounts SET cookies = ? WHERE email = ?", 
                          (cookies_json, self.account['email']))
            conn.commit()
            conn.close()
            self.log_signal.emit("Login session saved.")
        except Exception as e:
            self.log_signal.emit(f"Warning: Failed to save cookies: {e}")
        
        # Get username for skip own pins check
        account_username = self.account['email'].split('@')[0] if self.account and self.account['email'] else ""
        
        # Log active filters
        filter_summary = self.auto_settings.get_filter_summary()
        self.log_signal.emit(f"Active filters: {filter_summary}")
        
        results = []
        if self.mode == 'pins':
            # Smart iterative gathering for pins
            scraped_pins = set()
            filtered_count = 0
            attempt = 0
            max_attempts = 5
            
            while filtered_count < self.limit and attempt < max_attempts and self.is_running:
                attempt += 1
                needed = self.limit - filtered_count
                scrape_limit = max(needed * 5, 20)
                
                self.log_signal.emit(f"Attempt {attempt}: Need {needed} more pins, scraping {scrape_limit}...")
                
                continue_mode = (attempt > 1)
                raw_results = []
                
                # Check running before scraping
                if not self.is_running: break
                
                if self.mode == 'pins' and self.source_type == 'trends':
                    # Trending Mode: 
                    # 1. Get trending keywords
                    country = self.trend_options.get('country', 'US')
                    interest = self.trend_options.get('interest', 'ALL')
                    self.log_signal.emit(f"Fetching trending keywords for {country}...")
                    trending_keywords = self.automation.get_trending_keywords(country, interest, self.log_signal)
                    
                    if not trending_keywords:
                        self.log_signal.emit("No trending keywords found. Trying base keyword if provided...")
                        trending_keywords = [self.keyword] if self.keyword else []

                    # 2. Iterate and scrape pins for each
                    for kw in trending_keywords:
                        if not self.is_running or len(raw_results) >= self.limit * 2: break
                        self.log_signal.emit(f"Scraping pins for trending topic: {kw}")
                        kw_results = self.automation.scrape_pins(kw, limit=20)
                        raw_results.extend(kw_results)
                
                elif self.mode == 'pins':
                    # Standard Scrape
                    raw_results = self.automation.scrape_pins(
                        self.keyword, 
                        limit=scrape_limit, 
                        source_type=self.source_type,
                        continue_scrolling=continue_mode,
                        exclude_pins=scraped_pins,
                        should_stop=lambda: not self.is_running
                    )
                
                # Check running after scraping
                if not self.is_running: break
                
                # Filter duplicates (exclude_pins handles checking against scraped_pins set, 
                # but raw_results might contain duplicates within itself if scrape logic is loose, so we double check)
                new_pins = []
                for p in raw_results:
                    p_url = p['url'] if isinstance(p, dict) else p
                    if p_url not in scraped_pins:
                        new_pins.append(p)
                        scraped_pins.add(p_url)
                
                if not new_pins:
                    self.log_signal.emit(f"No new pins found in attempt {attempt}. Stopping.")
                    break
                    
                self.log_signal.emit(f"Scraped {len(new_pins)} new pins. Filtering...")
                
                # Check running before filtering
                if not self.is_running: break
                
                # Apply filters (now with batch details fetching)
                filtered_pins = self.auto_settings.apply_filters_to_pins(
                    new_pins, 
                    account_username, 
                    self.automation,
                    should_stop=lambda: not self.is_running
                )
                
                added_this_round = 0
                for pin in filtered_pins:
                    if not self.is_running: break
                    
                    pin_url = pin['url']
                    if pin_url not in results:
                        results.append(pin_url)
                        filtered_count += 1
                        added_this_round += 1
                        
                        if len(results) >= self.limit:
                            break
                
                self.log_signal.emit(f"Added {added_this_round} pins this round (total: {filtered_count}/{self.limit})")
                
                if added_this_round == 0 and filtered_count < self.limit:
                    self.log_signal.emit(f"No pins passed filters in this batch. Continuing search...")

            if filtered_count < self.limit:
                self.log_signal.emit(f"Filtered down to {filtered_count} pins.")
                
        elif self.mode == 'users':
            # Smart iterative gathering: Keep scraping until we have enough filtered results
            scraped_users = set()  # Track all scraped users to avoid duplicates
            filtered_count = 0
            attempt = 0
            max_attempts = 5  # Prevent infinite loops
            
            while filtered_count < self.limit and attempt < max_attempts and self.is_running:
                attempt += 1
                
                # Calculate how many more we need
                needed = self.limit - filtered_count
                # Scrape more aggressively: multiply by 5 to account for filtering
                scrape_limit = max(needed * 5, 20)  # At least 20 per attempt
                
                self.log_signal.emit(f"Attempt {attempt}: Need {needed} more users, scraping {scrape_limit}...")
                
                # Scrape users - use continue_scrolling for attempts after the first
                # Pass scraped_users as exclude_users to avoid getting duplicates
                continue_mode = (attempt > 1)
                
                if not self.is_running: break
                
                raw_results = self.automation.scrape_users(
                    self.keyword, 
                    limit=scrape_limit, 
                    source_type=self.source_type,
                    continue_scrolling=continue_mode,
                    exclude_users=scraped_users
                )
                
                # Filter out already scraped users (duplicates)
                new_users = [u for u in raw_results if u not in scraped_users]
                scraped_users.update(raw_results)
                
                if not new_users:
                    self.log_signal.emit(f"No new users found in attempt {attempt}. Stopping.")
                    break
                
                self.log_signal.emit(f"Scraped {len(new_users)} new users (total: {len(scraped_users)}). Filtering...")
                
                if not self.is_running: break
                
                # Apply filters using settings helper
                filtered_users = self.auto_settings.apply_filters_to_users(new_users, self.automation)
                
                # Add filtered users to results
                added_this_round = 0
                for user in filtered_users:
                    if not self.is_running:
                        break
                    
                    # Check if we already have this user
                    user_url = user.get('url') or user.get('user_url')
                    if user_url not in [r for r in results]:
                        results.append(user_url)
                        filtered_count += 1
                        added_this_round += 1
                        
                        if filtered_count >= self.limit:
                            break
                
                self.log_signal.emit(f"Added {added_this_round} users this round (total: {filtered_count}/{self.limit})")
                
                # If we didn't add any users this round despite having new users, 
                # it means none passed the filters - keep trying
                if added_this_round == 0 and filtered_count < self.limit:
                    self.log_signal.emit(f"No users passed filters in this batch. Continuing search...")
            
            if filtered_count < self.limit:
                self.log_signal.emit(f"⚠ Warning: Only found {filtered_count} users matching filters out of {self.limit} requested")



        self.automation.stop_browser()
        self.finished_signal.emit(results)
        self.log_signal.emit("Gathering finished.")

    def stop(self):
        self.is_running = False

class GatherUI(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.setup_ui()

    def setup_ui(self):
        main_vbox = QVBoxLayout(self)
        
        # Scroll Area for Premium Look
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll.setObjectName("ContentScroll")
        
        self.scroll_content = QWidget()
        layout = QVBoxLayout(self.scroll_content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)
        
        # Tabs
        self.tabs = QTabWidget()
        self.tab_pins = QWidget()
        self.tab_users = QWidget()
        
        self.setup_pins_tab()
        self.setup_users_tab()
        
        self.tabs.addTab(self.tab_pins, "📍 Gather Pins")
        self.tabs.addTab(self.tab_users, "👤 Gather Users")
        
        layout.addWidget(self.tabs)
        
        # Common Controls (Bottom)
        controls_group = QGroupBox("Execution Controls")
        controls_layout = QHBoxLayout()
        
        self.lbl_count = QLabel("Total Results: 0")
        self.lbl_count = QLabel("Total Results: 0")
        self.lbl_count.setObjectName("ResultCountLabel")
        
        self.btn_start = QPushButton("🚀 Start Gathering")
        self.btn_start.setMinimumHeight(50)
        self.btn_start.clicked.connect(self.start_gathering)
        
        self.btn_stop = QPushButton("🛑 Stop")
        self.btn_stop.setMinimumHeight(50)
        self.btn_stop.clicked.connect(self.stop_gathering)
        self.btn_stop.setEnabled(False)
        
        self.btn_clear = QPushButton("🗑️ Clear All")
        self.btn_clear.clicked.connect(self.clear_results)
        
        controls_layout.addWidget(self.lbl_count)
        controls_layout.addStretch()
        controls_layout.addWidget(self.btn_start)
        controls_layout.addWidget(self.btn_stop)
        controls_layout.addWidget(self.btn_clear)
        
        controls_group.setLayout(controls_layout)
        layout.addWidget(controls_group)
        
        # Results & Logs
        results_group = QGroupBox("Gathered Results & Activity")
        res_layout = QVBoxLayout()
        
        self.txt_results = QTextEdit()
        self.txt_results.setPlaceholderText("Gathered results will appear here...")
        self.txt_results.setMinimumHeight(200)
        res_layout.addWidget(self.txt_results)
        
        self.txt_logs = QTextEdit()
        self.txt_logs.setMaximumHeight(120)
        self.txt_logs.setReadOnly(True)
        self.txt_logs.setPlaceholderText("Activity Log...")
        res_layout.addWidget(self.txt_logs)
        
        results_group.setLayout(res_layout)
        layout.addWidget(results_group)
        
        # Finalize Scroll Area
        self.scroll.setWidget(self.scroll_content)
        main_vbox.addWidget(self.scroll)
        
        # Load existing results from database
        self.load_existing_results()
    
    def load_existing_results(self):
        """Load and display existing gathered results from database."""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Load gathered pins
            cursor.execute("SELECT COUNT(*) as count FROM gathered_pins")
            pin_count = cursor.fetchone()['count']
            
            if pin_count > 0:
                cursor.execute("SELECT pin_url, source, gathered_date FROM gathered_pins ORDER BY gathered_date DESC LIMIT 100")
                pins = cursor.fetchall()
                
                self.txt_results.append(f"=== {pin_count} Gathered Pins (showing last 100) ===\n")
                for pin in pins:
                    self.txt_results.append(f"{pin['pin_url']} (Source: {pin['source'] or 'unknown'})")
                self.txt_results.append("\n")
            
            # Load gathered users
            cursor.execute("SELECT COUNT(*) as count FROM gathered_users")
            user_count = cursor.fetchone()['count']
            
            if user_count > 0:
                cursor.execute("SELECT user_url, username, source, gathered_date FROM gathered_users ORDER BY gathered_date DESC LIMIT 100")
                users = cursor.fetchall()
                
                self.txt_results.append(f"=== {user_count} Gathered Users (showing last 100) ===\n")
                for user in users:
                    self.txt_results.append(f"{user['user_url']} ({user['username']}) - Source: {user['source'] or 'unknown'}")
                self.txt_results.append("\n")
            
            # Update count label
            total = pin_count + user_count
            self.lbl_count.setText(f"Results: {total}")
            
            conn.close()
        except Exception as e:
            self.log(f"Error loading existing results: {e}")

    def setup_pins_tab(self):
        layout = QVBoxLayout(self.tab_pins)
        layout.setSpacing(10)
        
        source_group = QGroupBox("Select Source")
        source_layout = QVBoxLayout()
        
        self.bg_pins_source = QButtonGroup(self)
        rb_keyword = QRadioButton("🔍 From Search Term")
        rb_user = QRadioButton("👤 From Specific Users")
        rb_trends = QRadioButton("📈 From Trending (Viral Rider)")
        self.bg_pins_source.addButton(rb_keyword, 0)
        self.bg_pins_source.addButton(rb_user, 1)
        self.bg_pins_source.addButton(rb_trends, 2)
        rb_keyword.setChecked(True)
        
        source_layout.addWidget(rb_keyword)
        source_layout.addWidget(rb_user)
        source_layout.addWidget(rb_trends)
        source_group.setLayout(source_layout)
        layout.addWidget(source_group)

        # Trends Settings (Hidden by default)
        self.trends_group = QWidget()
        trends_layout = QHBoxLayout(self.trends_group)
        trends_layout.setContentsMargins(20, 0, 0, 0)
        
        trends_layout.addWidget(QLabel("Region:"))
        self.combo_trend_region = QComboBox()
        self.trend_regions = {
            "United States": "US",
            "Great Britain & Ireland": "GB+IE",
            "Canada": "CA",
            "Southern Europe (IT, ES, PT, GR, MT)": "IT+ES+PT+GR+MT",
            "Italy": "IT",
            "Spain": "ES",
            "Germanic countries (DE, AT, CH)": "DE+AT+CH",
            "Germany": "DE",
            "France": "FR",
            "Nordic countries (SE, DK, FI, NO)": "SE+DK+FI+NO",
            "Benelux (NL, BE, LU)": "NL+BE+LU",
            "Eastern Europe (PL, RO, HU, SK, CZ)": "PL+RO+HU+SK+CZ",
            "Hispanic LatAm (MX, AR, CO, CL)": "MX+AR+CO+CL",
            "Colombia": "CO",
            "Argentina": "AR",
            "Mexico": "MX",
            "Brazil": "BR",
            "Australasia (AU, NZ)": "AU+NZ",
            "Malaysia": "MY",
            "Philippines": "PH",
            "Thailand": "TH",
            "Egypt": "EG",
            "Turkey": "TR",
            "Korea": "KR",
            "Latin America & Caribbean": "CR+DO+EC+GT+PE",
            "Eastern Europe & Mediterranean": "CY+CZ+GR+HU+MT+PL+RO+SK"
        }
        self.combo_trend_region.addItems(self.trend_regions.keys())
        trends_layout.addWidget(self.combo_trend_region)

        trends_layout.addWidget(QLabel("Interest:"))
        self.combo_trend_interest = QComboBox()
        self.trend_interests = {
            "All": "ALL",
            "Animals": "925056443165",
            "Architecture": "918105274631",
            "Art": "961238559656",
            "Beauty": "935541271955",
            "DIY and Crafts": "934876475639",
            "Education": "922134410098",
            "Event Planning": "941870572865",
            "Fashion": "FASHION",
            "Food and Drinks": "918530398158",
            "Gardening": "909983286710",
            "Health": "898620064290",
            "Home Decor": "935249274030",
            "Parenting": "920236059316",
            "Travel": "908182459161",
            "Wedding": "903260720461"
        }
        self.combo_trend_interest.addItems(self.trend_interests.keys())
        trends_layout.addWidget(self.combo_trend_interest)
        
        layout.addWidget(self.trends_group)
        self.trends_group.setVisible(False)

        # Connect Visibility
        rb_trends.toggled.connect(lambda checked: self.trends_group.setVisible(checked))
        rb_trends.toggled.connect(lambda checked: self.inp_pins_keyword.setPlaceholderText("Enter optional base topic (e.g. Christmas)..." if checked else "Enter keyword or user URL..."))
        
        # Input
        self.inp_pins_keyword = QLineEdit()
        self.inp_pins_keyword.setPlaceholderText("Enter keyword or user URL...")
        layout.addWidget(self.inp_pins_keyword)
        
        # Limit
        limit_layout = QHBoxLayout()
        limit_layout.addWidget(QLabel("Amount to gather:"))
        self.spin_pins_limit = QSpinBox()
        self.spin_pins_limit.setRange(1, 10000)
        self.spin_pins_limit.setValue(50)
        limit_layout.addWidget(self.spin_pins_limit)
        limit_layout.addStretch()
        layout.addLayout(limit_layout)
        
        layout.addStretch()

    def setup_users_tab(self):
        layout = QVBoxLayout(self.tab_users)
        layout.setSpacing(10)
        
        source_group = QGroupBox("Select Source")
        source_layout = QVBoxLayout()
        
        self.bg_users_source = QButtonGroup(self)
        rb_keyword = QRadioButton("🔍 From Search Term")
        rb_followers = QRadioButton("👥 From User's Followers")
        rb_following = QRadioButton("🏃 From User's Following")
        self.bg_users_source.addButton(rb_keyword, 0)
        self.bg_users_source.addButton(rb_followers, 1)
        self.bg_users_source.addButton(rb_following, 2)
        rb_keyword.setChecked(True)
        
        source_layout.addWidget(rb_keyword)
        source_layout.addWidget(rb_followers)
        source_layout.addWidget(rb_following)
        source_group.setLayout(source_layout)
        layout.addWidget(source_group)
        
        # Input
        self.inp_users_keyword = QLineEdit()
        self.inp_users_keyword.setPlaceholderText("Enter keyword or user URL...")
        layout.addWidget(self.inp_users_keyword)
        
        # Limit
        limit_layout = QHBoxLayout()
        limit_layout.addWidget(QLabel("Amount to gather:"))
        self.spin_users_limit = QSpinBox()
        self.spin_users_limit.setRange(1, 10000)
        self.spin_users_limit.setValue(50)
        limit_layout.addWidget(self.spin_users_limit)
        limit_layout.addStretch()
        layout.addLayout(limit_layout)
        
        layout.addStretch()

    def start_gathering(self):
        current_tab = self.tabs.currentIndex()
        
        if current_tab == 0: # Pins
            mode = 'pins'
            keyword = self.inp_pins_keyword.text()
            limit = self.spin_pins_limit.value()
            
            # Determine source type
            selected_id = self.bg_pins_source.checkedId()
            source_type = 'search'
            trend_options = None
            
            if selected_id == 0:
                source_type = 'search'
            elif selected_id == 1:
                source_type = 'user'
            elif selected_id == 2:
                source_type = 'trends'
                country_key = self.combo_trend_region.currentText()
                interest_key = self.combo_trend_interest.currentText()
                trend_options = {
                    'country': self.trend_regions.get(country_key, 'US'),
                    'interest': self.trend_interests.get(interest_key, 'ALL')
                }
            
            # For trends, keyword is optional
            if source_type != 'trends' and not keyword:
                QMessageBox.warning(self, "Error", "Please enter a keyword or URL.")
                return
                
        else: # Users
            mode = 'users'
            keyword = self.inp_users_keyword.text()
            limit = self.spin_users_limit.value()
            
            # Determine source type
            selected_id = self.bg_users_source.checkedId()
            if selected_id == 0:
                source_type = 'search'  # From Search Term
            elif selected_id == 1:
                source_type = 'followers'  # From User's Followers
            else:
                source_type = 'following'  # From User's Following
            
        self.worker = GatherWorker(mode, keyword, limit, source_type, trend_options=trend_options)
        self.worker.log_signal.connect(self.log)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()
        
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.log("Gathering started...")

    def stop_gathering(self):
        if self.worker:
            self.worker.stop()
            self.log("Stopping...")

    def on_finished(self, results):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        
        self.txt_results.clear()
        for item in results:
            self.txt_results.append(item)
            
        self.lbl_count.setText(f"Results: {len(results)}")
        self.log(f"Gathered {len(results)} items.")
        
        # Save results to database for automation features
        if results:
            self.save_to_database(results)
    
    def save_to_database(self, results):
        """Save gathered results to database for use by automation features."""
        try:
            from datetime import datetime
            conn = get_db_connection()
            cursor = conn.cursor()
            
            current_tab = self.tabs.currentIndex()
            saved_count = 0
            
            if current_tab == 0:  # Pins tab
                for pin_url in results:
                    try:
                        # Extract source info
                        keyword = self.inp_pins_keyword.text()
                        selected_id = self.bg_pins_source.checkedId()
                        
                        is_trending = 0
                        if selected_id == 0: source = f"search:{keyword}"
                        elif selected_id == 1: source = f"user:{keyword}"
                        elif selected_id == 2: 
                            source = f"trends:{self.combo_trend_region.currentText()}"
                            is_trending = 1
                        
                        cursor.execute(
                            "INSERT OR IGNORE INTO gathered_pins (pin_url, gathered_date, source, is_trending) VALUES (?, ?, ?, ?)",
                            (pin_url, datetime.now(), source, is_trending)
                        )
                        if cursor.rowcount > 0:
                            saved_count += 1
                    except Exception as e:
                        print(f"Error saving pin: {e}")
                        
            else:  # Users tab
                for user_url in results:
                    try:
                        # Extract username from URL
                        username = user_url.rstrip('/').split('/')[-1] if '/' in user_url else user_url
                        
                        # Extract source info
                        keyword = self.inp_users_keyword.text()
                        selected_id = self.bg_users_source.checkedId()
                        if selected_id == 0:
                            source = f"search:{keyword}"
                        elif selected_id == 1:
                            source = f"followers:{keyword}"
                        else:
                            source = f"following:{keyword}"
                        
                        cursor.execute(
                            "INSERT OR IGNORE INTO gathered_users (user_url, username, gathered_date, source) VALUES (?, ?, ?, ?)",
                            (user_url, username, datetime.now(), source)
                        )
                        if cursor.rowcount > 0:
                            saved_count += 1
                    except Exception as e:
                        print(f"Error saving user: {e}")
            
            conn.commit()
            conn.close()
            
            self.log(f"Saved {saved_count} new items to database")
            
        except Exception as e:
            self.log(f"Error saving to database: {e}")
            print(f"Database save error: {e}")

    def clear_results(self):
        """Clear gathered results from UI and database."""
        try:
            # Delete from database
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM gathered_pins")
            pins_deleted = cursor.rowcount
            
            cursor.execute("DELETE FROM gathered_users")
            users_deleted = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            # Clear UI
            self.txt_results.clear()
            self.lbl_count.setText("Results: 0")
            
            self.log(f"Cleared {pins_deleted} pins and {users_deleted} users from database")
            
        except Exception as e:
            self.log(f"Error clearing results: {e}")
            print(f"Clear error: {e}")

    def log(self, message):
        self.txt_logs.append(message)
