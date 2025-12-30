import json
import os
from pathlib import Path
import shutil
import threading
from typing import Any, Dict, Optional


class ConfigManager:
    """
    Utility class to manage torrent client state and peer IDs.

    Stores all torrent clients in a single JSON file inside a config directory.
    """

    _instance: Optional["ConfigManager"] = None
    _lock: threading.Lock = threading.Lock()  # ensures thread-safe singleton init

    def __new__(cls, *args, **kwargs) -> "ConfigManager":
        if cls._instance is None:
            with cls._lock :
                if cls._instance is None :
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config:str = "app_config.json") -> None:
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._initialized = True

        self.app_config_dir : Path = Path.cwd() / ".config"
        self.app_config_file: Path = self.app_config_dir / config
        self.client_state: Path = self.app_config_dir / "torrent_client_state.json"


        self.torrents_dir: Path = self.app_config_dir / "torrents"
        


        self.peer_id: bytes = b""

        self._ensure_config_dir()
        self._ensure_torrents_dir()
        self._load_or_create_app_config()

        if not self.client_state.exists():
            self.client_state.write_text(json.dumps({}))


    
    def _ensure_config_dir(self) -> None:
        """Ensure the .config folder exists."""
        self.app_config_dir.mkdir(parents=True, exist_ok=True)

    def _ensure_torrents_dir(self) -> None:
        """Ensure the .config/torrents folder exists."""
        self.torrents_dir.mkdir(parents=True, exist_ok=True)

    def _load_or_create_app_config(self) -> None:
        """Load app_config_file or create it with a new peer_id if missing or invalid."""
        config_valid = self._is_json_valid(self.app_config_file)

        if config_valid:
            with self.app_config_file.open("r") as file: 
                data = json.load(file)

            peer_id_hex = data.get('peer_id')
            if peer_id_hex and len(peer_id_hex) == 40 :
                self.peer_id = bytes.fromhex(peer_id_hex)
            else :
                self._create_new_peer_id()
        else :
            self._create_new_peer_id()

    def _create_new_peer_id(self) -> None:
        """
        Generate a 20-byte peer ID for the BitTorrent client and save it in app_config_file.

        The first 8 bytes identify the client and version:
            - Format: '-XXYYYY-'
            - 'XX' = client code (here 'PZ', chosen because it is not used by other clients)
            - 'YYYY' = client version (here '0001')

        The remaining 12 bytes are random, ensuring uniqueness for each peer instance.

        Example peer ID:
            b'-PZ0001-Ab3kL9x8Jq1R'

        See: https://wiki.theory.org/BitTorrentSpecification
        """

        peer_id = bytearray(os.urandom(20))       # 20 random bytes
        peer_id[0:8] = b'-PZ0001-'                # overwrite first 8 bytes

        self.peer_id = peer_id
        self._save_peer_id()

    def _save_peer_id(self) -> None :
        """Save the peer_id to app_config_file as hex, preserving other keys."""
        data: Dict[str, Any] = {}
        if self.app_config_file.exists():
            try:
                with self.app_config_file.open('r') as f:
                    data = json.load(f)
            except json.JSONDecodeError:
                data = {}

        data['peer_id'] = self.peer_id.hex()

        with self.app_config_file.open('w') as f:
            json.dump(data, f, indent=4)

    def save_torrent_file(self, source_path: Path) -> Path:
        """
        Save a copy of the .torrent file into the config torrents folder.

        Args:
            source_path (Path): Path to the original .torrent file.

        Returns:
            Path: Path to the saved copy in the torrents folder.
        """
        target_path = self.torrents_dir / source_path.name
        shutil.copy2(source_path, target_path)
        return target_path


    @staticmethod
    def _is_json_valid(file_path: Path) -> bool :
        """Check if the given JSON file is valid."""
        if not file_path.exists():
            return False
        try :
            with file_path.open("r") as f :
                json.load(f)
            return True
        except json.JSONDecodeError :
            return False