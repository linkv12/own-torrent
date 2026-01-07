
from src.torrent_app import TorrentApp
from src.torrent_ui import TorrentUI


if __name__ == "__main__":
    engine = TorrentApp()

    ui = TorrentUI(engine)
    ui.run()
