import json
from src.database import get_db_connection

class SettingsManager:
    def __init__(self):
        self.defaults = {
            # General
            "skip_followed": True,
            "skip_pinned": True,
            "skip_own_pins": False,
            "skip_videos": False,
            "skip_products": True,
            "skip_links_desc": False,
            "skip_links_pin": False,
            "skip_invited": True,
            "one_comment_per_user": False,
            "randomize_uploads": False,
            
            # Filters
            "filter_followers_enabled": False,
            "filter_followers_min": 0,
            "filter_followers_max": 1000000,
            "filter_following_enabled": False,
            "filter_following_min": 0,
            "filter_following_max": 1000000,
            
            # Time Delay
            "delay_min": 5,
            "delay_max": 15,
            "take_breaks": False,
            "break_after": 100,
            "break_min": 10,
            "break_max": 20,
            
            # Proxy
            "use_proxy": False,
            "proxy_host": "",
            "proxy_port": "",
            "proxy_user": "",
            "proxy_pass": "",
            
            # Rotation
            "rotation_enabled": False,
            "rotation_limit": 10,
            
            # Safety / Warmup
            "warmup_enabled": False,
            "warmup_duration": 10,
            
            # DM / Relationship Builder
            "dm_templates": {
                "follow": "Hi {username}, thanks for the follow! I love your boards...",
                "save": "Hey {username}, saw you saved my pin! Glad you liked it...",
                "like": "Hi {username}, thanks for liking my content!"
            },
            "dm_safety": {
                "limit": 5,
                "min_delay": 30,
                "max_delay": 60
            }
        }

    def get_setting(self, key):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            try:
                return json.loads(row['value'])
            except:
                return row['value']
        return self.defaults.get(key)

    def set_setting(self, key, value):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", 
                       (key, json.dumps(value)))
        conn.commit()
        conn.close()

    def get_all_settings(self):
        settings = self.defaults.copy()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM settings")
        rows = cursor.fetchall()
        conn.close()
        
        for row in rows:
            try:
                settings[row['key']] = json.loads(row['value'])
            except:
                settings[row['key']] = row['value']
        return settings
