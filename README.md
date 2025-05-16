# Pokémon Card Scraper

A robust Python-based web scraper that downloads high-quality Pokémon card images from multiple sources, organizing them by source, language, set, and card number with intelligent naming and progress tracking.

## 🌐 Supported Sources
- **Pokellector** - English and Japanese cards
- **TCG Collector** - English and Japanese cards

## ✨ Features

- **Multiple Sources**: Download cards from Pokellector or TCG Collector
- **Language Support**: Choose between English and Japanese cards
- **Interactive Menu**: Easy-to-use command line interface
- **Automatic Set Discovery**: Finds and processes all available Pokémon TCG sets
- **Resumable Downloads**: Saves progress to resume interrupted downloads
- **Intelligent Naming**: Names files using set codes and card numbers (e.g., `base-set-001-pikachu.jpg`)
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

### Interactive Menu
When you run the script, you'll be presented with an interactive menu:

1. **Select a source**:
   - Pokellector (English/Japanese)
   - TCG Collector (English/Japanese)
   - Exit

2. **Choose language**:
   - English (en)
   - Japanese (jp)

3. **Set output directory** (default: 'pokemon_cards')

4. **Select log level**:
   - DEBUG (Most detailed)
   - INFO (Recommended)
   - WARNING (Only warnings and errors)
   - ERROR (Only errors)

5. **Select sets to download**:
   - View the list of available sets and choose which ones to download
   - Type numbers separated by commas (e.g., 1,2,3) or 'all' to download everything

## 📁 Output Structure

Cards are organized in the following directory structure:

```
pokemon_cards/
├── pokellector/
│   ├── en/
│   │   ├── base-set/
│   │   │   ├── base-set-001-pikachu.jpg
│   │   │   └── ...
│   │   └── ...
│   └── jp/
│       └── ...
└── tcgcollector/
    ├── en/
    │   └── ...
    └── jp/
        └── ...
```

### File Naming Convention
- Files are named as: `{set_code}-{card_number}-{card_name}.jpg`
- Example: `base-set-001-pikachu.jpg`

## 🔍 How It Works

1. The scraper starts with an interactive menu to select source and language
2. It fetches the list of all available Pokémon TCG sets from the selected source
3. You can choose which sets to download
4. For each selected set, it finds all cards and their image URLs
5. Images are downloaded and saved with consistent naming and organization

### Technical Details
- Uses `requests` with retry logic for reliable downloads
- Implements connection pooling for better performance
- Saves progress to allow resuming interrupted downloads
- Includes rate limiting to be respectful to the source websites

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

- Be mindful of the website's terms of service and robots.txt
- Consider adding delays between requests to avoid overloading the servers
- Don't use this for commercial purposes or mass downloading
- All Pokémon content is © The Pokémon Company International, Inc.

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
