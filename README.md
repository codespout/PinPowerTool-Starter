# 📌 PinPowerTool

A powerful, feature-rich Pinterest automation and content management tool built with Python and PyQt6. Designed to streamline your Pinterest marketing workflow with advanced automation, content repurposing, and analytics.

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![PyQt6](https://img.shields.io/badge/PyQt6-Latest-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## ✨ Features

### 🎬 Content Repurposer (NEW!)
Download and repurpose viral content from multiple platforms:
- **Universal Video Downloader**: TikTok, Instagram Reels, YouTube Shorts & more
- **Watermark Removal**: Automatic watermark-free downloads
- **Multi-Method Fallback**: Uses yt-dlp → Cobalt API → TikWM API for maximum reliability
- **Local Content Library**: Visual grid management of downloaded videos
- **Direct Pinterest Integration**: One-click posting to Pinterest

### 🤖 Automation Suite
- **Auto-Repin**: Bulk repin from gathered pins with smart filters
- **Auto-Upload**: Batch upload pins with template-based titles/descriptions
- **Auto-Follow/Unfollow**: Target-based account growth automation
- **Auto-Comment**: Template-driven engagement with rotation support
- **Smart Scheduling**: Queue automation tasks with custom timing

### 🔍 Data Gathering
- **Pin Search**: Scrape pins by keyword with advanced filters
- **User Discovery**: Find and gather user profiles
- **Follower/Following Export**: Extract relationship data
- **Advanced Filtering**: By followers, repins, keywords, and more

### 📊 Analytics & Insights
- **Performance Dashboard**: Real-time metrics and KPIs
- **Pinterest Trends Integration**: Discover trending topics by country/interest
- **Activity History**: Track all automation actions
- **Account Analytics**: Monitor growth and engagement

### 💬 Direct Messaging
- **Bulk DM Campaigns**: Send personalized messages to users
- **Template System**: Create and manage DM templates
- **Smart Delays**: Human-like timing to avoid detection

### 🔐 Multi-Account Management
- **Account Rotation**: Cycle through multiple accounts automatically
- **Cookie-Based Auth**: Fast, secure login persistence
- **Board Management**: Per-account board configuration
- **Proxy Support**: Assign proxies to each account

### 🎨 Premium UI/UX
- **Modern Dark/Light Themes**: Glassmorphic design with smooth transitions
- **Responsive Layout**: Optimized for various screen sizes
- **Global Styling System**: Consistent, professional appearance
- **Real-time Feedback**: Progress indicators and status logs

### 🛡️ Advanced Safety Features
- **Human-Like Behavior**: Random delays, mouse movements, scrolling
- **Smart Rate Limiting**: Configurable action limits and breaks
- **Warmup Sessions**: Build human session fingerprints
- **Duplicate Detection**: Avoid re-pinning/re-commenting
- **Session Persistence**: Resume interrupted tasks

## 🚀 Installation

### Prerequisites
- Python 3.8 or higher
- Windows OS (currently optimized for Windows)
- Chrome/Chromium installed (for Playwright automation)

### Setup

1. **Extract the ZIP file**
   Extract the downloaded zip archive to your preferred directory and navigate to the project directory:
   ```bash
   cd PinPowerTool
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Playwright browsers**
   ```bash
   playwright install chromium
   ```

4. **Run the application**
   ```bash
   python main.py
   ```

## 📦 Dependencies

- **PyQt6**: Modern GUI framework
- **Playwright**: Browser automation
- **yt-dlp**: Universal video downloader
- **requests**: HTTP requests for API calls
- **SQLite3**: Local database (built-in)

## 🎯 Quick Start Guide

### 1. Add Pinterest Accounts
1. Navigate to **Accounts** tab
2. Click **Add Account**
3. Enter email and password
4. (Optional) Add proxy in format `ip:port:username:password`
5. Click **Verify & Save**

### 2. Gather Pins
1. Go to **Gather Pins** tab
2. Choose search mode (Keyword/User)
3. Enter search term or Pinterest profile URL
4. Set quantity and click **Start Gathering**

### 3. Repurpose Content
1. Navigate to **Repurposer** tab
2. Paste TikTok/Instagram/YouTube URL
3. Click **Download Video**
4. Select downloaded video and click **Post to Pinterest**

### 4. Automate Actions
1. Go to **Automation** → **Auto-Repin**
2. Select target board
3. Configure quantity and rotation settings
4. Click **Run Now** or **Add to Queue**

## ⚙️ Configuration

### Settings (Settings Tab)
- **Delays**: Min/max delays between actions
- **Filters**: Set follower/following/repin thresholds
- **Skip Options**: Skip own pins, already commented pins
- **Breaks**: Configure action limits before breaks
- **Warmup**: Enable pre-automation browsing sessions

### Account Rotation
Enable in Automation tabs to cycle through multiple accounts:
- Set actions per account before rotation
- Configure per-account board targets
- Supports all automation features

## 📁 Project Structure

```
PinPowerTool/
├── main.py                 # Application entry point
├── src/
│   ├── ui/                 # PyQt6 UI components
│   │   ├── main_window.py
│   │   ├── dashboard_ui.py
│   │   ├── repurposer_ui.py
│   │   ├── automation_ui.py
│   │   └── ...
│   ├── modules/            # Core functionality
│   │   ├── actions.py      # Pinterest automation
│   │   ├── repurposer.py   # Video download logic
│   │   ├── theme_manager.py
│   │   └── ...
│   └── database.py         # SQLite database manager
├── assets/                 # Images, icons, logos
└── requirements.txt
```

## 🔧 Advanced Features

### Custom Templates
Create dynamic templates with variables:
- `{filename}`: Insert image/video filename
- `{username}`: Target username
- Use in titles, descriptions, comments, DMs

### Scheduler
Queue multiple tasks with custom timing:
- Set intervals (minutes, hours, days)
- One-time or recurring schedules
- Pause/resume/delete queued tasks

### Trends Discovery
Fetch trending topics from Pinterest Trends:
- Filter by country (US, UK, CA, etc.)
- Filter by interest category
- Export trending keywords for content ideas

## 🛠️ Troubleshooting

### Video Download Fails
- Ensure yt-dlp is updated: `pip install --upgrade yt-dlp`
- Check network connection
- Try a different URL
- Some videos may be private or geo-restricted

### Automation Stops
- Check Pinterest account status (not banned)
- Verify cookies are valid
- Reduce action speed in settings
- Enable warmup sessions

### Login Issues
- Clear browser cookies and re-verify account
- Check proxy configuration
- Ensure Pinterest credentials are correct

## ⚠️ Disclaimer

This tool is for educational purposes only. Use responsibly and in accordance with Pinterest's Terms of Service. The developer is not responsible for any account bans or violations resulting from misuse of this software.

**Important Notes:**
- Respect Pinterest's rate limits
- Don't spam or engage in manipulative behavior
- Use reasonable delays and breaks
- Monitor your accounts regularly

## 📄 License

This project is licensed under the Envato Standard/Extended License.

## 💡 Support

For any questions, issues, or custom feature requests, please contact us directly through the CodeCanyon Support panel on our profile page.

## 🎉 Acknowledgments

- **yt-dlp**: Universal video downloader
- **Cobalt Tools**: API for social media downloads
- **Playwright**: Reliable browser automation
- **PyQt6**: Modern Python GUI framework

---

**Version**: 2.0.0  
**Last Updated**: January 2026  
**Built with** ❤️ **for Pinterest marketers and content creators**
