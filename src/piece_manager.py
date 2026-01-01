
from hashlib import sha1
import math
import struct
from typing import OrderedDict

from src.torrent_parser import total_size



class PieceManager:
    """
        ### Responsibilities
        - Track piece and block state
        - Maintain local bitfield
        - Decide next block to request
        - Validate piece hashes

        ### Important
        - **Not async**, but **async-safe**
        - Protected by `asyncio.Lock` on Torrent Client

        ### Does NOT
        - Perform I/O
        - Talk to peers directly
    
    """

    def __init__ (self:"PieceManager", torrent:OrderedDict) :
        self.info:OrderedDict = torrent.get(b'info', {})
        self.pieces_hashes: bytes = self.info.get(b'pieces', b'')

        self.total_pieces: int = len(self.pieces_hashes) // 20

        self.piece_size: int = torrent[b'info'][b'piece length']
        

        self.total_size:int = struct.unpack('>Q', total_size(torrent))[0]
        # Byte to bit divide by 8
        self.bitfield_size: int = math.ceil(self.total_pieces / 8)
        self.bitfield_container: bytearray = bytearray(self.bitfield_size)

    @property
    def bitfield(self: "PieceManager") -> bytes:
        """Returns the bitfield as immutable bytes for network transmission."""
        return bytes(self.bitfield_container)
    
    def mark_piece_complete(self: "PieceManager", index:int) -> None:
        if 0 <= index < self.total_pieces:
            # Find the byte location
            # By take the total_piece divide by 8 than flooring it
            # Simplified by // 8
            byte_index: int = index // 8
            
            # Find the bit index -> bit location in the byte
            # since we know each byte is 0 - 7
            # we can modulo it 
            bit_index: int = 7 - (index % 8)

            # Manipulate the bit
            self.bitfield_container[byte_index] |= (1 << bit_index)
    

    def to_hex(self: "PieceManager") -> str:
        """Converts the bitfield to a hex string for storage """
        return self.bitfield_container.hex()
    
    def from_hex(self: "PieceManager", hex_str: str) -> None :
        """Restores the bitfield from a hex string."""
        new_bitfield:bytearray = bytearray.fromhex(hex_str)
        if len(new_bitfield) != self.bitfield_size:
            raise ValueError("Bitfield Size Mismatch")

        self.bitfield_container:bytearray = new_bitfield

    def has_piece(self, index:int) -> bool :
        if 0 <= index < self.total_pieces :
            return False

        byte_index: int = index // 8
        bit_index: int = 7 - (index % 8)

        return bool(self.bitfield_container[byte_index] & (1 << bit_index)) 
    
    def verify_piece(self, index:int, data:bytes) -> bool:
        """
        Hashes the provided data and compares it against 
        the expected hash from the torrent file.
        """
        if not data :
            return False
        
        # 
        start:int = index * 20
        expected_hash:bytes = self.pieces_hashes[start : start+20]

        actual_hash:bytes = sha1(data).digest() 
        return actual_hash == expected_hash


    @property
    def completed_count(self) -> int :
        return bin(int.from_bytes(self.bitfield_container, 'big')).count('1')

