from src.modules.settings_manager import SettingsManager

class FilterModule:
    def __init__(self):
        self.settings_manager = SettingsManager()
        self.reload_settings()

    def reload_settings(self):
        self.settings = self.settings_manager.get_all_settings()

    def check_user(self, user_details):
        """Check if user meets filter criteria."""
        if not user_details:
            return False
            
        # Helper to check numeric filter
        def check_numeric(prefix, actual_value):
            mode = self.settings.get(f"filter_{prefix}_mode", 0) # 0=Off, 1=Less, 2=More
            if mode == 0:
                return True
            
            try:
                target_val = float(self.settings.get(f"filter_{prefix}_val", 0))
            except:
                return True # Invalid setting, ignore
                
            if mode == 1: # Less than
                return actual_value < target_val
            elif mode == 2: # More than
                return actual_value > target_val
            return True

        if not check_numeric("followers", user_details.get('followers', 0)):
            return False
            
        if not check_numeric("following", user_details.get('following', 0)):
            return False
            
        if not check_numeric("user_pins", user_details.get('pins', 0)):
            return False
            
        return True

    def check_pin(self, pin_details):
        """Check if pin meets filter criteria."""
        if not pin_details:
            return False
            
        # Repins
        mode = self.settings.get("filter_repins_mode", 0)
        if mode != 0:
            try:
                target = float(self.settings.get("filter_repins_val", 0))
                actual = pin_details.get('repins', 0)
                if mode == 1 and not (actual < target): return False
                if mode == 2 and not (actual > target): return False
            except:
                pass
                
        # Keywords
        kw_mode = self.settings.get("filter_keywords_mode", 0)
        if kw_mode == 1: # On
            keywords_str = self.settings.get("filter_keywords_val", "")
            keywords = [k.strip().lower() for k in keywords_str.split(',') if k.strip()]
            
            description = pin_details.get('description', '').lower()
            title = pin_details.get('title', '').lower()
            
            for kw in keywords:
                if kw in description or kw in title:
                    return False # Ignore if keyword found
                    
        return True
