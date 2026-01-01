
import asyncio
from http import client
import os
from pathlib import Path
from dotenv import load_dotenv


from src.torrent_client import TorrentClient
from src.torrent_source import TorrentSource
from src.utils.config_manager import ConfigManager

async def main_and_save():
    # 1. Load Environment
    load_dotenv()
    config:ConfigManager = ConfigManager()
    print("--- Phase 1: Environment Loaded and Config---")

    # 2. Setup Paths
    test_folder = os.environ.get("TESTFOLDER", "Empty")
    torrent_file = os.environ.get("TESTTorrent3", "puppy.torrent")
    
    torrent_path = Path(test_folder) / torrent_file
    config_dir = Path(".config/torrents")
    download_base_dir = Path.cwd() / os.environ.get("TESTFOLDERx", ".test")

    # 3. Initialize Source
    # This parses the .torrent file and sets up metadata
    torrent_source = TorrentSource(
        torrent_source=torrent_path, 
        torrents_dir=config_dir
    )
    print(f"Torrent Loaded: {torrent_source.name}")

    # 4. Initialize Client
    # This sets up the PieceManager and DiskManager
    torr_client = TorrentClient(
        torrent_source=torrent_source,
        download_path=download_base_dir
    )
    print("Client Initialized. Starting up...")

    # 5. Run Startup
    # MUST use 'await' here to run the integrity check and start the disk worker
    await torr_client.startup()
    
    # 6. Check Results
    print("--- Phase 2: Startup Complete ---")
    print(f"Status: {torr_client.status}")
    print(f"Progress: {torr_client.piece_manager.completed_count}/{torr_client.piece_manager.total_pieces} pieces verified.")

    # 7. Check Write Config
    print("--- Phase 7: Write to Client Config ---") # For resume
    config.save_client_state(torr_client.info_hash, torr_client.to_dict())
    # TODO: 
    # CHECK Shutdown
    # Check is config saved on exit [next]

async def test_restore_from_file():
    # 1. Load Environment
    load_dotenv()
    config:ConfigManager = ConfigManager()
    print("--- Phase 1: Environment Loaded and Config---")

    # 2. Setup Paths
    test_folder = os.environ.get("TESTFOLDER", "Empty")
    torrent_file = os.environ.get("TESTTorrent3", "puppy.torrent")
    torrent_hash = os.environ.get("TESTHASH")

    
    torrent_path = Path(test_folder) / torrent_file
    config_dir = Path(".config/torrents")
    download_base_dir = Path.cwd() / os.environ.get("TESTFOLDERx", ".test")


    
    # 3. Initialize Source
    # This parses the .torrent file and sets up metadata
    torrent_source = TorrentSource(
        torrent_source=torrent_path, 
        torrents_dir=config_dir
    )
    print(f"Torrent Loaded: {torrent_source.name}")

    # 4. Initialize Client
    # This sets up the PieceManager and DiskManager

    client_dict = config.get_all_client_state().get(torrent_hash)
    torr_client = TorrentClient.from_dict(client_dict)
    print("Client Initialized. Starting up...")

    # 5. Run Startup
    # MUST use 'await' here to run the integrity check and start the disk worker
    await torr_client.startup()
    
    # 6. Check Results
    print("--- Phase 2: Startup Complete ---")
    print(f"Status: {torr_client.status}")
    print(f"Progress: {torr_client.piece_manager.completed_count}/{torr_client.piece_manager.total_pieces} pieces verified.")


    
    # TODO: 
    # CHECK Shutdown
    # Check is config saved on exit [next]
    

if __name__ == "__main__":
    # This is the entry point for async Python scripts
    try:
        asyncio.run(test_restore_from_file())
    except KeyboardInterrupt:
        print("\nTest interrupted by user.")