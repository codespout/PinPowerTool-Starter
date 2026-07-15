import os
import sys

def get_app_data_dir():
    """Returns the application data directory where user files (db, config) should be saved."""
    if sys.platform == 'win32':
        app_data = os.environ.get('APPDATA')
        if app_data:
            path = os.path.join(app_data, 'PinPowerTool')
            os.makedirs(path, exist_ok=True)
            return path
            
    # Fallback to user home folder (.pinpowertool) or execution directory
    fallback = os.path.join(os.path.expanduser("~"), ".pinpowertool")
    os.makedirs(fallback, exist_ok=True)
    return fallback

def get_db_path():
    """Returns the path to the sqlite database file."""
    return os.path.join(get_app_data_dir(), 'pinpower.db')

def get_config_path():
    """Returns the path to the config.json file."""
    return os.path.join(get_app_data_dir(), 'config.json')
