

import asyncio
from enum import Enum
from pathlib import Path
from time import time
from typing import Any, Dict, Optional, Union


from src.disk_manager import DiskManager
from src.peer_manager import PeerManager
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


        self._initialized: bool = False
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

        # Self Hydrate Flag
        # $for re-check
        self.hydrate: bool = hydrate

        # Lock 
        self._piece_manager_lock: asyncio.Lock = asyncio.Lock()

        # backup_torrents :Path = self.config_manager.torrents_dir / self.
        # What it need
        # $piece_manager = Manage Pieces
        self.piece_manager: PieceManager = PieceManager(torrent=self.torrent_source.decoded_torrent)


        # New components for peer handling
        self.peer_queue: asyncio.Queue[tuple[str, int]] = asyncio.Queue()
        self.discovered_peers: set[tuple[str, int]] = set()
        self._processor_task: Optional[asyncio.Task] = None


        # $disk_manager  = write and read from disk
        # $peer_manager = Manage peer connection
        if not hydrate :
            # New Creation
            file_map = DiskManager.generate_filemap(torrent=self.torrent_source.decoded_torrent, download_base_dir=self.download_path)
            self.disk_manager:DiskManager = DiskManager(file_map, self.piece_manager.piece_size)
            self.peer_manager: PeerManager = PeerManager(self.piece_manager, self.disk_manager)
        else :
            # This two component will be handled on @from_dict
            self.disk_manager: DiskManager = None
            self.peer_manager: PeerManager = None

        # $tracker_manager = periodically announce and receive tracker response
        
        
        #



    # For startup
    # Do the boring stuff 
    async def startup(self) :
        """
        Transitions the client from a static state to an active process.
        1. Check local files integrity 
        """

        # 2. Integrity Check (The "Force Recheck")
        # Refine to not do on each start up, but believe saved state bitfield


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
        # piece_length:int = self.piece_manager.piece_size
        # total_size:int = self.piece_manager.total_size

        for i in range(total_pieces):

            data:bytes = await self.disk_manager.read_piece(i)
            # data:bytes = await self.disk_manager.read_piece(i, piece_length, total_size)
            # Optimization: If the data is all zeros or empty, skip hashing
            # if not data or all(v == 0 for v in data):
            #     continue

            if self.piece_manager.verify_piece(i, data):
                self.piece_manager.mark_piece_complete(i)
            
        
        # 3. Finalize Status
        # Calculate how much we have vs how much we need
        percent:float = (self.piece_manager.completed_count / total_pieces) * 100
        print(f"Integrity check complete: {percent:.2f}% downloaded.")

        self.status = TorrentStatus.DOWNLOADING

        self._initialized: bool = True

        
    def add_peers(self, peers: list[tuple[str, int]]) -> None:
        """
        Called periodically by TrackerManager (via TorrentClientManager).
        Pushes new peers into the queue for connection attempts.
        """
        for ip, port in peers:
            if (ip, port) not in self.discovered_peers:
                self.discovered_peers.add((ip, port))
                # Thread-safe way to add to queue from the Tracker loop
                self.peer_queue.put_nowait((ip, port))

    async def _peer_processor(self):
        """
        Background task that manages connection attempts.
        """
        while self.status != TorrentStatus.FINISHED:
            try:
                # Wait for next peer from the tracker
                ip, port = await self.peer_queue.get()

                # Only connect if we haven't hit the max_peers limit
                if self.peers_amount < self.max_peers:
                    # We create a task so we can connect to multiple peers in parallel
                    asyncio.create_task(
                        self.add_peer(
                            ip, 
                            port
                        )
                    )
                
                self.peer_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception :
                # Log error without stopping the whole loop
                continue


    def add_peer(self, ip:str, port:int) -> None :
        self.peer_manager.add_peer(ip, port, bytes.fromhex(self.info_hash), self.peer_id)

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
    
    @property
    def info_hash(self) -> str:
        return self.torrent_source.info_hash
    
    @property
    def torrent_name(self) -> str:
        if isinstance(self.torrent_source, TorrentSource) :
            return self.torrent_source.name
        else :
            return "Unknown Torrent"
    
    @property
    def calculate_progress(self) -> float:
        try :
            return (self.piece_manager.completed_count / self.piece_manager.total_pieces) * 100
        except Exception :
            return 0.0
        
    @property
    def peers_amount(self) -> int:
        try :
            return len(self.peer_manager.peers)
        except Exception :
            return 0

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
            client.disk_manager = DiskManager(file_map, client.piece_manager.piece_size)


        # Init our peer manager here
        client.peer_manager = PeerManager(client.piece_manager, client.disk_manager)

        return client
    

    async def start(self) -> None :
        """
        The Main Event Loop for the Torrent Client.
        """
        # 1. Boring stuff (Integrity check and starting Disk Workers)
        await self.startup()

        # 2. Start the PeerManager Dispatcher
        self.p: asyncio.Task = asyncio.create_task(self.peer_manager.start())

        # 3. Start the Peer Queue Processor
        self._processor_task = asyncio.create_task(self._peer_processor())

        # CRITICAL: This allows the Peer.run task to actually begin!
        await asyncio.sleep(5)

        # 
        try:
            while self.status == TorrentStatus.DOWNLOADING: 
                if self.piece_manager.is_complete:
                    self.status = TorrentStatus.FINISHED
                    break

                # Dynamic adjustment: if we dropped too many peers, 
                # maybe clear 'discovered' to allow retries.
                if self.peers_amount < (self.max_peers // 2) and self.peer_queue.empty():
                    self.discovered_peers.clear()
                    
                await asyncio.sleep(1) # Frequency of status/UI checks
        except asyncio.CancelledError:
            print(f"Shutting down client: {self.torrent_name}")
        finally:
            if self._processor_task:
                self._processor_task.cancel()
            await self.shutdown()

    
    async def shutdown(self) -> Dict[str, Any] :
        # state: Dict[str, Any] = {self.info_hash: self.to_dict()}
        state: Dict[str, Any] = self.to_dict()

        _ = await self.disk_manager.shutdown()
        await self.peer_manager.stop()

        
        print("TorrentClient shutdown ...")

        return state