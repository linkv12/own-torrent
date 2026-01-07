# own-torrent

**own-torrent** is a Python application for downloading torrent data.

Capable to download from UDP tracked torrent. 

> 🚧 This project is under active development and is not yet production-ready.<br>Heavy Refactoring is needed.

This project is experimental and not ready for real-world use.

## Features

- Parse local `.torrent` files
- Download data from peers
- Basic torrent protocol handling

## Roadmap

Planned improvements and features:

- [ ] Implement end-game stategy
- [x] Implement block request timeout
- [x] Terminal Interface
- [ ] Clear debug log
- [ ] Refactor project structure
- [ ] Configuration for the App

## Usage
Clone the repository, then do the following step.

```sh
# 1. Create Vitual Enviroment
python -m venv .venv

# 2. Activate
source .venv/bin/activate

# 3. Instal depedency
pip install -r requirements.txt

# 4. Run the app
python app.py
```

## Contributing

Pull requests are welcome. For major changes, please open an issue first
to discuss what you would like to change.

Please make sure to update tests as appropriate.

## License

This project is licensed under the **MIT License**.  
See the full license text here:  
[MIT License](https://choosealicense.com/licenses/mit/)


