

import asyncio
from typing import Any, Dict, Optional

from src.message import _build_handshake_bytes, parse_handshake


class Peer:

    def __init__(self, ip:str, port:int, info_hash:bytes, peer_id:bytes):
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
        self.bitfield: Optional[bytes] = None
        self.intrested:bool = False
        self.choking:bool = True


        # Handshake success n General Connection Health
        self.handshake_sucess:bool = False


    async def run(self) :
        try:
            # 1. Open TCP Connection
            (self.reader, self.writer) = await asyncio.open_connection(host=self.ip, port=self.port)

            # 2. Handshake
            await self._do_handshake() 
             
        except Exception as e:
            print(f"Connection lost with {self.ip}: {e}")
        finally:
            await self.close()

    async def _do_handshake(self) -> None :
        hndshake_massage:bytes = _build_handshake_bytes(peer_id=self.my_peer_id, info_hash=self.info_hash)
        try :
            self.writer.write(hndshake_massage)
            await self.writer.drain()

            response:bytes = await asyncio.wait_for(self.reader.readexactly(68), timeout=10)
            parsed_resp:  Dict[str, Any] = parse_handshake(response)


            self.peer_id:bytes = parsed_resp['peer_id'].encode('ascii')

            self.handshake_sucess:bool = True

            # DEBUG
            print("Here is the response")
            print(parsed_resp)
        except asyncio.TimeoutError:
            raise Exception("Handshake timed out")
        except ConnectionResetError:
            raise Exception("Peer closed connection during handshake")
        except asyncio.IncompleteReadError:
            raise Exception("Peer sent less than 68 bytes")
        finally :
            # do something
            pass

    async def close(self):
        """Safely shuts down the TCP connection and clears the writer."""
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


        

    

