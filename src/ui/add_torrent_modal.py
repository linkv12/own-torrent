import os
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Input, Label
from textual.containers import Vertical
from textual.suggester import Suggester

class AddTorrentModal(ModalScreen[str]):
    """A pop-up to enter the path to a .torrent file."""
    
    def compose(self) -> ComposeResult:
        with Vertical(id="modal_container"):
            yield Label("[b]Add New Torrent[/b]", id="modal_title")
            yield Label("Enter absolute path to .torrent file:")
            yield Input(placeholder="~/Downloads/linux.torrent", id="file_input",suggester=FileSuggester())
            yield Label("[dim]Press Enter to Confirm or Esc to Cancel[/dim]")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        raw_path = event.value.strip()
        if raw_path:
            expanded_path = os.path.expanduser(raw_path)
            self.dismiss(expanded_path)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)

    CSS = """
    AddTorrentModal { align: center middle; }
    #modal_container {
        width: 70; height: auto;
        padding: 1 2; background: $surface;
        border: thick $accent;
    }
    #modal_title { margin-bottom: 1; color: $accent; }
    """


class FileSuggester(Suggester):
    async def get_suggestion(self, value: str) -> str | None:
        if len(value) < 2:
            return None

        # 1. Expand for the OS, but keep the original for the UI
        expanded_path = os.path.expanduser(value)
        
        # 2. Get the directory we are looking in
        # If I type ~/Down, dirname is /home/user/ and basename is Down
        dirname = os.path.dirname(expanded_path)
        prefix = os.path.basename(expanded_path)

        try:
            if os.path.isdir(dirname):
                for entry in os.listdir(dirname):
                    if entry.startswith(prefix):
                        # Construct what the user typed + the rest of the match
                        # We take the user's input and append the 'missing' part
                        remainder = entry[len(prefix):]
                        suggestion = value + remainder
                        
                        # If it's a directory, add a slash to make it helpful
                        if os.path.isdir(os.path.join(dirname, entry)):
                            suggestion += os.sep
                            
                        return suggestion
        except Exception:
            return None
        return None