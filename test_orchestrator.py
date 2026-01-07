

import asyncio

from dotenv import load_dotenv

from src.tracker_manager import TrackerManager
from src.utils.config_manager import ConfigManager

# Load .env
load_dotenv()


async def main_2() :

    # Load Config
    config: ConfigManager = ConfigManager()
    peer_id: bytes = config.peer_id


    traker_man: TrackerManager = TrackerManager(peer_id=peer_id, config_manager=config)
    
    await traker_man._annouce_udp('a0ab72e493a3cfa9390f2c551ddfd5bb85b3f16f')


if __name__ == "__main__":
    # This is the entry point for async Python scripts
    try:
        asyncio.run(main_2())
    except KeyboardInterrupt:
        print("\nTest interrupted by user.")