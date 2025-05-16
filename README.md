# Pokémon Card Scraper

A robust Python-based web scraper that downloads high-quality Pokémon card images from [Pokellector](https://www.pokellector.com/), organizing them by set and card number with intelligent naming and progress tracking.

## ✨ Features

- **Automatic Set Discovery**: Finds and processes all available Pokémon TCG sets
- **Resumable Downloads**: Saves progress to resume interrupted downloads
- **Intelligent Naming**: Names files using set codes and card numbers (e.g., `swsh12-001-victini.jpg`)
- **Robust Error Handling**: Automatic retries with exponential backoff for failed requests
- **Progress Tracking**: Shows detailed progress for each set being processed
- **Efficient**: Uses connection pooling and keep-alive for better performance
- **Comprehensive Logging**: Detailed logs for troubleshooting and monitoring

## 🚀 Requirements

- Python 3.8+
- Required packages (install via `pip install -r requirements.txt`):
  - requests
  - beautifulsoup4
  - tqdm
  - lxml (for faster HTML parsing)

## 🛠 Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/pokemon-card-scraper.git
   cd pokemon-card-scraper
   ```

2. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

## 🏃‍♂️ Usage

### Basic Usage
```bash
python scraper.py
```

### Command Line Options

- `--log-level`: Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
  ```bash
  python scraper.py --log-level DEBUG
  ```

- `--output-dir`: Specify a custom output directory
  ```bash
  python scraper.py --output-dir ~/pokemon_cards
  ```

- `--resume`: Resume from last saved progress
  ```bash
  python scraper.py --resume
  ```

## 📁 Output Structure

Cards are organized in the following directory structure:
```
pokemon_cards/
├── base-set/
│   ├── base-001-pikachu.jpg
│   ├── base-002-raichu.jpg
│   └── ...
├── jungle/
│   ├── jungle-001-venonat.jpg
│   └── ...
└── ...
```

## 🔍 How It Works

1. The scraper first fetches the list of all available Pokémon TCG sets
2. For each set, it finds all cards and their image URLs
3. Images are downloaded and saved with consistent naming:
   - Format: `{set_code}-{card_number:03d}-{card_name}.jpg`
   - Example: `swsh12-001-victini.jpg`

## 🛡 Error Handling

The scraper includes several features to handle errors gracefully:
- Automatic retries for failed requests
- Exponential backoff between retries
- Detailed logging of all operations
- Progress saving to resume interrupted downloads

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This project is for educational purposes only. Please respect the terms of service of the websites being scraped. The author is not responsible for any misuse of this software.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## ⭐️ Support

If you find this project useful, consider giving it a ⭐️ on GitHub!

## 📝 Notes

- The scraper respects the website's `robots.txt` and includes delays between requests
- If the script is interrupted, it will skip already downloaded files when run again
- Some cards might be skipped if they don't have proper image URLs or card numbers
- The script includes rate limiting to avoid overloading the server
- All downloaded content is cached locally to minimize network requests

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## ⚠️ Disclaimer

This project is for educational purposes only. Please respect the copyright of the Pokémon Company and the website's terms of service. The author is not responsible for any misuse of this software.
