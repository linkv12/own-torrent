
from __future__ import annotations
from ast import List
import asyncio
import socket
import struct
from typing import TYPE_CHECKING, Any, Dict, OrderedDict

import urllib
import urllib.parse
from src.message import parse_handshake
# from src.torrent_app import TorrentApp
# from src.torrent_client_manager import TorrentClientManager
from src.torrent_source import TorrentSource
from src.tracker import build_announce_request, build_conn_request, parse_announce_response, parse_conn_response
from src.utils.config_manager import ConfigManager


if TYPE_CHECKING:
    # This only exists for your IDE/Linter
    from src.torrent_app import TorrentApp
    from src.torrent_client_manager import TorrentClientManager

class TrackerManager: 
    def __init__(self, peer_id:bytes, config_manager:ConfigManager, port:int = 51415) -> None :
        
        self.peer_id: bytes = peer_id
        self.config_manager: ConfigManager = config_manager
        self.port = port

        self.torrents : Dict[str, TorrentSource] = self._load_torrent()

        # Dont accept from this
        self.ban_list: List[bytes] = None


        # Composition
        self.__torrent_app: None | TorrentApp = None
        self.__torrent_client_man: None | TorrentClientManager = None
        



    async def start_listening(self, port:int = 51415) -> None:

        server: asyncio.Server = await asyncio.start_server(
            self.handle_incoming, 
            '0.0.0.0', 
            port 
        )

        async with server:
            await server.serve_forever()

    async def handle_incoming(self, reader:asyncio.StreamReader, writer:asyncio.StreamWriter) -> None:

        try:
            handshake: bytes = await asyncio.wait_for(reader.readexactly(68), timeout=5)
            p:Dict[str, Any] =parse_handshake(handshake)
            print(f'{p["info_hash"]} : {p["peer_id"]}')

            # Simple block ourselves
            if p['peer_id'] not in self.ban_list :
                if (p['peer_id'] == self.peer_id) or (p['info_hash'] not in self.torrents.keys()):
                    self.ban_list.append(p['peer_id'])

            # DEBUG
            raise Exception("Testing")

        except Exception:
            writer.close()
        
    def _load_torrent(self) -> Dict[str, TorrentSource] : 

        client_state: Dict[str, Any] = self.config_manager.get_all_client_state()
        torrent: Dict[str, TorrentSource] = {}

        for info_hash, torrent_data in client_state.items() :
            # print(info_hash)
            torrent_src: TorrentSource = TorrentSource.from_dict(torrent_data['torrent_source'])
            torrent[info_hash] = torrent_src


        return torrent

    async def _annouce_udp(self, info_hash:str) -> None : 
        """Announce to UDP tracker"""

        _torrent: OrderedDict = self.torrents[info_hash].decoded_torrent


        conn_msg: bytes = build_conn_request()
        transaction_id: int = struct.unpack(">L", conn_msg[12:16])[0]

        # announce_msg: bytes = build_announce_request(self.peer_id, _torrent, 51415)
        


        announce_url: urllib.parse.ParseResult = urllib.parse.urlparse(_torrent[b'announce'].decode('utf-8'))
        announce_hostname = announce_url.hostname
        announce_port = announce_url.port

        # Guard against non-UDP trackers in the UDP function
        if announce_url.scheme != 'udp':
            # print(f"Skipping non-udp tracker for {info_hash}")
            return

        # 1. Start Socket
        sock: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)
        loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()

        try:
            # P1. Connect
            await loop.sock_sendto(sock, conn_msg, (announce_hostname, announce_port))
            resp, addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 1024), timeout=10)

            # Action, TransID, ConnectionID
            conn_reponse:Dict[str, int | bytes] = parse_conn_response(resp)

            if (conn_reponse['transaction_id'] != transaction_id) or conn_reponse['action'] != 0 :
                raise Exception("UDP connection failed: Invalid Response")
            
            print(conn_reponse)

            # P2. Announce
            announce_req: bytes = build_announce_request(conn_id=conn_reponse["connection_id"], torrent=_torrent, port=self.port)
            await loop.sock_sendto(sock, announce_req, (announce_hostname, announce_port))
            ann_resp, ann_addr = await asyncio.wait_for(loop.sock_recvfrom(sock, 65536), timeout=10)

            announce_response_p : Dict[str, int | List[Dict]] = parse_announce_response(ann_resp)
            print(f"Discovered {len(announce_response_p['peers'])} peers via UDP for {info_hash}")



            # self.__torrent_app.notify_user(f"Discovered {ann_resp} peers via UDP for {info_hash}", f"UPD: {info_hash}")
            # Pass this value to torrent_client
            self.__torrent_client_man._add_peers(info_hash=info_hash, announce_resp=announce_response_p)

        except Exception:
            print('Fail....')

        finally:
            sock.close()

    def register_torrent_app(self, torrent_app: TorrentApp) -> None : 
        self.__torrent_app = torrent_app

    def register_client_man(self, client_man: TorrentClientManager) -> None : 
        self.__torrent_client_man = client_man


    # def add_new_file
    async def tracker_loop(self) -> None:
        """
        Background task that periodically announces all torrents to their trackers.
        """
        while True:
            # We use a list to avoid 'dictionary changed size during iteration' 
            # if a new torrent is added while we are looping.
            info_hashes = list(self.torrents.keys())
            
            for info_hash in info_hashes:
                # We check if the client is actually 'DOWNLOADING' or 'STARTED' 
                # before wasting bandwidth on an announce.
                if self.__torrent_client_man.is_client_running(info_hash):
                    # Create a task so one slow tracker doesn't block the others
                    asyncio.create_task(self._annouce_udp(info_hash))

            # Wait 30 minutes (1800 seconds) before the next periodic update
            # Most trackers will ban you if you announce more frequently.
            await asyncio.sleep(1800)

    async def announce_manually(self, info_hash: str) -> None:
        """
        Triggered by a UI button or keypress (e.g., 'CTRL+R' for Refresh).
        """
        # print(f"Manual announce triggered for: {info_hash}")
        self.__torrent_app.notify_user('Announcing', "UDP")
        await self._annouce_udp(info_hash)
