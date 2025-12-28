import socket
import struct
from urllib.parse import urlparse
import random

from typing import Dict, Union



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


