from __future__ import annotations
import asyncio
from pathlib import Path
import threading
from typing import TYPE_CHECKING, Dict, Any, List, Optional, Tuple, Union

if TYPE_CHECKING:
    from src.torrent_app import TorrentApp
from src.torrent_client import TorrentClient, TorrentStatus
from src.torrent_source import TorrentSource
from src.tracker_manager import TrackerManager
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
        self.active_client: Dict[str, TorrentClient] = {}

        self._client_task: Dict[str, asyncio.Task] = {}
        self.__torrent_app: None | TorrentApp = None
        # Composition
        self.__tracker_man: TrackerManager | None = None


        # Startup load from saved state
        self._load_state()
    
    def _load_state(self) -> None :
        d = self.config_manager.get_all_client_state()

        for key, value in d.items():
            self.active_client[key] = TorrentClient.from_dict(value)



    def register_tracker_manager(self, tracker_man: TrackerManager) -> None :
        self.__tracker_man: TrackerManager = tracker_man


    def _add_torrent(self, info_hash: str, torrent_src: TorrentSource, download_path: Path) -> TorrentClient:
        
        

        if (info_hash not in self.active_client) : 
            tc: TorrentClient  = TorrentClient(torrent_source=torrent_src, download_path=download_path)
            self.active_client[info_hash] = tc

            return tc
        else :
            return (self.active_client.get(info_hash))
        

    
    def _add_peers(self, info_hash: str,announce_resp: Dict[str, Union[int, List[Dict]]]) -> None:
        # Test
        
        
        if (info_hash not in self.active_client.keys()) :
            return f'Torrent not found for {info_hash}' 
        else :
            tc: TorrentClient = self.active_client[info_hash]
            self.__torrent_app.notify_user(f"{tc.peers_amount} && {tc._initialized}", f"UPD: {info_hash}")
            

            if (tc._initialized): 
                
                peers: Dict[str, int|str] = announce_resp['peers']

                peer_list: List[Tuple[str, int]] = [(a['ip'], a['port']) for a in peers]

                self.__torrent_app.notify_user(f"{peer_list[0]}", f"UPD: {info_hash}")

                tc.add_peers(peer_list)
                
            else:
                return f'{tc.torrent_name} is not started yet.' 

    async def _shutdown (self) -> Dict[str, Any] :
        """
        Shuts down all clients concurrently and collects their final states.
        """
        # 1. Cancel the background tasks first to trigger the 'finally' blocks
        for info_hash, task in self._client_task.items():
            task.cancel()

        # 2. Run all shutdowns in parallel using asyncio.gather
        # This ensures we don't wait for TC1 to finish before starting TC2's shutdown
        # info_hashes = list(self.active_client.keys())
        shutdown_coros = [tc.shutdown() for tc in self.active_client.values()]      # List of func
        
        # This executes all shutdowns at once
        await asyncio.gather(*shutdown_coros, return_exceptions=True)

        # 3. Collect final serialized states for the Dict
        results = {}
        for info_hash, tc in self.active_client.items():
            results[info_hash] = tc.to_dict()
            
        # Clear the task tracking
        self._client_task.clear()
        
        return results

    async def _start_all_client(self) -> None:
        for info_hash, tc in self.active_client.items():
            if (info_hash not in self._client_task.keys()) :
                self._client_task[info_hash] = asyncio.create_task(tc.start())


    def register_torrent_app(self, tap: TorrentApp): 
        self.__torrent_app = tap

    @property
    def is_client_running(self, info_hash: str) -> bool:
        if (info_hash not in self.active_client.keys()) :
            return self.active_client[info_hash].status == TorrentStatus.DOWNLOADING
        
        return False




