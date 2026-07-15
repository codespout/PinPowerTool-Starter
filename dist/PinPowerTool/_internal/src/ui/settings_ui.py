from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTabWidget, QCheckBox, QLabel, 
                             QGridLayout, QLineEdit, QRadioButton, QButtonGroup, 
                             QHBoxLayout, QPushButton, QFrame, QSpinBox, QGroupBox)
from PySide6.QtCore import Qt
from src.modules.settings_manager import SettingsManager

class SettingsUI(QWidget):
    def __init__(self):
        super().__init__()
        self.settings_manager = SettingsManager()
        self.settings = self.settings_manager.get_all_settings()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        lbl_title = QLabel("🛠️ Global Settings")
        lbl_title.setObjectName("HeaderTitle")
        layout.addWidget(lbl_title)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.addTab(self.create_general_tab(), "⚙️ General")
        self.tabs.addTab(self.create_filters_tab(), "🔍 Filters")
        self.tabs.addTab(self.create_time_delay_tab(), "⏱️ Delay")
        self.tabs.addTab(self.create_proxy_tab(), "🌐 Proxy")
        self.tabs.addTab(self.create_safety_tab(), "🛡️ Safety")
        layout.addWidget(self.tabs)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("💾 Save All Changes")
        btn_save.setMinimumHeight(45)
        btn_save.clicked.connect(self.save_settings)
        
        btn_cancel = QPushButton("✖ Cancel")
        btn_cancel.setMinimumHeight(45)

        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def create_general_tab(self):
        tab = QWidget()
        layout = QGridLayout(tab)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.chk_skip_followed = QCheckBox("Skip people I have followed before")
        self.chk_skip_pinned = QCheckBox("Skip pins I have repinned before")
        self.chk_skip_own = QCheckBox("Skip my own pins when repinning")
        self.chk_skip_videos = QCheckBox("Skip videos when repinning")
        self.chk_skip_products = QCheckBox("Skip products for sale")
        self.chk_skip_links_desc = QCheckBox("Skip pins with links in the description")
        self.chk_skip_links_pin = QCheckBox("Skip pins with links in the pin itself")
        self.chk_skip_invited = QCheckBox("Skip people I have invited to the same board before")
        
        # Right column
        self.chk_disable_images = QCheckBox("Disable images for faster browsing")
        self.chk_auto_refresh = QCheckBox("Automatically refresh boards after logging in")
        
        # Set values
        self.chk_skip_followed.setChecked(self.settings.get("skip_followed", True))
        self.chk_skip_pinned.setChecked(self.settings.get("skip_pinned", True))
        self.chk_skip_own.setChecked(self.settings.get("skip_own_pins", False))
        self.chk_skip_videos.setChecked(self.settings.get("skip_videos", False))
        self.chk_skip_products.setChecked(self.settings.get("skip_products", True))
        self.chk_skip_links_desc.setChecked(self.settings.get("skip_links_desc", False))
        self.chk_skip_links_pin.setChecked(self.settings.get("skip_links_pin", False))
        self.chk_skip_invited.setChecked(self.settings.get("skip_invited",  False))
        self.chk_disable_images.setChecked(self.settings.get("disable_images", False))
        self.chk_auto_refresh.setChecked(self.settings.get("auto_refresh", False))
        
        # Add to layout
        layout.addWidget(self.chk_skip_followed, 0, 0)
        layout.addWidget(self.chk_skip_pinned, 1, 0)
        layout.addWidget(self.chk_skip_own, 2, 0)
        layout.addWidget(self.chk_skip_videos, 3, 0)
        layout.addWidget(self.chk_skip_products, 4, 0)
        layout.addWidget(self.chk_skip_links_desc, 5, 0)
        layout.addWidget(self.chk_skip_links_pin, 6, 0)
        layout.addWidget(self.chk_skip_invited, 7, 0)
        
        layout.addWidget(self.chk_disable_images, 0, 1)
        layout.addWidget(self.chk_auto_refresh, 1, 1)
        
        return tab

    def create_filters_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Description
        layout.addWidget(QLabel("ID's that don't match these filters will be skipped."))
        
        # Remove non-matching checkbox
        self.chk_remove_non_matching = QCheckBox("Remove non-matching ID's from the gathered list")
        layout.addWidget(self.chk_remove_non_matching)
        
        layout.addSpacing(10)
        
        # User ID Filters Group
        user_group = QGroupBox("User ID filters")
        user_layout = QGridLayout()
        
        # Helper to create filter row
        def create_filter_row(label_text, prefix):
            lbl = QLabel(label_text)
            lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            
            # Radio Buttons
            rb_off = QRadioButton("Filter Off")
            rb_less = QRadioButton("Less than")
            rb_more = QRadioButton("More than")
            
            # Group radios
            bg = QButtonGroup(tab)
            bg.addButton(rb_off, 0)
            bg.addButton(rb_less, 1)
            bg.addButton(rb_more, 2)
            rb_off.setChecked(True) # Default
            
            # Input
            inp = QLineEdit()
            inp.setFixedWidth(80)
            inp.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # Store references
            setattr(self, f"rb_{prefix}_off", rb_off)
            setattr(self, f"rb_{prefix}_less", rb_less)
            setattr(self, f"rb_{prefix}_more", rb_more)
            setattr(self, f"bg_{prefix}", bg)
            setattr(self, f"txt_{prefix}_val", inp)
            
            return lbl, rb_off, rb_less, rb_more, inp

        # Followers
        l1, r1a, r1b, r1c, i1 = create_filter_row("Followers:", "followers")
        user_layout.addWidget(l1, 0, 0)
        user_layout.addWidget(r1a, 0, 1)
        user_layout.addWidget(r1b, 0, 2)
        user_layout.addWidget(r1c, 0, 3)
        user_layout.addWidget(i1, 0, 4)
        
        # Following
        l2, r2a, r2b, r2c, i2 = create_filter_row("Following:", "following")
        user_layout.addWidget(l2, 1, 0)
        user_layout.addWidget(r2a, 1, 1)
        user_layout.addWidget(r2b, 1, 2)
        user_layout.addWidget(r2c, 1, 3)
        user_layout.addWidget(i2, 1, 4)
        
        # Pins (User's pin count)
        l3, r3a, r3b, r3c, i3 = create_filter_row("Pins:", "user_pins")
        user_layout.addWidget(l3, 2, 0)
        user_layout.addWidget(r3a, 2, 1)
        user_layout.addWidget(r3b, 2, 2)
        user_layout.addWidget(r3c, 2, 3)
        user_layout.addWidget(i3, 2, 4)
        
        user_group.setLayout(user_layout)
        layout.addWidget(user_group)
        
        layout.addSpacing(10)

        # Pin ID Filters Group
        pin_group = QGroupBox("Pin ID filters")
        pin_layout = QGridLayout()
        
        # Repins
        l4, r4a, r4b, r4c, i4 = create_filter_row("Repins:", "repins")
        pin_layout.addWidget(l4, 0, 0)
        pin_layout.addWidget(r4a, 0, 1)
        pin_layout.addWidget(r4b, 0, 2)
        pin_layout.addWidget(r4c, 0, 3)
        pin_layout.addWidget(i4, 0, 4)
        
        # Ignore Keywords
        lbl_kw = QLabel("Ignore keywords:")
        rb_kw_off = QRadioButton("Filter Off")
        rb_kw_on = QRadioButton("Filter On")
        bg_kw = QButtonGroup(tab)
        bg_kw.addButton(rb_kw_off, 0)
        bg_kw.addButton(rb_kw_on, 1)
        rb_kw_off.setChecked(True)
        
        lbl_kw_input = QLabel("Keywords:")
        txt_kw = QLineEdit()
        
        self.rb_keywords_off = rb_kw_off
        self.rb_keywords_on = rb_kw_on
        self.bg_keywords = bg_kw
        self.txt_keywords = txt_kw
        
        pin_layout.addWidget(lbl_kw, 1, 0)
        pin_layout.addWidget(rb_kw_off, 1, 1)
        pin_layout.addWidget(rb_kw_on, 1, 2)
        pin_layout.addWidget(lbl_kw_input, 1, 3)
        pin_layout.addWidget(txt_kw, 1, 4)
        
        pin_group.setLayout(pin_layout)
        layout.addWidget(pin_group)
        
        layout.addStretch()
        
        # Load values
        self.chk_remove_non_matching.setChecked(self.settings.get("filter_remove_non_matching", False))
        
        def load_filter_row(prefix):
            mode = self.settings.get(f"filter_{prefix}_mode", 0) # 0=Off, 1=Less, 2=More
            val = self.settings.get(f"filter_{prefix}_val", "")
            
            bg = getattr(self, f"bg_{prefix}")
            btn = bg.button(mode)
            if btn: btn.setChecked(True)
            
            getattr(self, f"txt_{prefix}_val").setText(str(val))

        load_filter_row("followers")
        load_filter_row("following")
        load_filter_row("user_pins")
        load_filter_row("repins")
        
        # Keywords
        kw_mode = self.settings.get("filter_keywords_mode", 0)
        self.bg_keywords.button(kw_mode).setChecked(True)
        self.txt_keywords.setText(self.settings.get("filter_keywords_val", ""))
        
        return tab

    def create_time_delay_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        layout.addWidget(QLabel("<b>A high time delay helps prevent being flagged for spamming</b>"))
        
        # Random Interval
        h_layout = QHBoxLayout()
        h_layout.addWidget(QLabel("Random interval after each action:"))
        self.spin_delay_min = QSpinBox()
        self.spin_delay_max = QSpinBox()
        self.spin_delay_min.setRange(1, 3600)
        self.spin_delay_max.setRange(1, 3600)
        h_layout.addWidget(self.spin_delay_min)
        h_layout.addWidget(QLabel("to"))
        h_layout.addWidget(self.spin_delay_max)
        h_layout.addWidget(QLabel("seconds"))
        layout.addLayout(h_layout)
        
        # Set values
        self.spin_delay_min.setValue(self.settings.get("delay_min", 5))
        self.spin_delay_max.setValue(self.settings.get("delay_max", 15))
        
        layout.addSpacing(20)
        
        # Take breaks checkbox
        self.chk_take_breaks = QCheckBox("Take occasional breaks during automation (every 50 actions)")
        self.chk_take_breaks.setChecked(self.settings.get("take_breaks", False))
        layout.addWidget(self.chk_take_breaks)
        
        layout.addStretch()
        return tab


    def create_proxy_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        self.chk_use_proxy = QCheckBox("Enable proxy")
        layout.addWidget(self.chk_use_proxy)
        
        form_layout = QGridLayout()
        self.txt_proxy_host = QLineEdit()
        self.txt_proxy_port = QLineEdit()
        self.txt_proxy_user = QLineEdit()
        self.txt_proxy_pass = QLineEdit()
        self.txt_proxy_pass.setEchoMode(QLineEdit.EchoMode.Password)
        
        form_layout.addWidget(QLabel("Proxy:"), 0, 0)
        form_layout.addWidget(self.txt_proxy_host, 0, 1)
        form_layout.addWidget(QLabel("Port:"), 0, 2)
        form_layout.addWidget(self.txt_proxy_port, 0, 3)
        
        form_layout.addWidget(QLabel("Username:"), 1, 0)
        form_layout.addWidget(self.txt_proxy_user, 1, 1)
        form_layout.addWidget(QLabel("Password:"), 2, 0)
        form_layout.addWidget(self.txt_proxy_pass, 2, 1)
        
        layout.addLayout(form_layout)
        layout.addStretch()
        
        # Init values
        self.chk_use_proxy.setChecked(self.settings.get("use_proxy", False))
        self.txt_proxy_host.setText(self.settings.get("proxy_host", ""))
        self.txt_proxy_port.setText(self.settings.get("proxy_port", ""))
        self.txt_proxy_user.setText(self.settings.get("proxy_user", ""))
        self.txt_proxy_pass.setText(self.settings.get("proxy_pass", ""))
        
        return tab

    def create_safety_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Human Warmup Group
        warmup_group = QGroupBox("Autonomous Human-Warmup Interaction")
        warmup_layout = QVBoxLayout()
        
        lbl_info = QLabel("Mimics real user browsing patterns before starting automated tasks to reduce bot detection.")
        lbl_info.setObjectName("InfoLabel")
        warmup_layout.addWidget(lbl_info)
        
        self.chk_warmup_enabled = QCheckBox("Enable Human-Warmup session")
        self.chk_warmup_enabled.setChecked(self.settings.get("warmup_enabled", False))
        warmup_layout.addWidget(self.chk_warmup_enabled)
        
        h_layout = QHBoxLayout()
        h_layout.addWidget(QLabel("Warmup Duration:"))
        self.spin_warmup_duration = QSpinBox()
        self.spin_warmup_duration.setRange(2, 30)
        self.spin_warmup_duration.setSuffix(" minutes")
        self.spin_warmup_duration.setValue(self.settings.get("warmup_duration", 10))
        h_layout.addWidget(self.spin_warmup_duration)
        h_layout.addStretch()
        warmup_layout.addLayout(h_layout)
        
        warmup_group.setLayout(warmup_layout)
        layout.addWidget(warmup_group)
        
        layout.addStretch()
        return tab

    def save_settings(self):
        try:
            # General
            self.settings_manager.set_setting("skip_followed", self.chk_skip_followed.isChecked())
            self.settings_manager.set_setting("skip_pinned", self.chk_skip_pinned.isChecked())
            self.settings_manager.set_setting("skip_own_pins", self.chk_skip_own.isChecked())
            self.settings_manager.set_setting("skip_videos", self.chk_skip_videos.isChecked())
            self.settings_manager.set_setting("skip_products", self.chk_skip_products.isChecked())
            self.settings_manager.set_setting("skip_links_desc", self.chk_skip_links_desc.isChecked())
            self.settings_manager.set_setting("skip_links_pin", self.chk_skip_links_pin.isChecked())
            self.settings_manager.set_setting("skip_invited", self.chk_skip_invited.isChecked())
            self.settings_manager.set_setting("disable_images", self.chk_disable_images.isChecked())
            self.settings_manager.set_setting("auto_refresh", self.chk_auto_refresh.isChecked())
            
            # Filters
            self.settings_manager.set_setting("filter_remove_non_matching", self.chk_remove_non_matching.isChecked())
            
            def save_filter_row(prefix):
                bg = getattr(self, f"bg_{prefix}")
                mode = bg.checkedId()
                val = getattr(self, f"txt_{prefix}_val").text()
                
                self.settings_manager.set_setting(f"filter_{prefix}_mode", mode)
                self.settings_manager.set_setting(f"filter_{prefix}_val", val)

            save_filter_row("followers")
            save_filter_row("following")
            save_filter_row("user_pins")
            save_filter_row("repins")
            
            self.settings_manager.set_setting("filter_keywords_mode", self.bg_keywords.checkedId())
            self.settings_manager.set_setting("filter_keywords_val", self.txt_keywords.text())
                
            # Time Delay
            self.settings_manager.set_setting("delay_min", self.spin_delay_min.value())
            self.settings_manager.set_setting("delay_max", self.spin_delay_max.value())
            self.settings_manager.set_setting("take_breaks", self.chk_take_breaks.isChecked())
            
            # Proxy
            self.settings_manager.set_setting("use_proxy", self.chk_use_proxy.isChecked())
            self.settings_manager.set_setting("proxy_host", self.txt_proxy_host.text())
            self.settings_manager.set_setting("proxy_port", self.txt_proxy_port.text())
            self.settings_manager.set_setting("proxy_user", self.txt_proxy_user.text())
            self.settings_manager.set_setting("proxy_pass", self.txt_proxy_pass.text())
            
            # Safety
            self.settings_manager.set_setting("warmup_enabled", self.chk_warmup_enabled.isChecked())
            self.settings_manager.set_setting("warmup_duration", self.spin_warmup_duration.value())
            
            print("Settings Saved")
            
            # Show success notification
            from PySide6.QtWidgets import QMessageBox
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setWindowTitle("Success")
            msg.setText("Settings saved successfully!")
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.exec()
            
        except Exception as e:
            # Show error notification
            from PySide6.QtWidgets import QMessageBox
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setWindowTitle("Error")
            msg.setText(f"Failed to save settings:\n{str(e)}")
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.exec()
            print(f"Error saving settings: {e}")
            import traceback
            traceback.print_exc()
