import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, 
                             QMessageBox, QListWidget, QProgressBar, QGroupBox, QScrollArea, QAbstractItemView)
from PySide6.QtCore import Qt, QThread, Signal as pyqtSignal, QSize
from PySide6.QtGui import QIcon, QPixmap
from src.modules.repurposer import VideoDownloader, ContentLibrary

class DownloadWorker(QThread):
    progress_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(dict)

    def __init__(self, downloader, url):
        super().__init__()
        self.downloader = downloader
        self.url = url

    def run(self):
        self.progress_signal.emit(f"📥 Starting download: {self.url[:50]}...")
        self.progress_signal.emit("🔄 Trying Method 1: yt-dlp (Universal downloader)...")
        
        # Try yt-dlp
        result = self.downloader._try_ytdlp(self.url)
        if result['success']:
            # Check if multi-video
            if result.get('multi_video'):
                self.progress_signal.emit(f"✅ Downloaded {result['count']} videos successfully with yt-dlp!")
                self.finished_signal.emit(result)
            else:
                self.progress_signal.emit("✅ Downloaded successfully with yt-dlp!")
                self.finished_signal.emit(result)
            return
        
        self.progress_signal.emit(f"⚠️ Method 1 failed: {result.get('error', 'Unknown error')[:100]}")
        
        # Try Cobalt API
        self.progress_signal.emit("🔄 Trying Method 2: Cobalt API (Multi-platform)...")
        result = self.downloader._try_cobalt_api(self.url)
        if result['success']:
            self.progress_signal.emit("✅ Downloaded successfully with Cobalt API!")
            self.finished_signal.emit(result)
            return
        
        self.progress_signal.emit(f"⚠️ Method 2 failed: {result.get('error', 'Unknown error')[:100]}")
        
        # Try TikWM if TikTok
        if 'tiktok' in self.url.lower():
            self.progress_signal.emit("🔄 Trying Method 3: TikWM API (TikTok-specific)...")
            result = self.downloader._try_tikwm_api(self.url)
            if result['success']:
                self.progress_signal.emit("✅ Downloaded successfully with TikWM API!")
                self.finished_signal.emit(result)
                return
            
            self.progress_signal.emit(f"⚠️ Method 3 failed: {result.get('error', 'Unknown error')[:100]}")
        
        # All methods failed
        error_msg = "❌ All download methods failed. This URL may not be supported or the video is private/deleted."
        self.progress_signal.emit(error_msg)
        self.finished_signal.emit({'success': False, 'error': error_msg})

