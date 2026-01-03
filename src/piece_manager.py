
from enum import Enum
from hashlib import sha1
import math
import struct
from typing import Dict, List, Optional, OrderedDict, Tuple

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

        # Pieces 
        self.pieces: Dict[int,Piece] = {}
        # Init empty
        self._init_pieces_list()

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

            self.pieces[index].mark_as_finished()

    def invalidate_piece(self, index:int) -> None :
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
            self.bitfield_container[byte_index] &= ~(1 << bit_index)
            self.pieces[index]._invalidate_all_blocks()

    def mark_block_received(self: 'PieceManager', index:int, offset: int) -> bool :

        piece: Piece = self.pieces.get(index)

        if not piece :
            # Here is errror Piece not found
            return False

        return piece.mark_received(offset)

    
    def get_next_request(self, peer_bitfield:bytes) -> Optional[Tuple[int, int, int]] :

        # print('Peer bitfield: ',peer_bitfield.hex())
        for index, piece in self.pieces.items() :
            if piece.is_verified:
                continue

            if not self._peer_has_piece(peer_bitfield, index) :
                # print(f"{index}: {not self._peer_has_piece(peer_bitfield, index)}")
                continue

            for block in piece.blocks:
                if block['state'] == BlockState.Missing :
                    block['state'] = BlockState.Pending

                    
                    return (piece.index, block['begin'], block['length'])

        return None

    def _peer_has_piece(self, peer_bitfield:bytes, index:int) -> bool :
        

        byte_index: int = index // 8
        if byte_index >= len(peer_bitfield) :
            return False
        bit_index: int = 7 - (index % 8)

        return bool(peer_bitfield[byte_index] & (1 << bit_index))

    def to_hex(self: "PieceManager") -> str:
        """Converts the bitfield to a hex string for storage """
        return self.bitfield_container.hex()
    

    # Since this one will be called after _constrtuctor
    # We have to update all piece in self.pieces to reflect new bitfield
    def from_hex(self: "PieceManager", hex_str: str) -> None :
        """Restores the bitfield from a hex string."""
        new_bitfield:bytearray = bytearray.fromhex(hex_str)
        if len(new_bitfield) != self.bitfield_size:
            raise ValueError("Bitfield Size Mismatch")

        self.bitfield_container:bytearray = new_bitfield
        self._update_all_pieces_data()

    # Only for updating used in from_hex only
    def _update_all_pieces_data(self) -> None :
        # print(self.bitfield.hex())
        for i in range(self.total_pieces):
            piece: Piece = self.pieces[i]


            
            # print(f'{i} : {self.has_piece(i)}')
            # Get the index from piece obj
            # Since its our ground truth
            if (self.has_piece(i)) :
                piece.mark_as_finished()
                # print(f'{i} : {piece.blocks}')
                
    # Init empty pieces: List[Piece]
    def _init_pieces_list(self) -> None:
        for i in range(self.total_pieces):
            piece: Piece = Piece(i, self.piece_size)

            if (self.has_piece(i)) :
                piece.mark_as_finished()


            self.pieces[i] = piece

    def has_piece(self, index:int) -> bool :
        if not (0 <= index < self.total_pieces) :
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

        # Data failed hashsing
        if not (actual_hash == expected_hash) :
            
            return False
        return actual_hash == expected_hash

    @property
    def completed_count(self) -> int :
        return bin(int.from_bytes(self.bitfield_container, 'big')).count('1')

    @property
    def is_complete(self) -> bool :
        return self.completed_count == self.total_pieces
    
    # DEBUG
    # def _

class Piece :
    def __init__(self, index:int, piece_size: int) :
        
        # Block Size
        # FLAG: !CONSTANT
        self._MAX_BLOCK_SIZE: int = 16384

        # Piece Index in the torrent
        self.index: int = index

        # Piece Size 
        self.piece_size: int = piece_size

        # Calc. Number of block in this piece
        self.num_of_block:int= math.ceil(piece_size/self._MAX_BLOCK_SIZE)

        # Track state of every block
        self.blocks: List[Dict[str, int | BlockState]] = self._generate_blocks()

        # is verified
        self.is_verified: bool = False

    def _generate_blocks(self) :
        block : List[Dict[str, int | BlockState]] = []

        for i in range(self.num_of_block):
            begin: int = i * self._MAX_BLOCK_SIZE
            length: int = min(self._MAX_BLOCK_SIZE, self.piece_size - begin)

            block.append(
                {
                    'begin': begin,
                    'length': length,
                    'state' : BlockState.Missing

                }

            )

        return block


    def _invalidate_all_blocks(self) -> None:
        """
        Invalidate all blocks since the piece have marked as invalid on verify
        """
        self.blocks = self._generate_blocks()
        self.is_verified = False

    def mark_received(self, offset:int) -> bool :
        
        block_id: int = offset // self._MAX_BLOCK_SIZE
        if block_id < self.num_of_block :
            self.blocks[block_id]['state'] = BlockState.Retrieved
        return self.is_full

    def is_complete(self) -> bool:
        if self.is_verified:
            return True
        return all(s['state'] == BlockState.Retrieved for s in self.blocks) 
    
    @property
    def is_full(self) -> bool :
        return self.is_complete()
    
    def mark_as_finished(self) -> None:
        # if in bitfield is says we have this block
        # for b in self.blocks :
        #     b['state'] = BlockState.Retrieved
        
        self.is_verified = True
        self.blocks = []

class BlockState(Enum):
    Missing = 0
    Pending = 1
    Retrieved = 2
