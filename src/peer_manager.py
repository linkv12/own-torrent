



import asyncio
import struct
from typing import Callable, Dict, List, Tuple

from src.disk_manager import DiskManager
from src.message import parse_piece, parse_request
from src.peer_client import Peer
from src.piece_manager import PieceManager


# TODO :
# Encryption and Uploading

class PeerManager:
    def __init__(self, piece_manager: PieceManager, disk_manager: DiskManager) -> None :
        
        # init peer list
        self.peers: List[Peer] = []

        # Assign manager
        self.piece_manager: PieceManager = piece_manager
        self.disk_manager: DiskManager = disk_manager


        # message queue
        self.message_queue: asyncio.Queue[Tuple[Peer, Dict]] = asyncio.Queue()

        # 
        self.running: asyncio.Event = asyncio.Event()
        self._dispatch_task: asyncio.Task | None = None  
        self._scheduler_task: asyncio.Task | None = None  


    async def start(self) -> None :
        self.running.set()
        self._dispatch_task = asyncio.create_task(self._global_dispatcher())
        self._scheduler_task = asyncio.create_task(self._request_scheduler())
        print('PeerManager Dispatcher running ...')

    async def stop(self) -> None :
        self.running.clear()

        if self._dispatch_task :
            self._dispatch_task.cancel()

        print('PeerManager Dispatcher stoping ...')


    async def _global_dispatcher(self) -> None :
        """Handle received from Peer
        """
        while self.running.is_set():
            try :
                # (peer, payload) = await self.message_queue.get()
                (peer, payload) = await asyncio.wait_for(
                    self.message_queue.get(),
                    timeout=1.0
                )

                await self._route_message(peer, payload)
                self.message_queue.task_done()
                

            except asyncio.TimeoutError :
                continue
            except Exception as e:
                print(f'Dispatcher error: {e}')

            await asyncio.sleep(0.1)

    async def _request_scheduler(self) -> None :
        while self.running.is_set() :
            try:
                for peer in self.peers:
                    # print(f'{peer.ip}:{peer.port}')
                    # print(f'{peer.handshake_sucess}')
                    if peer.handshake_sucess and peer.am_intrested and not peer.peer_choking:

                        if not(peer.request_queue.full()):
                            block_request: Tuple[int, int, int] = self.piece_manager.get_next_request(peer.peer_bitfield)

                            # print(f'br:{block_request}')
                            if block_request :
                                req_payload:Dict[str, int] = {
                                    'index': block_request[0],
                                    'begin': block_request[1], 
                                    'length': block_request[2] 
                                }
                                # print('add block request', req_payload)
                                await peer.add_block_request(req_payload)


                await asyncio.sleep(0.1)
            except Exception as e:
                print(f"Scheduler error: {e}")
                await asyncio.sleep(1)

    async def add_to_queue(self, peer: Peer, payload: Dict[str, int | bytes]) -> None :
        await self.message_queue.put((peer, payload))


    async def _route_message(self, peer: Peer, payload: Dict[str, int | bytes]) -> None:

        handlers: Dict[int, Callable[[Peer, Dict[str, int | bytes]], None]] = {
            0: self._handle_choke,
            1: self._handle_unchoke,
            2: self._handle_interested,
            3: self._handel_un_interested,
            4: self._handle_have,
            5: self._handle_bitfield,           
            6: self._handle_request,            # [Upload]      Read
            7: self._handle_piece               # [Download]    Write
        }

        # print(f'Recv: {peer.ip}:{peer.port}, msg_id: {payload["msg_id"]}')
        msg_id: int = payload.get('msg_id', 99)
        handler: Callable[[Peer, Dict[str, int | bytes]], None] = handlers.get(msg_id, None)
        if handler :
            await handler(peer, payload)
        else :
            # Likely cancel
            print(f'Unknown Message ID: {msg_id} from {peer.ip}')
        
    # Add and remove peer
    def add_peer(self, ip: str, port: int, info_hash: bytes, peer_id: bytes) -> None :
        print("DEBUG add peer called inside PeerManager")
        if not(any(p.ip == ip and p.port == port for p in self.peers)) :
            try :
                new_peer: Peer = Peer(ip, port, info_hash, peer_id)
                self.peers.append(new_peer)

                task:asyncio.Task =  asyncio.create_task(new_peer.run(self))
                # this will print the reason.
                def task_checker(task):
                    try:
                        task.result()
                    except asyncio.CancelledError:
                        # Ignore cancellation during shutdown
                        pass
                    except Exception as e:
                        print(f"!!! CRITICAL: Peer Task for {ip} CRASHED: {e}")

                task.add_done_callback(task_checker)
                print(f"DEBUG: Task created for {ip}. Task status: {task}")
            except Exception as e:
                print(f"!!! ERROR during Peer object creation: {e}")

            # print(self.peers)
        else :
            print("Peers already exist")



    # Verify downloaded
    async def _verify_and_broadcast(self, index:int) -> None :
        # print('Ind')
        data:bytes = await self.disk_manager.read_piece(index)
        if self.piece_manager.verify_piece(index, data):
            self.piece_manager.mark_piece_complete(index)


            for peer in self.peers :
                if not peer.peer_has_piece(index) :
                    asyncio.create_task(peer._send_have(index))

    # Handlers for Received Data from Peer
    async def _handle_choke(self, peer: Peer, payload: Dict[str, int | bytes]) -> None :
        """Peer sending us a choke message
        Args:
            peer (Peer): Peer that received message from Connected Peers
            payload (Dict[str, int  |  bytes]): Payload based on Convention
                - 'msg_len' (int)   : Total payload length excluding itself
                - 'msg_id'  (int)   : Message ID in Integer
                - 'payload' (bytes) : No Payload
        """ 
        # print("Handle Choke from Peer ")
        peer.peer_choking = True
        
    async def _handle_unchoke(self, peer: Peer, payload: Dict[str, int | bytes]) -> None :
        """Peer sending us an  un-choke message
        Args:
            peer (Peer): Peer that received message from Connected Peers
            payload (Dict[str, int  |  bytes]): Payload based on Convention
                - 'msg_len' (int)   : Total payload length excluding itself
                - 'msg_id'  (int)   : Message ID in Integer
                - 'payload' (bytes) : No Payload
        """ 
        # print("Handle Un-Choke from Peer")
        peer.peer_choking = False

    async def _handle_interested(self, peer: Peer, payload: Dict[str, int | bytes]) -> None :
        """
        Peer sending us an interested message
        Peer do want our Piece

        Args:
            peer (Peer): Peer that received message from Connected Peers
            payload (Dict[str, int  |  bytes]): Payload based on Convention
                - 'msg_len' (int)   : Total payload length excluding itself
                - 'msg_id'  (int)   : Message ID in Integer
                - 'payload' (bytes) : No Payload
        """
        # print("Handle Interested")
        peer.peer_intrested = True
        
    async def _handel_un_interested(self, peer: Peer, payload: Dict[str, int | bytes]) -> None :
        """
        Peer sending us not not interested message
        Peer dont want our Piece

        Args:
            peer (Peer): Peer that received message from Connected Peers
            payload (Dict[str, int  |  bytes]): Payload based on Convention
                - 'msg_len' (int)   : Total payload length excluding itself
                - 'msg_id'  (int)   : Message ID in Integer
                - 'payload' (bytes) : No Payload
        """
        # print("Handle un-nterested")
        peer.peer_intrested = False

    async def _handle_have(self, peer: Peer, payload: Dict[str, int | bytes]) -> None :
        """
        Peer send us a have message
        Update its peer bitfield

        Args:
            peer (Peer): Peer that received message from Connected Peers
            payload (Dict[str, int  |  bytes]): Payload based on Convention
                - 'msg_len' (int)   : Total payload length excluding itself
                - 'msg_id'  (int)   : Message ID in Integer
                - 'payload' (bytes) : Index of Piece that the peer have
        """
        # MSG_ID        : 4                    (Have)
        # Payload:int   : piece_index          (Peer have this pieces)
        # Note          : We have to update peer bitfield
        if (peer.peer_bitfield is None) :
            peer.peer_bitfield = bytearray(self.piece_manager.bitfield_size)
        
        # 
        peer_have_index:int = struct.unpack('>I', payload)[0]
        peer.update_peer_bitfield(peer_have_index)

        if not self.piece_manager.has_piece(peer_have_index) and not self.am_intrested:
           await peer._send_interested()

        # peer.update_peer_bitfield()

    async def _handle_bitfield(self, peer: Peer, payload: Dict[str, int | bytes]) -> None :
        """Peer send us its bitfield take note 

        Args:
            peer (Peer): Peer that received message from Connected Peers
            payload (Dict[str, int  |  bytes]): Payload based on Convention
                - 'msg_len' (int)   : Total payload length excluding itself
                - 'msg_id'  (int)   : Message ID in Integer
                - 'payload' (bytes) : Peers Bitfield value
        """

        # # MSG_ID            : 5                     (Bitfield)
        # # Payload:bytes     : Peer Bitfield         (Peers bitfield in bytes)
        # # Note              : We have to update peer bitfield from payload
        peer.peer_bitfield = bytearray(payload['payload'])
        print('their bitfield: ',payload['payload'].hex())

    async def _handle_request(self, peer: Peer, payload: Dict[str, int | bytes]) -> None :
        """Peer send us its request for data block
        Args:
            peer (Peer): Peer that received message from Connected Peers
            payload (Dict[str, int  |  bytes]): Payload based on Convention
                - 'msg_len' (int)   : Total payload length excluding itself
                - 'msg_id'  (int)   : Message ID in Integer
                - 'payload' (bytes) : Packed >III {index:int}{begin:int}{length:int}
                                    # Length limited to 16kb / 2^14 in int 
        """
        # # MSG_ID                    : 6                     (Request)
        # # Payload:Dict[str, int]    : Peer Request          (Peer Request a block of pieces)
        # # Note                      : Fixed length, used to request a block of pieces. 
        # #                             The payload contains integer values specifying the index, begin location and length.
         # Scratch Implementation
         # 1. Parse the payload from peer
        req_payload: Dict[str, int] = parse_request(payload)

        # 1.1 Enforce MAX BLOCK SIZE, currently at 16 kB
        if (req_payload['length'] > peer._MAX_BLOCK_SIZE) :
            # Greedy basterd lets just drop em
            self._stop_event.set()
        
        # 2. Check are we choking
        if self.am_choking :
            return None
        
        # 3. Check if we have the piece requested
        if self.piece_manager.has_piece(req_payload['index']) :
            # 4. Read using DiskManager
            block_data: bytes = self.disk_manager.read_block(req_payload['index'], req_payload['begin'], req_payload['length'])

            # 5. Sending it to the peers
            await peer._send_piece(req_payload['index'], req_payload['begin'], block_data)

    async def _handle_piece(self, peer: Peer, payload: Dict[str, int | bytes]) -> None :
        """Peer send us the response of our block request

        Args:
            peer (Peer): Peer that received message from Connected Peers
            payload (Dict[str, int  |  bytes]): Payload based on Convention
                - 'msg_len' (int)   : Total payload length excluding itself
                - 'msg_id'  (int)   : Message ID in Integer
                - 'payload' (bytes) : Packer >II {index:int}{begin:int} + block <data block>
        """
        # We downloading
        # 1. Re-construct
        resp_payload: bytes = struct.pack('>IB', payload['msg_len'], payload['msg_id']) + payload['payload']
        pars_payload: Dict[str, int | bytes] = parse_piece(resp_payload)

        # 2. Calculate Global Offsett
        global_offset: int = (pars_payload['index'] * self.piece_manager.piece_size) + pars_payload['begin']
        # DO THE IMPLEMENTATION
        await self.disk_manager.add_write_request(global_offset, pars_payload['block'])

        is_piece_finished : bool = self.piece_manager.mark_block_received(pars_payload['index'], pars_payload['begin'])

        # print(self.piece_manager.bitfield.hex())
        # Verify the piece and update bitfield
        if (is_piece_finished) :
            print(f"piece finished: {pars_payload['index']}")
            asyncio.create_task(self._verify_and_broadcast(pars_payload['index']))




    # HANDLE CANCEL TOO
    # msg_id = 8 it will look like a request but do the oposite
    # async def _handle_cancel(self, peer: Peer)
