import struct
from typing import Any, Dict, OrderedDict

from src.torrent_parser import info_hash
from src.utils.generate_id import gen_peer_id

def build_handshake_bytes (info_hash:bytes, peer_id:bytes) -> bytes:
    """
    Build a BitTorrent handshake message from peer_id and info_hash.

    Handshake format:
        <pstrlen><pstr><reserved><info_hash><peer_id>

    Fields:
        pstrlen:
            Length of the protocol string <pstr>, as a single raw byte.
        pstr:
            Protocol identifier string.
        reserved:
            Eight (8) reserved bytes. All current implementations use zeroes.
        info_hash:
            20-byte SHA1 hash of the bencoded 'info' dictionary from the torrent.
        peer_id:
            20-byte string used as a unique ID for the client.

    Notes:
        In BitTorrent protocol version 1.0:
            - pstrlen = 19
            - pstr = "BitTorrent protocol"

    Args:
        info_hash (Bytes):
            20-byte SHA1 hash of the bencoded 'info' dictionary from the torrent.
        peer_id (Bytes):
            20-byte string used as a unique ID for the client.
        

    Returns:
        bytes:
            The complete 68-byte BitTorrent handshake message.
    """
    # Constant for Protocol
    pstr = b"BitTorrent protocol"
    pstrlen = len(pstr)

    handshake_bytes = bytearray(68)

    # pstrlen
    handshake_bytes[0] = pstrlen

    # pstr 
    handshake_bytes[1:1 + pstrlen] = pstr

    # reserved (8 bytes)
    handshake_bytes[1 + pstrlen : 1 + pstrlen + 8] = b"\x00" * 8

    # info_hash (20 bytes)
    handshake_bytes[28:48] = info_hash

    # peer_id (20 bytes)
    handshake_bytes[48:68] = peer_id


    return bytes(handshake_bytes)

def build_handshake (torrent:OrderedDict) -> bytes:
    """
    Build a BitTorrent handshake message from a decoded .torrent file.

    Handshake format:
        <pstrlen><pstr><reserved><info_hash><peer_id>

    Fields:
        pstrlen:
            Length of the protocol string <pstr>, as a single raw byte.
        pstr:
            Protocol identifier string.
        reserved:
            Eight (8) reserved bytes. All current implementations use zeroes.
        info_hash:
            20-byte SHA1 hash of the bencoded 'info' dictionary from the torrent.
        peer_id:
            20-byte string used as a unique ID for the client.

    Notes:
        In BitTorrent protocol version 1.0:
            - pstrlen = 19
            - pstr = "BitTorrent protocol"

    Args:
        torrent (OrderedDict):
            Decoded bencoded torrent metadata. Must contain the key b'info'.

    Returns:
        bytes:
            The complete 68-byte BitTorrent handshake message.
    """
    # Constant for Protocol
    pstr = b"BitTorrent protocol"
    pstrlen = len(pstr)

    # Singleton
    peer_id = gen_peer_id()

    handshake_bytes = bytearray(68)

    # pstrlen
    handshake_bytes[0] = pstrlen

    # pstr 
    handshake_bytes[1:1 + pstrlen] = pstr

    # reserved (8 bytes)
    handshake_bytes[1 + pstrlen : 1 + pstrlen + 8] = b"\x00" * 8

    # info_hash (20 bytes)
    handshake_bytes[28:48] = info_hash(torrent)

    # peer_id (20 bytes)
    handshake_bytes[48:68] = peer_id


    return bytes(handshake_bytes)

def parse_handshake (payload: bytes) -> Dict[str, Any] : 


    # IF < 68 bytes error

    pstr_len:int = payload[0]

    pstr_start:int = 1
    pstr_end:int = pstr_start + pstr_len
    pstr:str = payload[pstr_start:pstr_end].decode("utf-8")

    #

    reserved_start:int = pstr_end
    reserved_end:int = reserved_start + 8
    reserved: bytes = payload[reserved_start: reserved_end]


    # info hash
    info_hash_start:int = reserved_end
    info_hash_end:int = info_hash_start + 20
    info_hash:str = (payload[info_hash_start:info_hash_end]).hex()

    # peer_id (20 bytes) 
    peer_id_start = info_hash_end 
    peer_id_end = peer_id_start + 20 
    peer_id = payload[peer_id_start:peer_id_end].decode('ascii')  


    return {
        "pstrlen": pstr_len,
        "pstr": pstr,
        "reserved": reserved.hex(),             # hex str
        "info_hash": info_hash,                 # hex string
        "peer_id": peer_id,                     # if ASCII-safe
    }

def build_keep_alive() -> bytes:
    """
    Build a BitTorrent keep-alive message.

    A keep-alive message consists only of a 4-byte length prefix set to zero.
    It has no message ID and no payload.

    Format:
        <length=0>

    Returns:
        bytes: 4-byte keep-alive message.
    """
    return struct.pack('>I', 0)

def build_choke() -> bytes:
    """
    Build a BitTorrent choke message.

    Format:
        <length=1><id=0>
    Where:
        length:
            4-byte big-endian integer indicating the message length,
            excluding the length prefix itself.
        id:
            Message ID for the choke message (0).

    Returns:
        bytes: 5-byte choke message.
    """
    return struct.pack('>IB', 1, 0)

def build_unchoke() -> bytes:
    """
    Build a BitTorrent unchoke message.

    Format:
        <length=1><id=1>
    Where:
        length:
            4-byte big-endian integer indicating the message length,
            excluding the length prefix itself.
        id:
            Message ID for the unchoke message (1).

    Returns:
        bytes: 5-byte unchoke message.
    """
    return struct.pack('>IB', 1, 1)

