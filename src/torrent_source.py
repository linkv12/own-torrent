import shutil
from pathlib import Path
from typing import Any, Dict, Optional, OrderedDict, Union

from src.torrent_parser import get_torrent_name, info_hash, open_torrent


class TorrentSource:
    def __init__(self, torrent_source: Union[str, Path], torrents_dir: Path) :
        # 
        self.torrents_dir = torrents_dir
        self.name:str = 'Unknown torrent'

        # Hash for uniqueness
        self.info_hash: str = None

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

        self.name = get_torrent_name(self.decoded_torrent)
        self.info_hash = info_hash(self.decoded_torrent).hex()

    def to_dict(self) -> Dict[str, Any] :
        """Return a JSON-serializable dict of this TorrentSource."""
        return {
            "info_hash"     : self.info_hash,
            "magnet_link"   : self.magnet_link,
            "torrent_file"  : str(self.torrent_file) if self.torrent_file else None,
            "torrents_dir"  : str(self.torrents_dir)
        }
    
    @property
    def size(self: "TorrentSource") -> str | None :
        """Return a Human readable size from torrent

        Args:
            self (TorrentSource): its own

        Returns:
            str | None: Human readable or None
        """
        info: OrderedDict = self.decoded_torrent[b"info"]
        length:int = 0
        return_str: str|None = None


        if (b"length" in info) :
            length = info[b"length"]
        elif b"files" in info:
            length = sum(file[b"length"] for file in info[b"files"])
        


        for unit in ["B", "KB", "MB", "GB", "TB"] :
            if (length < 1024) :
                return_str = f"{length:.2f} {unit}"
                break
            length = length / 1024

        return return_str

    @classmethod
    def from_dict(cls, data: dict) -> "TorrentSource":
        """Restore TorrentSource from a dict."""
        torrents_dir: Path = Path(data["torrents_dir"])
        source: Union[str, Path] = data["magnet_link"] if data["torrent_file"] is None else Path(data["torrent_file"])
        instance: TorrentSource = cls(torrent_source=source, torrents_dir=torrents_dir)
        return instance


    @classmethod
    def info_hash(cls, torr_path: Path) -> str :
        ret_val: str = ''
        try :


            # torr_path : Have to be exists
            torr: OrderedDict = open_torrent(path=torr_path)

            ret_val = info_hash(torr).hex()
        except Exception:
            pass

        finally:
            return ret_val

        




