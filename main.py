import sys
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QDialog
from PySide6.QtGui import QIcon, QAction
from src.ui.main_window import MainWindow
from src.ui.startup_wizard import StartupWizard
from src.database import create_tables
from src.modules.automation_manager import AutomationManager
import os

def main():
    # Initialize Database
    create_tables()
    
    # Initialize Automation Manager
    manager = AutomationManager()
    
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # Important for background running
    
    # Set Window Icon
    icon_path = os.path.join(os.path.dirname(__file__), 'assets', 'logo.png')
    app_icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()
    if os.path.exists(icon_path):
        app.setWindowIcon(app_icon)
    
    # Check for first run or config
    config_path = "config.json"
    if not os.path.exists(config_path):
        wizard = StartupWizard()
        if wizard.exec() != QDialog.DialogCode.Accepted:
            sys.exit(0)  # User cancelled wizard

    window = MainWindow()
    
    # --- Start Scheduler Worker ---
    from src.modules.scheduler_worker import SchedulerWorker
    scheduler = SchedulerWorker()
    manager.register_worker('scheduler', scheduler)
    scheduler.start()
    print("[OK] Scheduler Worker started in background")

    # -------------------------------
    
    # --- System Tray Implementation ---
    tray_icon = QSystemTrayIcon(app_icon, app)
    tray_icon.setToolTip("PinPowerTool - Running in Background")
    
    menu = QMenu()
    
    action_show = QAction("Show Dashboard", app)
    action_show.triggered.connect(lambda: (window.show(), window.activateWindow()))
    menu.addAction(action_show)
    
    action_exit = QAction("Exit Application", app)
    
    def exit_app():
        manager.stop_all_workers()
        app.quit()
        
    action_exit.triggered.connect(exit_app)
    menu.addAction(action_exit)
    
    tray_icon.setContextMenu(menu)
    tray_icon.activated.connect(lambda reason: window.show() if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
    tray_icon.show()
    
    # Override close event to minimize to tray
    original_close_event = window.closeEvent
    
    def close_event_handler(event):
        try:
            from PySide6.QtWidgets import QMessageBox
            reply = QMessageBox.question(window, 'Run in Background?',
                                        'Do you want to keep running PinPowerTool in the background?\n'
                                        'Click "Yes" to minimize to tray.\n'
                                        'Click "No" to exit completely.',
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                        QMessageBox.StandardButton.Yes)
            
            if reply == QMessageBox.StandardButton.Yes:
                event.ignore()
                window.hide()
                tray_icon.showMessage("PinPowerTool is running", 
                                    "The application is now running in the background.",
                                    QSystemTrayIcon.MessageIcon.Information, 2000)
            else:
                # User wants to exit completely
                print("Stopping all workers...")
                manager.stop_all_workers()
                tray_icon.hide()  # Hide tray icon before quitting
                event.accept()
                app.quit()  # Actually quit the application
        except Exception as e:
            print(f"Error in close handler: {e}")
            event.accept()

    window.closeEvent = close_event_handler
    # ----------------------------------

    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
