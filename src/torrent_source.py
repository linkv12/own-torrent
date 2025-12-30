import shutil
from pathlib import Path
from typing import Any, Dict, Optional, OrderedDict, Union

from src.torrent_parser import open_torrent


class TorrentSource:
    def __init__(self, torrent_source: Union[str, Path], torrents_dir: Path) :
        # 
        self.torrents_dir = torrents_dir


        # Refference to a string of magnet link
        self.magnet_link: Optional[str] = None
        # Path to .torrent file               
        self.torrent_file: Optional[Path] = None

        # Decoded info bendoced decode
        self.decoded_torrent: Optional[OrderedDict] = None

        if isinstance(torrent_source, str) and torrent_source.startswith("magnet:") :
            self.magnet_link = torrent_source
        elif isinstance(torrent_source, Path) and torrent_source.suffix == ".torrent" :
            # Here copy to the .config 
            # print("Copy to .config/torrents")
            # check if exist first if not copy
            self._torrent_copy_path(torrent_source, torrents_dir)


        self._decode_torrent_source()

        # print(torrent_source.name)

    def _torrent_copy_path(self, torrent_source_file:Path, torrents_dir: Path) -> None:
        """
        Automatically copies the original .torrent file
        to .config/torrents/*.torrent
        """

        destination: Path = torrents_dir / torrent_source_file.name
        if not destination.exists():
            shutil.copy2(torrent_source_file, destination)
        
        self.torrent_file:Optional[Path] = destination

    def _decode_torrent_source(self) -> None:
        if (self.torrent_file is not None) :
            self.decoded_torrent: Optional[OrderedDict] = open_torrent(self.torrent_file)

    def to_dict(self) -> Dict[str, Any] :
        """Return a JSON-serializable dict of this TorrentSource."""
        return {
            "magnet_link": self.magnet_link,
            "torrent_file" : str(self.torrent_file) if self.torrent_file else None,
            "torrents_dir" : str(self.torrents_dir)
        }
    

    @classmethod
    def from_dict(cls, data: dict) -> "TorrentSource":
        """Restore TorrentSource from a dict."""
        torrents_dir = Path(data["torrents_dir"])
        source: Union[str, Path] = data["magnet_link"] if data["torrent_file"] is None else Path(data["torrent_file"])
        instance = cls(torrent_source=source, torrents_dir=torrents_dir)
        return instance



