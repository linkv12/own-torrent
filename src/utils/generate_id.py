from src.utils.config_manager import ConfigManager

def gen_peer_id() -> bytes:
    """
    Get the 20-byte peer ID from the ConfigManager.

    Ensures a single peer ID per app instance. Loads from
    config if available, otherwise generates a new one.

    Returns:
        bytes: The 20-byte peer ID.
    """
    config = ConfigManager()  # singleton ensures same instance
    return config.peer_id