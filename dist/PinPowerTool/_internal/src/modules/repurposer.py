import os
import yt_dlp
import sqlite3
from src.database import get_db_connection

class VideoDownloader:
    def __init__(self, download_path):
        self.download_path = download_path
        if not os.path.exists(self.download_path):
            os.makedirs(self.download_path)

    def download_video(self, url):
        """
        Downloads video using multiple methods with automatic fallback.
        """
        # 1. Try yt-dlp with robust headers
        result = self._try_ytdlp(url)
        if result['success']:
            return result
        
        # 2. Try Cobalt API (works for TikTok, Instagram, YouTube, etc.)
        print("yt-dlp failed, trying Cobalt API...")
        result = self._try_cobalt_api(url)
        if result['success']:
            return result
        
        # 3. Try TikWM API (TikTok-specific)
        if 'tiktok' in url.lower():
            print("Cobalt failed, trying TikWM API...")
            result = self._try_tikwm_api(url)
            if result['success']:
                return result
        
        return {'success': False, 'error': "All download methods failed"}

    def _try_ytdlp(self, url):
        """Try downloading with yt-dlp."""
        # Use different format strings based on platform
        if 'youtube' in url.lower() or 'youtu.be' in url.lower():
            # For YouTube, use simpler format that works better with Shorts
            format_str = 'best[ext=mp4]/best'
        else:
            format_str = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        
        ydl_opts = {
            'outtmpl': os.path.join(self.download_path, '%(title).50s [%(id)s].%(ext)s'),
            'format': format_str,
            'writethumbnail': False,  # Disable thumbnail download to avoid confusion
            'noplaylist': False,  # Allow playlists/carousels
            'quiet': False,  # Show output for debugging
            'no_warnings': False,  # Show warnings for debugging
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                # Check if this is a playlist/multi-video entry
                if 'entries' in info:
                    # Multiple videos downloaded
                    results = []
                    for entry in info['entries']:
                        if entry:  # Some entries might be None if download failed
                            result = self._process_ydl_info(ydl, entry, url)
                            if result['success']:
                                results.append(result)
                    
                    if results:
                        # Return a special multi-video result
                        return {
                            'success': True,
                            'multi_video': True,
                            'videos': results,
                            'count': len(results)
                        }
                    else:
                        return {'success': False, 'error': 'yt-dlp: No videos extracted from playlist'}
                else:
                    # Single video
                    return self._process_ydl_info(ydl, info, url)
                    
        except Exception as e:
            # Return more detailed error
            error_str = str(e)
            # Truncate very long errors but keep meaningful parts
            if len(error_str) > 200:
                error_str = error_str[:200] + "..."
            return {'success': False, 'error': f"yt-dlp: {error_str}"}

    def _process_ydl_info(self, ydl, info, url):
        """Process yt-dlp download info."""
        filename = ydl.prepare_filename(info)
        
        # Since we disabled thumbnails, no need to look for them
        thumbnail = None
        
        extractor = info.get('extractor', 'unknown')
        platform = 'other'
        if 'tiktok' in extractor.lower(): platform = 'tiktok'
        elif 'instagram' in extractor.lower(): platform = 'instagram'
        elif 'youtube' in extractor.lower(): platform = 'youtube'

        return {
            'success': True,
            'file_path': filename,
            'title': info.get('title', 'Unknown Title'),
            'duration': info.get('duration', 0),
            'thumbnail_path': thumbnail,
            'platform': platform,
            'original_url': url
        }

    def _try_cobalt_api(self, url):
        """
        Try downloading via Cobalt API (supports TikTok, Instagram, YouTube, etc.)
        API docs: https://github.com/imputnet/cobalt
        """
        try:
            import requests
            import re
            
            api_url = "https://api.cobalt.tools/api/json"
            
            payload = {
                "url": url,
                "vCodec": "h264",
                "vQuality": "720",
                "aFormat": "mp3",
                "filenamePattern": "basic",
                "isAudioOnly": False,
                "isTTFullAudio": False
            }
            
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
            
            response = requests.post(api_url, json=payload, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('status') == 'redirect' or data.get('status') == 'stream':
                    download_url = data.get('url')
                    
                    if download_url:
                        # Download the video
                        title = self._extract_title_from_url(url)
                        filename = f"{title}.mp4"
                        file_path = os.path.join(self.download_path, filename)
                        
                        print(f"Downloading from Cobalt API...")
                        video_response = requests.get(download_url, stream=True, timeout=60)
                        
                        if video_response.status_code == 200:
                            with open(file_path, 'wb') as f:
                                for chunk in video_response.iter_content(chunk_size=8192):
                                    f.write(chunk)
                            
                            platform = 'tiktok' if 'tiktok' in url.lower() else 'instagram' if 'instagram' in url.lower() else 'other'
                            
                            return {
                                'success': True,
                                'file_path': file_path,
                                'title': title,
                                'duration': 0,
                                'thumbnail_path': None,
                                'platform': platform,
                                'original_url': url
                            }
            
            error_detail = f"Status: {response.status_code}"
            if response.status_code == 200:
                data = response.json()
                error_detail += f", Response: {str(data)[:150]}"
            return {'success': False, 'error': f"Cobalt API: {error_detail}"}
            
        except Exception as e:
            return {'success': False, 'error': f"Cobalt API: {str(e)[:150]}"}

    def _try_tikwm_api(self, url):
        """
        Try downloading TikTok via TikWM API.
        """
        try:
            import requests
            import re
            
            # Extract video ID from URL
            video_id = re.search(r'/video/(\d+)', url)
            if not video_id:
                return {'success': False, 'error': "Could not extract TikTok video ID"}
            
            video_id = video_id.group(1)
            
            api_url = f"https://www.tikwm.com/api/"
            params = {
                "url": url,
                "hd": 1
            }
            
            response = requests.get(api_url, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('code') == 0:  # Success
                    video_data = data.get('data', {})
                    
                    # Try HD first, then fall back to normal
                    download_url = video_data.get('hdplay') or video_data.get('play')
                    
                    if download_url:
                        title = video_data.get('title', f"TikTok_{video_id}")
                        # Sanitize title
                        title = re.sub(r'[\\/*?:"<>|]', "", title)[:50].strip()
                        
                        filename = f"{title}.mp4"
                        file_path = os.path.join(self.download_path, filename)
                        
                        print(f"Downloading from TikWM API...")
                        video_response = requests.get(download_url, stream=True, timeout=60)
                        
                        if video_response.status_code == 200:
                            with open(file_path, 'wb') as f:
                                for chunk in video_response.iter_content(chunk_size=8192):
                                    f.write(chunk)
                            
                            return {
                                'success': True,
                                'file_path': file_path,
                                'title': title,
                                'duration': video_data.get('duration', 0),
                                'thumbnail_path': None,
                                'platform': 'tiktok',
                                'original_url': url
                            }
            
            error_detail = f"Status: {response.status_code}"
            if response.status_code == 200:
                data = response.json()
                error_detail += f", Response: {str(data)[:150]}"
            return {'success': False, 'error': f"TikWM API: {error_detail}"}
            
        except Exception as e:
            return {'success': False, 'error': f"TikWM API: {str(e)[:150]}"}

    def _extract_title_from_url(self, url):
        """Extract a basic title from URL."""
        import re
        from urllib.parse import urlparse
        
        # Try to get something meaningful from the URL
        if 'tiktok' in url:
            match = re.search(r'/video/(\d+)', url)
            return f"TikTok_{match.group(1)}" if match else "TikTok_Video"
        elif 'instagram' in url:
            match = re.search(r'/reel/([^/?]+)', url)
            return f"Instagram_{match.group(1)}" if match else "Instagram_Video"
        else:
            parsed = urlparse(url)
            return parsed.path.split('/')[-1] or "Video"


class ContentLibrary:
    def add_video(self, video_data):
        conn = get_db_connection()
        try:
            conn.execute('''
                INSERT INTO repurposed_videos (original_url, file_path, platform, title, duration, thumbnail_path)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                video_data['original_url'],
                video_data['file_path'],
                video_data['platform'],
                video_data['title'],
                video_data['duration'],
                video_data['thumbnail_path']
            ))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False # Already exists
        finally:
            conn.close()

    def get_all_videos(self):
        conn = get_db_connection()
        videos = conn.execute('SELECT * FROM repurposed_videos ORDER BY created_at DESC').fetchall()
        conn.close()
        return videos

    def delete_video(self, video_id):
        conn = get_db_connection()
        # Get path to delete file
        row = conn.execute('SELECT file_path, thumbnail_path FROM repurposed_videos WHERE id = ?', (video_id,)).fetchone()
        if row:
            try:
                if row['file_path'] and os.path.exists(row['file_path']):
                    os.remove(row['file_path'])
                if row['thumbnail_path'] and os.path.exists(row['thumbnail_path']):
                    os.remove(row['thumbnail_path'])
            except:
                pass # File might be gone properly

        conn.execute('DELETE FROM repurposed_videos WHERE id = ?', (video_id,))
        conn.commit()
        conn.close()
