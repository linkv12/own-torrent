

import asyncio
from enum import Enum
from pathlib import Path
from time import time
from typing import Any, Dict, Optional, Union


from src.disk_manager import DiskManager
from src.piece_manager import PieceManager
from src.torrent_source import TorrentSource
from src.utils.config_manager import ConfigManager


class TorrentStatus(Enum) :
    DOWNLOADING = 'downloading'
    PAUSED = "paused"
    FINISHED = "finished"
    ERROR = "error"

class TorrentClient:
    def __init__(self, 
                 torrent_source: Union[str, Path, TorrentSource], 
                 download_path: Union[str, Path], 
                 date_added: Optional[float] = None,
                 max_peers: int = 10,
                 hydrate:bool = False) :  
        """
        Initialize a TorrentClient.

        Args:
            torrent_source (Union[str, Path, TorrentSource]):
                Either:
                    - Path to a .torrent file
                    - Magnet link string
                    - TorrentSource custom class
            download_path (Union[str, Path]): Directory or file path to save the downloaded data.
        """

        # Note peer id is generated for each run

        self.config_manager: ConfigManager = ConfigManager()
        self.download_path: Path = download_path
        
        if isinstance(torrent_source, TorrentSource):
            self.torrent_source: TorrentSource = torrent_source
        else :
            self.torrent_source: TorrentSource = TorrentSource(torrent_source=torrent_source, torrents_dir=self.config_manager.torrents_dir)


        self.status: TorrentStatus = TorrentStatus.PAUSED
        self.peer_id: bytes = self.config_manager.peer_id
        self.date_added: float = date_added or time()
        self.max_peers: int = max_peers

        # Lock 
        self._piece_manager_lock: asyncio.Lock = asyncio.Lock()

        # backup_torrents :Path = self.config_manager.torrents_dir / self.
        # What it need
        # $piece_manager = Manage Pieces
        self.piece_manager: PieceManager = PieceManager(torrent=self.torrent_source.decoded_torrent)

        # $disk_manager  = write and read from disk
        if not hydrate :
            file_map = DiskManager.generate_filemap(torrent=self.torrent_source.decoded_torrent, download_base_dir=self.download_path)
            self.disk_manager:DiskManager = DiskManager(file_map)
        else :
            self.disk_manager: DiskManager = None
        # $tracker_manager = periodically announce and receive tracker response
        # $peer_manager = Manage peer connection

        #

    # For startup
    # Do the boring stuff 
    async def startup(self) :
        """
        Transitions the client from a static state to an active process.
        1. Check local files integrity 
        """

        # Assumption :
        # 1. PieceManager Initialized
        # 2. DiskManager Initialized

        # 1. Start the Disk Worker
        # We must start this first because read_piece uses the thread pool/logic
        # inside the DiskManager infrastructure.
        if self.disk_manager:
            self._disk_worker_task: asyncio.Task = asyncio.create_task(self.disk_manager.start_worker())

        print(f"Checking integrity for: {self.torrent_source.name}...")

        # 2. Integrity Check (The "Force Recheck")
        # We loop through every piece index defined in the metadata
        total_pieces:int = self.piece_manager.total_pieces
        piece_length:int = self.piece_manager.piece_size
        total_size:int = self.piece_manager.total_size

        for i in range(total_pieces):

            data:bytes = await self.disk_manager.read_piece(i, piece_length, total_size)
            # Optimization: If the data is all zeros or empty, skip hashing
            if not data or all(v == 0 for v in data):
                continue

            if self.piece_manager.verify_piece(i, data):
                self.piece_manager.mark_piece_complete(i)
            
        
        # 3. Finalize Status
        # Calculate how much we have vs how much we need
        percent:float = (self.piece_manager.completed_count / total_pieces) * 100
        print(f"Integrity check complete: {percent:.2f}% downloaded.")

        self.status = TorrentStatus.DOWNLOADING



    def to_dict(self: "TorrentClient") -> Dict[str, Any] :
        """
        Serializes the Orchestrator state.
        Note: self: "TorrentClient" is implied and usually omitted but I like to be Implicit.
        """
        return {
            "torrent_source": self.torrent_source.to_dict(),
            "download_path": str(self.download_path),
            "date_added": self.date_added,
            "status" : self.status.value,
            "max_peers": self.max_peers,
            # Temporary set to None
            "state" : {
                "bitfield": self.piece_manager.to_hex() ,                   # self.piece_manager.get_bitfield_hex()
                "disk_man_state" : self.disk_manager.to_dict()
            }
        }
    
    @classmethod
    def from_dict(cls, data:Dict[str, Any]) -> "TorrentClient" :

        source:TorrentSource = TorrentSource.from_dict(data["torrent_source"])
        client:TorrentClient = cls(torrent_source=source, 
                                   download_path=data["download_path"], 
                                   date_added=data.get('date_added', None), 
                                   max_peers=data.get('max_peers', 10), 
                                   hydrate=True)

        client.status = TorrentStatus(data.get("status", "paused"))

        # Restore from BitField
        client.piece_manager = PieceManager(source.decoded_torrent)
        bitfield:str = data.get('state', {}).get('bitfield', None)

        if bitfield :
            client.piece_manager.from_hex(bitfield)


        # Restore Disk Manager State
        disk_man_state:Dict = data.get('state', {}).get('disk_man_state', None)
        if (disk_man_state) :
            client.disk_manager = DiskManager.from_dict(disk_man_state)
        else :
            # if corrupted re-initialize
            file_map = DiskManager.generate_filemap(torrent=client.torrent_source.decoded_torrent, download_base_dir=client.download_path)
            client.disk_manager = DiskManager(file_map)

        return client
