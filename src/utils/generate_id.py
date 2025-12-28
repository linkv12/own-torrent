import os

_id = None

def gen_peer_id() -> bytes:
    """
    Generate a 20-byte peer ID for the BitTorrent client.

    The first 8 bytes identify the client version ('-OT0001-').
    The remaining 12 bytes are random.
    Returns:
        bytes: The packed peer id as a 20-byte binary string.

    """
    global _id
    if _id is None:
        _id = bytearray(os.urandom(20))       # 20 random bytes
        _id[0:8] = b'-AT0001-'                # overwrite first 8 bytes
    return bytes(_id)