from pathlib import Path
import struct
from typing import OrderedDict, Union
import hashlib
import bencodepy

from src.utils.error_catching import catch_exception


@catch_exception
def open_torrent(path: Union[str, Path]) -> OrderedDict:
    """
    Open and decode a .torrent file using bencodepy.

    Args:
        path (Union[str, Path]): Path to the .torrent file.

    Returns:
        OrderedDict: Decoded Bencoded content of the torrent file.
    """
    if isinstance(path, str) :
        path = Path(path)

    with path.open('rb') as files :
        return bencodepy.decode(files.read())

@catch_exception
def info_hash(torrent: OrderedDict) -> bytes:
    info = bencodepy.encode(torrent[b'info'])
    return hashlib.sha1(info).digest()

@catch_exception
def total_size(torrent: OrderedDict) -> bytes: 
    """
    Calculate the total size of a torrent in bytes.

    Handles both single-file and multi-file torrents.
    
    Args:
        torrent (OrderedDict): Decoded torrent content (from bencodepy).

    Returns:
        bytes: 8-byte big-endian representation of total size.
    """

    size = 0
    info = torrent.get(b'info', {})
    if b'files' in info and info[b'files'] :
        size =  sum(file[b'length'] for file in info[b'files'])
    else :
        size = info[b'length']
    
    # Convert integer to 8-byte big-endian binary
    return struct.pack('>Q', size)

def get_torrent_name(torrent:OrderedDict) -> str:
    """
    Get Torrent name from info/name
    
    Args:
        torrent (OrderedDict): Decoded torrent content (from bencodepy).

    Returns:
        str: string representing torrent name or fallback
    """

    info: OrderedDict = torrent.get(b'info')
    if not info:
        return "Unknown"

    name_bytes:bytes = info.get(b'name', b'unknown_torrent')

    return name_bytes.decode('utf-8', errors='replace')

