import os
import struct
import random

from typing import List, Dict, OrderedDict, Union

from src.torrent_parser import info_hash, total_size
from src.utils import generate_id



def build_conn_request() -> bytes:
    """
    Generate a UDP tracker connection request packet.

    See: http://bittorrent.org/beps/bep_0015.html

    Returns:
        bytes: The packed connection request as a 16-byte binary string.
    """
    transaction_id = random.randint(0, 2**32-1)
    connect_msg = struct.pack(">QLL", 0x41727101980, 0, transaction_id)

    return connect_msg

def parse_conn_response(resp:bytes) -> Dict[str, Union[int, bytes]]:
    """
    Parse a UDP tracker connection response packet according to BEP 0015.

    See: http://bittorrent.org/beps/bep_0015.html

    Args:
        resp (bytes): The raw 16-byte response from the UDP tracker.

    Returns:
        dict: A dictionary containing:
            - "action" (int): The action field from the response.
            - "transaction_id" (int): The transaction ID from the response.
            - "connection_id" (bytes): The 8-byte connection ID.
    """
    action = struct.unpack(">I", resp[0:4])[0]
    transaction_id = struct.unpack(">I", resp[4:8])[0] 
    connection_id = resp[8:]

    return {
        "action": action,
        "transaction_id": transaction_id,
        "connection_id": connection_id
    }

def build_announce_request(conn_id:bytes, torrent: OrderedDict, port:int = 6969) -> bytes :
    """
    Build a UDP tracker announce request packet (98 bytes).

    Args:
        conn_id (bytes): 8-byte connection ID from tracker connect response.
        torrent (OrderedDict): Decoded torrent content from bencodepy.
        port (int, optional): Port number to announce. Defaults to 6969.

    Returns:
        bytes: Packed 98-byte UDP announce request.
    """

    buf = bytearray(98)

    # Connection ID
    buf[0:8] = conn_id
    # Action = 1 (announce)
    buf[8:12]= struct.pack(">I", 1)
    # Transaction ID: random 4 bytes
    buf[12:16] = os.urandom(4)
    # Info hash: SHA1 of bencoded 'info' dictionary
    buf[16:36] = info_hash(torrent)

    # Peer ID
    buf[36:56] = generate_id.gen_peer_id()

    # Downloaded
    buf[56:64] = struct.pack(">Q", 0)

    # Left (Data not Dowloaded) ==> All
    buf[64:72] = total_size(torrent)

    # Uploaded ==> 0 since no uploaded yet
    buf[72:80] = struct.pack(">Q", 0)

    # Event => 0
    buf[80:84] = struct.pack(">I", 0)

    # IP Address => 0
    buf[84:88] = struct.pack(">I", 0)


    # Key: random 4 bytes
    buf[88:92] = os.urandom(4)
    # Num want = -1 (all)
    buf[92:96] = struct.pack(">i", -1)
    # Port
    buf[96:98] = struct.pack(">H", port)

    return bytes(buf)


def parse_announce_response(resp: bytes) -> Dict[str, Union[int, List[Dict]]] :
    """
    Parse a UDP tracker announce response.

    Args:
        resp (bytes): Raw response from tracker.

    Returns:
        dict: Parsed announce info with action, transactionId, leechers, seeders, and peers.
    """

    # Read fixed-size integers (big-endian)
    action, transaction_id, leechers, seeders = struct.unpack(">IIII", resp[:16])

    # Peers list (offset 20)
    peers_bytes: bytes = resp[20:]
    peers: List[Dict] = []

    # IP address    is 32 bit => 4 Bytes
    # Port          is 16 bit => 2 Bytes
    for i in range(0, len(peers_bytes), 6) :
        ip_bytes = peers_bytes[i:i+4]
        port_bytes = peers_bytes[i+4:i+6]

        ip = ".".join(str(b) for b in ip_bytes)
        port = struct.unpack(">H", port_bytes)[0]

        peers.append({"ip": ip, "port": port})

    return {
        "action": action,
        "transactionId": transaction_id,
        "leechers": leechers,
        "seeders": seeders,
        "peers": peers
    }


def parse_response_type(resp:bytes) -> str:
    """
    Parse the action type from a BitTorrent UDP tracker response.

    The first 4 bytes of a UDP tracker response represent the
    action field (big-endian unsigned int), which determines
    the type of response.

    Action values:
        0 -> connect response
        1 -> announce response

    Else :
        unknown response    

    Args:
        resp (bytes): Raw UDP tracker response data.

    Returns:
        str: The response type ("connect" or "announce").
    """
    action = struct.unpack('>I', resp[:4])
    if (action == 0) :
        return 'connect'
    elif (action == 1) :
        return 'annouce'
    else :
        return 'unknown'