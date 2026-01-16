
from __future__ import annotations
from ast import Dict
import asyncio
import struct
from typing import Any, Optional
from typing import TYPE_CHECKING

from src.message import build_bitfield, build_handshake_bytes, build_have, build_interested, build_piece, build_request, parse_handshake

if TYPE_CHECKING:
    # This is only seen by IDEs/Type checkers, ignored at runtime
    from src.peer_manager import PeerManager





class Peer:

    def __init__(self, ip:str, port:int, info_hash:bytes, peer_id:bytes):
        # FLAG: !CONSTANT
        self._MAX_BLOCK_SIZE: int = 16384


        self.ip:str = ip
        self.port: int = port
        self.info_hash :bytes = info_hash

        # my peer id
        self.my_peer_id:bytes = peer_id
        self.peer_id:Optional[bytes] = None         # Other peer id


        # 
        self.reader:Optional[asyncio.StreamReader] = None
        self.writer:Optional[asyncio.StreamWriter] = None

        # BitTorrent Protocol state
        self.peer_bitfield: Optional[bytearray] = None
        self.am_choking:bool = True
        self.am_intrested:bool = False

        self.peer_choking: bool = True
        self.peer_intrested:bool = False


        self._stop_event: asyncio.Event = asyncio.Event()

        # Handshake success n General Connection Health
        self.handshake_sucess:bool = False
        self.bad_peer:bool = False

        # Tracking Request for Block
        self.request_queue: asyncio.Queue[Dict[str, int]] = asyncio.Queue(maxsize=2)


        # 
        self.is_active: bool = True


    def peer_has_piece(self, index: int) -> bool:
        if not (0 <= index < len(self.peer_bitfield)) :
            return False

        byte_index: int = index // 8
        bit_index: int = 7 - (index % 8)

        return bool(self.peer_bitfield[byte_index] & (1 << bit_index))

    async def run(self, peer_manager: PeerManager) :
        print(f"peer is running @{self.ip}:{self.port}")
        try:
            # 1. Open TCP Connection
            (self.reader, self.writer) = await asyncio.open_connection(host=self.ip, port=self.port)

            # 2. Handshake
            await self._do_handshake()


            if (self.handshake_sucess) :
                # 2.1 Send bitfield
                # Check our bitfield
                # Rule: Only send if we have at least one bit set to 1
                if any(byte != 0 for byte in peer_manager.piece_manager.bitfield) :
                    print(f'Sending our bitfield : {peer_manager.piece_manager.bitfield.hex()}')
                    await self._send_bitfield(peer_manager.piece_manager.bitfield)

                # 2.2. Send Interested
                if not peer_manager.piece_manager.is_complete :
                    # print("We are interested not Complete yet")
                    await self._send_interested()

                # 2.3. Send Unchoke for Upload Capability 
                


                # 3. Main Event Loop
                await asyncio.gather(
                    self._handle_message(peer_manager),
                    self._process_outgoing_requests()
                )


        except Exception as e:
            print(f"Connection lost with {self.ip}: {e}")
        finally:
            self.is_active = False # CRITICAL: mark as inactive
            await self.close()
            await peer_manager.remove_peer(self)



    # Sending to peer
    async def _send_bitfield(self, bitfield: bytes) -> None:
        bitfield_msg: bytes = build_bitfield(bitfield)
        self.writer.write(bitfield_msg)
        await self.writer.drain()

    async def _send_interested(self) -> None :
        print(f'sending interested to {self.ip}:{self.port}')
        self.writer.write(build_interested())
        await self.writer.drain()

        self.am_intrested = True

    async def _send_request(self, payload : Dict[str, int]) -> None :
        # print('DEBUG Requesting')
        self.writer.write(build_request(payload))
        await self.writer.drain()

    async def _send_have(self, index:int) -> bool :
        self.writer.write(build_have(index))
        await self.writer.drain()


    # We Uploading
    async def _send_piece(self, index:int, begin:int, data:bytes) -> None :
        payload: Dict[str, int | bytes] = {
            'index' : index,
            'begin' : begin,
            'block' : data

        }
        self.writer.write(build_piece(payload))
        await self.writer.drain()


    async def _process_outgoing_requests(self) -> None:

        try :
            while not self._stop_event.is_set() :
                # print("Sending request")
                req_payload: Dict[str, int] = await self.request_queue.get()
                await self._send_request(req_payload)
                self.request_queue.task_done()
          
        except Exception as e :  # noqa: F841
            return 




    async def _do_handshake(self) -> None :
        hndshake_massage:bytes = build_handshake_bytes(peer_id=self.my_peer_id, info_hash=self.info_hash)
        try :
            self.writer.write(hndshake_massage)
            await self.writer.drain()

            response:bytes = await asyncio.wait_for(self.reader.readexactly(68), timeout=10)
            parsed_resp:  Dict[str, Any] = parse_handshake(response)


            self.peer_id:bytes = parsed_resp['peer_id'].encode('ascii')

            self.handshake_sucess = True

            # DEBUG
            print("Here is the response")
            print(parsed_resp)

            if not (self.info_hash.hex() == parsed_resp['info_hash']) :
                self.handshake_sucess = False
                raise Exception("Info hash mismatch droping connection .... ")



        except asyncio.TimeoutError:
            raise Exception("Handshake timed out")
        except ConnectionResetError:
            raise Exception("Peer closed connection during handshake")
        except asyncio.IncompleteReadError:
            raise Exception("Peer sent less than 68 bytes")

        finally :
            # do something
            # self.close()
            pass


    # async def _handle_message(self, piece_manager:PieceManager, disk_manager:DiskManager):
    async def _handle_message(self, peer_manager: PeerManager):
        """Infinite loop that reads and dispatches BitTorrent messages."""
        try :
            while not self._stop_event.is_set() :
                msg_len_bytes:bytes = await self.reader.readexactly(4)
                msg_len:int = struct.unpack('>I', msg_len_bytes)[0]

                if msg_len == 0:
                    continue

                # Message ID
                msg_id:int = (await self.reader.readexactly(1))[0]

                payload:bytes = await self.reader.readexactly(msg_len - 1)

                # DEBUG!!
                # print(f"msg_len : {msg_len}")
                # print(f"msg_id  : {msg_id}")
                # print(f"payload : {payload.hex()}")


                payload_dict: Dict[str, int | bytes] = {
                    'msg_len' : msg_len,
                    'msg_id'  : msg_id,
                    'payload' : payload
                }


                await peer_manager.add_to_queue(self, payload_dict)
        except asyncio.IncompleteReadError:
            print(f"Peer {self.ip} disconnected.")
            self.bad_peer = True
            self.is_active = False
        except Exception as e:
            print(f"Error handling message from {self.ip}: {e}")
            self.bad_peer = True
            self.is_active = False

    async def close(self):
        """Safely shuts down the TCP connection and clears the writer."""
        self._stop_event.set()
        if self.writer:
            try:
                # 1. Stop sending data and close the socket
                self.writer.close()

                # 2. Wait for the socket to actually finish closing
                # This is an async call and is vital for cleanup
                await self.writer.wait_closed()
            except Exception as e:  # noqa: F841
                # If the peer already disconnected, this might throw
                # an error which we can safely ignore during cleanup.
                pass
            finally:
                self.writer = None
                self.reader = None


    def update_peer_bitfield(self, index:int) -> None:

        # Find the byte location
        # By take the total_piece divide by 8 than flooring it
        # Simplified by // 8
        byte_index: int = index // 8

        # Find the bit index -> bit location in the byte
        # since we know each byte is 0 - 7
        # we can modulo it 
        bit_index: int = 7 - (index % 8)

        # Manipulate the bit
        self.peer_bitfield[byte_index] |= (1 << bit_index)


    # Add what block to request
    # payload is the same as massage.build_request
    async def add_block_request(self, payload:Dict[str, int]) -> None :
        await self.request_queue.put(payload)

    # Queue management
    @property
    def can_receive_requests(self) -> bool :
        return False

    @property
    def ready_for_request(self) -> bool:
        """Checks if we are actually allowed to ask this peer for data."""
        return (
            self.handshake_sucess and
            not self.peer_choking and
            not self.request_queue.full()
        )
