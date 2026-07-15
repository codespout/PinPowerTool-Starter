from PySide6.QtCore import QThread, Signal as pyqtSignal
import time
import os
import requests
from urllib.parse import urlparse
from src.database import get_db_connection
from src.modules.actions import PinterestAutomation
import json

class DownloaderWorker(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal()

    def __init__(self, mode, data, folder, limit, renaming, custom_pattern=""):
        super().__init__()
        self.mode = mode
        self.data = data # Search term or links text
        self.folder = folder
        self.limit = limit
        self.renaming = renaming
        self.custom_pattern = custom_pattern
        self.is_running = True
        
        # Get active account
        self.account = self.get_active_account()
        
        # Configure automation
        proxy_dict = None
        if self.account and self.account['proxy']:
            parts = self.account['proxy'].split(':')
            if len(parts) >= 2:
                proxy_dict = {'server': f"http://{parts[0]}:{parts[1]}"}
                if len(parts) >= 4:
                    proxy_dict['username'] = parts[2]
                    proxy_dict['password'] = parts[3]
        
        self.automation = PinterestAutomation(headless=False, proxy=proxy_dict)

    def get_active_account(self):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM accounts WHERE is_selected = 1 LIMIT 1")
        account = cursor.fetchone()
        conn.close()
        return account

    def run(self):
        self.log_signal.emit(f"Worker started. Mode: {self.mode}")
        
        # Load cookies
        cookies = None
        if self.account and self.account['cookies']:
            try:
                cookies = json.loads(self.account['cookies'])
            except: pass
            
        # Start browser
        if not self.automation.start_browser(cookies=cookies):
            self.log_signal.emit("Error: Failed to start browser")
            self.finished_signal.emit()
            return
            
        # Ensure logged in (if we have account)
        if self.account:
            if not self.automation.ensure_logged_in(self.account['email'], self.account['password']):
                self.log_signal.emit("Error: Login failed")
                self.automation.stop_browser()
                self.finished_signal.emit()
                return

        try:
            pin_urls = []
            
            if self.mode == "search":
                pin_urls = self.process_search()
            else:
                pin_urls = self.process_links()
            
            self.log_signal.emit(f"Found {len(pin_urls)} pins to process.")
            
            processed = 0
            for pin_url in pin_urls:
                if not self.is_running: break
                
                success = self.download_image(pin_url, processed + 1)
                if success:
                    processed += 1
                    self.progress_signal.emit(int((processed / len(pin_urls)) * 100))
                
                time.sleep(1) # Polite delay
                
            self.log_signal.emit(f"Finished. Downloaded {processed} images.")
            
        except Exception as e:
            self.log_signal.emit(f"Error in downloader: {e}")
            import traceback
            traceback.print_exc()
        
        self.automation.stop_browser()
        self.finished_signal.emit()

    def stop(self):
        self.is_running = False

    def process_search(self):
        term = self.data
        self.log_signal.emit(f"Searching for: {term}")
        
        # Navigate to search
        search_url = f"https://www.pinterest.com/search/pins/?q={term}&rs=typed"
        self.automation.page.goto(search_url, timeout=60000, wait_until="domcontentloaded")
        time.sleep(5)
        
        # Scroll to load pins
        pins = set()
        scrolls = 0
        max_scrolls = 10 # Adjust based on limit
        
        while len(pins) < self.limit and scrolls < max_scrolls and self.is_running:
            # Extract pin URLs
            elements = self.automation.page.query_selector_all('a[href*="/pin/"]')
            for el in elements:
                href = el.get_attribute('href')
                if href:
                    full_url = f"https://www.pinterest.com{href}"
                    pins.add(full_url)
                    if len(pins) >= self.limit: break
            
            if len(pins) >= self.limit: break
            
            self.automation.page.evaluate("window.scrollBy(0, 1000)")
            time.sleep(2)
            scrolls += 1
            self.log_signal.emit(f"Scrolled {scrolls}/{max_scrolls}. Found {len(pins)} pins so far...")
            
        return list(pins)[:self.limit]

    def process_links(self):
        raw_links = self.data.split('\n')
        valid_links = [l.strip() for l in raw_links if l.strip().startswith('http')]
        return valid_links

    def download_image(self, pin_url, index):
        try:
            self.log_signal.emit(f"Processing pin: {pin_url}")
            self.automation.page.goto(pin_url, timeout=60000, wait_until="domcontentloaded")
            time.sleep(3)
            
            # Find image URL
            # Look for the main image (usually has specific class or is the largest)
            # Strategy: Look for img with src containing 'originals' or '736x'
            img_url = None
            
            # Try finding the main image
            images = self.automation.page.query_selector_all('img')
            best_img = None
            max_size = 0
            
            for img in images:
                src = img.get_attribute('src')
                if not src: continue
                
                # Check for high res indicators
                if 'originals' in src:
                    img_url = src
                    break
                
                # Fallback logic: find largest image
                try:
                    box = img.bounding_box()
                    if box:
                        area = box['width'] * box['height']
                        if area > max_size:
                            max_size = area
                            best_img = src
                except: pass
            
            if not img_url and best_img:
                img_url = best_img
                
            if not img_url:
                self.log_signal.emit("  Could not find image URL.")
                return False
                
            # Determine filename
            pin_id = pin_url.split('/pin/')[-1].strip('/').split('/')[0]
            if not pin_id: pin_id = f"pin_{int(time.time())}"
            
            title = "pin"
            try:
                title_el = self.automation.page.query_selector('h1')
                if title_el: title = title_el.inner_text().strip()
                # Sanitize title
                title = "".join([c for c in title if c.isalnum() or c in (' ', '-', '_')]).strip()
            except: pass
            
            filename = ""
            ext = ".jpg"
            if ".png" in img_url: ext = ".png"
            
            if self.renaming == "Original ID":
                filename = f"{pin_id}{ext}"
            elif self.renaming == "Number Sequence":
                filename = f"{index}{ext}"
            elif self.renaming == "Pin Title":
                filename = f"{title}_{pin_id}{ext}"
            elif self.renaming == "Custom":
                # Replace placeholders
                name = self.custom_pattern.replace("{id}", pin_id).replace("{title}", title)
                # Sanitize
                name = "".join([c for c in name if c.isalnum() or c in (' ', '-', '_', '.')]).strip()
                if not name: name = pin_id
                filename = f"{name}{ext}"
            else:
                filename = f"{pin_id}{ext}"
                
            filepath = os.path.join(self.folder, filename)
            
            # Download
            self.log_signal.emit(f"  Downloading image to: {filename}")
            response = requests.get(img_url, stream=True)
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(1024):
                        f.write(chunk)
                self.log_signal.emit("  ✓ Download successful")
                return True
            else:
                self.log_signal.emit(f"  Failed to download image. Status: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_signal.emit(f"  Error processing pin: {e}")
            return False
