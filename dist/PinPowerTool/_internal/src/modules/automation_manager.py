from PySide6.QtCore import QObject, Signal as pyqtSignal
import threading

class AutomationManager(QObject):
    _instance = None
    _lock = threading.Lock()
    
    # Signals to update specific UIs when they are active
    # We use a generic update signal that UIs can subscribe to: signal(worker_type, message)
    log_update = pyqtSignal(str, str) 
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(AutomationManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        super().__init__()
        self._initialized = True
        
        # Registry of active worker threads
        # Format: {'worker_type': worker_instance}
        # Types: 'repin', 'upload', 'comment', 'follow', 'gather', 'scheduler'
        self.workers = {}
        
        # Log buffers for persistence
        # Format: {'worker_type': ['line 1', 'line 2']}
        self.log_buffers = {}
        self.MAX_LOG_LINES = 1000
        
        print("AutomationManager initialized")

    def register_worker(self, worker_type, worker):
        """Register a new worker and optionally stop the old one if exists."""
        if worker_type in self.workers:
            # Check if old worker is running
            old_worker = self.workers[worker_type]
            if hasattr(old_worker, 'isRunning') and old_worker.isRunning():
                print(f"Warning: Replacing running worker for {worker_type}")
                # We don't automatically stop it here strictly, but usually UI handles stop
        
        self.workers[worker_type] = worker
        
        # Connect signals for persistence
        try:
            # Disconnect old signals if we can, but easier to just ensure new worker signals are handled
            worker.log_signal.connect(lambda msg: self._handle_log(worker_type, msg))
        except Exception as e:
            print(f"Error connecting signals for {worker_type}: {e}")
            
    def get_worker(self, worker_type):
        """Get the active worker instance if it exists."""
        return self.workers.get(worker_type)
        
    def is_worker_running(self, worker_type):
        """Check if a specific worker is currently running."""
        worker = self.workers.get(worker_type)
        if worker and hasattr(worker, 'isRunning'):
            return worker.isRunning()
        return False

    def unregister_worker(self, worker_type):
        """Remove a worker from registry (e.g. when fully stopped/finished)."""
        if worker_type in self.workers:
            del self.workers[worker_type]

    def add_log(self, worker_type, message):
        """Public method to add a log entry to a specific buffer."""
        self._handle_log(worker_type, message)

    def _handle_log(self, worker_type, message):
        """Internal handler to buffer logs and emit signal."""
        if worker_type not in self.log_buffers:
            self.log_buffers[worker_type] = []
            
        buffer = self.log_buffers[worker_type]
        buffer.append(message)
        
        # Trim buffer
        if len(buffer) > self.MAX_LOG_LINES:
            self.log_buffers[worker_type] = buffer[-self.MAX_LOG_LINES:]
            
        # Emit signal for any listening UI
        # self.log_update.emit(worker_type, message) 
        # Note: Direct Qt signal connection from worker to UI is usually preferred for real-time
        # This buffer is mainly for restoration when restoring tab

    def get_logs(self, worker_type):
        """Retrieve buffered logs for a worker type."""
        return self.log_buffers.get(worker_type, [])
        
    def clear_logs(self, worker_type):
        """Clear logs for a specific worker type."""
        if worker_type in self.log_buffers:
            self.log_buffers[worker_type] = []

    def stop_all_workers(self):
        """Stop all registered workers (e.g. on app exit)."""
        for w_type, worker in self.workers.items():
            if hasattr(worker, 'stop'):
                worker.stop()
            if hasattr(worker, 'wait'):
                worker.wait()
