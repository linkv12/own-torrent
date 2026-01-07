from __future__ import annotations
import asyncio
from typing import TYPE_CHECKING
from textual.app import App, ComposeResult
from textual.widgets import DataTable, Header, Footer, Log
from textual.containers import Container

# from src.torrent_app import TorrentApp
from src.torrent_client import TorrentClient
from src.ui.add_torrent_modal import AddTorrentModal

if TYPE_CHECKING:
    # This only runs for IDEs/Type Checkers, NOT at runtime.
    from src.torrent_app import TorrentApp

class TorrentUI(App):

    TITLE = "Own Torrent"
    SUB_TITLE = "v1.0.0 - BitTorrent Engine"

    BINDINGS = [
        ("a", "add_torrent", "Add Torrent"),
        ("s", "start_torrent", "Start Torrent"),
        ("ctrl+r", "force_announce", "Re-announce"),
        ("q", "quit", "Quit"),
    ]


    CSS = """
        #main_container {
            layout: vertical;
            width: 100%;
            height: 100%;
        }



        #torrent_list {
            height: 100%;
            width: 100%;
            border: none;
            /* Removing margin makes it truly full width */
            margin: 0; 
        }

        """
    def __init__(self, engine: TorrentApp):
        

        super().__init__()
        self.engine: TorrentApp = engine  # Access your torrents here

        # self.engine.register_ui(self)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="main_container"):
            yield DataTable(id="torrent_list", cursor_type="row") # "row" makes it interactable
            yield Log(id="event_log")
        yield Footer()

    async def on_mount(self) -> None:
        """Initialize the table columns when the app starts."""


        self.engine.register_ui(self)


        # 1. Start the engine background tasks (Tracker loop, Listening server)
        # We use create_task so it runs concurrently with the UI
        asyncio.create_task(self.engine.run())
        
        
        # 2. Optionally, tell the engine to auto-resume torrents 
        # that were downloading when the app last closed
        await self.engine._start_all_torrent()

        self.notify("Engine started and resuming torrents...")
        # table = self.query_one("#torrent_list", DataTable)
        # table.add_columns("Name", "Size", "Status", "Progress")

        table = self.query_one("#torrent_list", DataTable)
        # We give each column a 'key' so we can reference them later
        
        table.add_column("#", key="col_no", width=2)
        table.add_column("Name", key="col_name")
        table.add_column("Status", key="col_status")
        table.add_column("Progress", key="col_progress")
        table.add_column("Peers", key="col_peers")
        
        # # Example row (you will later populate this from your engine)
        # table.add_row("ubuntu-24.04.iso", "4.2 GB", "Downloading", "85%")
        # # Set up a background timer to refresh UI stats from the engine
        self.set_interval(1.0, self.update_stats)

    def update_stats(self) -> None:
        """Polls the Engine's pre-computed property and updates the UI."""
        table = self.query_one("#torrent_list", DataTable)
        
        # Pull data from engine
        torrents = self.engine.ui_data()
        
        # Apply search filter if you have one
        # filtered = [t for t in torrents if self.search_query in t.name.lower()]

        for i, torrent in enumerate(torrents, start=1):
            row_key = torrent.info_hash
            
            # Prepare display values
            idx_str = str(i)
            prog_str = f"{torrent.progress:.1f}%"
            peer_str = str(torrent.num_peers)

            try:
                # Check if row exists
                table.get_row_index(row_key)
                
                # ✅ Update cells (including the # number)
                table.update_cell(row_key, "col_no", idx_str)
                table.update_cell(row_key, "col_status", torrent.status)
                table.update_cell(row_key, "col_progress", prog_str)
                table.update_cell(row_key, "col_peers", peer_str)
            
            except Exception:
                # ✅ Add new row - MUST match the number of columns in on_mount
                table.add_row(
                    idx_str,          # Matches col_no
                    torrent.name,     # Matches col_name
                    torrent.status,   # Matches col_status
                    prog_str,         # Matches col_progress
                    peer_str,         # Matches col_peers
                    key=row_key
                )



    def notify_ui(self, message:str, title:str) -> None :
        self.notify(f"{message}", title=title)


    # Action
    async def action_quit(self) -> None :
        """Override the default quit action to clean up the engine."""
        # 1. Show a notification so the user knows why it's hanging for a second
        self.notify("Shutting down engine and saving state...", title="Exit") 


        try :
            await self.engine.shutdown_and_save()

        except Exception as e:
            print(f"Error during shutdown: {e}")

        # 3. Finally, close the UI
        self.exit() # This is the "Textual way" to close

    async def action_start_torrent(self) -> None:
        """The heavy lifting: Starting torrent"""
        try:
            # 1. Ask Engine to load and initialize the TorrentSource
            await self.engine._start_all_torrent()


            # 2. Log it to the UI
            self.notify("Starting all Torrent ....")
            
        except Exception as e:
            self.notify(f"Failed to Start: {e}", severity="error")
        
    async def action_add_torrent(self) -> None:
        def handle_path(file_path: str | None) -> None:
            if file_path:
                self.run_worker(self._async_add_torrent(file_path))

        self.push_screen(AddTorrentModal(), handle_path)

    async def _async_add_torrent(self, path: str) -> None:
        """The heavy lifting: Parsing and starting the swarm connection."""
        try:
            # 1. Ask Engine to load and initialize the TorrentSource
            new_torrent: TorrentClient = self.engine._add_torrent(path)
            
            # 2. Log it to the UI
            self.query_one("#event_log", Log).write(f"✅ Loaded: {path}")
            self.notify(f"Added Torrent: {new_torrent.torrent_name}")
            
        except Exception as e:
            self.notify(f"Failed to load: {e}", severity="error")

    async def action_force_announce(self) -> None:
        """Manual refresh via UI triggered by Ctrl+R."""
        table = self.query_one("#torrent_list", DataTable)
        
        # Ensure a row is actually selected
        if table.cursor_row is not None:
            try:
                # Get the RowKey (which we set as the info_hash earlier)
                coord = table.cursor_coordinate
                row_key = table.coordinate_to_cell_key(coord).row_key
                
                # Extract the value (the actual info_hash string/bytes)
                info_hash = row_key.value
                
                # 1. Trigger the tracker manager
                await self.engine.tracker_man.announce_manually(info_hash)
                
                # 2. Provide visual feedback
                self.notify(f"Refreshed: {info_hash[:8]}...", title="Tracker Update")
            except Exception as e:
                self.notify(f"Announce failed: {e}", severity="error")
        else:
            self.notify("No torrent selected to re-announce", severity="warning")