def build_interested() -> bytes:
    """
    Build a BitTorrent interested message.

    An interested message is sent to inform a peer that this client
    is interested in downloading pieces from them.

    Format:
        <length=1><id=2>

    Where:
        length:
            4-byte big-endian integer indicating the message length,
            excluding the length prefix itself.
        id:
            Message ID for the interested message (2).

    Returns:
        bytes: 5-byte interested message.
    """
    return struct.pack('>IB', 1, 2)

def build_not_interested() -> bytes:
    """
    Build a BitTorrent not interested message.

    A not interested message is sent to inform a peer that this client
    is no longer interested in downloading pieces from them.

    Format:
        <length=1><id=3>

    Where:
        length:
            4-byte big-endian integer indicating the message length,
            excluding the length prefix itself.
        id:
            Message ID for the not interested message (3).

    Returns:
        bytes: 5-byte not interested message.
    """
    return struct.pack('>IB', 1, 3)

def build_have(piece_index:int) -> bytes:
    """
    Build a BitTorrent have message.

    Indicates that the sender has successfully downloaded and verified
    the specified piece.

    Format:
        <length=5><id=4><piece_index>

    Args:
        piece_index (int): Zero-based index of the piece.

    Returns:
        bytes: 9-byte have message.
    """

    return struct.pack('>IBI', 5, 4, piece_index)

def build_bitfield(bitfield: bytes) -> bytes:
    """
    Build a BitTorrent bitfield message.

    Conveys which pieces the sender has using a bitfield bitmap.

    Format:
        <length=1+X><id=5><bitfield>

    Args:
        bitfield (bytes): Bitfield bitmap.

    Returns:
        bytes: Bitfield message.
    """
    length = 1 + len(bitfield)
    return struct.pack('>IB', length, 5) + bitfield

def build_request(payload:dict) -> bytes :
    """
    Build a BitTorrent request message.

    Requests a specific block within a piece.

    Format:
        <length=13><id=6><index><begin><length>

    Args:
        payload (dict): Dictionary containing:
            - 'index' (int): Piece index.
            - 'begin' (int): Byte offset within the piece.
            - 'length' (int): Number of bytes requested.

    Returns:
        bytes: 17-byte request message.
    """
    return struct.pack(
        '>IBIII', 
        13, 
        6, 
        payload['index'], 
        payload['begin'], 
        payload['length'])

def parse_request(payload:bytes) -> Dict[str, int]:
    """
    Parse a BitTorrent request message.
    12 bytes >III of <index><begin><length>

    Requests a specific block within a piece.

    Format:
        <length=13><id=6><index><begin><length>
        With out >IB length=13 and id

    Args:
        payload (byte): Packed bittorrent request

    Returns:
        dict: Dictionary containing:
            - 'index' (int): Piece index.
            - 'begin' (int): Byte offset within the piece.
            - 'length' (int): Number of bytes requested.
    """

    index:int = 0
    begin:int = 0
    length:int = 0

    index, begin, length = struct.unpack('>III', payload)
    return {
        'index': index,
        'begin': begin,
        'length': length,
    }

def build_piece(payload:dict) -> bytes :
    """
    Build a BitTorrent piece message.

    Sends a block of data for a specific piece.

    Format:
        <length=9+X><id=7><index><begin><block>

    Args:
        payload (dict): Dictionary containing:
            - index (int): Piece index.
            - begin (int): Byte offset within the piece.
            - block (bytes): Block data.

    Returns:
        bytes: Piece message.
    """ 
    length = 9 + len(payload['block'])
    return struct.pack('>IBII', length, 7, payload['index'], payload['begin']) + payload['block']

def parse_piece(payload:bytes) -> Dict[str, int | bytes] :
    """
    Parse a BitTorrent piece message.

    Receive a block of data for a specific piece.

    Format:
        <length=9+X><id=7><index><begin><block>

    Args:
        payload (bytes) : expected response from bittorrent client

    Returns:
        Dict[str, int | bytes]: Dictionary containing:
            - index (int): Piece index.
            - begin (int): Byte offset within the piece.
            - block (bytes): Block data.
    """
    length: int = struct.unpack('>I', payload[0:4])[0]

    # msg_id: int = struct.unpack('>B', payload[4:5])[0]  

    # print(f'gggggg :{msg_id}')
    # we already know 

    index:int   = struct.unpack('>I', payload[5:9])[0]
    begin:int   = struct.unpack('>I', payload[9:13])[0]

    block: bytes = payload[13: 13 + (length - 9)]

    return {
        'index': index,
        'begin': begin,
        'block': block
    }







def build_cancel(payload:dict) -> bytes :
    """
    Build a BitTorrent cancel message.

    Cancels a previously sent request message.

    Format:
        <length=13><id=8><index><begin><length>

    Args:
        payload (dict): Dictionary containing:
            - 'index' (int): Piece index.
            - 'begin' (int): Byte offset within the piece.
            - 'length' (int): Number of bytes requested.

    Returns:
        bytes: 17-byte request message.
    """
    return struct.pack(
        '>IBIII', 
        13, 
        8, 
        payload['index'], 
        payload['begin'], 
        payload['length'])

def build_port(port: int) -> bytes: 
    """
    Build a BitTorrent port message.

    Announces the UDP port the sender is listening on for DHT.

    Format:
        <length=3><id=9><port>

    Args:
        port (int): UDP port number.

    Returns:
        bytes: 7-byte port message.
    """
    return struct.pack('>IBH', 3, 9, port)