class RepurposerUI(QWidget):
    request_upload = pyqtSignal(str, str) # file_path, title

    def __init__(self):
        super().__init__()
        # Default download path
        self.download_path = os.path.join(os.path.expanduser("~"), "Documents", "PinPowerTool", "Downloads")
        self.downloader_module = VideoDownloader(self.download_path)
        self.library_module = ContentLibrary()
        
        self.setup_ui()
        self.refresh_library()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)

        # Header
        header = QLabel("♻️ Content Repurposer")
        header.setObjectName("HeaderTitle")
        layout.addWidget(header)

        # Main Content Layout (Split into Left: Downloader, Right: Library - or stacked?)
        # Let's do a top-down approach: Input area at top, Library list below.
        
        # --- Downloader Area ---
        input_group = QGroupBox("Video Downloader")
        input_layout = QVBoxLayout()
        
        url_row = QHBoxLayout()
        self.txt_url = QLineEdit()
        self.txt_url.setPlaceholderText("Paste TikTok or Instagram Reel URL here...")
        self.btn_download = QPushButton("⬇️ Download Video")
        self.btn_download.setFixedWidth(150)
        self.btn_download.clicked.connect(self.start_download)
        
        url_row.addWidget(self.txt_url)
        url_row.addWidget(self.btn_download)
        input_layout.addLayout(url_row)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximum(0)  # Indeterminate mode
        self.progress_bar.setMinimum(0)
        self.progress_bar.hide()
        input_layout.addWidget(self.progress_bar)
        
        # Multi-line status output
        from PySide6.QtWidgets import QTextEdit
        self.txt_status = QTextEdit()
        self.txt_status.setReadOnly(True)
        self.txt_status.setMaximumHeight(100)
        self.txt_status.setPlaceholderText("Download status will appear here...")
        self.txt_status.setObjectName("InfoLabel")
        input_layout.addWidget(self.txt_status)
        
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

        # --- Library Area ---
        lib_header_layout = QHBoxLayout()
        lib_title = QLabel("📚 Local Content Library")
        lib_title.setObjectName("SectionTitle")
        lib_header_layout.addWidget(lib_title)
        
        self.btn_refresh = QPushButton("🔄 Refresh")
        self.btn_refresh.setObjectName("ActionBtn")
        self.btn_refresh.setFixedWidth(100)
        self.btn_refresh.clicked.connect(self.refresh_library)
        lib_header_layout.addWidget(self.btn_refresh)
        
        layout.addLayout(lib_header_layout)

        # Library Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Thumbnail", "Title", "Platform", "Duration", "Actions"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(80) # Taller rows for thumbnails
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setIconSize(QSize(60, 60))
        layout.addWidget(self.table)
        
        # Action Buttons for Selected Item
        action_layout = QHBoxLayout()
        self.btn_post_pinterest = QPushButton("📌 Post to Pinterest")
        self.btn_post_pinterest.clicked.connect(self.post_to_pinterest)
        
        self.btn_open_folder = QPushButton("📂 Open Folder")
        self.btn_open_folder.clicked.connect(self.open_file_location)
        
        self.btn_delete = QPushButton("🗑️ Delete")
        self.btn_delete.clicked.connect(self.delete_video)
        
        action_layout.addWidget(self.btn_post_pinterest)
        action_layout.addWidget(self.btn_open_folder)
        action_layout.addStretch()
        action_layout.addWidget(self.btn_delete)
        layout.addLayout(action_layout)

    def start_download(self):
        url = self.txt_url.text().strip()
        if not url:
            QMessageBox.warning(self, "Error", "Please enter a URL")
            return

        self.btn_download.setEnabled(False)
        self.progress_bar.show()
        self.txt_status.clear()
        self.txt_status.append("🚀 Initializing download...")
        
        self.worker = DownloadWorker(self.downloader_module, url)
        self.worker.progress_signal.connect(self.update_status)
        self.worker.finished_signal.connect(self.on_download_finished)
        self.worker.start()

    def update_status(self, message):
        """Append status message to the text area."""
        self.txt_status.append(message)
        # Auto-scroll to bottom
        scrollbar = self.txt_status.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def on_download_finished(self, result):
        self.btn_download.setEnabled(True)
        self.progress_bar.hide()
        
        if result['success']:
            # Check if multi-video download
            if result.get('multi_video'):
                # Multiple videos downloaded
                videos = result.get('videos', [])
                self.txt_status.append(f"✅ MULTI-VIDEO DOWNLOAD COMPLETE: {len(videos)} videos")
                
                # Add each video to library
                for idx, video in enumerate(videos, 1):
                    self.library_module.add_video(video)
                    self.txt_status.append(f"  #{idx}: {video['title'][:50]}")
                
                self.txt_url.clear()
                self.refresh_library()
            else:
                # Single video
                self.txt_status.append(f"✅ DOWNLOAD COMPLETE: {result['title']}")
                self.txt_status.append(f"📁 Saved to: {result['file_path']}")
                self.txt_url.clear()
                # Add to DB
                self.library_module.add_video(result)
                self.refresh_library()
        else:
            error_msg = result.get('error', 'Unknown error')
            self.txt_status.append(f"\n❌ DOWNLOAD FAILED")
            self.txt_status.append(f"Error: {error_msg}")
            QMessageBox.critical(self, "Download Failed", error_msg)

    def refresh_library(self):
        self.table.setRowCount(0)
        videos = self.library_module.get_all_videos()
        
        for row_idx, video in enumerate(videos):
            self.table.insertRow(row_idx)
            
            # Thumbnail
            thumb_path = video['thumbnail_path']
            if thumb_path and os.path.exists(thumb_path):
                icon = QIcon(thumb_path)
                self.table.setItem(row_idx, 0, QTableWidgetItem(icon, ""))
            else:
                self.table.setItem(row_idx, 0, QTableWidgetItem("No Image"))
            
            # Title
            self.table.setItem(row_idx, 1, QTableWidgetItem(video['title']))
            
            # Platform
            self.table.setItem(row_idx, 2, QTableWidgetItem(video['platform'].capitalize()))
            
            # Duration
            duration = f"{video['duration']}s" if video['duration'] else "?"
            self.table.setItem(row_idx, 3, QTableWidgetItem(duration))
            
            # Store ID and Path
            self.table.item(row_idx, 1).setData(Qt.ItemDataRole.UserRole, video['id'])
            self.table.item(row_idx, 1).setData(Qt.ItemDataRole.UserRole + 1, video['file_path'])

    def get_selected_video(self):
        selected = self.table.selectedItems()
        if not selected:
            return None
        # item 1 has the data
        row = selected[0].row()
        return {
            'id': self.table.item(row, 1).data(Qt.ItemDataRole.UserRole),
            'path': self.table.item(row, 1).data(Qt.ItemDataRole.UserRole + 1),
            'title': self.table.item(row, 1).text()
        }

    def post_to_pinterest(self):
        vid = self.get_selected_video()
        if not vid:
            QMessageBox.warning(self, "Selection", "Select a video first.")
            return
        
        # Emit signal to main window to switch tabs and load data
        self.request_upload.emit(vid['path'], vid['title'])

    def open_file_location(self):
        vid = self.get_selected_video()
        if not vid: return
        
        folder = os.path.dirname(vid['path'])
        os.startfile(folder)

    def delete_video(self):
        vid = self.get_selected_video()
        if not vid: return
        
        confirm = QMessageBox.question(self, "Confirm", "Delete this video from library and disk?", 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            self.library_module.delete_video(vid['id'])
            self.refresh_library()
