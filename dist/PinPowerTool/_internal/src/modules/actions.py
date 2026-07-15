from playwright.sync_api import sync_playwright
import time
import os
import json
import re
import random

class PinterestAutomation:
    def __init__(self, headless=False, proxy=None, disable_images=False):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.headless = headless
        self.proxy = proxy
        self.disable_images = disable_images
    
    def start_browser(self, cookies=None):
        """Initialize browser with optional cookies and verify login status."""
        try:
            # Start Playwright - Ensure no asyncio interference
            import asyncio
            try:
                # Playwright sync API cannot run if an asyncio loop is already present on the thread.
                # This often happens in QThreads or certain environments.
                asyncio.set_event_loop(None)
            except:
                pass
            self.playwright = sync_playwright().start()
            
            # Configure browser launch options
            launch_options = {
                "headless": self.headless,
                "args": [
                    "--disable-blink-features=AutomationControlled"
                ]
            }
            
            # Launch browser
            self.browser = self.playwright.chromium.launch(**launch_options)
            
            # Configure context options
            context_options = {
                "viewport": {"width": 1920, "height": 1080},
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            if self.proxy:
                print(f"Using proxy: {self.proxy.get('server')}")
                context_options["proxy"] = self.proxy
            
            # Create context
            self.context = self.browser.new_context(**context_options)
            
            # Block images if requested
            if self.disable_images:
                self.context.route("**/*.{png,jpg,jpeg,gif,webp,svg}", lambda route: route.abort())
                print("Image loading disabled for faster browsing")
            
            # Load cookies if provided
            if cookies:
                try:
                    self.context.add_cookies(cookies)
                    print("Cookies loaded successfully")
                except Exception as e:
                    print(f"Warning: Failed to load cookies: {e}")
            
            # Create page
            self.page = self.context.new_page()
            
            # Set longer timeout for page operations
            self.page.set_default_timeout(60000)  # 60 seconds
            
            # Navigate to Pinterest with increased timeout and less strict wait
            print("Navigating to Pinterest...")
            self.page.goto("https://www.pinterest.com/", timeout=60000, wait_until="domcontentloaded")
            
            # Wait a bit for dynamic content
            time.sleep(2)
            
            print("Browser started successfully")
            return True
            
        except Exception as e:
            print(f"Error starting browser: {e}")
            self.stop_browser()
            return False
    
    def stop_browser(self):
        """Clean up browser resources."""
        try:
            if self.page:
                self.page.close()
                self.page = None
            if self.context:
                self.context.close()
                self.context = None
            if self.browser:
                self.browser.close()
                self.browser = None
            if self.playwright:
                self.playwright.stop()
                self.playwright = None
        except Exception as e:
            print(f"Error stopping browser: {e}")
    
    def ensure_logged_in(self, email, password):
        """Ensure user is logged in, re-authenticate if necessary."""
        if not self.page:
            return False
        
        try:
            # Check if already logged in
            if self.is_logged_in():
                print("Already logged in.")
                return True
            
            # Not logged in, perform login
            print("Not logged in. Attempting to login...")
            self.page.goto("https://www.pinterest.com/login/", timeout=60000, wait_until="domcontentloaded")
            time.sleep(2)
            
            # Fill credentials
            try:
                # Wait for login form to be visible
                self.page.wait_for_selector('input[id="email"]', timeout=15000)
                self.page.fill('input[id="email"]', email)
                self.page.fill('input[id="password"]', password)
                
                # Click login button
                self.page.click('button[type="submit"]')
                
                # Wait for navigation or login completion
                time.sleep(5)  # Give it time to process login
                
                # Verify login was successful
                if self.is_logged_in():
                    print("Login successful!")
                    return True
                else:
                    print("Login failed - unable to verify login status")
                    return False
                    
            except Exception as e:
                print(f"Login form interaction failed: {e}")
                return False
                
        except Exception as e:
            print(f"Error during login verification: {e}")
            return False

    def human_warmup(self, duration_mins=5, log_signal=None):
        """Perform natural browsing actions to build a human session fingerprint."""
        import random
        from datetime import datetime, timedelta
        
        if not self.page:
            return
            
        end_time = datetime.now() + timedelta(minutes=duration_mins)
        if log_signal:
            log_signal.emit(f"🛡️ Starting Human-Warmup session ({duration_mins} mins)...")
            
        def natural_move(target_x, target_y):
            # Move mouse in small steps to look human
            steps = random.randint(15, 30)
            self.page.mouse.move(target_x, target_y, steps=steps)

        try:
            # Initial landing
            self.page.goto("https://www.pinterest.com/", wait_until="domcontentloaded")
            time.sleep(3)

            destinations = [
                "https://www.pinterest.com/",
                "https://www.pinterest.com/ideas/",
                "https://www.pinterest.com/today/",
                "settings_profile" # Special handle for profile
            ]

            while datetime.now() < end_time:
                # Randomly choose a destination or stay on current
                if random.random() > 0.7:
                    dest = random.choice(destinations)
                    if dest == "settings_profile":
                        if log_signal: log_signal.emit("  🔄 Warmup: Visiting personal profile...")
                        self.page.click('div[data-test-id="header-profile"]', timeout=5000)
                    else:
                        if log_signal: log_signal.emit(f"  🔄 Warmup: Navigating to {dest.split('/')[-2] or 'home'}...")
                        self.page.goto(dest, wait_until="domcontentloaded")
                    time.sleep(random.randint(3, 7))

                # Perform a series of human actions on the current page
                for _ in range(random.randint(5, 12)):
                    if datetime.now() >= end_time: break
                    
                    action = random.choice(['scroll', 'hover', 'click_pin', 'mouse_jitter', 'search'])
                    
                    if action == 'scroll':
                        direction = 'down' if random.random() > 0.3 else 'up'
                        amount = random.randint(300, 800)
                        self.human_scroll(direction=direction, amount=amount)
                        time.sleep(random.uniform(1, 4))
                        
                    elif action == 'hover':
                        # Find buttons or pins to hover
                        elements = self.page.query_selector_all('div[data-test-id="pin"], button, a')
                        if elements:
                            target = random.choice(elements[:min(15, len(elements))])
                            box = target.bounding_box()
                            if box:
                                natural_move(box['x'] + box['width']/2, box['y'] + box['height']/2)
                                time.sleep(random.uniform(0.5, 2))
                                
                    elif action == 'click_pin':
                        # Click a random pin link
                        pins = self.page.query_selector_all('a[href*="/pin/"]')
                        if pins:
                            pin = random.choice(pins[:min(10, len(pins))])
                            if log_signal: log_signal.emit(f"  👁️ Warmup: Interest browsing...")
                            pin.click()
                            time.sleep(random.uniform(8, 20)) # Spend time looking
                            
                            # Small scroll on pin page
                            if random.random() > 0.4:
                                self.human_scroll(direction='down', amount=400)
                            
                            # Back to feed
                            if random.random() > 0.3:
                                self.page.go_back()
                                time.sleep(3)
                    
                    elif action == 'mouse_jitter':
                        # Just move mouse slightly like a human thinking
                        curr_x = random.randint(100, 1000)
                        curr_y = random.randint(100, 800)
                        natural_move(curr_x, curr_y)
                        time.sleep(random.uniform(2, 5))

                    elif action == 'search':
                        # Search for a random popular topic
                        topics = ["home decor", "outfit ideas", "recipes", "travel", "diy", "art", "fitness"]
                        topic = random.choice(topics)
                        if log_signal: log_signal.emit(f"  🔍 Warmup: Searching for '{topic}'...")
                        
                        search_box = self.page.query_selector('input[name="q"]')
                        if search_box:
                            search_box.click()
                            self.human_type(search_box, topic)
                            self.page.keyboard.press("Enter")
                            time.sleep(random.randint(5, 10))
                            # Scroll results
                            self.human_scroll(direction='down', amount=600)
                            time.sleep(3)
                            # Go back home
                            self.page.goto("https://www.pinterest.com/", wait_until="domcontentloaded")
                            time.sleep(2)

                    # Check time remaining
                    remaining = (end_time - datetime.now()).total_seconds()
                    if remaining <= 0: break
                    if log_signal and random.random() > 0.9:
                         log_signal.emit(f"  ⏳ Warmup: {int(remaining/60)}m {int(remaining%60)}s left...")

            if log_signal:
                log_signal.emit("✅ Human-Warmup session completed.")
        except Exception as e:
            if log_signal:
                log_signal.emit(f"⚠️ Note: Warmup interruption ({str(e)})")
            else:
                print(f"Warning during warmup: {e}")
    
    def get_trending_keywords(self, country='US', interest='ALL', log_signal=None):
        """Scrape trending keywords from Pinterest Trends."""
        import random
        from urllib.parse import quote
        
        if not self.page:
            return []
            
        try:
            # Construct URL
            # Note: interest 'ALL' might not need topicInterestIds
            url = f"https://trends.pinterest.com/?country={country}"
            if interest != 'ALL':
                url += f"&topicInterestIds={interest}"
            
            if log_signal: log_signal.emit(f"  🌐 Navigating to Trends: {country} / {interest}...")
            self.page.goto(url, wait_until="networkidle", timeout=60000)
            time.sleep(5) # Wait for table to load
            
            # Selectors based on user data
            # The trending terms are usually in the first column of the trends table
            # Based on standard Pinterest Trends UI, they have data-test-id="trend-term" or similar
            # Or we can look for links that look like detail pages
            
            keywords = []
            
            # Try to find terms in the trends table
            # Standard selector for trend terms in the table:
            term_selectors = [
                'div[data-test-id="trend-term"]',
                'div.grid-item-term', # Older selector maybe?
                'a[href*="/detail/"] div' # Text inside detail links
            ]
            
            for selector in term_selectors:
                elements = self.page.query_selector_all(selector)
                if elements:
                    for el in elements:
                        text = el.inner_text().strip()
                        if text and text not in keywords:
                            keywords.append(text)
                    if keywords: break
            
            if not keywords:
                # Fallback: Scrape anything that looks like a trend link
                links = self.page.query_selector_all('a[href*="/detail/"]')
                for link in links:
                    # Often the term is in the 'terms' query param of the link
                    href = link.get_attribute('href')
                    if 'terms=' in href:
                        from urllib.parse import urlparse, parse_qs
                        parsed = urlparse(href)
                        params = parse_qs(parsed.query)
                        if 'terms' in params:
                            term = params['terms'][0]
                            if term not in keywords:
                                keywords.append(term)
                    else:
                        # Or just the text
                        text = link.inner_text().strip()
                        if text and text not in keywords:
                            keywords.append(text)

            if log_signal: log_signal.emit(f"  📈 Found {len(keywords)} trending topics.")
            return keywords[:20] # Return top 20
            
        except Exception as e:
            if log_signal: log_signal.emit(f"⚠️ Error fetching trends: {str(e)}")
            return []

    # Humanization Helper Methods
    def human_delay(self, base_seconds=1, variance=0.5):
        """Add human-like delay with randomness."""
        import random
        delay = base_seconds + random.uniform(-variance, variance)
        delay = max(0.5, delay)  # Minimum 0.5s
        time.sleep(delay)
    
    def human_type(self, element, text, min_delay=30, max_delay=120):
        """Type text with human-like delays between keystrokes."""
        import random
        for char in text:
            element.type(char)
            delay = random.randint(min_delay, max_delay)
            time.sleep(delay / 1000.0)  # Convert to seconds
    
    def human_scroll(self, direction='down', amount=None):
        """Scroll with human-like behavior."""
        import random
        if amount is None:
            amount = random.randint(200, 600)
        
        if direction == 'down':
            self.page.evaluate(f"window.scrollBy(0, {amount})")
        elif direction == 'up':
            self.page.evaluate(f"window.scrollBy(0, -{amount})")
        else:
            self.page.evaluate(f"window.scrollTo(0, {amount})")
        
        self.human_delay(0.5, 0.3)
    
    def human_mouse_move(self, x, y):
        """Move mouse to coordinates with slight randomness."""
        import random
        # Add small random offset to make it more natural
        x_offset = random.randint(-5, 5)
        y_offset = random.randint(-5, 5)
        self.page.mouse.move(x + x_offset, y + y_offset)
        self.human_delay(0.2, 0.1)
    
    def verify_login(self, email, password):
        """Login and verify account status/type."""
        if not self.start_browser():
            return {"success": False, "message": "Failed to start browser"}
            
        try:
            self.page.goto("https://www.pinterest.com/login/")
            self.page.wait_for_load_state('networkidle')
            
            # Fill credentials
            self.page.fill('input[name="id"]', email)
            self.page.fill('input[name="password"]', password)
            self.page.click('button[type="submit"]')
            
            # Wait for navigation or error
            # Check for home feed or profile to confirm login
            try:
                self.page.wait_for_selector('div[data-test-id="header-profile"]', timeout=15000)
            except:
                # Check for error message
                if self.page.is_visible('div[data-test-id="login-error-message"]'):
                    return {"success": False, "message": "Invalid credentials"}
                return {"success": False, "message": "Login timeout or unknown error"}

            # Handle soft interruptions (e.g., "Save password", "Get the app")
            # This is generic; specific selectors needed for actual popups
            
            # Detect Account Type
            account_type = "Personal"
            try:
                self.page.click('div[data-test-id="header-profile"]')
                self.page.wait_for_selector('div[data-test-id="profile-header"]', timeout=5000)
                
                # Check for "Business" indicators in the profile or settings
                # Simplified check: Look for "Business Hub" link often present for business accounts
                if self.page.is_visible('a[href*="/business/hub/"]'):
                    account_type = "Business"
            except:
                pass
                
            # Get Account Name
            name = email.split('@')[0] # Fallback
            try:
                name_el = self.page.query_selector('h1')
                if name_el:
                    name = name_el.inner_text()
            except:
                pass

            return {
                "success": True, 
                "message": "Login successful",
                "account_type": account_type,
                "name": name,
                "cookies": self.context.cookies()
            }
            
        except Exception as e:
            return {"success": False, "message": f"Error during verification: {str(e)}"}
        finally:
            self.stop_browser()

    def login(self, email, password, cookies_path=None):
        """Login to Pinterest using cookies or credentials."""
        if not self.page:
            self.start_browser()

        # Try loading cookies first
        if cookies_path and os.path.exists(cookies_path):
            try:
                with open(cookies_path, 'r') as f:
                    cookies = json.load(f)
                self.context.add_cookies(cookies)
                self.page.goto("https://www.pinterest.com/")
                if self.is_logged_in():
                    return True
            except Exception as e:
                print(f"Failed to load cookies: {e}")

        # Manual Login
        self.page.goto("https://www.pinterest.com/login/")
        try:
            # Wait for email field to be sure page loaded
            self.page.wait_for_selector('input[id="email"]', timeout=15000)
            self.page.fill('input[id="email"]', email)
            self.page.fill('input[id="password"]', password)
            self.page.click('button[type="submit"]')
            
            # Wait for any of the logged-in indicators (Home Feed, Profile Icon, or News Hub)
            # This handles both Personal and Business account redirects
            try:
                self.page.wait_for_selector('div[data-test-id="header-profile"], [data-test-id="news-hub-sidebar"], [data-test-id="news-hub-list-item"]', timeout=20000)
            except:
                # Fallback check
                if not self.is_logged_in():
                    print("Login verification failed: Profile element not found after timeout.")
                    return False
            
            print("Login successful (verified via UI elements)")
            
            # Save cookies
            if cookies_path:
                cookies = self.context.cookies()
                with open(cookies_path, 'w') as f:
                    json.dump(cookies, f)
            
            return True
        except Exception as e:
            print(f"Login failed: {e}")
            return False

    def is_logged_in(self):
        """Check if logged in by looking for specific elements."""
        try:
            # Check for profile icon or home feed element
            self.page.wait_for_selector('div[data-test-id="header-profile"]', timeout=5000)
            return True
        except:
            return False
    
    def get_account_type(self):
        """Detect if account is Business or Personal."""
        if not self.page:
            return "Personal"
        
        try:
            # Click profile to check for business indicators
            current_url = self.page.url
            self.page.click('div[data-test-id="header-profile"]')
            time.sleep(1)
            
            # Check for business hub or ads manager link
            if self.page.is_visible('a[href*="/business/hub/"]') or \
               self.page.is_visible('a[href*="/ads/"]') or \
               self.page.is_visible('text=Business Hub'):
                account_type = "Business"
            else:
                account_type = "Personal"
            
            # Navigate back
            if current_url:
                self.page.goto(current_url)
            
            return account_type
        except Exception as e:
            print(f"Error detecting account type: {e}")
            return "Personal"  # Default to Personal



    def pin_url(self, image_path, board_name, title, description, link):
        """Upload a pin from a local file."""
        if not self.page:
            return False
        
        try:
            self.page.goto("https://www.pinterest.com/pin-builder/")
            # Upload image
            self.page.set_input_files('input[type="file"]', image_path)
            
            # Fill details
            self.page.fill('input[placeholder="Add your title"]', title)
            self.page.fill('div[role="textbox"]', description) # Description is often a div contenteditable
            self.page.fill('input[placeholder="Add a destination link"]', link)
            
            # Select board (simplified, might need more complex selector)
            self.page.click('div[data-test-id="board-dropdown-select-button"]')
            self.page.fill('input[id="pickerSearchField"]', board_name)
            self.page.click(f'div[title="{board_name}"]')
            
            # Publish
            self.page.click('button[data-test-id="board-dropdown-save-button"]')
            self.page.wait_for_selector('div:has-text("Saved")', timeout=10000)
            return True
        except Exception as e:
            print(f"Error pinning: {e}")
            return False

    def repin(self, pin_url, board_name):
        """Repin an existing pin to a board."""
        if not self.page:
            return False
            
        try:
            self.page.goto(pin_url)
            self.page.click('div[data-test-id="board-dropdown-select-button"]')
            self.page.fill('input[id="pickerSearchField"]', board_name)
            self.page.click(f'div[title="{board_name}"]')
            self.page.click('button[data-test-id="board-dropdown-save-button"]')
            return True
        except Exception as e:
            print(f"Error repinning: {e}")
            return False

    def get_user_details(self, user_url):
        """Scrape user details like followers, following, etc."""
        if not self.page:
            return None
            
        try:
            self.page.goto(user_url, timeout=30000, wait_until="domcontentloaded")
            time.sleep(2)  # Wait for dynamic content
            
            # Try to extract follower and following counts
            followers = 0
            following = 0
            pins = 0
            
            # Strategy: Look for text containing "followers", "following", "pins"
            # Pinterest shows these as stats near the profile
            try:
                # Get all text elements that might contain stats
                stats_elements = self.page.query_selector_all('div, span, a')
                
                for elem in stats_elements:
                    try:
                        text = elem.inner_text(timeout=1000) if elem.is_visible() else ""
                        text_lower = text.lower()
                        
                        # Check for followers
                        if 'follower' in text_lower and followers == 0:
                            followers = self._parse_number(text)
                        
                        # Check for following
                        if 'following' in text_lower and following == 0:
                            following = self._parse_number(text)
                        
                        # Check for pins
                        if 'pin' in text_lower and 'repin' not in text_lower and pins == 0:
                            pins = self._parse_number(text)
                        
                        # Break early if we found all three
                        if followers > 0 and following > 0 and pins > 0:
                            break
                    except:
                        continue
            except Exception as e:
                print(f"Error parsing stats: {e}")
            
            return {
                "followers": followers,
                "following": following,
                "pins": pins,
                "url": user_url
            }
        except Exception as e:
            print(f"Error getting user details for {user_url}: {e}")
            # Return basic data even on error
            return {
                "followers": 0,
                "following": 0,
                "pins": 0,
                "url": user_url
            }
    
    def batch_get_user_details(self, user_urls, batch_size=5):
        """
        Fetch user details for multiple users in parallel using multiple tabs.
        
        Args:
            user_urls (list): List of user URLs to fetch details for
            batch_size (int): Number of tabs to open simultaneously (default: 5)
            
        Returns:
            list: List of user detail dicts
        """
        if not self.context:
            return []
        
        results = []
        
        # Process in batches
        for i in range(0, len(user_urls), batch_size):
            batch = user_urls[i:i + batch_size]
            print(f"Processing batch {i//batch_size + 1}: {len(batch)} users...")
            
            # Create multiple pages for parallel processing
            pages = []
            try:
                for url in batch:
                    page = self.context.new_page()
                    pages.append((page, url))
                
                # Navigate all pages simultaneously
                for page, url in pages:
                    try:
                        page.goto(url, timeout=30000, wait_until="domcontentloaded")
                    except Exception as e:
                        print(f"Error navigating to {url}: {e}")
                
                # Wait for pages to load
                time.sleep(3)
                
                # Extract data from all pages
                for page, url in pages:
                    try:
                        followers = 0
                        following = 0
                        pins = 0
                        
                        # Get all text elements
                        stats_elements = page.query_selector_all('div, span, a')
                        
                        for elem in stats_elements[:100]:  # Limit to first 100 elements for speed
                            try:
                                if not elem.is_visible():
                                    continue
                                    
                                text = elem.inner_text(timeout=500)
                                text_lower = text.lower()
                                
                                if 'follower' in text_lower and followers == 0:
                                    followers = self._parse_number(text)
                                
                                if 'following' in text_lower and following == 0:
                                    following = self._parse_number(text)
                                
                                if 'pin' in text_lower and 'repin' not in text_lower and pins == 0:
                                    pins = self._parse_number(text)
                                
                                if followers > 0 and following > 0 and pins > 0:
                                    break
                            except:
                                continue
                        
                        results.append({
                            "followers": followers,
                            "following": following,
                            "pins": pins,
                            "url": url
                        })
                    except Exception as e:
                        print(f"Error extracting data from {url}: {e}")
                        results.append({
                            "followers": 0,
                            "following": 0,
                            "pins": 0,
                            "url": url
                        })
            finally:
                # Close all pages in this batch
                for page, url in pages:
                    try:
                        page.close()
                    except:
                        pass
        
        return results


    def _parse_number(self, text):
        """Parse number from string like '1.2k followers'."""
        if not text:
            return 0
        try:
            # This is a placeholder. Real parsing needs to handle 'k', 'm', etc.
            # And filter out non-numeric chars
            import re
            num_str = re.search(r'([\d\.]+)([km]?)', text.lower())
            if not num_str:
                return 0
            
            val = float(num_str.group(1))
            multiplier = num_str.group(2)
            
            if multiplier == 'k':
                val *= 1000
            elif multiplier == 'm':
                val *= 1000000
                
            return int(val)
        except:
            return 0

    def comment_on_pin(self, pin_url, comment_text):
        """Post a comment on a pin."""
        if not self.page:
            return False
            
        try:
            self.page.goto(pin_url)
            # Click comment button/field (selectors vary, need to be robust)
            # Often there's a "Comments" section to expand
            self.page.click('div[data-test-id="comment-button"]', timeout=3000)
            
            # Type comment
            self.page.fill('div[role="textbox"]', comment_text)
            
            # Click send
            self.page.click('button[aria-label="Done"]')
            return True
        except Exception as e:
            print(f"Error commenting: {e}")
            return False

    def scrape_pins(self, query, limit=50, source_type='search', continue_scrolling=False, exclude_pins=None, should_stop=None):
        """Scrape pin URLs based on search or from a specific user.
        
        Args:
            query: Search keyword or user URL
            limit: Number of pins
            source_type: 'search' or 'user'
            continue_scrolling: If True, continues from current position
            exclude_pins: Set/list of pin URLs to exclude
            should_stop: Callable returning True to stop scraping
        """
        if not self.page:
            print("Error: No page object available")
            return []
            
        if exclude_pins is None:
            exclude_pins = set()
            
        results = [] 
        
        try:
            if not continue_scrolling:
                if source_type == 'search':
                    print(f"Searching for pins with keyword: {query}")
                    self.page.goto(f"https://www.pinterest.com/search/pins/?q={query}", timeout=60000, wait_until="domcontentloaded")
                    time.sleep(3)
                    
                elif source_type == 'user':
                    if query.startswith('http'):
                        username = query.rstrip('/').split('/')[-1]
                    else:
                        username = query
                    
                    print(f"Gathering pins from user: {username}")
                    url = f"https://www.pinterest.com/{username}/_created/"
                    self.page.goto(url, timeout=60000, wait_until="domcontentloaded")
                    time.sleep(3)
                    
                    # Logic to traverse boards if no created pins found
                    has_created_pins = False
                    try:
                        self.page.wait_for_selector('a[href*="/pin/"]', timeout=5000)
                        has_created_pins = True
                    except:
                        pass
                        
                    if not has_created_pins:
                        # Board traversal logic
                        print("Navigating to user's boards to collect saved pins...")
                        boards_url = f"https://www.pinterest.com/{username}/_saved/"
                        self.page.goto(boards_url, timeout=60000, wait_until="domcontentloaded")
                        time.sleep(3)
                        
                        board_links = self.page.query_selector_all('a[href*="/' + username + '/"]')
                        boards = set()
                        for link in board_links:
                            href = link.get_attribute('href')
                            if href and '/pin/' not in href:
                                if href.startswith('http'):
                                    boards.add(href.split('?')[0])
                                else:
                                    boards.add(f"https://www.pinterest.com{href.split('?')[0]}")
                        
                        # Visit boards
                        for board_url in list(boards)[:10]:
                            if len(results) >= limit: break
                            self.page.goto(board_url, timeout=60000, wait_until="domcontentloaded")
                            time.sleep(2)
                            
                            pins = self.page.query_selector_all('a[href*="/pin/"]')
                            for pin in pins:
                                href = pin.get_attribute('href')
                                if href and '/pin/' in href:
                                    url = href.split('?')[0] if href.startswith('http') else f"https://www.pinterest.com{href.split('?')[0]}"
                                    if url not in exclude_pins:
                                        # Dedupe against current results
                                        if not any(r['url'] == url for r in results):
                                            results.append({'url': url})
                                            if len(results) >= limit: break
                                            
                        if results:
                            return results[:limit]

            
            print(f"Starting to scrape pins... (continue={continue_scrolling})")
            
            # Scroll and collect pins
            last_height = 0
            scroll_attempts = 0
            max_scroll_attempts = 30 if continue_scrolling else 20
            no_new_results_count = 0
            
            while len(results) < limit and scroll_attempts < max_scroll_attempts:
                # Check stop signal
                if should_stop and should_stop():
                    break
                    
                # Get multiple types of pin links (standard pin, video pin, etc.)
                selectors = ['a[href*="/pin/"]']
                
                found_in_scroll = 0
                
                for selector in selectors:
                    links = self.page.query_selector_all(selector)
                    
                    for link in links:
                        href = link.get_attribute('href')
                        if href and '/pin/' in href and not '/sent/' in href:
                            if href.startswith('http'):
                                clean_url = href.split('?')[0]
                            else:
                                clean_url = f"https://www.pinterest.com{href.split('?')[0]}"
                            
                            # Skip if excluded
                            if clean_url not in exclude_pins:
                                # Add basic dict structure if not already in results
                                is_dup = False
                                for r in results:
                                    if isinstance(r, dict) and r['url'] == clean_url:
                                        is_dup = True
                                        break
                                    elif isinstance(r, str) and r == clean_url:
                                        is_dup = True
                                        break
                                
                                if not is_dup:
                                    results.append({'url': clean_url})
                                    found_in_scroll += 1
                            
                            if len(results) >= limit:
                                break
                    if len(results) >= limit:
                        break
                
                print(f"Found {found_in_scroll} new pins in this scroll. Total: {len(results)}")
                
                # Simple scroll
                self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(2)
                
                new_height = self.page.evaluate("document.body.scrollHeight")
                if new_height == last_height:
                    scroll_attempts += 1
                else:
                    scroll_attempts = 0
                last_height = new_height
                
            return results[:limit]

        except Exception as e:
            print(f"Error scraping pins: {e}")
            import traceback
            traceback.print_exc()
            return list(results)

    def batch_get_pin_details(self, pin_urls, batch_size=5, should_stop=None):
        """
        Fetch details for multiple pins in parallel using multiple tabs.
        
        Args:
            pin_urls: List of URLs
            batch_size: Parallel tabs count
            should_stop: Callable returning True if operation should cancel
        """
        if not self.context:
            return []
        
        results = []
        
        # Process in batches
        for i in range(0, len(pin_urls), batch_size):
            # Check stop signal
            if should_stop and should_stop():
                print("Batch processing stopped by user.")
                break
                
            batch = pin_urls[i:i + batch_size]
            print(f"Fetching details for batch {i//batch_size + 1}: {len(batch)} pins...")
            
            pages = []
            try:
                # Open tabs
                for url in batch:
                    page = self.context.new_page()
                    pages.append((page, url))
                
                # Navigate
                for page, url in pages:
                    try:
                        page.goto(url, timeout=45000, wait_until="domcontentloaded")
                    except:
                        pass
                
                # Check stop before waiting
                if should_stop and should_stop():
                    break
                    
                # Wait for load
                time.sleep(3)
                
                # Extract details
                for page, url in pages:
                    try:
                        data = {
                            'url': url,
                            'description': '',
                            'title': '',
                            'repins': 0,
                            'is_video': False,
                            'is_product': False,
                            'has_link': False
                        }
                        
                        # Get description/title
                        try:
                            desc_el = page.query_selector('h2') or page.query_selector('h1')
                            if desc_el:
                                data['title'] = desc_el.inner_text()
                            
                            # Description
                            desc_sel = ['div[data-test-id="pin-description"]', 
                                       'div[data-test-id="visual-search-result-item"]', 
                                       'meta[property="og:description"]']
                            for sel in desc_sel:
                                el = page.query_selector(sel)
                                if el:
                                    if el.tag_name == 'meta':
                                        data['description'] = el.get_attribute('content')
                                    else:
                                        data['description'] = el.inner_text()
                                    if data['description']: break
                                
                            # Check for Repins (Saved count)
                            # Try multiple strategies
                            repin_text = ""
                            # 1. Look for text like "1.2k saved"
                            saved_el = page.query_selector('div:has-text("saved")')
                            if saved_el:
                                repin_text = saved_el.inner_text()
                                
                            # 2. Look for specific metrics container
                            if not repin_text:
                                metrics = page.query_selector_all('[data-test-id="pin-stats-count"]')
                                if metrics:
                                    repin_text = metrics[0].inner_text()
                                    
                            if repin_text:
                                # Extract number
                                import re
                                match = re.search(r'([\d,\.]+[kKmM]?)', repin_text)
                                if match:
                                    num_str = match.group(1).lower().replace(',', '')
                                    multiplier = 1
                                    if 'k' in num_str:
                                        multiplier = 1000
                                        num_str = num_str.replace('k', '')
                                    elif 'm' in num_str:
                                        multiplier = 1000000
                                        num_str = num_str.replace('m', '')
                                    
                                    try:
                                        data['repins'] = int(float(num_str) * multiplier)
                                    except:
                                        pass

                        except Exception as e:
                            pass

                        # Check if video
                        if page.query_selector('video'):
                            data['is_video'] = True
                            
                        # Check product (simplified)
                        if page.query_selector('div[data-test-id="product-price"]'):
                            data['is_product'] = True
                            
                        # Check destination link
                        link_sel = 'a[href^="http"]:not([href*="pinterest.com"])'
                        if page.query_selector(link_sel):
                            data['has_link'] = True
                            
                        results.append(data)
                    except Exception as e:
                        print(f"Error extracting pin details {url}: {e}")
                        results.append({'url': url})
                        
            finally:
                for page, _ in pages:
                    try:
                        page.close()
                    except:
                        pass
        
        return results


    def scrape_users(self, query, limit=50, source_type='search', continue_scrolling=False, exclude_users=None):
        """Scrape user profiles from search, followers, or following.
        
        Args:
            query: Search keyword or user URL/username
            limit: Number of users to scrape
            source_type: 'search', 'followers', or 'following'
            continue_scrolling: If True, continues from current page position instead of navigating
            exclude_users: Set of user URLs to exclude (already scraped)
        """
        if not self.page:
            return []
        
        if exclude_users is None:
            exclude_users = set()
            
        results = set()
        try:
            # Only navigate if NOT continuing from previous scroll
            if not continue_scrolling:
                if source_type == 'search':
                    # Search for people by keyword
                    print(f"Searching for users with keyword: {query}")
                    self.page.goto(f"https://www.pinterest.com/search/people/?q={query}", timeout=60000, wait_until="domcontentloaded")
                    time.sleep(3)  # Wait for dynamic content
                    
                elif source_type == 'followers':
                    # Navigate to user's followers
                    if query.startswith('http'):
                        username = query.rstrip('/').split('/')[-1]
                    else:
                        username = query
                        
                    print(f"Gathering followers of user: {username}")
                    url = f"https://www.pinterest.com/{username}/_followers/"
                    self.page.goto(url, timeout=60000, wait_until="domcontentloaded")
                    time.sleep(3)
                    
                elif source_type == 'following':
                    # Navigate to user's following
                    if query.startswith('http'):
                        username = query.rstrip('/').split('/')[-1]
                    else:
                        username = query
                        
                    print(f"Gathering following of user: {username}")
                    url = f"https://www.pinterest.com/{username}/_following/"
                    self.page.goto(url, timeout=60000, wait_until="domcontentloaded")
                    time.sleep(3)
                
                print("Starting to scrape users...")
            else:
                print(f"Continuing to scrape from current position (need {limit} more)...")
            
            # Scroll and collect user profiles
            last_height = 0
            scroll_attempts = 0
            max_scroll_attempts = 30  # Increased for continuation mode
            
            while len(results) < limit and scroll_attempts < max_scroll_attempts:
                # Get user profile links
                # Look for profile links that match Pinterest user URL pattern
                links = self.page.query_selector_all('a[href]')
                
                for link in links:
                    href = link.get_attribute('href')
                    if href:
                        # Clean and validate user profile URLs
                        # User profiles are typically: /username/ or https://pinterest.com/username/
                        if href.startswith('/') and href.count('/') >= 2:
                            # Remove leading slash and trailing slash for checking
                            parts = href.strip('/').split('/')
                            # Valid user profile: single segment without special chars
                            if len(parts) == 1 and parts[0] and \
                               '/pin/' not in href and '/search/' not in href and \
                               '/_' not in href and not parts[0].startswith('_'):
                                user_url = f"https://www.pinterest.com/{parts[0]}/"
                                # Skip if already in exclude list
                                if user_url not in exclude_users:
                                    results.add(user_url)
                                
                                if len(results) >= limit:
                                    break
                        elif href.startswith('http') and 'pinterest.com/' in href:
                            # Extract from full URL
                            try:
                                path = href.split('pinterest.com/')[-1]
                                parts = path.strip('/').split('/')
                                if len(parts) == 1 and parts[0] and \
                                   '/pin/' not in href and '/search/' not in href and \
                                   '/_' not in href and not parts[0].startswith('_'):
                                    user_url = f"https://www.pinterest.com/{parts[0]}/"
                                    # Skip if already in exclude list
                                    if user_url not in exclude_users:
                                        results.add(user_url)
                                    
                                    if len(results) >= limit:
                                        break
                            except:
                                continue
                
                # Scroll - detect if we're in a popup/modal (for followers/following)
                # Pinterest shows followers/following in a modal overlay
                scroll_container = None
                
                try:
                    # Try to find the modal/popup container
                    # Pinterest uses: <div aria-label="Followers" aria-modal="true" role="dialog">
                    modal_selectors = [
                        'div[role="dialog"][aria-modal="true"]',  # Exact Pinterest modal
                        'div[aria-label*="ollower"]',  # Followers/Following
                        'div[aria-label*="ollowing"]',
                        '[role="dialog"]',
                        '[data-test-id="modal"]',
                        'div[class*="Modal"]'
                    ]
                    
                    for selector in modal_selectors:
                        modal = self.page.query_selector(selector)
                        if modal and modal.is_visible():
                            # The dialog itself might not be scrollable, but an inner div is.
                            # Look for common scrollable containers inside the modal
                            potential_scrollers = [
                                modal,  # The modal itself
                                modal.query_selector('[data-test-id="profile-followers-feed"]'),
                                modal.query_selector('div[style*="max-height"]'),
                                modal.query_selector('div[style*="overflow"]'),
                                modal.query_selector('[role="list"]'), # Sometimes we need to scroll the parent of this
                            ]
                            
                            for container in potential_scrollers:
                                if not container:
                                    continue
                                    
                                try:
                                    # Check if this specific element is scrollable
                                    scroll_height = container.evaluate("el => el.scrollHeight")
                                    client_height = container.evaluate("el => el.clientHeight")
                                    
                                    # Also check if it has a parent that is the real scroller (common in virtual lists)
                                    if scroll_height <= client_height:
                                         parent = container.evaluate_handle("el => el.parentElement")
                                         p_scroll = parent.evaluate("el => el.scrollHeight")
                                         p_client = parent.evaluate("el => el.clientHeight")
                                         if p_scroll > p_client:
                                             scroll_container = parent
                                             print(f"Found scrollable modal parent container")
                                             break

                                    if scroll_height > client_height:
                                        scroll_container = container
                                        print(f"Found scrollable container inside modal")
                                        break
                                except:
                                    continue
                            
                            if scroll_container:
                                break
                            
                            # If we found the modal but no inner scroller, assume modal might become scrollable
                            # or use it as fallback
                            if not scroll_container:
                                print("Using modal as fallback scroll container")
                                scroll_container = modal
                                break
                except Exception as e:
                    print(f"Error finding modal: {e}")
                
                # Scroll either the modal or the main page
                if scroll_container:
                    # Scroll within the modal
                    try:
                        scroll_container.evaluate("el => el.scrollTop = el.scrollHeight")
                        time.sleep(2)
                        new_height = scroll_container.evaluate("el => el.scrollHeight")
                    except:
                        # Fallback to main page scroll
                        self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        time.sleep(2)
                        new_height = self.page.evaluate("document.body.scrollHeight")
                else:
                    # No modal found, scroll main page
                    self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(2)
                    new_height = self.page.evaluate("document.body.scrollHeight")
                
                if new_height == last_height:
                    scroll_attempts += 1
                else:
                    scroll_attempts = 0
                last_height = new_height
                
            return list(results)[:limit]
        except Exception as e:
            print(f"Error scraping users: {e}")
            return list(results)
    
    def follow_user(self, user_url, skip_check=None):
        """Follow a Pinterest user with UI check and DB fallback."""
        if not self.page:
            return False, "Browser not initialized"
        
        try:
            print(f"Following user: {user_url}")
            self.page.goto(user_url, timeout=60000, wait_until="domcontentloaded")
            time.sleep(3)
            
            # Priority 1: UI Check for existing follow
            already_followed = False
            already_followed_selectors = [
                'button[data-test-id="user-following-button"]',
                'button:has-text("Following")',
                'button:has-text("Unfollow")'
            ]
            
            for selector in already_followed_selectors:
                btn = self.page.query_selector(selector)
                if btn and btn.is_visible():
                    already_followed = True
                    break
            
            if already_followed:
                print(f"UI Check: Already following")
                return True, "Already following (UI)"
            
            # Priority 2: Database Check Fallback
            if skip_check and skip_check(user_url):
                print(f"DB Check: Already following (fallback)")
                return True, "Already following (DB)"
            
            # Priority 3: Perform Follow
            try:
                # Pinterest follow button selectors
                follow_button = self.page.wait_for_selector('button[data-test-id="user-follow-button"]', timeout=3000)
                if follow_button:
                    # Final check of text to be safe
                    btn_text = follow_button.inner_text().lower()
                    if 'following' in btn_text or 'unfollow' in btn_text:
                         return True, "Already following (UI)"
                    
                    follow_button.click()
                    time.sleep(2)
                    print("Following successfully")
                    return True, "Following successfully"
            except:
                # Try alternative selector
                buttons = self.page.query_selector_all('button')
                for btn in buttons:
                    if not btn.is_visible(): continue
                    text = btn.inner_text().lower()
                    if text == 'follow':
                        btn.click()
                        time.sleep(2)
                        print("Following successfully (alt method)")
                        return True, "Following successfully"
            
            print("Could not find follow button")
            return False, "Follow button not found"
            
        except Exception as e:
            print(f"Error following user: {e}")
            return False, f"Error: {str(e)}"
    
    def unfollow_user(self, user_url):
        """Unfollow a Pinterest user."""
        if not self.page:
            return False
        
        try:
            print(f"Unfollowing user: {user_url}")
            self.page.goto(user_url, timeout=60000, wait_until="domcontentloaded")
            time.sleep(2)
            
            # Look for unfollow button (following button)
            try:
                # Pinterest following button selectors
                following_button = self.page.wait_for_selector('button[data-test-id="user-following-button"]', timeout=5000)
                if following_button:
                    following_button.click()
                    time.sleep(1)
                    print("Unfollowed successfully")
                    return True
            except:
                # Try alternative selector
                try:
                    buttons = self.page.query_selector_all('button')
                    for btn in buttons:
                        text = btn.inner_text().lower()
                        if 'following' in text:
                            btn.click()
                            time.sleep(1)
                            print("Unfollowed successfully (alt method)")
                            return True
                except:
                    pass
            
            print("Could not find unfollow button (user might not be followed)")
            return False
            
        except Exception as e:
            print(f"Error unfollowing user: {e}")
            return False
    
    def check_if_following_back(self, user_url):
        """Check if a user is following the current account back."""
        if not self.page:
            return False
        
        try:
            # Navigate to the user's following page
            username = user_url.rstrip('/').split('/')[-1]
            following_url = f"https://www.pinterest.com/{username}/_following/"
            
            print(f"Checking if {username} follows back...")
            self.page.goto(following_url, timeout=60000, wait_until="domcontentloaded")
            time.sleep(2)
            
            # Get current account username
            # This would require knowing the current logged-in username
            # For now, we'll return False (not following back) as a safe default
            # This can be enhanced by scraping the current user's profile first
            
            # TODO: Implement proper mutual follow detection
            # For now, return False to be safe
            return False
            
        except Exception as e:
            print(f"Error checking follow status: {e}")
            return False
    
    def comment_on_pin(self, pin_url, comment_text):
        """Post a comment on a Pinterest pin."""
        if not self.page:
            return False
        
        try:
            print(f"Commenting on pin: {pin_url}")
            self.page.goto(pin_url, timeout=60000, wait_until="domcontentloaded")
            time.sleep(5)
            
            # Scroll to comment section
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            time.sleep(3)
            
            # Click comments area to activate it
            try:
                print("Looking for Comments section to click...")
                comment_section = self.page.query_selector('div:has-text("Comment")')
                if comment_section:
                    comment_section.click()
                    time.sleep(2)
                    print("Clicked Comments section")
            except Exception as e:
                print(f"Could not click comments section: {e}")
            
            # Find the contenteditable div with aria-label="Add a comment"
            print("Looking for comment input (contenteditable div)...")
            try:
                comment_input = self.page.query_selector('div[contenteditable="true"][aria-label="Add a comment"]')
                
                if not comment_input:
                    print("Could not find contenteditable div, trying alternative...")
                    comment_input = self.page.query_selector('div[contenteditable="true"]')
                
                if comment_input and comment_input.is_visible():
                    print("Found comment input, clicking...")
                    comment_input.click()
                    time.sleep(2)
                    
                    print(f"Typing comment: {comment_text[:30]}...")
                    # Pinterest uses contenteditable, use type with longer delay
                    comment_input.type(comment_text, delay=100)
                    time.sleep(3)
                    
                    print("Looking for Post button with aria-label='Post'...")
                    # Use the EXACT selector from user's inspection
                    try:
                        # Primary method: Look for button with aria-label="Post"
                        post_button = self.page.query_selector('button[aria-label="Post"]')
                        
                        if post_button and post_button.is_visible():
                            print("Found Post button via aria-label, clicking...")
                            post_button.click()
                            time.sleep(5)
                            print("Comment posted successfully!")
                            return True
                        else:
                            print("Post button not found or not visible via aria-label")
                            
                            # Fallback: Look for button with class euRXRl
                            post_button = self.page.query_selector('button.euRXRl')
                            if post_button and post_button.is_visible():
                                print("Found Post button via class euRXRl, clicking...")
                                post_button.click()
                                time.sleep(5)
                                print("Comment posted successfully!")
                                return True
                            else:
                                print("Post button not found via class either")
                                
                    except Exception as e:
                        print(f"Error finding Post button: {e}")
                    
                    # Last resort fallback - search all buttons
                    print("Trying fallback: searching all visible buttons...")
                    all_buttons = self.page.query_selector_all('button')
                    
                    for btn in all_buttons:
                        try:
                            if btn.is_visible():
                                aria_label = btn.get_attribute('aria-label') or ''
                                btn_class = btn.get_attribute('class') or ''
                                
                                # Check for Post in aria-label or specific class
                                if 'post' in aria_label.lower() or 'euRXRl' in btn_class:
                                    print(f"Found Post button (fallback): aria='{aria_label}', class='{btn_class}'")
                                    btn.click()
                                    time.sleep(5)
                                    print("Comment posted successfully!")
                                    return True
                        except Exception as e:
                            continue
                    
                    # No button found - fail
                    print("ERROR: Could not find Post button. Comment was typed but not posted.")
                    return False
            except Exception as e:
                print(f"Error finding or clicking comment input: {e}")
                return False
                
        except Exception as e:
            print(f"Error commenting on pin: {e}")
            return False
            
    def repin_pin(self, pin_url, board_name, auto_like=False, skip_check=None):
        """Repin a pin to a specific board - with UI check and DB fallback"""
        if not self.page:
            return False, "Browser not initialized"
            
        try:
            print(f"Repinning pin: {pin_url} to board: {board_name}")
            
            # STEP 1: Navigate to pin page
            print("Step 1: Navigating to pin...")
            self.page.goto(pin_url, timeout=60000, wait_until="domcontentloaded")
            time.sleep(5) 
            
            # Priority 1: UI CHECK: Check if the main button already says "Saved"
            save_btn_check = self.page.query_selector('button[data-test-id="PinBetterSaveDropdown"]') or \
                            self.page.query_selector('button[aria-label*="Select a board"]')
            
            main_save_btn = self.page.query_selector('button[data-test-id="pdp-save-button"]')
            if main_save_btn:
                btn_text = main_save_btn.inner_text().lower()
                if 'saved' in btn_text:
                    print(f"UI Check: Pin already saved (Main button)")
                    return True, "Already saved to a board (UI)"

            # Priority 2: Database Check Fallback
            if skip_check and skip_check(pin_url):
                print(f"DB Check: Pin already repinned recently (fallback)")
                return True, "Already repinned recently (DB)"

            # STEP 2: Click the dropdown button to open board selector modal
            print("Step 2: Opening board selector modal...")
            dropdown_btn = save_btn_check
            
            if not dropdown_btn:
                print("✗ Could not find board selector button")
                return False, "Board selector button not found"
            
            dropdown_btn.click(force=True)
            print("✓ Clicked dropdown button")
            time.sleep(3)
            
            # STEP 3: Find search input and type board name
            print(f"Step 3: Searching for board '{board_name}'...")
            search_input = self.page.query_selector('input#pickerSearchField')
            if not search_input:
                search_input = self.page.query_selector('input[aria-label="Search through your boards"]')
            
            if not search_input:
                print("✗ Could not find search input")
                return False, "Search input not found"
            
            search_input.click()
            self.page.keyboard.press('Control+A')
            self.page.keyboard.press('Backspace')
            search_input.fill(board_name)
            print(f"✓ Typed '{board_name}' in search box")
            time.sleep(5) # Give results time to settle
            
            # STEP 4: Click on the board result
            print("Step 4: Clicking on board result...")
            
            # We strictly prioritize standard board rows (boardWithoutSection)
            # This completely avoids the 'Create board' footer which has a different ID
            rows = self.page.query_selector_all('div[data-test-id="boardWithoutSection"]')
            print(f"Found {len(rows)} potential board rows")
            
            target_btn = None
            for row in rows:
                if not row.is_visible(): continue
                
                # Check for title match inside the row
                title_elem = row.query_selector('[title]')
                row_text = ""
                if title_elem:
                    row_text = title_elem.get_attribute('title') or ""
                
                if not row_text:
                    row_text = row.inner_text()
                
            # Precision matching logic
            # 1. Normalize target: lower case + strip extra spaces
            clean_target = board_name.lower().strip()
            
            target_btn = None
            for row in rows:
                if not row.is_visible(): continue
                
                # Check for "Saved" text inside the row - THIS IS THE NEW GRANULAR CHECK
                # If the pin is already on this board, Pinterest often shows a 'Saved' label or different button text
                row_text_full = row.inner_text().lower()
                if "saved" in row_text_full:
                    print(f"  ✓ UI Check: Pin already saved to board '{board_name}' (found 'saved' text in row)")
                    return True, f"Already saved to {board_name} (UI Granular)"

                # Check for title match inside the row
                title_elem = row.query_selector('[title]')
                row_text = ""
                if title_elem:
                    row_text = title_elem.get_attribute('title') or ""
                
                if not row_text:
                    row_text = row.inner_text()
                
                # 2. Normalize row text
                clean_row = row_text.lower().strip()
                
                # 3. Match logic: Precise match OR aggressive fallback match
                is_match = (clean_target == clean_row)
                
                if not is_match:
                    # Fallback: aggressive check (strip all non-alphanumeric) for legacy compatibility
                    import re
                    agg_target = re.sub(r'[^a-zA-Z0-9]', '', clean_target)
                    agg_row = re.sub(r'[^a-zA-Z0-9]', '', clean_row)
                    if agg_target == agg_row and agg_target != "":
                        is_match = True

                if is_match or clean_target in clean_row or clean_row in clean_target:
                    print(f"  ✓ Match found: '{row_text}'")
                    # Find the specific 'Save' button inside this row
                    # Markup: <button aria-label="save" ...>
                    save_btn = row.query_selector('button[aria-label="save"]')
                    if save_btn:
                        btn_text = save_btn.inner_text().lower()
                        if "saved" in btn_text:
                             print(f"  ✓ UI Check: Save button says 'Saved' for board '{board_name}'")
                             return True, f"Already saved to {board_name} (UI Button)"
                        
                        print("    Found 'save' button inside row, targeting it...")
                        target_btn = save_btn
                    else:
                        print("    'save' button not found, targeting row's role=button parent...")
                        # The row is often wrapped in a role=button div
                        parent_btn = row.query_selector_all('xpath=ancestor::div[@role="button"]')
                        target_btn = parent_btn[-1] if parent_btn else row
                    break

            if not target_btn:
                # Fallback to suggestions if no standard row matched
                suggestions = self.page.query_selector_all('div[data-test-id="board-suggestion-row-button"]')
                for sug in suggestions:
                    if not sug.is_visible(): continue
                    sug_text = sug.inner_text().lower()
                    if board_name.lower().strip() in sug_text:
                        print(f"  ✓ Match found in suggestion: '{sug_text.strip()}'")
                        target_btn = sug
                        break

            if target_btn:
                target_btn.scroll_into_view_if_needed()
                time.sleep(0.5)
                # Use evaluate click to bypass any interception
                self.page.evaluate('(el) => el.click()', target_btn)
                print("✓ Clicked result successfully")
                time.sleep(5) # Wait for save to complete
                return self._after_repin_actions(auto_like, board_name)
            
            print("✗ No matching board found.")
            return False, "Board match failed"
                
        except Exception as e:
            print(f"Error in flow: {e}")
            import traceback
            traceback.print_exc()
            return False, f"Error: {e}"

    def _after_repin_actions(self, auto_like, board_name):
        """Helper to handle Like button after a successful save"""
        if auto_like:
            print("Step 5: Clicking Like (Heart) button...")
            time.sleep(2) # Breath after save modal closes
            
            like_btn = self.page.query_selector('button[data-test-id="react-button"]')
            if like_btn and like_btn.is_visible():
                # Check if already liked to avoid 'unliking'
                # Liked buttons usually have 'Remove reaction' in aria-label
                aria = (like_btn.get_attribute('aria-label') or '').lower()
                if 'remove' in aria or 'unreact' in aria:
                    print("  Pin is already liked, skipping click.")
                else:
                    # Double check SVG path M14.1 5.6
                    html = like_btn.inner_html()
                    if 'M14.1 5.6' in html:
                        print("  ✓ Found Heart button, performing simulated click...")
                        like_btn.scroll_into_view_if_needed()
                        like_btn.hover()
                        time.sleep(0.8)
                        self.page.evaluate('(el) => el.click()', like_btn)
                        print("✓ Successfully Liked")
                        time.sleep(2)
            else:
                 print("  ⚠ Like button not found or not visible")
        
        print(f"✓✓✓ Successfully processed pin to '{board_name}'!")
        return True, f"Repinned to '{board_name}'"

    def upload_pin(self, image_path, board_name, title, description, link="", tags=""):
        """Upload a new pin to Pinterest - FOOLPROOF VERSION V7 (Proven Board Selection)"""
        if not self.page:
            return False
            
        try:
            print(f"Uploading pin: {title} to board: {board_name}")
            
            # STEP 0: Navigate to Pinterest create page
            self.page.goto("https://www.pinterest.com/pin-creation-tool/", timeout=60000, wait_until="domcontentloaded")
            time.sleep(5)
            
            # STEP 1: Handle blocking banners and find file input
            file_input = self.page.query_selector('input[type="file"]')
            if not file_input:
                print("Could not find file input. Checking for blocking banners or refreshing...")
                close_btns = self.page.query_selector_all('button[aria-label="Close"], button[data-test-id="cancel-button"], div[role="button"][aria-label="Close"]')
                for btn in close_btns:
                    if btn.is_visible():
                        print("Found blocking element, closing it...")
                        btn.click(force=True)
                        time.sleep(3)
                        break
                
                file_input = self.page.query_selector('input[type="file"]')
                if not file_input:
                    print("No obvious banner. Refreshing page...")
                    self.page.reload(wait_until="domcontentloaded")
                    time.sleep(7)
                    file_input = self.page.query_selector('input[type="file"]')
            
            if not file_input:
                print("✗ Error: Could not find file input area.")
                return False
                
            print("✓ Found file input, uploading image...")
            file_input.set_input_files(image_path)
            print("Image file selected, waiting for upload and form to load...")
            time.sleep(12) 
            
            # Refresh input list after transition
            all_text_inputs = self.page.query_selector_all('input[type="text"], input[type="url"], textarea, div[contenteditable="true"]')
            print(f"Found {len(all_text_inputs)} potential input fields")

            # STEP 2: Fill Title
            title_filled = False
            for inp in all_text_inputs:
                try:
                    if not inp.is_visible(): continue
                    placeholder = (inp.get_attribute('placeholder') or '').lower()
                    aria = (inp.get_attribute('aria-label') or '').lower()
                    if any(word in placeholder or word in aria for word in ['title', 'add your title']):
                        print("  Filling Title...")
                        inp.click(force=True)
                        self.page.keyboard.press('Control+A')
                        self.page.keyboard.press('Backspace')
                        inp.type(title, delay=35)
                        title_filled = True
                        time.sleep(3) 
                        break
                except: continue
            
            # STEP 3: Fill Description
            description_filled = False
            if description:
                print("  Filling Description...")
                desc_editor = self.page.query_selector('.public-DraftEditor-content[aria-label*="description"]') or \
                              self.page.query_selector('.public-DraftEditor-content') or \
                              self.page.query_selector('.public-DraftEditorPlaceholder-inner')
                
                if desc_editor:
                    desc_editor.click(force=True)
                    time.sleep(1)
                    self.page.keyboard.press('Control+A')
                    self.page.keyboard.press('Backspace')
                    self.page.keyboard.type(description, delay=35)
                    description_filled = True
                    time.sleep(3) 
                else:
                    print("  ⚠ Could not find description editor.")

            # STEP 4: Fill Link
            if link:
                print("  Filling Link...")
                for inp in all_text_inputs:
                    try:
                        if not inp.is_visible(): continue
                        placeholder = (inp.get_attribute('placeholder') or '').lower()
                        aria = (inp.get_attribute('aria-label') or '').lower()
                        if any(word in placeholder or word in aria for word in ['link', 'destination', 'website']):
                            inp.click(force=True)
                            self.page.keyboard.press('Control+A')
                            self.page.keyboard.press('Backspace')
                            inp.type(link, delay=25)
                            time.sleep(3) 
                            break
                    except: continue

            # STEP 5: Fill Tags
            if tags:
                print("  Filling Tags...")
                for inp in all_text_inputs:
                    try:
                        if not inp.is_visible(): continue
                        placeholder = (inp.get_attribute('placeholder') or '').lower()
                        aria = (inp.get_attribute('aria-label') or '').lower()
                        if any(word in placeholder or word in aria for word in ['tag', 'keyword']):
                            inp.click(force=True)
                            inp.type(tags, delay=25)
                            time.sleep(3) 
                            break
                    except: continue

            # STEP 6: Select Board (Using PROVEN REPIN LOGIC)
            board_selected = False
            print(f"  Step 6: Selecting board: '{board_name}'")
            
            board_trigger = self.page.query_selector('[data-test-id="board-dropdown-select-button"]')
            if not board_trigger:
                # Fallback search for any button with 'board' text
                btns = self.page.query_selector_all('button')
                for b in btns:
                    if b.is_visible() and ('board' in b.inner_text().lower() or 'choose' in b.inner_text().lower()):
                        board_trigger = b
                        break
            
            if board_trigger:
                print("    Opening board selector...")
                self.page.evaluate('(el) => el.click()', board_trigger)
                time.sleep(5) 
                
                search_box = self.page.query_selector('#pickerSearchField')
                if search_box:
                    print(f"    Searching for: '{board_name}'")
                    search_box.fill(board_name)
                    time.sleep(5) 
                
                # GET ALL POTENTIAL ROWS (Using ID provided in markup)
                rows = self.page.query_selector_all('div[data-test-id="boardWithoutSection"]')
                print(f"    Found {len(rows)} potential board rows")
                
                target_btn = None
                for row in rows:
                    if not row.is_visible(): continue
                    
                    # Exact robustness logic from repin_pin
                    title_elem = row.query_selector('[title]')
                    row_text = ""
                    if title_elem:
                        row_text = title_elem.get_attribute('title') or ""
                    
                    if not row_text:
                        row_text = row.inner_text()
                    
                    # Precision matching logic from repin_pin
                    # 1. Normalize target: lower case + strip extra spaces
                    clean_target = board_name.lower().strip()
                    
                    # 2. Normalize row text
                    clean_row = row_text.lower().strip()
                    
                    # 3. Match logic: Precise match OR aggressive fallback match
                    is_match = (clean_target == clean_row)
                    
                    if not is_match:
                        # Fallback: aggressive check (strip all non-alphanumeric)
                        import re
                        agg_target = re.sub(r'[^a-zA-Z0-9]', '', clean_target)
                        agg_row = re.sub(r'[^a-zA-Z0-9]', '', clean_row)
                        if agg_target == agg_row and agg_target != "":
                            is_match = True

                    if is_match or clean_target in clean_row or clean_row in clean_target:
                        print(f"    ✓ Robust Match: '{row_text}'")
                        # In upload dropdown, the clickable button is the inner role="button"
                        target_btn = row.query_selector('[role="button"]') or row
                        break
                
                if target_btn:
                    print(f"    Attempting final click on result...")
                    # Combine physical simulations
                    target_btn.hover()
                    time.sleep(1)
                    self.page.evaluate('(el) => el.click()', target_btn)
                    board_selected = True
                    print(f"    ✓ Successfully selected board!")
                    time.sleep(5)
                else:
                    print("    ✗ Error: No board row matched the search result")
            else:
                print("    ✗ Error: Could not find board dropdown button")
            
            if not board_selected:
                print("✗ ERROR: Board selection failed. Aborting.")
                return False

            # STEP 7: Click Publish
            publish_btn = self.page.query_selector('button[data-test-id="board-dropdown-save-button"]')
            if not publish_btn:
                all_buttons = self.page.query_selector_all('button')
                for btn in all_buttons:
                    if btn.is_visible() and btn.is_enabled():
                        text = btn.inner_text().lower()
                        if 'publish' in text or 'save' in text:
                            publish_btn = btn
                            break
            
            if publish_btn:
                print("✓ Clicking Publish...")
                publish_btn.click(force=True)
                time.sleep(15) 
                print("✓✓✓ Pin successfully uploaded!")
                return True
            else:
                print("✗ ERROR: Publish button not found.")
                return False
                
        except Exception as e:
            print(f"Error in upload sequence: {e}")
            import traceback
            traceback.print_exc()
            return False

    # ==================== Pin Detection Methods ====================
    
    def is_video_pin(self, pin_url):
        """
        Check if pin contains video content.
        
        Args:
            pin_url (str): URL of the pin to check
            
        Returns:
            bool: True if pin is a video, False otherwise
        """
        if not self.page:
            return False
            
        try:
            # Navigate if not already on the pin page
            current_url = self.page.url
            if pin_url not in current_url:
                self.page.goto(pin_url, timeout=30000, wait_until="domcontentloaded")
                time.sleep(2)
            
            # Strategy 1: Look for video element
            video_elem = self.page.query_selector('video')
            if video_elem and video_elem.is_visible():
                return True
            
            # Strategy 2: Look for video player data attribute
            video_player = self.page.query_selector('[data-test-id*="video"]')
            if video_player:
                return True
            
            # Strategy 3: Check for GIF or animated content indicators
            gif_indicator = self.page.query_selector('[data-test-id="animated-image"]')
            if gif_indicator:
                return True  # Treat GIFs as videos for filtering purposes
            
            return False
            
        except Exception as e:
            print(f"Error checking if pin is video: {e}")
            return False  # Safe default: assume not video
    
    def get_pin_author(self, pin_url):
        """
        Get the username of the pin creator.
        
        Args:
            pin_url (str): URL of the pin to check
            
        Returns:
            str: Username of pin author, or empty string if not found
        """
        if not self.page:
            return ""
            
        try:
            # Navigate if not already on the pin page
            current_url = self.page.url
            if pin_url not in current_url:
                self.page.goto(pin_url, timeout=30000, wait_until="domcontentloaded")
                time.sleep(2)
            
            # Strategy 1: Look for creator profile link
            profile_link = self.page.query_selector('a[data-test-id="creator-profile-link"]')
            if profile_link:
                href = profile_link.get_attribute('href')
                if href:
                    # Extract username from URL like /username/
                    parts = href.strip('/').split('/')
                    if parts:
                        return parts[-1]
            
            # Strategy 2: Look for any profile link in pin details
            all_links = self.page.query_selector_all('a[href*="pinterest.com/"]')
            for link in all_links:
                href = link.get_attribute('href') or ''
                # Profile links look like: /username/ (not /pin/, /search/, etc.)
                if '/' in href and '/pin/' not in href and '/search/' not in href:
                    parts = href.strip('/').split('/')
                    if len(parts) >= 1 and parts[-1]:
                        username = parts[-1]
                        # Skip known non-username patterns
                        if username not in ['me', 'search', 'pin', 'today', 'explore']:
                            return username
            
            return ""
            
        except Exception as e:
            print(f"Error getting pin author: {e}")
            return ""
    
    def is_product_pin(self, pin_url):
        """
        Check if pin is marked as a product/shopping pin.
        
        Args:
            pin_url (str): URL of the pin to check
            
        Returns:
            bool: True if pin is a product, False otherwise
        """
        if not self.page:
            return False
            
        try:
            # Navigate if not already on the pin page
            current_url = self.page.url
            if pin_url not in current_url:
                self.page.goto(pin_url, timeout=30000, wait_until="domcontentloaded")
                time.sleep(2)
            
            # Strategy 1: Look for price indicator
            price_elem = self.page.query_selector('[data-test-id="price"]')
            if price_elem and price_elem.is_visible():
                return True
            
            # Strategy 2: Look for shopping/product tag
            product_tag = self.page.query_selector('[data-test-id="product-tag"]')
            if product_tag:
                return True
            
            # Strategy 3: Check for "Shop" or "Buy" buttons
            shop_buttons = self.page.query_selector_all('button, a')
            for btn in shop_buttons:
                text = (btn.inner_text() or '').lower()
                if any(word in text for word in ['shop', 'buy', 'purchase', 'checkout']):
                    if btn.is_visible():
                        return True
            
            # Strategy 4: Look for price in text (e.g., "$19.99")
            page_text = self.page.inner_text('body')
            import re
            if re.search(r'\$\d+\.?\d*', page_text):
                # Has price, likely a product
                return True
            
            return False
            
        except Exception as e:
            print(f"Error checking if pin is product: {e}")
            return False
    
    def has_destination_link(self, pin_url):
        """
        Check if pin has an outbound destination link.
        
        Args:
            pin_url (str): URL of the pin to check
            
        Returns:
            bool: True if pin has destination link, False otherwise
        """
        if not self.page:
            return False
            
        try:
            # Navigate if not already on the pin page
            current_url = self.page.url
            if pin_url not in current_url:
                self.page.goto(pin_url, timeout=30000, wait_until="domcontentloaded")
                time.sleep(2)
            
            # Strategy 1: Look for destination link button
            link_button = self.page.query_selector('a[data-test-id="pin-link-button"]')
            if link_button and link_button.is_visible():
                return True
            
            # Strategy 2: Look for external link indicator
            external_link = self.page.query_selector('[data-test-id="external-link"]')
            if external_link:
                return True
            
            # Strategy 3: Check for "Visit" button/link
            visit_buttons = self.page.query_selector_all('a, button')
            for btn in visit_buttons:
                text = (btn.inner_text() or '').lower()
                aria_label = (btn.get_attribute('aria-label') or '').lower()
                if 'visit' in text or 'visit' in aria_label:
                    if btn.is_visible():
                        href = btn.get_attribute('href')
                        # Check if it's an external link (not pinterest.com)
                        if href and 'pinterest.com' not in href:
                            return True
            
            return False
            
        except Exception as e:
            print(f"Error checking destination link: {e}")
            return False
    
    
    def get_pin_data(self, pin_url):
        """
        Get comprehensive pin data for filtering.
        
        Args:
            pin_url (str): URL of the pin
            
        Returns:
            dict: Pin data with keys: is_video, author, is_product, has_link, description, title, repins
        """
        if not self.page:
            return None
            
        try:
            # Navigate to pin
            self.page.goto(pin_url, timeout=30000, wait_until="domcontentloaded")
            time.sleep(2)
            
            # Collect pin data using detection methods
            pin_data = {
                'is_video': self.is_video_pin(pin_url),
                'author': self.get_pin_author(pin_url),
                'is_product': self.is_product_pin(pin_url),
                'has_link': self.has_destination_link(pin_url),
                'description': '',
                'title': '',
                'repins': 0
            }
            
            # Get title
            try:
                title_elem = self.page.query_selector('h1')
                if title_elem:
                    pin_data['title'] = title_elem.inner_text() or ''
            except:
                pass
            
            # Get description
            try:
                desc_elem = self.page.query_selector('[data-test-id="pin-description"]')
                if desc_elem:
                    pin_data['description'] = desc_elem.inner_text() or ''
            except:
                pass
            
            # Get repin count
            try:
                # Look for saves/repins count
                stats = self.page.query_selector_all('div, span')
                for stat in stats:
                    text = stat.inner_text() or ''
                    if 'saves' in text.lower() or 'repins' in text.lower():
                        import re
                        match = re.search(r'(\d+(?:,\d+)*(?:K|M)?)', text)
                        if match:
                            count_str = match.group(1).replace(',', '')
                            if 'K' in count_str:
                                pin_data['repins'] = int(float(count_str.replace('K', '')) * 1000)
                            elif 'M' in count_str:
                                pin_data['repins'] = int(float(count_str.replace('M', '')) * 1000000)
                            else:
                                pin_data['repins'] = int(count_str)
                            break
            except:
                pass
            
            return pin_data
            
        except Exception as e:
            print(f"Error getting pin data: {e}")
            return None
    
    def get_my_boards(self):
        """Fetch list of user's boards."""
        if not self.page:
            return []
        
        try:
            print("Fetching user boards...")
            # Navigate to user's profile
            self.page.goto("https://www.pinterest.com/me/", timeout=60000, wait_until="domcontentloaded")
            time.sleep(3)
            
            # Click on "Saved" tab to show boards
            try:
                print("Looking for Saved tab...")
                # Look for Saved tab/link
                saved_links = self.page.query_selector_all('a, div[role="link"]')
                for link in saved_links:
                    text = link.inner_text().lower() if link.inner_text() else ''
                    if 'saved' in text:
                        print("Clicking Saved tab")
                        link.click()
                        time.sleep(3)
                        break
            except Exception as e:
                print(f"Could not click Saved tab: {e}")
            
            # Scroll to load boards
            self.page.evaluate("window.scrollTo(0, 800)")
            time.sleep(3)
            
            boards = []
            
            # Method 1: Look for board cards with data-test-id (MOST ACCURATE DISPLAY NAME)
            try:
                print("Method 1: Looking for board card elements...")
                board_cards = self.page.query_selector_all('div[data-test-id="board-card"], div[data-test-id="board"]')
                
                for card in board_cards[:50]:  # Limit to first 50
                    try:
                        # Try multiple selectors for board name within the card
                        name_elem = card.query_selector('h2, h3, div[data-test-id="board-name"], span[aria-label]')
                        if name_elem:
                            board_name = name_elem.inner_text().strip()
                            if board_name and board_name not in boards:
                                boards.append(board_name)
                    except:
                        continue
                
                if boards:
                    print(f"Found {len(boards)} boards via Method 1 (Cards)")
            except Exception as e:
                print(f"Method 1 failed: {e}")

            # Method 2: Get board names from visible text elements
            if len(boards) < 5:
                try:
                    print("Method 2: Extracting from heading elements...")
                    headings = self.page.query_selector_all('h2, h3')
                    
                    for heading in headings:
                        try:
                            board_name = heading.inner_text().strip()
                            # Filter out non-board text (like "1 Pin", "Profile", etc.)
                            if board_name and len(board_name) > 0 and len(board_name) < 50:
                                # Skip if it's just numbers, or contains common non-board phrases
                                skip_phrases = ['pin', 'board', 'following', 'follower', 'created', 'saved', 'profile']
                                if not any(phrase in board_name.lower() for phrase in skip_phrases):
                                    if board_name not in boards:
                                        boards.append(board_name)
                        except:
                            continue
                    
                    if boards:
                        print(f"Found {len(boards)} boards via Method 2 (Headings)")
                except Exception as e:
                    print(f"Method 2 failed: {e}")
            
            # Method 3: Look for board links in href (FALLBACK - SLUG BASED)
            if len(boards) < 5:
                try:
                    print("Method 3: Extracting from board URLs...")
                    all_links = self.page.query_selector_all('a[href]')
                    seen_names = set(boards)
                    
                    for link in all_links:
                        href = link.get_attribute('href')
                        if href and '/_saved' not in href and '/_created' not in href:
                            if '/pin/' not in href and '/search/' not in href and '/_' not in href:
                                parts = href.strip('/').split('/')
                                if len(parts) == 2:
                                    board_name_slug = parts[1]
                                    from urllib.parse import unquote
                                    # Fallback parsing: replaces - with space
                                    # We keep this as last resort because it loses punctuation like '
                                    board_name = unquote(board_name_slug).replace('-', ' ').title()
                                    
                                    if board_name and board_name not in seen_names:
                                        if not any(x in board_name.lower() for x in ['http', 'www', 'settings', 'notifications']):
                                            boards.append(board_name)
                                            seen_names.add(board_name)
                    
                    if boards:
                        print(f"Found {len(boards)} boards via Method 3 (URLs)")
                except Exception as e:
                    print(f"Method 3 failed: {e}")
            
            # If still no boards found, try scrolling and re-attempting
            if not boards:
                print("No boards found, trying to scroll and reload...")
                self.page.evaluate("window.scrollTo(0, 1500)")
                time.sleep(3)
                
                # Try method 1 again
                try:
                    all_links = self.page.query_selector_all('a[href]')
                    for link in all_links[:100]:
                        href = link.get_attribute('href')
                        if href:
                            parts = href.strip('/').split('/')
                            if len(parts) == 2 and '/pin/' not in href:
                                board_name = parts[1].replace('-', ' ').title()
                                if board_name and board_name not in boards:
                                    boards.append(board_name)
                except:
                    pass
            
            # Final fallback: return placeholder boards ONLY if truly no boards found
            if not boards:
                print("WARNING: Could not fetch any boards, returning placeholders")
                return ["My Board", "Inspiration", "Ideas", "Fashion", "Home Decor"]
            
            print(f"Successfully fetched {len(boards)} boards")
            return boards[:50]
            
        except Exception as e:
            print(f"Error fetching boards: {e}")
            import traceback
            traceback.print_exc()
            return ["My Board", "Inspiration", "Ideas"]  # Fallback
    
    # ==================== Pin Detection Methods ====================
    
    def is_video_pin(self, pin_url=None):
        """Check if current pin (or specified pin URL) is a video."""
        if not self.page:
            return False
        
        try:
            if pin_url:
                self.page.goto(pin_url, timeout=30000, wait_until="domcontentloaded")
                time.sleep(2)
            
            video_selectors = ['video', 'video[class*="video"]', 'div[data-test-id*="video"]']
            for selector in video_selectors:
                try:
                    elem = self.page.query_selector(selector)
                    if elem and elem.is_visible():
                        return True
                except:
                    continue
            return False
        except Exception as e:
            print(f"Error checking if video pin: {e}")
            return False
    
    def get_pin_author(self, pin_url=None):
        """Get the username of the pin's author/creator."""
        if not self.page:
            return ""
        
        try:
            if pin_url:
                self.page.goto(pin_url, timeout=30000, wait_until="domcontentloaded")
                time.sleep(2)
            
            author_selectors = [
                'div[data-test-id="creator-profile-image"] ~ div a',
                'a[data-test-id="creator-profile-link"]',
                'a[href*="/"][title]'
            ]
            
            for selector in author_selectors:
                try:
                    elem = self.page.query_selector(selector)
                    if elem:
                        href = elem.get_attribute('href')
                        if href and '/' in href:
                            username = href.strip('/').split('/')[-1]
                            if username and not username.startswith('pin'):
                                return username
                except:
                    continue
            return ""
        except Exception as e:
            print(f"Error getting pin author: {e}")
            return ""
    
    def has_link_in_description(self, pin_url=None):
        """Check if pin description contains a URL."""
        if not self.page:
            return False
        
        try:
            if pin_url:
                self.page.goto(pin_url, timeout=30000, wait_until="domcontentloaded")
                time.sleep(2)
            
            desc_selectors = [
                'div[data-test-id="pin-description"]',
                'div[class*="DescriptionText"]'
            ]
            
            description = ""
            for selector in desc_selectors:
                try:
                    elem = self.page.query_selector(selector)
                    if elem:
                        description = elem.inner_text() or ""
                        break
                except:
                    continue
            
            import re
            url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
            return bool(re.search(url_pattern, description))
        except Exception as e:
            print(f"Error checking description for links: {e}")
            return False
    
    def has_destination_link(self, pin_url=None):
        """Check if pin has a destination (outbound) link."""
        if not self.page:
            return False
        
        try:
            if pin_url:
                self.page.goto(pin_url, timeout=30000, wait_until="domcontentloaded")
                time.sleep(2)
            
            link_selectors = ['a[data-test-id="pin-link"]', 'a[href*="http"]']
            
            for selector in link_selectors:
                try:
                    links = self.page.query_selector_all(selector)
                    for link in links:
                        href = link.get_attribute('href') or ''
                        if href and 'http' in href and 'pinterest.com' not in href:
                            return True
                except:
                    continue
            return False
        except Exception as e:
            print(f"Error checking for destination link: {e}")
            return False
    
    def is_product_pin(self, pin_url=None):
        """Check if pin is a shopping/product pin."""
        if not self.page:
            return False
        
        try:
            if pin_url:
                self.page.goto(pin_url, timeout=30000, wait_until="domcontentloaded")
                time.sleep(2)
            
            product_indicators = [
                'div[data-test-id="price-value"]',
                'div[data-test-id="shopping-button"]',
                'button[aria-label*="Shop"]'
            ]
            
            for selector in product_indicators:
                try:
                    elem = self.page.query_selector(selector)
                    if elem and elem.is_visible():
                        return True
                except:
                    continue
            return False
        except Exception as e:
            print(f"Error checking if product pin: {e}")
            return False
    
    def get_pin_data(self, pin_url):
        """Extract comprehensive pin data including all characteristics."""
        if not self.page:
            return {}
        
        try:
            self.page.goto(pin_url, timeout=30000, wait_until="domcontentloaded")
            time.sleep(3)
            
            pin_data = {
                'url': pin_url,
                'author': self.get_pin_author(),
                'is_video': self.is_video_pin(),
                'is_product': self.is_product_pin(),
                'has_link': self.has_destination_link(),
                'description': '',
                'title': '',
                'repins': 0
            }
            
            try:
                desc_elem = self.page.query_selector('div[data-test-id="pin-description"]')
                if desc_elem:
                    pin_data['description'] = desc_elem.inner_text() or ''
            except:
                pass
            
            try:
                title_elem = self.page.query_selector('h1, div[data-test-id="pin-title"]')
                if title_elem:
                    pin_data['title'] = title_elem.inner_text() or ''
            except:
                pass
            
            return pin_data
        except Exception as e:
            print(f"Error getting pin data: {e}")
            return {}

    def get_latest_engagements(self, limit=20):
        """Scrape latest user interactions from notifications"""
        if not self.page: return []
        
        try:
            print("Navigating to notifications...")
            # Navigate directly to notifications page
            self.page.goto("https://www.pinterest.com/notifications/", timeout=60000, wait_until="domcontentloaded")
            time.sleep(5)
            
            # Container check
            sidebar = self.page.query_selector('#news-feed-sidebar') or \
                      self.page.query_selector('[data-test-id="scrollable-container"]') or \
                      self.page.query_selector('ul.scrollableList')
                      
            if not sidebar:
                print("✗ Could not find notification container.")
                # Try a broad search for any notification items
                items = self.page.query_selector_all('[data-test-id="news-hub-list-item"]')
                if not items: return []
            else:
                items = sidebar.query_selector_all('[data-test-id="news-hub-list-item"]')
            
            print(f"Found {len(items)} notification items.")
            
            engagements = []
            
            # Patterns for interactions - refined to avoid "Pins you've saved"
            # We look for "your Pin" or "your Pins" or "followed you"
            patterns = [
                (r"(.+?)\s+followed you", "follow"),
                (r"(.+?)\s+saved your Pin", "save"),
                (r"(.+?)\s+liked your Pin", "like"),
                (r"(.+?)\s+liked your comment", "like"),
                (r"(.+?)\s+commented on your Pin", "comment")
            ]
            
            for item in items[:limit]:
                try:
                    text_elem = item.query_selector('[data-test-id="updates-link-text"]')
                    if not text_elem: continue
                    
                    full_text = text_elem.inner_text().strip()
                    print(f"Parsing notification: {full_text}")
                    
                    # Core filter: Skip notifications about engagement with pins YOU saved (not yours)
                    # "X commented on Pins you've saved" or "X saved a Pin you've saved"
                    if "Pins you've saved" in full_text or "Pin you've saved" in full_text:
                        continue

                    # Skip common Pinterest system messages
                    system_keywords = ["for you", "inspired by", "searching for", "curating", "your taste", " mood", "ideas to explore"]
                    if any(x in full_text.lower() for x in system_keywords):
                        continue
                        
                    fan_type = None
                    username = None
                    
                    # Match against our interaction patterns
                    for pattern, action_type in patterns:
                        match = re.search(pattern, full_text, re.IGNORECASE)
                        if match:
                            username = match.group(1).strip()
                            fan_type = action_type
                            break
                    
                    if fan_type and username:
                        # Attempt to find a real user link in the item
                        links = item.query_selector_all('a')
                        user_url = ""
                        for link in links:
                            href = link.get_attribute('href')
                            if href and not any(x in href for x in ['/news_hub', '/pin/', '/search/', '/explore/']):
                                user_url = f"https://www.pinterest.com{href}" if href.startswith('/') else href
                                break
                        
                        # Fallback: create a likely URL from username
                        if not user_url:
                            safe_name = re.sub(r'[^a-zA-Z0-9]', '', username.lower())
                            user_url = f"https://www.pinterest.com/{safe_name}/"
                            
                        engagements.append({
                            'username': username,
                            'type': fan_type,
                            'url': user_url,
                            'text': full_text
                        })
                        print(f"  ✓ Identified: {username} ({fan_type})")
                except Exception as e:
                    print(f"Error parsing notification item: {e}")
                    continue
            
            return engagements
            
        except Exception as e:
            print(f"Error getting engagements: {e}")
            return []

    def send_direct_message(self, user_url, message):
        """Send a DM with profile restriction handling"""
        if not self.page: return False
        
        try:
            print(f"Navigating to profile for DM: {user_url}")
            self.page.goto(user_url, timeout=60000, wait_until="domcontentloaded")
            time.sleep(5)
            
            # Check for "Contact" button (profile restriction)
            contact_btn = self.page.query_selector('button:has-text("Contact")')
            if contact_btn:
                print("⚠️ Profile restricted: Only 'Contact' button available. Skipping DM.")
                return "restricted" # Special return value for UI log

            # 1. Look for direct Message button
            message_btn = self.page.query_selector('button:has-text("Message")') or \
                          self.page.query_selector('[data-test-id="user-profile-message-button"]') or \
                          self.page.query_selector('button[aria-label="Message"]')
                          
            # 2. If not found, try the '...' ellipsis menu
            if not message_btn:
                print("  Message button not direct. Checking 'More' menu...")
                more_btn = self.page.query_selector('button[aria-label="More options"]') or \
                           self.page.query_selector('button[data-test-id="more-options-button"]')
                if more_btn:
                    more_btn.click()
                    time.sleep(2)
                    message_btn = self.page.query_selector('div[role="menuitem"]:has-text("Message")')
            
            if not message_btn:
                print("✗ Error: Message button not found.")
                return False
                
            print("  Clicking Message button...")
            message_btn.click()
            
            # 3. Wait for chat window/input
            # Update with user provided selector: textarea#message
            chat_input = None
            for _ in range(8):
                chat_input = self.page.query_selector('textarea#message') or \
                             self.page.query_selector('textarea[aria-label="Write a message"]') or \
                             self.page.query_selector('div[contenteditable="true"][aria-label="Write a message"]') or \
                             self.page.query_selector('#message-draft-editor') 
                if chat_input and chat_input.is_visible():
                    break
                time.sleep(1)
                
            if not chat_input:
                print("✗ Error: Chat input field not found.")
                # Check if a popup appeared but it's not the one we thought
                return False
                
            print("  Typing message...")
            chat_input.click()
            time.sleep(1)
            self.page.keyboard.type(message, delay=random.randint(40, 70))
            time.sleep(1)
            
            # Find Send button if Enter doesn't work or just press Enter
            send_btn = self.page.query_selector('button:has-text("Send")')
            if send_btn:
                send_btn.click()
            else:
                self.page.keyboard.press("Enter")
            
            time.sleep(3)
            print(f"✓ DM successfully sent to {user_url}")
            return True
            
        except Exception as e:
            print(f"Error during DM flow: {e}")
            return False

