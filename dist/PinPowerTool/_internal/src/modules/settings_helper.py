"""
Settings helper module for automation.
Provides centralized access to settings and validation methods.
"""

from src.modules.settings_manager import SettingsManager
import random
import re


class AutomationSettings:
    """Central settings management for all automations."""
    
    def __init__(self):
        self.settings_manager = SettingsManager()
        self.settings = self.settings_manager.get_all_settings()
        self._action_count = 0
        self._break_count = 0
    
    def reload_settings(self):
        """Reload settings from database."""
        self.settings = self.settings_manager.get_all_settings()
    
    # ==================== User Filters ====================
    
    def should_skip_user(self, user_data):
        """
        Check if user should be skipped based on filter settings.
        
        Args:
            user_data (dict): User data with keys: followers, following, pins
            
        Returns:
            tuple: (should_skip: bool, reason: str)
        """
        # Check followers filter
        followers_mode = self.settings.get("filter_followers_mode", 0)
        if followers_mode != 0:  # 0 = Filter Off
            threshold = int(self.settings.get("filter_followers_val", 0) or 0)
            followers = user_data.get('followers', 0)
            
            if followers_mode == 1 and followers >= threshold:  # Less than
                return True, f"Followers {followers} >= {threshold}"
            elif followers_mode == 2 and followers <= threshold:  # More than
                return True, f"Followers {followers} <= {threshold}"
        
        # Check following filter
        following_mode = self.settings.get("filter_following_mode", 0)
        if following_mode != 0:
            threshold = int(self.settings.get("filter_following_val", 0) or 0)
            following = user_data.get('following', 0)
            
            if following_mode == 1 and following >= threshold:
                return True, f"Following {following} >= {threshold}"
            elif following_mode == 2 and following <= threshold:
                return True, f"Following {following} <= {threshold}"
        
        # Check pins filter
        pins_mode = self.settings.get("filter_user_pins_mode", 0)
        if pins_mode != 0:
            threshold = int(self.settings.get("filter_user_pins_val", 0) or 0)
            pins = user_data.get('pins', 0)
            
            if pins_mode == 1 and pins >= threshold:
                return True, f"Pins {pins} >= {threshold}"
            elif pins_mode == 2 and pins <= threshold:
                return True, f"Pins {pins} <= {threshold}"
        
        return False, ""
    
    # ==================== Pin Filters ====================
    
    def should_skip_pin(self, pin_data, current_account_username=None):
        """
        Check if pin should be skipped based on filter and skip settings.
        
        Args:
            pin_data (dict): Pin data with keys: repins, description, author, is_video, etc.
            current_account_username (str): Current logged-in account username
            
        Returns:
            tuple: (should_skip: bool, reason: str)
        """
        # Check repins filter
        repins_mode = self.settings.get("filter_repins_mode", 0)
        if repins_mode != 0:
            threshold = int(self.settings.get("filter_repins_val", 0) or 0)
            repins = pin_data.get('repins', 0)
            
            if repins_mode == 1 and repins >= threshold:
                return True, f"Repins {repins} >= {threshold}"
            elif repins_mode == 2 and repins <= threshold:
                return True, f"Repins {repins} <= {threshold}"
        
        # Check keywords filter
        keywords_mode = self.settings.get("filter_keywords_mode", 0)
        if keywords_mode == 1:  # Filter On
            keywords_str = self.settings.get("filter_keywords_val", "")
            if keywords_str:
                keywords = [k.strip().lower() for k in keywords_str.split(",")]
                description = (pin_data.get('description', '') or '').lower()
                title = (pin_data.get('title', '') or '').lower()
                
                for keyword in keywords:
                    if keyword and (keyword in description or keyword in title):
                        return True, f"Contains keyword: {keyword}"
        
        # Check skip own pins
        if self.settings.get("skip_own_pins", False):
            author = pin_data.get('author', '')
            if current_account_username and author.lower() == current_account_username.lower():
                return True, "Own pin"
        
        # Check skip videos
        if self.settings.get("skip_videos", False):
            if pin_data.get('is_video', False):
                return True, "Video pin"
        
        # Check skip products
        if self.settings.get("skip_products", False):
            if pin_data.get('is_product', False):
                return True, "Product pin"
        
        # Check skip pins with links in description
        if self.settings.get("skip_links_desc", False):
            description = pin_data.get('description', '') or ''
            if self._has_url(description):
                return True, "Link in description"
        
        # Check skip pins with destination link
        if self.settings.get("skip_links_pin", False):
            if pin_data.get('has_link', False):
                return True, "Has destination link"
        
        return False, ""
    
    def _has_url(self, text):
        """Check if text contains a URL."""
        url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        return bool(re.search(url_pattern, text))
    
    # ==================== Skip Settings ====================
    
    def should_skip_followed(self):
        """Check if 'skip followed users' setting is enabled."""
        return self.settings.get("skip_followed", True)
    
    def should_skip_pinned(self):
        """Check if 'skip repinned pins' setting is enabled."""
        return self.settings.get("skip_pinned", True)
    
    def is_pin_repinned(self, account_id, pin_url, days=30):
        """Check database if pin was repinned by this account recently."""
        if not self.should_skip_pinned():
            return False
            
        from src.database import get_db_connection
        from datetime import datetime, timedelta
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute("""
            SELECT COUNT(*) FROM repin_history 
            WHERE account_id = ? AND pin_url = ? AND repinned_date > ?
        """, (account_id, pin_url, cutoff_date))
        
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0

    def is_user_followed(self, account_id, user_url):
        """Check database if user was followed by this account."""
        if not self.should_skip_followed():
            return False
            
        from src.database import get_db_connection
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) FROM followed_users 
            WHERE account_id = ? AND user_url = ?
        """, (account_id, user_url))
        
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    
    # ==================== Delay & Break Management ====================
    
    def get_random_delay(self):
        """
        Get a random delay between min and max settings.
        
        Returns:
            int: Delay in seconds
        """
        min_delay = self.settings.get("delay_min", 5)
        max_delay = self.settings.get("delay_max", 15)
        
        # Ensure min <= max
        if min_delay > max_delay:
            min_delay, max_delay = max_delay, min_delay
        
        return random.randint(min_delay, max_delay)
    
    def should_take_break(self, action_count=None):
        """
        Check if a break should be taken based on settings.
        
        Args:
            action_count (int): Number of actions performed (optional, uses internal counter if None)
            
        Returns:
            tuple: (should_break: bool, duration_seconds: int)
        """
        if not self.settings.get("take_breaks", False):
            return False, 0
        
        # Use provided count or internal counter
        count = action_count if action_count is not None else self._action_count
        
        # TODO: Add break interval settings to UI
        # For now, use hardcoded values: break after every 50 actions for 60-120 seconds
        break_interval = 50
        break_min = 60
        break_max = 120
        
        if count > 0 and count % break_interval == 0:
            duration = random.randint(break_min, break_max)
            self._break_count += 1
            return True, duration
        
        return False, 0
    
    def increment_action_count(self):
        """Increment internal action counter."""
        self._action_count += 1
    
    def reset_action_count(self):
        """Reset internal action counter."""
        self._action_count = 0
        self._break_count = 0
        
    def get_proxy_config(self, account_proxy=None):
        """
        Get proxy configuration prioritizing global settings.
        
        Args:
            account_proxy (str): Proxy string from account DB (optional)
            
        Returns:
            dict: Playwright proxy config or None
        """
        # 1. Global Proxy
        if self.settings.get("use_proxy", False):
            host = self.settings.get("proxy_host", "").strip()
            port = self.settings.get("proxy_port", "").strip()
            user = self.settings.get("proxy_user", "").strip()
            pwd = self.settings.get("proxy_pass", "").strip()
            
            if host and port:
                proxy_dict = {'server': f"http://{host}:{port}"}
                if user and pwd:
                    proxy_dict['username'] = user
                    proxy_dict['password'] = pwd
                print(f"DEBUG: Using Global Proxy: {host}:{port}")
                return proxy_dict
        
        # 2. Account Proxy
        if account_proxy:
            p_str = account_proxy.strip().replace('http://', '').replace('https://', '')
            parts = p_str.split(':')
            if len(parts) >= 2:
                proxy_dict = {'server': f"http://{parts[0]}:{parts[1]}"}
                if len(parts) >= 4:
                    proxy_dict['username'] = parts[2]
                    proxy_dict['password'] = parts[3]
                print(f"DEBUG: Using Account Proxy: {parts[0]}:***")
                return proxy_dict
                
        return None
    
    # ==================== Helper Methods ====================
    
    def apply_filters_to_users(self, users_list, automation=None):
        """
        Apply user filters to a list of users.
        
        Args:
            users_list (list): List of user dicts or URLs (strings)
            automation (PinterestAutomation): Automation instance for fetching details (optional)
            
        Returns:
            list: Filtered list of users (as dicts)
        """
        filtered = []
        
        # Check if any filters are active that require detailed user data
        needs_details = (
            self.settings.get("filter_followers_mode", 0) != 0 or
            self.settings.get("filter_following_mode", 0) != 0 or
            self.settings.get("filter_user_pins_mode", 0) != 0
        )
        
        # Convert all string URLs to dicts
        user_dicts = []
        for user in users_list:
            if isinstance(user, str):
                user_dicts.append({'url': user, 'user_url': user})
            else:
                user_dicts.append(user)
        
        # If filters are active, fetch details in batch
        if needs_details and automation:
            # Find users that need details
            users_needing_details = []
            users_with_details = []
            
            for user in user_dicts:
                if 'followers' not in user or user.get('followers') is None:
                    users_needing_details.append(user)
                else:
                    users_with_details.append(user)
            
            # Fetch details in batch (parallel processing)
            if users_needing_details:
                print(f"Fetching details for {len(users_needing_details)} users using batch processing...")
                urls_to_fetch = [u.get('url') or u.get('user_url') for u in users_needing_details]
                
                try:
                    # Use batch processing with 5 tabs at a time
                    batch_results = automation.batch_get_user_details(urls_to_fetch, batch_size=5)
                    
                    # Create a lookup dict by URL
                    details_by_url = {r['url']: r for r in batch_results}
                    
                    # Update users with fetched details
                    for user in users_needing_details:
                        user_url = user.get('url') or user.get('user_url')
                        if user_url in details_by_url:
                            user.update(details_by_url[user_url])
                except Exception as e:
                    print(f"Error in batch user details fetch: {e}")
            
            # Combine back the users
            user_dicts = users_with_details + users_needing_details
        
        # Now apply filters
        for user in user_dicts:
            should_skip, reason = self.should_skip_user(user)
            if not should_skip:
                filtered.append(user)
        
        return filtered
    
    def apply_filters_to_pins(self, pins_list, current_account_username=None, automation=None, should_stop=None):
        """
        Apply pin filters to a list of pins.
        
        Args:
            pins_list (list): List of pin dicts or URLs
            current_account_username (str): Current account username
            automation (PinterestAutomation): Automation instance for fetching details
            should_stop (callable): Check if should stop
            
        Returns:
            list: Filtered list of pins
        """
        filtered = []
        
        # Convert strings to dicts
        pin_dicts = []
        for pin in pins_list:
            if isinstance(pin, str):
                pin_dicts.append({'url': pin})
            else:
                pin_dicts.append(pin)
                
        # Check if we need to fetch details
        # We only fetch if automation is available AND filters that require details are enabled
        needs_details = False
        if automation:
            # Check if any filter requiring details is active
            if (self.settings.get("filter_repins_mode", 0) != 0 or
                self.settings.get("filter_keywords_mode", 0) == 1 or
                self.settings.get("skip_own_pins", False) or
                self.settings.get("skip_videos", False) or
                self.settings.get("skip_products", False) or
                self.settings.get("skip_links_desc", False) or
                self.settings.get("skip_links_pin", False)):
                needs_details = True
        
        if automation and needs_details:
            pins_needing_details = []
            for pin in pin_dicts:
                if 'is_video' not in pin:
                    pins_needing_details.append(pin)
            
            if pins_needing_details:
                print(f"Fetching details for {len(pins_needing_details)} pins (Filters enabled)...")
                urls = [p['url'] for p in pins_needing_details]
                try:
                    batch_data = automation.batch_get_pin_details(urls, batch_size=5, should_stop=should_stop)
                    data_map = {d['url']: d for d in batch_data}
                    
                    for pin in pins_needing_details:
                        if pin['url'] in data_map:
                            pin.update(data_map[pin['url']])
                except Exception as e:
                    print(f"Error in batch pin details: {e}")
            
            if should_stop and should_stop():
                return []

        for pin in pin_dicts:
            if should_stop and should_stop():
                break
            should_skip, reason = self.should_skip_pin(pin, current_account_username)
            if not should_skip:
                filtered.append(pin)
        
        return filtered
    
    def get_filter_summary(self):
        """
        Get a summary of active filters.
        
        Returns:
            str: Human-readable filter summary
        """
        active_filters = []
        
        # User filters
        if self.settings.get("filter_followers_mode", 0) != 0:
            mode = "Less than" if self.settings.get("filter_followers_mode") == 1 else "More than"
            val = self.settings.get("filter_followers_val", "")
            active_filters.append(f"Followers: {mode} {val}")
        
        if self.settings.get("filter_following_mode", 0) != 0:
            mode = "Less than" if self.settings.get("filter_following_mode") == 1 else "More than"
            val = self.settings.get("filter_following_val", "")
            active_filters.append(f"Following: {mode} {val}")
        
        if self.settings.get("filter_user_pins_mode", 0) != 0:
            mode = "Less than" if self.settings.get("filter_user_pins_mode") == 1 else "More than"
            val = self.settings.get("filter_user_pins_val", "")
            active_filters.append(f"User Pins: {mode} {val}")
        
        # Pin filters
        if self.settings.get("filter_repins_mode", 0) != 0:
            mode = "Less than" if self.settings.get("filter_repins_mode") == 1 else "More than"
            val = self.settings.get("filter_repins_val", "")
            active_filters.append(f"Repins: {mode} {val}")
        
        if self.settings.get("filter_keywords_mode", 0) == 1:
            keywords = self.settings.get("filter_keywords_val", "")
            if keywords:
                active_filters.append(f"Keywords: {keywords}")
        
        # Skip settings
        skip_settings = []
        if self.settings.get("skip_own_pins", False): skip_settings.append("own pins")
        if self.settings.get("skip_videos", False): skip_settings.append("videos")
        if self.settings.get("skip_products", False): skip_settings.append("products")
        if self.settings.get("skip_links_desc", False): skip_settings.append("links in desc")
        if self.settings.get("skip_links_pin", False): skip_settings.append("pins with links")
        
        if skip_settings:
            active_filters.append(f"Skip: {', '.join(skip_settings)}")
        
        if not active_filters:
            return "No active filters"
        
        return "; ".join(active_filters)
