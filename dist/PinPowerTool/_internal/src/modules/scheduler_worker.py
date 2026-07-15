from PySide6.QtCore import QThread, Signal as pyqtSignal
from src.database import get_db_connection
from src.modules.actions import PinterestAutomation
import time
import json
from datetime import datetime, timedelta
import random

class SchedulerWorker(QThread):
    """Background worker that executes scheduled tasks from the database."""
    
    log_signal = pyqtSignal(str)
    task_executed = pyqtSignal(int, str)  # task_id, status
    
    def __init__(self):
        super().__init__()
        self.is_running = True
        self.check_interval = 60  # Check every 60 seconds
        from src.modules.automation_manager import AutomationManager
        self.manager = AutomationManager()
        self.current_action_type = None
        
    def run(self):
        """Main loop that checks for and executes pending tasks."""
        self.log("✓ Scheduler Worker started")
        
        while self.is_running:
            try:
                self.check_and_execute_tasks()
            except Exception as e:
                self.log(f"Scheduler error: {e}")
                import traceback
                traceback.print_exc()
            
            # Sleep in smaller intervals for better responsiveness to stop signal
            for _ in range(self.check_interval):
                if not self.is_running:
                    break
                time.sleep(1)
        
        self.log("✓ Scheduler Worker stopped")
    
    def check_and_execute_tasks(self):
        """Check database for pending tasks that are due."""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get all pending tasks whose time has arrived
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("""
            SELECT s.*, a.email, a.password, a.cookies, a.proxy, a.id as account_id
            FROM scheduled_actions s
            LEFT JOIN accounts a ON s.account_id = a.id
            WHERE s.status = 'pending' AND s.scheduled_time <= ?
            ORDER BY s.scheduled_time ASC
            LIMIT 5
        """, (now,))
        
        tasks = cursor.fetchall()
        conn.close()
        
        if not tasks:
            return
        
        self.log(f"📋 Found {len(tasks)} task(s) ready to execute")
        
        for task in tasks:
            if not self.is_running:
                break
            
            self.execute_task(task)
    
    def execute_task(self, task):
        """Execute a single scheduled task."""
        task_id = task['id']
        account_email = task['email']
        action_type = task['action_type']
        self.current_action_type = action_type
        
        self.log(f"▶ Executing Task #{task_id}: {action_type} for {account_email}")
        
        # Mark as processing
        self.update_task_status(task_id, 'processing', None)
        
        try:
            # Parse target data
            target_data = json.loads(task['target_data'])
            
            # Setup browser automation
            cookies = None
            if task['cookies']:
                try:
                    cookies = json.loads(task['cookies'])
                except:
                    pass
            
            # Parse proxy
            proxy_dict = None
            if task['proxy']:
                parts = task['proxy'].split(':')
                if len(parts) >= 2:
                    proxy_dict = {'server': f"http://{parts[0]}:{parts[1]}"}
                    if len(parts) >= 4:
                        proxy_dict['username'] = parts[2]
                        proxy_dict['password'] = parts[3]
            
            automation = PinterestAutomation(headless=False, proxy=proxy_dict)
            
            if not automation.start_browser(cookies=cookies):
                raise Exception("Failed to start browser")
            
            # Ensure logged in
            if not automation.ensure_logged_in(task['email'], task['password']):
                raise Exception("Login failed")
            
            # Execute based on action type
            result = self.execute_action(automation, action_type, target_data, task['account_id'])
            
            automation.stop_browser()
            
            if result:
                self.update_task_status(task_id, 'completed', f"✓ Executed successfully")
                self.log(f"  ✓ Task #{task_id} completed")
            else:
                self.update_task_status(task_id, 'failed', "Action returned False")
                self.log(f"  ✗ Task #{task_id} failed")
                
        except Exception as e:
            error_msg = str(e)
            self.update_task_status(task_id, 'failed', error_msg)
            self.log(f"  ✗ Task #{task_id} error: {error_msg}")
        finally:
            self.current_action_type = None
    
    def execute_action(self, automation, action_type, data, account_id):
        """Execute the specific automation action with smart skip support."""
        from src.modules.settings_helper import AutomationSettings
        auto_settings = AutomationSettings()
        
        try:
            if action_type == 'repin':
                # Fetch pins from database and repin
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT pin_url FROM gathered_pins LIMIT ?", (data.get('limit', 10) * 10,))
                pins = cursor.fetchall()
                conn.close()
                
                if not pins:
                    self.log("  ⚠ No gathered pins found in database")
                    return False
                
                self.log(f"  → Found {len(pins)} pins, limit {data.get('limit', 10)}")
                processed = 0
                for pin in pins:
                    if not self.is_running or processed >= data.get('limit', 10):
                        break
                    
                    pin_url = pin['pin_url']
                    self.log(f"  [{processed+1}/{data.get('limit', 10)}] Repinning: {pin_url}")
                    
                    # Define skip check callback for DB fallback
                    def db_skip_check(url):
                        return auto_settings.is_pin_repinned(account_id, url)
                    
                    result = automation.repin_pin(pin_url, data['board_name'], data.get('auto_like', False), skip_check=db_skip_check)
                    
                    success = False
                    msg = ""
                    if isinstance(result, tuple):
                        success, msg = result
                    else:
                        success = result
                        msg = "Repinned successfully" if success else "Failed to repin"

                    if success:
                        if "Already" not in msg:
                            processed += 1
                        self.log(f"  ✓ {msg}")
                        # Save to history if not skipped by DB already
                        if "DB" not in msg:
                            try:
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                cursor.execute("INSERT OR IGNORE INTO repin_history (account_id, pin_url, board_name) VALUES (?, ?, ?)",
                                             (account_id, pin_url, data['board_name']))
                                conn.commit()
                                conn.close()
                            except: pass
                    else:
                        self.log(f"  ✗ {msg}")
                        
                    if processed < data.get('limit', 10):
                        time.sleep(auto_settings.get_random_delay())
                
                return processed > 0
                
            elif action_type == 'upload':
                # Upload pins from file list
                image_files = data.get('image_files', [])
                if not image_files:
                    self.log("  ⚠ No image files provided")
                    return False
                
                processed = 0
                limit = data.get('limit', 10)
                self.log(f"  → Uploading {min(len(image_files), limit)} images")
                
                for img_path in image_files[:limit]:
                    if not self.is_running:
                        break
                        
                    import os
                    if not os.path.exists(img_path):
                        self.log(f"  ⚠ File not found: {img_path}")
                        continue
                    
                    filename = os.path.basename(img_path)
                    filename_no_ext = os.path.splitext(filename)[0]
                    
                    title = data.get('title_tmpl', '').replace('{filename}', filename_no_ext) or filename_no_ext
                    desc = data.get('desc_tmpl', '').replace('{filename}', filename_no_ext)
                    link = data.get('link_tmpl', '').replace('{filename}', filename_no_ext)
                    
                    self.log(f"  [{processed+1}/{limit}] Uploading: {filename}")
                    result = automation.upload_pin(
                        img_path,
                        data['board_name'],
                        title,
                        desc,
                        link,
                        data.get('tags', '')
                    )
                    
                    if result:
                        processed += 1
                        self.log(f"  ✓ Uploaded successfully")
                    else:
                        self.log(f"  ✗ Failed to upload")
                        
                    if processed < limit:
                        time.sleep(10)
                
                return processed > 0
            
            elif action_type == 'comment':
                # Comment on gathered pins
                import random
                conn = get_db_connection()
                cursor = conn.cursor()
                
                # Load comment templates
                cursor.execute("SELECT comment_text FROM comment_templates WHERE is_active = 1")
                templates = cursor.fetchall()
                
                if not templates:
                    self.log("  ⚠ No active comment templates found")
                    conn.close()
                    return False
                
                comment_texts = [t['comment_text'] for t in templates]
                
                # Fetch pins to comment on
                cursor.execute("SELECT pin_url FROM gathered_pins LIMIT ?", (data.get('limit', 10) * 2,))
                pins_to_check = cursor.fetchall()
                conn.close()
                
                if not pins_to_check:
                    self.log("  ⚠ No gathered pins found")
                    return False
                
                limit = data.get('limit', 10)
                processed = 0
                for pin in pins_to_check:
                    if not self.is_running or processed >= limit:
                        break
                    
                    pin_url = pin['pin_url']
                    
                    # Check if we commented on this user recently (Account specific)
                    # We need the pin owner for this
                    pin_data = automation.get_pin_data(pin_url)
                    if not pin_data:
                        continue
                        
                    pin_owner = pin_data.get('author')
                    if pin_owner:
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        # Use 30 days default or data.get('skip_recent_days')
                        skip_days = data.get('skip_recent_days', 30)
                        cutoff = (datetime.now() - timedelta(days=skip_days)).strftime('%Y-%m-%d %H:%M:%S')
                        cursor.execute(
                            "SELECT COUNT(*) FROM commented_pins WHERE account_id = ? AND pin_owner = ? AND commented_date > ?",
                            (account_id, pin_owner, cutoff)
                        )
                        if cursor.fetchone()[0] > 0:
                            self.log(f"  ⊘ Skipping {pin_owner} (already commented recently)")
                            conn.close()
                            continue
                        conn.close()

                    comment = random.choice(comment_texts)
                    self.log(f"  [{processed+1}/{limit}] Commenting: {pin_url}")
                    result = automation.comment_on_pin(pin_url, comment)
                    
                    if result:
                        processed += 1
                        self.log(f"  ✓ Commented successfully")
                        # Save to commented_pins table
                        try:
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            cursor.execute(
                                "INSERT INTO commented_pins (account_id, pin_url, pin_owner, comment_text, commented_date) VALUES (?, ?, ?, ?, ?)",
                                (account_id, pin_url, pin_owner, comment, datetime.now())
                            )
                            conn.commit()
                            conn.close()
                        except: pass
                        
                        # Follow after comment if enabled
                        if data.get('follow_after_comment', False) and pin_owner:
                            self.log(f"  → Following pin owner...")
                            user_url = f"https://www.pinterest.com/{pin_owner}/"
                            # Smart Follow
                            def follow_db_check(url):
                                return auto_settings.is_user_followed(account_id, url)
                            automation.follow_user(user_url, skip_check=follow_db_check)
                            
                    else:
                        self.log(f"  ✗ Failed to comment")
                    
                    if processed < limit:
                        time.sleep(auto_settings.get_random_delay())
                
                return processed > 0
            
            elif action_type == 'follow':
                # Follow or unfollow users
                mode = data.get('mode', 'follow')
                
                if mode == 'follow':
                    # Fetch users to follow from gathered database
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT user_url, username FROM gathered_users LIMIT ?", (data.get('limit', 10) * 10,))
                    users_to_check = cursor.fetchall()
                    conn.close()
                    
                    if not users_to_check:
                        self.log("  ⚠ No gathered users found")
                        return False
                    
                    limit = data.get('limit', 10)
                    processed = 0
                    for user in users_to_check:
                        if not self.is_running or processed >= limit:
                            break
                        
                        user_url = user['user_url']
                        username = user['username'] or user_url
                        self.log(f"  [{processed+1}/{limit}] Following: {username}")
                        
                        # Define skip check callback
                        def db_skip_check(url):
                            return auto_settings.is_user_followed(account_id, url)
                            
                        result = automation.follow_user(user_url, skip_check=db_skip_check)
                        
                        success = False
                        msg = ""
                        if isinstance(result, tuple):
                            success, msg = result
                        else:
                            success = result
                            msg = "Following successfully" if success else "Failed to follow"

                        if success:
                            if "Already" not in msg:
                                processed += 1
                            self.log(f"  ✓ {msg}")
                            # Save to followed_users table
                            if "DB" not in msg:
                                try:
                                    conn = get_db_connection()
                                    cursor = conn.cursor()
                                    cursor.execute(
                                        "INSERT OR IGNORE INTO followed_users (account_id, user_url, username, followed_date) VALUES (?, ?, ?, ?)",
                                        (account_id, user_url, user['username'], datetime.now())
                                    )
                                    conn.commit()
                                    conn.close()
                                except: pass
                        else:
                            self.log(f"  ✗ {msg}")
                        
                        if processed < limit:
                            time.sleep(auto_settings.get_random_delay())
                    
                    return processed > 0
                
                else:  # unfollow mode
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT user_url, username FROM followed_users LIMIT ?", (data.get('limit', 10),))
                    users = cursor.fetchall()
                    conn.close()
                    
                    if not users:
                        self.log("  ⚠ No followed users found to unfollow")
                        return False
                    
                    limit = data.get('limit', 10)
                    self.log(f"  → Found {len(users)} users to unfollow, limit {limit}")
                    processed = 0
                    unfollow_options = data.get('unfollow_options', {})
                    
                    for user in users:
                        if not self.is_running or processed >= limit:
                            break
                        
                        username = user['username'] or user['user_url']
                        # Check if following back if option enabled
                        if unfollow_options.get('only_not_following_back'):
                            try:
                                self.log(f"  → Checking follow back for {username}...")
                                if automation.check_if_following_back(user['user_url']):
                                    self.log(f"  ⊘ Skipping (follows you back)")
                                    continue
                            except:
                                pass
                        
                        self.log(f"  [{processed+1}/{limit}] Unfollowing: {username}")
                        result = automation.unfollow_user(user['user_url'])
                        if result:
                            processed += 1
                            self.log(f"  ✓ Unfollowed successfully")
                            # Remove from followed_users table
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            cursor.execute("DELETE FROM followed_users WHERE user_url = ?", (user['user_url'],))
                            conn.commit()
                            conn.close()
                        else:
                            self.log(f"  ✗ Failed to unfollow")
                        
                        if processed < limit:
                            time.sleep(5)
                    
                    return processed > 0
            
            return False
            
        except Exception as e:
            raise Exception(f"Action execution error: {e}")
    
    def update_task_status(self, task_id, status, log_output):
        """Update task status in database."""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE scheduled_actions
                SET status = ?, log_output = ?
                WHERE id = ?
            """, (status, log_output, task_id))
            conn.commit()
            conn.close()
            
            self.task_executed.emit(task_id, status)
        except Exception as e:
            print(f"Error updating task status: {e}")
    
    def log(self, message):
        """Add log message and echo to action-specific buffer if applicable."""
        self.log_signal.emit(message)
        
        # If we are currently performing an action, echo the log to that tab's buffer
        if self.current_action_type:
            # Map scheduler action types to UI manager keys
            mapping = {
                'repin': 'repin',
                'upload': 'repin', # Upload is handled in Repin UI
                'comment': 'comment',
                'follow': 'follow'
            }
            target_key = mapping.get(self.current_action_type)
            if target_key:
                self.manager.add_log(target_key, f"[Scheduled] {message}")
    
    def stop(self):
        """Stop the scheduler worker."""
        self.is_running = False
