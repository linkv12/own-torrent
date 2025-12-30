
import asyncio
import os
import socket
from dotenv import load_dotenv
import urllib 


from src.message import build_bitfield
from src.peer_client import Peer
from src.torrent_parser import info_hash, open_torrent
from src.tracker import build_announce_request, build_conn_request, parse_announce_response, parse_conn_response
from src.utils.config_manager import ConfigManager

print(build_bitfield(b'Hello'))

# Load .env
load_dotenv()


async def test_single_peer():

    config = ConfigManager()
    peer_id = config.peer_id
    # curr_ip: str = os.environ.get("CURR_IP")


    torrent = open_torrent(os.path.join(
        os.environ.get("TESTFOLDER", "Empty"), 
        os.environ.get("TESTTorrent3", "puppy.torrent")))


    # 1. Setup Mock/Minimal Data
    # In a real test, use the actual 20-byte info_hash from your .torrent file
    _info_hash = info_hash(torrent) 
    my_peer_id = peer_id # Your dummy client ID


    # UDP TRACKER
    # Conn Request
    # socket
    announce = urllib.parse.urlparse(torrent[b'announce'].decode('utf-8'))
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    conn_req = build_conn_request()
    sock.sendto(conn_req, (announce.hostname, announce.port))


    # Wait for a response
    data, addr = sock.recvfrom(1024)
    conn_data = parse_conn_response(data)
    print("Connection Data Received:", conn_data)


    # Announce Request
    announce_req = build_announce_request(conn_id=conn_data["connection_id"], torrent=torrent, port=announce.port)
    sock.sendto(announce_req, (announce.hostname, announce.port))

    # Wait for a response
    data, addr = sock.recvfrom(65536)
    announce_data = parse_announce_response(data)
    # print("Announce Data Received:", announce_data)
    
    peers_data = announce_data.get('peers')
    peers_data.insert(0, {'ip': '127.0.0.1', 'port': 51413}) # Add local for testing

    for peers_dict in peers_data[:20] :
        # Target Peer (Replace with an actual IP from a tracker or local node)
        target_ip = peers_dict['ip']
        target_port = peers_dict['port']

        # 2. Initialize the Peer
        peer:Peer = Peer(target_ip, target_port, _info_hash, my_peer_id)
        


        print(f"--- Attempting connection to {target_ip}:{target_port} ---")
        
        try:
            # 4. Start the Peer's internal logic
            await peer.run()
        except KeyboardInterrupt:
            print("\nStopping test...")
        finally:
            await peer.close()


    print('Done testing')
if __name__ == "__main__":
    # This is how you "start" the async execution
    asyncio.run(test_single_peer())
    













# announce = urllib.parse.urlparse(torrent[b'announce'].decode('utf-8'))
# print(announce.hostname, announce.port)
# # Conn Request
# # socket
# sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# conn_req = build_conn_request()
# sock.sendto(conn_req, (announce.hostname, announce.port))


# # Wait for a response
# data, addr = sock.recvfrom(1024)
# conn_data = parse_conn_response(data)
# print("Connection Data Received:", conn_data)


# # Announce Request
# announce_req = build_announce_request(conn_id=conn_data["connection_id"], torrent=torrent, port=announce.port)
# sock.sendto(announce_req, (announce.hostname, announce.port))

# # Wait for a response
# data, addr = sock.recvfrom(65536)
# announce_data = parse_announce_response(data)
# # print("Announce Data Received:", announce_data)

# # Write
# with h.open('w') as f :
#     json.dump(announce_data, f, ensure_ascii=False, indent=4)

# d = announce_data.get('peers')
# # m_peer: Dict[str, Union[str, int]] = next((pp for pp in d if pp['ip'] == curr_ip), {'ip': '127.0.0.1', 'port': 51413})
# m_peer: Dict[str, Union[str, int]] = d[3]
# # force :
# # m_peer = {'ip': '127.0.0.1', 'port': 51413}

# print(m_peer)

# # we have target peer try to do the handshake now


# # we have target peer try to do the handshake now
# PeerC: Peer = Peer(ip=m_peer['ip'], port=m_peer['port'], info_hash=info_hash(torrent=torrent), peer_id=peer_id )

# print(f"--- Attempting connection to {m_peer['ip']}:{m_peer['port']} ---")

# try:
#     # 4. Start the Peer's internal logic
#     await PeerC.run()
# except KeyboardInterrupt:
#     print("\nStopping test...")
# finally:
#     await PeerC.close()

# # sock_tcp: socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# # sock_tcp.settimeout(5)

# # sock_tcp.connect((m_peer['ip'], m_peer['port']))

# # handshake_msg: bytes = build_handshake(torrent=torrent)
# # sock_tcp.sendall(handshake_msg)

# # resp = sock_tcp.recv(68)
# # print(parse_handshake(resp))


