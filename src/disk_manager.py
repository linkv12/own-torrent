import os
from pathlib import Path
import asyncio
from typing import Dict, List, OrderedDict, Tuple, Union

class DiskManager:

    @classmethod
    def generate_filemap(cls : "DiskManager" ,torrent: OrderedDict, download_base_dir:Path) -> List[Dict[str, Union[Path, int]]] :
        if not download_base_dir :
            raise Exception("Download Base Dir not Supplied")
        
        file_map: List[Dict] = []
        current_global_offset: int = 0

        base_path: Path = Path(download_base_dir)

        info: OrderedDict = torrent.get(b'info', {})

        # # 1. Multi-File Torrent
        if b'files' in info:
            # root
            root_dir:str = info[b'name'].decode('utf-8') 

            for f in info[b'files'] :   # f is OrderedDict
                length:int = f[b'length']

                path_parts:List[str] = [p.decode('utf-8') for p in f[b'path']]

                full_path:Path = base_path / root_dir / Path(*path_parts)

                file_map.append({
                    'path'          : full_path,
                    'size'          : length,
                    'start_offset'  : current_global_offset,
                    'end_offset'    : current_global_offset + length
                })
                current_global_offset += length
        else :
            length: int = info[b'length']
            filename: str = info[b'name'].decode('utf-8')
            full_path: Path = base_path / filename
            
            file_map.append({
                'path'          : full_path,
                'size'          : length,
                'start_offset'  : current_global_offset,
                'end_offset'    : current_global_offset + length
            })

        return file_map

    # Constructor
    def __init__(self: "DiskManager", file_map:List[Dict[str, Union[Path, int]]], queue_size: int = 200) -> None:
        
        self.file_map: List[Dict[str, Union[Path, int]]] = file_map
        self.queue: asyncio.Queue[Tuple[int, bytes]] = asyncio.Queue(maxsize=queue_size)

        self._stop_event : asyncio.Event = asyncio.Event()

        # Ensure the file structure exists on disk
        self._prepare_files() 

    def _prepare_files(self : "DiskManager") -> None:
        """Creates folders and initializes sparse files if they don't exist."""
        for f_info in self.file_map :
            path: Path = f_info['path']

            # Create parent directories if missing (mkdir -p)
            path.parent.mkdir(parents=True, exist_ok=True)


            if not path.exists() :
                with path.open('wb') as file :
                    file.truncate(f_info['size'])

    # Write to disk
    async def _sync_write(self, global_offset:int, data:bytes) :
        """Standard library blocking I/O performed in a thread."""
        remaining_data:bytes = data
        current_offset:int = global_offset

        for f_info in self.file_map:
            # Check if the data chunk overlaps with this file
            if (current_offset < f_info['end_offset'] and 
                (current_offset + len(remaining_data)) > f_info['start_offset']):
                
                # Calculate local file seek position
                local_offset:int = max(0, current_offset - f_info['start_offset'])

                # Calculate how much to write to this specific file
                space_in_file:int = f_info['size'] - local_offset
                write_size:int = min(len(remaining_data), space_in_file)

                chunk:bytes = remaining_data[:write_size]

                # do write
                try :

                    with f_info['path'].open('rb+') as f:
                        f.seek(local_offset)
                        f.write(chunk)
                        f.flush()
                        os.fsync(f.fileno())
                except FileNotFoundError:
                    print(f"Critial Error: File {f_info['path']} missing!")
                    _ = self.shutdown() # Kill the worker
                
                remaining_data = remaining_data[write_size:]
                current_offset += write_size

            if not remaining_data:
                break 
    

    # Read Piece from disk 
    def _sync_read(self, global_offset:int, length:int) -> bytes :
        """
        Performs synchronous, blocking read operations across the file_map.

        This method treats the multi-file structure as one contiguous virtual file. 
        It iterates through the file_map to find which physical files overlap with 
        the requested byte range and extracts the relevant slices.

        Args:
            global_offset (int): The starting byte position within the virtual 
                concatenation of all files in the torrent.
            length (int): The total number of bytes to attempt to read from the 
                current offset.

        Returns:
            bytes: A single concatenated byte-string containing the data requested 
                from one or more physical files.

        Raises:
            OSError: If a file exists but cannot be accessed due to permissions 
                or hardware failure.
        """

        read_buffer: bytearray = bytearray()
        remaining_to_read: int = length

        current_offset:int = global_offset

        for f_info in self.file_map:
            # Check if this file contains any part of our data range
            if current_offset < f_info['end_offset'] and (current_offset + remaining_to_read) > f_info['start_offset']:

                # Calculate the local offset
                local_offset:int = max(0, current_offset - f_info['start_offset'])

                available_in_file:int = f_info['size'] - local_offset
                read_size:int = min(remaining_to_read, available_in_file)

                if f_info['path'].exists():
                    with f_info['path'].open('rb') as f:
                        f.seek(local_offset)
                        read_buffer.extend(f.read(read_size))
                else :
                    # if not exist write 0
                    read_buffer.extend(b'\x00', read_size)
                
                remaining_to_read -= read_size
                current_offset += read_size
            
            if remaining_to_read <= 0:
                break 


        return bytes(read_buffer)

    # Read Piece High Level API
    async def read_piece(self, index:int, piece_length:int, total_size:int) -> bytes:
        """
        Calculates the global offset and reads a full piece from the virtual byte stream.
        
        This method translates a BitTorrent piece index into a byte-offset across
        multiple files. It uses total_size to ensure that the last piece, which is 
        usually shorter than the standard piece_length, is read with the correct 
        number of bytes for accurate SHA-1 hashing.

        Args:
            index (int): The zero-based index of the piece to read.
            piece_length (int): The standard length of a piece in bytes.
            total_size (int): The total size of the torrent (sum of all files).

        Returns:
            bytes: The raw data for the requested piece, exactly as it exists on disk.
        """
        global_offset:int = index * piece_length

        if (global_offset + piece_length > total_size) :
            actual_read_length:int = total_size - global_offset
        else :
            actual_read_length:int = piece_length



        return await asyncio.to_thread(self._sync_read, global_offset, actual_read_length)
    

    # Main Event Loop
    async def start_worker(self):
        """The background loop that processes the queue."""
        while self._stop_event.is_set():
            try :

                # 1. Get data from queue
                # (int, bytes)
                (global_offset, data) = await self.queue.get() 

                # Offload the blocking write to a separate thread
                # This keeps the main loop responsive
                await asyncio.to_thread(self._sync_write, global_offset, data) 
                
            except Exception as e :
                print(f"Disk Worker Error: {e}")

            finally :
                self.queue.task_done()




    # Add to queue
    async def add_write_request(self, global_offset:int, data:bytes) -> None:
        """Peers call this to schedule a write."""
        await self.queue.put((global_offset, data))

    # Stop the worker
    def stop(self) :
        self._stop_event.set()

    # Quit procedure
    async def shutdown (self) -> Dict[str, Union[List, int]] :

        # await the queue process
        await self.queue.join()

        self.stop()

        return self.to_dict()

    # Serialization
    def to_dict(self) -> Dict[str, Union[List, int]] :
        return {
            'file_map'   : [
                {
                    'path'          : str(f['path']),
                    'size'          : f['size'],
                    'start_offset'  : f['start_offset'],
                    'end_offset'    : f['end_offset'],
                } for f in self.file_map

            ], 
            'queue_size' : self.queue.maxsize
        }
    
    # De-Serialization
    @classmethod
    def from_dict(cls, data:Dict[str, Union[List[Dict], int]]) -> 'DiskManager':

        file_map: List[Dict] = [
            {
                'path'          : Path(f['path']),
                'size'          : f['size'],
                'start_offset'  : f['start_offset'],
                'end_offset'    : f['end_offset'],  
            } for f in data['file_map']
        ]

        queue_size: int = data['queue_size'] or 200

        instance: DiskManager = cls(file_map, queue_size)

        return instance

