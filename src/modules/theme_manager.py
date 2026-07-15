import json

class ThemeManager:
    # Color Palettes
    DARK_PALETTE = {
        "bg_main": "#1e1e2e",      # Deep Charcoal
        "bg_sidebar": "#181825",   # Midnight Slate
        "bg_card": "#313244",      # Lighter slate for cards
        "accent": "#e60023",       # Pinterest Red
        "accent_hover": "#ad081b", # Darker Red for hover
        "text_main": "#cdd6f4",    # Off-white
        "text_muted": "#a6adc8",   # Greyed out
        "border": "#45475a",
        "input_bg": "#11111b"
    }

    LIGHT_PALETTE = {
        "bg_main": "#eff1f5",
        "bg_sidebar": "#e6e9ef",
        "bg_card": "#ffffff",
        "accent": "#e60023",       # Pinterest Red
        "accent_hover": "#ad081b",
        "text_main": "#4c4f69",
        "text_muted": "#5c5f77",   # Darker Grey for better readability
        "border": "#9ca0b0",       # Darker Grey for better visibility
        "input_bg": "#e6e9ef"      # Slightly darker input bg
    }

    def __init__(self):
        self.is_dark = True # Default to Dark Mode

    def toggle_theme(self):
        self.is_dark = not self.is_dark
        return self.is_dark

    def get_style(self):
        p = self.DARK_PALETTE if self.is_dark else self.LIGHT_PALETTE
        
        # Determine semi-transparent backgrounds based on theme
        card_bg_alpha = "rgba(255, 255, 255, 0.05)" if self.is_dark else "rgba(0, 0, 0, 0.03)"
        
        return f"""
            /* --- Global Container --- */
            QMainWindow, QWidget#MainContainer {{
                background-color: {p['bg_main']};
            }}

            QScrollArea, QScrollArea > QWidget {{
                background-color: transparent;
                border: none;
            }}
            
            QScrollArea#ContentScroll {{
                background-color: transparent;
                border: none;
            }}

            QWidget {{
                color: {p['text_main']};
                font-family: 'Segoe UI', 'Roboto', 'Arial', sans-serif;
                font-size: 13px;
                outline: none;
            }}

            /* --- Typography --- */
            QLabel#HeaderTitle {{
                font-size: 24px;
                font-weight: bold;
                color: {p['text_main']};
                margin-bottom: 10px;
            }}
            
            QLabel#SectionTitle {{
                font-size: 14px;
                font-weight: bold;
                color: {p['text_main']};
                margin-top: 10px;
                margin-bottom: 5px;
            }}
            
            QLabel#InfoLabel {{
                color: {p['text_muted']};
                font-style: italic;
                font-size: 12px;
            }}
            
            QLabel#ResultCountLabel {{
                font-weight: bold;
                font-size: 14px;
                color: {p['accent']};
            }}

            /* --- Sidebar --- */
            #Sidebar {{
                background-color: {p['bg_sidebar']};
                border-right: 1px solid {p['border']};
            }}

            /* Sidebar Buttons - Modern & Minimal */
            #Sidebar QPushButton {{
                text-align: left;
                padding: 12px 20px;
                border: none;
                border-radius: 0px 8px 8px 0px; /* One side rounded */
                margin: 4px 10px 4px 0px;
                color: {p['text_muted']};
                background-color: transparent;
                font-weight: 500;
                border-left: 4px solid transparent; /* Placeholder for indicator */
                font-size: 14px;
            }}

            #Sidebar QPushButton:hover {{
                background-color: {p['bg_card']};
                color: {p['text_main']};
            }}

            /* Active State - Vertical Indicator Line */
            #Sidebar QPushButton[active="true"] {{
                background-color: {p['bg_card']}; /* Subtle highlight */
                color: {p['accent']};
                font-weight: bold;
                border-left: 4px solid {p['accent']}; /* The Indicator */
            }}

            /* --- Metric Cards --- */
            QFrame#MetricCard {{
                background-color: {card_bg_alpha};
                border: 1px solid {p['border']};
                border-radius: 12px;
            }}
            
            QLabel[class="MetricValue"] {{
                font-size: 28px;
                font-weight: bold;
                color: {p['text_main']};
            }}
            
            QLabel[class="MetricLabel"] {{
                font-size: 11px;
                font-weight: bold;
                color: {p['text_muted']};
                text-transform: uppercase;
                letter-spacing: 1px;
            }}

            /* --- Cards (Group Boxes) --- */
            QGroupBox {{
                background-color: {p['bg_card']};
                border: 1px solid {p['border']};
                border-bottom: 2px solid {p['border']}; /* Subtle depth */
                border-radius: 12px;
                margin-top: 25px; /* Space for title */
                padding: 20px;
                font-weight: bold;
            }}

            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top center;
                top: 5px;
                color: {p['accent']};
                font-size: 11px;
                font-weight: 900;
                text-transform: uppercase;
                background-color: transparent;
                padding: 0px 5px;
            }}

            /* --- Inputs - "Flush" Look --- */
            QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDateEdit, QDateTimeEdit {{
                background-color: {p['input_bg']};
                border: 1px solid {p['border']};
                border-radius: 6px;
                padding: 10px;
                color: {p['text_main']};
                selection-background-color: {p['accent']};
                font-size: 13px;
            }}

            QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus, QDateTimeEdit:focus {{
                border: 1px solid {p['accent']}; /* Slim accent border */
                background-color: {p['bg_main']};
            }}
            
            QComboBox::drop-down {{
                border: none;
                width: 25px;
            }}

            /* --- Buttons - Premium Solid --- */
            QPushButton {{
                background-color: {p['accent']};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 24px;
                font-weight: bold;
                font-size: 13px;
                min-height: 20px;
            }}

            QPushButton:hover {{
                background-color: {p['accent_hover']};
            }}

            QPushButton:pressed {{
                background-color: {p['accent']};
                margin-top: 2px; /* Physical press feel */
            }}

            QPushButton:disabled {{
                background-color: {p['border']};
                color: {p['text_muted']};
            }}
            
            /* Secondary Action Buttons (like Refresh) */
            QPushButton#ActionBtn {{
                background-color: transparent;
                border: 1px solid {p['border']};
                color: {p['text_main']};
            }}
            
            QPushButton#ActionBtn:hover {{
                border-color: {p['text_main']};
                background-color: {p['bg_card']};
            }}

            /* Theme Toggle Exception */
            #Sidebar QPushButton#ThemeToggle {{
                background-color: rgba(0,0,0,0.05);
                color: {p['text_muted']};
                font-weight: normal;
                margin-top: 20px;
                border-left: 4px solid transparent;
            }}
            
            #Sidebar QPushButton#ThemeToggle:hover {{
                color: {p['text_main']};
                background-color: rgba(255,255,255,0.05);
            }}

            /* --- Tables - Clean & Spacious --- */
            QTableWidget {{
                background-color: {p['bg_card']};
                color: {p['text_main']};
                gridline-color: {p['border']}; /* Subtle grid lines */
                border: 1px solid {p['border']};
                border-radius: 8px;
                alternate-background-color: {p['bg_main']}; /* Alternating rows */
                selection-background-color: rgba(230, 0, 35, 0.1);
                selection-color: {p['text_main']};
            }}

            QHeaderView::section {{
                background-color: {p['bg_sidebar']};
                color: {p['text_muted']};
                padding: 12px;
                border: none;
                border-bottom: 2px solid {p['border']};
                border-right: 1px solid {p['border']};
                font-weight: bold;
                font-size: 11px;
                text-transform: uppercase;
            }}

            QTableWidget::item {{
                padding: 10px;
                border-bottom: 1px solid {p['border']};
            }}

            /* --- Tabs & Scrollbars --- */
            QTabWidget::pane {{
                border: 1px solid {p['border']};
                border-radius: 8px;
                background-color: {p['bg_card']};
                margin-top: -1px; /* Overlap tab bar border */
            }}

            QTabBar::tab {{
                background-color: transparent;
                color: {p['text_muted']};
                padding: 12px 24px;
                font-weight: bold;
                border-bottom: 3px solid transparent;
                margin-right: 5px;
            }}
            
            QTabBar::tab:hover {{
                color: {p['text_main']};
            }}

            QTabBar::tab:selected {{
                color: {p['accent']};
                border-bottom: 3px solid {p['accent']};
            }}

            QScrollBar:vertical {{
                border: none;
                background: {p['bg_main']};
                width: 10px;
                margin: 0;
            }}

            QScrollBar::handle:vertical {{
                background: {p['border']};
                min-height: 20px;
                border-radius: 5px;
                margin: 2px;
            }}
            
            QScrollBar::handle:vertical:hover {{
                background: {p['text_muted']};
            }}
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            
            /* --- Miscellaneous --- */
            QProgressBar {{
                border: 1px solid {p['border']};
                border-radius: 5px;
                text-align: center;
                background-color: {p['input_bg']};
            }}
            
            QProgressBar::chunk {{
                background-color: {p['accent']};
                border-radius: 4px;
            }}
            
            QCheckBox {{
                spacing: 8px;
                color: {p['text_main']};
            }}
            
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 1px solid {p['border']};
                border-radius: 4px;
                background-color: {p['input_bg']};
            }}
            
            QCheckBox::indicator:checked {{
                background-color: {p['accent']};
                border-color: {p['accent']};
                /* Add a checkmark image if possible, or just solid color for now */
            }}
            
            QRadioButton {{
                spacing: 8px;
                color: {p['text_main']};
            }}
            
            QRadioButton::indicator {{
                width: 18px;
                height: 18px;
                border: 1px solid {p['border']};
                border-radius: 10px;
                background-color: {p['input_bg']};
            }}
            
            QRadioButton::indicator:checked {{
                background-color: {p['accent']};
                border-color: {p['accent']};
            }}
        """
