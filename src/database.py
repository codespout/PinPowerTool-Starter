import sqlite3
import os
from src.utils.paths import get_db_path

DB_NAME = get_db_path()

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def create_tables():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Accounts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            proxy TEXT,
            status TEXT DEFAULT 'Inactive',
            cookies TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            account_type TEXT DEFAULT 'Personal',
            is_selected BOOLEAN DEFAULT 0,
            name TEXT
        )
    ''')
    
    # Settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # Action History table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS action_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER,
            action_type TEXT,
            target_id TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES accounts (id)
        )
    ''')
    
    # Gathered Pins table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gathered_pins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pin_url TEXT UNIQUE NOT NULL,
            gathered_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            source TEXT
        )
    ''')
    
    # Gathered Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gathered_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_url TEXT UNIQUE NOT NULL,
            username TEXT,
            gathered_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            source TEXT
        )
    ''')
    
    # Followed Users table (for tracking follows/unfollows)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS followed_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER,
            user_url TEXT NOT NULL,
            username TEXT,
            followed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_following_back BOOLEAN DEFAULT 0,
            FOREIGN KEY (account_id) REFERENCES accounts (id),
            UNIQUE(account_id, user_url)
        )
    ''')
    
    # Repin History table (for duplicate repin prevention)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS repin_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER,
            pin_url TEXT NOT NULL,
            board_name TEXT,
            repinned_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES accounts (id),
            UNIQUE(account_id, pin_url)
        )
    ''')
    
    # Commented Pins table (for duplicate prevention)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS commented_pins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER,
            pin_url TEXT,
            pin_owner TEXT,
            comment_text TEXT,
            commented_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES accounts (id)
        )
    ''')
    
    # Comment Templates table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS comment_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            comment_text TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1
        )
    ''')
    
    # Insert default templates if empty
    cursor.execute("SELECT COUNT(*) FROM comment_templates")
    count = cursor.fetchone()[0]
    if count == 0:
        default_comments = [
            "Love this! 😍",
            "Great pin! Thanks for sharing",
            "So inspiring! ✨",
            "Beautiful work! 💖",
            "Amazing! 👏",
            "This is perfect! 🌟",
            "Wonderful idea!",
            "Absolutely gorgeous! 😊"
        ]
        for comment in default_comments:
            cursor.execute("INSERT INTO comment_templates (comment_text) VALUES (?)", (comment,))
            
    # Board Invites table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS board_invites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            board_url TEXT,
            user_url TEXT,
            invited_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Scheduler Queue table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scheduled_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER,
            action_type TEXT,        -- 'repin', 'upload', 'comment', 'follow'
            target_data TEXT,        -- JSON: {board, pin_url, image_path, etc.}
            scheduled_time TIMESTAMP, -- When it should run
            status TEXT DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed', 'cancelled'
            log_output TEXT,         -- Result message
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Migration: Add new columns if they don't exist (for existing DBs)
    try:
        cursor.execute("ALTER TABLE accounts ADD COLUMN account_type TEXT DEFAULT 'Personal'")
    except sqlite3.OperationalError:
        pass # Column likely exists
        
    try:
        cursor.execute("ALTER TABLE accounts ADD COLUMN is_selected BOOLEAN DEFAULT 0")
    except sqlite3.OperationalError:
        pass
        
    try:
        cursor.execute("ALTER TABLE accounts ADD COLUMN name TEXT")
    except sqlite3.OperationalError:
        pass

    # Migration: Add account_id to existing action tables
    try:
        cursor.execute("ALTER TABLE followed_users ADD COLUMN account_id INTEGER")
    except sqlite3.OperationalError:
        pass
        
    try:
        cursor.execute("ALTER TABLE commented_pins ADD COLUMN account_id INTEGER")
    except sqlite3.OperationalError:
        pass
        
    try:
        cursor.execute("ALTER TABLE board_invites ADD COLUMN account_id INTEGER")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE accounts ADD COLUMN boards TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE gathered_pins ADD COLUMN is_trending BOOLEAN DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    # Sent DMs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sent_dms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER,
            receiver_url TEXT,
            interaction_type TEXT,
            message TEXT,
            sent_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Repurposed Videos Library
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS repurposed_videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_url TEXT UNIQUE,
            file_path TEXT,
            platform TEXT,
            title TEXT,
            duration INTEGER,
            thumbnail_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Database initialized.")
