
import sys
import atexit
import signal
import threading
from typing import List, Optional

from src.torrent_client import TorrentClient
from src.utils.config_manager import ConfigManager


class TorrentClientManager: 


    _instance: Optional["TorrentClientManager"] = None
    _lock: threading.Lock = threading.Lock()


    def __new__(cls, *args, **kwargs) -> "TorrentClientManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    

    def __init__(self) -> None:
        self.config_manager: ConfigManager = ConfigManager()
        self.active_client: List[TorrentClient] = []


        # atexit
        atexit.register(self.save_all_clients)
        signal.signal(signal.SIGINT, self._exit_signal_handler)
        signal.signal(signal.SIGTERM, self._exit_signal_handler)

    

    def save_all_clients(self):
        """Save state of all active clients to JSON via ConfigManager."""
        for client in self.active_clients:
            client.save_state()

    def _signal_handler(self, sig, frame):
        print("Program exiting, saving all torrent client states...")
        self.save_all_clients()
        sys.exit(0)