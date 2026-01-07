
from __future__ import annotations
import asyncio

import threading
from typing import Any, Dict, List, Optional

from pathlib import Path

from attr import dataclass


from src.torrent_client import TorrentClient
from src.torrent_client_manager import TorrentClientManager
from src.torrent_source import TorrentSource
from src.torrent_ui import TorrentUI
from src.tracker_manager import TrackerManager

from src.utils.config_manager import ConfigManager

@dataclass
class TorrentState:
    info_hash: str
    name: str
    status: str
    progress: float
    num_peers: int


class TorrentApp:
    _instance: Optional["TorrentApp"] = None
    _lock: threading.Lock = threading.Lock()  # ensures thread-safe singleton init


    def __new__(cls, *args, **kwargs) -> "TorrentApp":
        if cls._instance is None:
            with cls._lock :
                if cls._instance is None :
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, config:str = "app_config.json", port:int = 51415, dowload_base: Path = None) -> None:
        if hasattr(self, "_initialized") and self._initialized:
            return
        
        self.__ui: TorrentUI = None
        self._initialized = True


        self._ui_snapshot: list[TorrentState] = []

        # Default download dir
        self.download_base_dir: Path = Path.cwd() / "Downloads" if dowload_base is None else dowload_base 


        # Singleton
        self.config_man: ConfigManager = ConfigManager(config)
        self.tracker_man: TrackerManager = TrackerManager(self.config_man.peer_id, self.config_man)
        self.torrent_client_man: TorrentClientManager = TorrentClientManager()




        # Register the Composition 
        self.tracker_man.register_torrent_app(self)
        self.tracker_man.register_client_man(self.torrent_client_man)

        self.torrent_client_man.register_torrent_app(self)


        # Load from Config


        # atexit
        # atexit.register(self._signal_handler)
        # signal.signal(signal.SIGINT, self._signal_handler)
        # signal.signal(signal.SIGTERM, self._signal_handler)



    # UI
    def ui_data(self)-> List[TorrentState] :
        """The UI calls this. It returns pre-computed data."""
        self.update_snapshot()
        return self._ui_snapshot
    
    def update_snapshot(self):
        """Called by your engine's internal loop (e.g., every 1s)."""
        new_snapshot = []
        active_client: Dict[str, TorrentClient] = self.torrent_client_man.active_client 
        for h, c in active_client.items():
            new_snapshot.append(TorrentState(
                info_hash=h,
                name=c.torrent_name,
                status=c.status.name,
                progress=c.calculate_progress, # Compute once here
                num_peers=c.peers_amount
            ))
        self._ui_snapshot = new_snapshot


    def notify_user(self, message:str, title:str="Info")-> None:
        if not(getattr(self, "__ui", None)):
            self.__ui.notify_ui(message, title)

    # Closing

    async def shutdown_and_save(self):
        """The clean entry point for stopping the engine."""
        if self._shutting_down:
            return
        self._shutting_down = True
        
        print("\n[!] Shutdown initiated. Saving state...")
        try:
            # We await the logic we built earlier
            await asyncio.wait_for(self.save_all_clients(), timeout=10.0)
        except Exception as e:
            print(f"Error during save: {e}")
    async def save_all_clients(self):
        """Save state of all active clients to JSON via ConfigManager."""
        # d: Dict[str, Any] = self.config_man.get_all_client_state()
        # print('(###)')

        d_a: Dict[str, Any] = await self.torrent_client_man._shutdown()
        
        for info_hash, client_state in d_a.items():
            self.config_man.save_client_state(info_hash, client_state)
        

    async def _signal_handler(self):
        # Prevent multiple signal triggers from running shutdown twice
        if getattr(self, "_shutting_down", False):
            return
        self._shutting_down = True

        print("\n[!] Shutdown signal received. Saving state...")
        
        try:
            # Give it a strict timeout so the OS doesn't kill it mid-write
            await asyncio.wait_for(self.save_all_clients(), timeout=10.0)
        except Exception as e:
            print(f"Error during emergency save: {e}")
        finally:
            print("Shutdown complete. Exiting.")
            # Stop the loop and let the process end
            loop = asyncio.get_running_loop()
            loop.stop()

    # Register Composition
    def register_ui(self, ui:TorrentUI) -> None :
        self.__ui = ui

    # 
    def _add_torrent(self, path: str | Path) -> TorrentClient: 
        
        torrent_path : Path =  None
        if (isinstance(path, str)) :
            torrent_path = Path(path)
        elif (isinstance(path, Path)) :
            torrent_path = path
        else :
            raise Exception("Invalid path parameter....")

        if not torrent_path.exists() :
            raise Exception("File not exists....")
        
        # t_source: TorrentSource = TorrentSource(torrent_source=p, torrents_dir=self.config_man.torrents_dir)
        torr_info_hash: str = TorrentSource.info_hash(torrent_path)
        

        if (torr_info_hash in self.torrent_client_man.active_client.keys()) :
            # it already exist 
            tc: TorrentClient = self.torrent_client_man.active_client[torr_info_hash]
        else :
            t_source: TorrentSource = TorrentSource(torrent_source=torrent_path, torrents_dir=self.config_man.torrents_dir)
            # Create new client and add to ConfigManager
            tc:TorrentClient = self.torrent_client_man._add_torrent(info_hash=torr_info_hash, torrent_src=t_source, download_path=self.download_base_dir)


            # Update the client 
            self.config_man.save_client_state(torr_info_hash, tc.to_dict())
        

        return tc


        # self.tracker_man.add

    async def _start_all_torrent(self) -> None:
        await self.torrent_client_man._start_all_client()

    # Main Loop
    async def run(self):
        # ... other setups ...
        
        # Start the listening server (for incoming peer handshakes)
        # asyncio.create_task(self.tracker_manager.start_listening())
        
        # Start the periodic tracker announce loop
        asyncio.create_task(self.tracker_man.tracker_loop())

