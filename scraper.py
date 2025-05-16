import functools
import os
import re
import time
import zipfile
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
from urllib.parse import urljoin, unquote
import concurrent.futures
from pathlib import Path
import json
import logging
from typing import List, Dict, Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('scraper.log')
    ]
)
logger = logging.getLogger(__name__)

class PokemonCardScraper:
    def __init__(self, base_url: str = "https://www.pokellector.com"):
        self.base_url = base_url
        
        # Configure session with connection pooling and timeouts
        session = requests.Session()
        
        # Create a custom adapter with retry strategy
        retry_strategy = requests.adapters.Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        
        # Mount the adapter with retry strategy
        adapter = requests.adapters.HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,  # Number of connection pools to cache
            pool_maxsize=10,      # Max number of connections per pool
            pool_block=False
        )
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        
        # Set default headers
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'DNT': '1',
            'Sec-GPC': '1',
        })
        
        # Configure session timeouts
        session.request = functools.partial(session.request, timeout=(10, 30))  # (connect, read) timeouts
        
        self.session = session
        self.downloaded_files = set()
        
        # Create necessary directories
        self.output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pokemon_cards')
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Load progress if exists
        self.progress_file = os.path.join(self.output_dir, 'progress.json')
        self.load_progress()
    
    def load_progress(self):
        """Load progress from previous run"""
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r') as f:
                    progress = json.load(f)
                    self.downloaded_files = set(progress.get('downloaded_files', []))
                logger.info(f"Loaded progress: {len(self.downloaded_files)} files already downloaded")
            except Exception as e:
                logger.error(f"Error loading progress: {e}")
    
    def save_progress(self):
        """Save current progress to file"""
        try:
            with open(self.progress_file, 'w') as f:
                json.dump({'downloaded_files': list(self.downloaded_files)}, f)
        except Exception as e:
            logger.error(f"Error saving progress: {e}")
    
    def get_soup(self, url: str, max_retries: int = 3, initial_delay: float = 1.0) -> Optional[BeautifulSoup]:
        """
        Get BeautifulSoup object from URL with retry logic and exponential backoff.
        
        Args:
            url: The URL to fetch
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay between retries in seconds (will be doubled after each retry)
            
        Returns:
            BeautifulSoup object if successful, None otherwise
        """
        delay = initial_delay
        last_exception = None
        
        for attempt in range(max_retries + 1):  # +1 because we want to try at least once
            try:
                # Increase timeout for the initial request
                response = self.session.get(
                    url,
                    headers=self.session.headers,
                    timeout=(10, 30)  # (connect timeout, read timeout) in seconds
                )
                response.raise_for_status()
                return BeautifulSoup(response.content, 'html.parser')
                
            except requests.exceptions.Timeout as e:
                last_exception = e
                if attempt < max_retries:
                    retry_after = min(delay * (2 ** attempt), 60)  # Cap at 60 seconds
                    logger.warning(
                        f"Timeout fetching {url} (attempt {attempt + 1}/{max_retries}). "
                        f"Retrying in {retry_after:.1f} seconds..."
                    )
                    time.sleep(retry_after)
                
            except requests.exceptions.RequestException as e:
                last_exception = e
                if attempt < max_retries and self._is_retryable_error(e):
                    retry_after = min(delay * (2 ** attempt), 60)
                    logger.warning(
                        f"Error fetching {url} (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {retry_after:.1f} seconds..."
                    )
                    time.sleep(retry_after)
                else:
                    break
            
            except Exception as e:
                last_exception = e
                logger.error(f"Unexpected error fetching {url}: {e}")
                break
        
        logger.error(f"Failed to fetch {url} after {max_retries + 1} attempts. Last error: {last_exception}")
        return None
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """
        Determine if an error is retryable.
        
        Args:
            error: The exception to check
            
        Returns:
            bool: True if the error is retryable, False otherwise
        """
        if isinstance(error, (requests.exceptions.Timeout,
                            requests.exceptions.ConnectionError,
                            requests.exceptions.ChunkedEncodingError,
                            requests.exceptions.RetryError)):
            return True
            
        # Check for HTTP status codes that can be retried
        if isinstance(error, requests.exceptions.HTTPError):
            status_code = error.response.status_code
            return status_code in [429, 500, 502, 503, 504, 522, 524]
            
        return False

    def get_sets(self) -> List[Dict[str, str]]:
        """Get all Pokémon card sets from the main page."""
        logger.info("Fetching list of all Pokémon sets...")
        soup = self.get_soup(f"{self.base_url}/sets")
        if not soup:
            return []
        
        sets = []
        # Find all set links in the grid - they're in <a> tags with class 'button' and have a name attribute
        set_links = soup.select('a.button[name]')
        
        for link in set_links:
            try:
                # Get the set URL from the href attribute
                set_url = urljoin(self.base_url, link['href'])
                
                # Get the set name from the title attribute or the span text
                set_name = link.get('title', '').replace(' Set', '').strip()
                if not set_name:
                    set_name = link.find('span')
                    set_name = set_name.get_text(strip=True) if set_name else ''
                
                # Get the set code from the URL (e.g., 'Destined-Rivals-Expansion')
                set_code = set_url.rstrip('/').split('/')[-1]
                
                # Skip if we don't have a valid set code or name
                if not set_code or not set_name:
                    continue
                
                # Clean up set code for directory name (remove 'Expansion' and special chars)
                clean_set_code = re.sub(r'(-Expansion)?[^\w-]', '', set_code)
                
                sets.append({
                    'name': set_name.strip(),
                    'code': clean_set_code,
                    'url': set_url
                })
                
                logger.debug(f"Found set: {set_name} ({clean_set_code}) at {set_url}")
                
            except Exception as e:
                logger.error(f"Error processing set link: {e}")
                continue
        
        logger.info(f"Found {len(sets)} sets")
        return sets

    def get_cards_from_set(self, set_info: Dict[str, str]) -> List[Dict[str, str]]:
        """Get all cards from a specific set with pagination support."""
        logger.info(f"Processing set: {set_info['name']} ({set_info['code']})")
        
        # Try multiple URL patterns to find the card list
        base_urls = [
            set_info['url'].rstrip('/') + '/cards',  # Try /cards suffix first
            set_info['url'].rstrip('/') + '/all',    # Try /all suffix
            set_info['url'].rstrip('/')              # Try the original URL
        ]
        
        soup = None
        card_list_url = ""
        
        # Try each URL pattern until we find one that works
        for url in base_urls:
            logger.debug(f"Trying URL: {url}")
            soup = self.get_soup(url)
            if soup:
                card_list_url = url
                logger.info(f"Found valid URL: {url}")
                break
        
        if not soup:
            logger.warning(f"Failed to fetch set page: {set_info['name']}")
            return []
        
        # Check if this is a card detail page
        card = self._extract_card_details_from_page(soup, card_list_url, set_info)
        if card:
            logger.info(f"Found single card: {card['name']} ({card['number']})")
            return [card]
        
        cards = []
        page = 1
        has_more = True
        
        while has_more and page <= 20:  # Safety limit of 20 pages
            # For the first page, use the URL we already have
            if page > 1:
                url = f"{card_list_url}?page={page}"  # Some sites use ?page=
                logger.debug(f"Fetching page {page} from {url}")
                soup = self.get_soup(url)
                if not soup:
                    # Try with /page/ format if ?page= didn't work
                    url = f"{card_list_url}/page/{page}"
                    logger.debug(f"Trying alternative pagination: {url}")
                    soup = self.get_soup(url)
                    if not soup:
                        logger.warning(f"Failed to fetch page {page} for set {set_info['name']}")
                        break
            
            # Try to find card containers - these might contain the actual card links
            card_containers = soup.select('.card-container, .card-item, .card-wrapper, .grid-item')
            logger.debug(f"Found {len(card_containers)} potential card containers")
            
            # If no containers found, try to find any links that might be cards
            if not card_containers:
                all_links = soup.find_all('a', href=True)
                card_links = []
                
                # Look for links that contain common card URL patterns
                for link in all_links:
                    href = link.get('href', '').lower()
                    if any(pattern in href for pattern in ['/card/', '/set/', '-card-', '-pkmn-']):
                        card_links.append(link)
                
                logger.debug(f"Found {len(card_links)} potential card links")
                
                # Process the card links we found
                for card_link in card_links:
                    try:
                        card_url = urljoin(self.base_url, card_link['href'])
                        
                        # Skip if we've already processed this card
                        if any(c['card_url'] == card_url for c in cards):
                            continue
                        
                        # Try to get card details from the card's page
                        card_soup = self.get_soup(card_url)
                        if not card_soup:
                            continue
                        
                        # Extract card details from the card page
                        card = self._extract_card_details_from_page(card_soup, card_url, set_info)
                        if card:
                            cards.append(card)
                            logger.info(f"Found card: {card['name']} ({card['number']})")
                        
                        # Be nice to the server
                        time.sleep(0.5)
                        
                    except Exception as e:
                        logger.error(f"Error processing card: {e}")
                        continue
            else:
                # Process card containers
                for container in card_containers:
                    try:
                        # Find the first link in the container
                        link = container.find('a', href=True)
                        if not link:
                            continue
                            
                        card_url = urljoin(self.base_url, link['href'])
                        
                        # Skip if we've already processed this card
                        if any(c['card_url'] == card_url for c in cards):
                            continue
                        
                        # Try to get card details from the container first
                        card = self._extract_card_from_container(container, card_url, set_info)
                        if not card:
                            # If that fails, fetch the card page
                            card_soup = self.get_soup(card_url)
                            if not card_soup:
                                continue
                            card = self._extract_card_details_from_page(card_soup, card_url, set_info)
                        
                        if card:
                            cards.append(card)
                            logger.info(f"Found card: {card['name']} ({card['number']})")
                        
                        # Be nice to the server
                        time.sleep(0.5)
                        
                    except Exception as e:
                        logger.error(f"Error processing card container: {e}")
                        continue
            
            # Check if there's a next page
            next_page = soup.select_one('a.next, .pagination .next, .next-page, a[rel="next"], .pagination-next a')
            if not next_page:
                has_more = False
            else:
                page += 1
                # Be nice to the server
                time.sleep(1)
        
        logger.info(f"Found {len(cards)} cards in set {set_info['name']}")
        return cards
    
    def _extract_card_from_container(self, container, card_url: str, set_info: Dict[str, str]) -> Optional[Dict[str, str]]:
        """Extract card details from a container element."""
        try:
            # Try to find the card name
            name_elem = container.select_one('.card-name, .name, .title, h3, h4')
            card_name = name_elem.get_text(strip=True) if name_elem else ""
            
            # Try to find the card number
            number_elem = container.select_one('.card-number, .number, .num')
            card_number = ""
            if number_elem:
                # Extract first sequence of digits
                match = re.search(r'(\d+)', number_elem.get_text(strip=True))
                if match:
                    card_number = match.group(1)
            
            # If we couldn't find a number, try to extract from URL
            if not card_number:
                url_parts = card_url.rstrip('/').split('/')
                if len(url_parts) >= 2 and url_parts[-1].isdigit():
                    card_number = url_parts[-1]
                else:
                    # Try to find number in the last part of the URL
                    last_part = url_parts[-1]
                    match = re.search(r'(\d+)(?:-\w+)?$', last_part)
                    if match:
                        card_number = match.group(1)
            
            # Try to find the image
            img = container.find('img')
            img_url = ""
            if img:
                img_url = img.get('data-src') or img.get('src', '')
                if img_url and not img_url.startswith('http'):
                    img_url = urljoin(self.base_url, img_url)
            
            if not card_name:
                if img and img.get('alt'):
                    card_name = img['alt'].strip()
                else:
                    card_name = f"Card-{card_number}" if card_number else "Unknown"
            
            if not card_number:
                logger.warning(f"Couldn't determine card number for: {card_name}")
                return None
            
            return {
                'name': card_name,
                'number': card_number.zfill(3),
                'img_url': img_url,
                'card_url': card_url,
                'set_code': set_info['code'],
                'set_name': set_info['name']
            }
            
        except Exception as e:
            logger.error(f"Error extracting card from container: {e}")
            return None
    
    def _extract_card_number(self, card_link, card_url: str) -> Optional[str]:
        """Extract and clean the card number from various possible locations."""
        # Try to get from card number element first
        card_number_elem = card_link.select_one('.card-number')
        if card_number_elem:
            number_text = card_number_elem.get_text(strip=True)
            # Extract first sequence of digits (e.g., '1/102' -> '1')
            match = re.search(r'(\d+)', number_text.split('/')[0])
            if match:
                return match.group(1)
        
        # If not found, try to extract from URL (e.g., '/card/set/SWSH12/1' -> '1')
        url_parts = card_url.rstrip('/').split('/')
        if len(url_parts) >= 2 and url_parts[-1].isdigit():
            return url_parts[-1]
        
        # Try to find number in the last part of the URL
        last_part = url_parts[-1]
        match = re.search(r'(\d+)(?:-\w+)?$', last_part)
        if match:
            return match.group(1)
        
        logger.warning(f"Couldn't determine card number for: {card_url}")
        return None
    
    def _extract_card_details_from_page(self, soup, card_url: str, set_info: Dict[str, str]) -> Optional[Dict[str, str]]:
        """Extract card details from a card detail page."""
        try:
            logger.debug(f"Extracting card details from: {card_url}")
            
            # First, try to extract card number from the URL
            # Example: https://www.pokellector.com/Journey-Together-Expansion/Meowscarada-ex-Card-18
            card_number = None
            url_parts = card_url.rstrip('/').split('/')
            
            # Debug: Log URL parts for analysis
            logger.debug(f"URL parts: {url_parts}")
            
            # Try to extract number from the last part of the URL (e.g., "Meowscarada-ex-Card-18" -> "18")
            last_part = url_parts[-1]
            logger.debug(f"Last part of URL: {last_part}")
            
            # Try different patterns to extract the card number
            patterns = [
                r'Card[-_](\d+)$',           # Matches "Card-123" at end of string
                r'[-_](\d+)$',                # Matches any number at end after - or _
                r'#(\d+)',                   # Matches "#123"
                r'(?:No\.?|#)?\s*(\d+)',    # Matches "No. 123" or "#123" or "123"
                r'\b(\d{1,3})\b'            # Matches any 1-3 digit number
            ]
            
            for pattern in patterns:
                match = re.search(pattern, last_part, re.IGNORECASE)
                if match:
                    card_number = match.group(1)
                    logger.debug(f"Extracted card number '{card_number}' using pattern: {pattern}")
                    break
            
            # If not found in URL, try to find it in the page content
            if not card_number:
                logger.debug("Card number not found in URL, checking page content")
                # Look for common number patterns in the page
                number_selectors = [
                    '.card-number',
                    '.number',
                    '.card-info',
                    '.card-details',
                    'p:contains("Card Number")',
                    'th:contains("Number") + td',
                    '.card-num',
                    '.card-number',
                    '.number',
                    '.card-info-number',
                    '.card-details-number',
                    '.card-data-number',
                    '.card-meta-number',
                    '.card-header-number',
                    '.card-footer-number',
                    'span:contains("No.")',
                    'span:contains("#")',
                    'div:contains("Card Number:")',
                    'div:contains("Card No:")',
                    'div:contains("Number:")',
                    'div:contains("No.:")',
                    'div:contains("#:")',
                    'td:contains("Card Number") + td',
                    'td:contains("Card No") + td',
                    'td:contains("Number") + td',
                    'td:contains("No.") + td',
                    'td:contains("#") + td',
                    'li:contains("Card Number")',
                    'li:contains("Card No")',
                    'li:contains("Number")',
                    'li:contains("No.")',
                    'li:contains("#")'
                ]
                
                for selector in number_selectors:
                    try:
                        number_elems = soup.select(selector)
                        for elem in number_elems:
                            text = elem.get_text(strip=True)
                            # Look for patterns like "#123" or "123/200" or "No. 123"
                            match = re.search(r'(?:#|No\.?\s*)?(\d+)(?:\s*/\s*\d+)?', text)
                            if match:
                                card_number = match.group(1)
                                logger.debug(f"Found card number '{card_number}' in selector: {selector}")
                                break
                            
                            # Also check for numbers in data attributes
                            for attr in ['data-number', 'data-card-number', 'data-num']:
                                if attr in elem.attrs:
                                    match = re.search(r'(\d+)', elem[attr])
                                    if match:
                                        card_number = match.group(1)
                                        logger.debug(f"Found card number '{card_number}' in {attr} attribute of: {selector}")
                                        break
                            
                            if card_number:
                                break
                        
                        if card_number:
                            break
                            
                    except Exception as e:
                        logger.debug(f"Error processing selector '{selector}': {e}")
                        continue
            
            if not card_number:
                logger.warning(f"Couldn't determine card number for: {card_url}")
                logger.debug(f"Page title: {soup.title.string if soup.title else 'No title'}")
                
                # Dump the first 1000 characters of the page for debugging
                page_text = str(soup)[:1000]
                logger.debug(f"Page content (first 1000 chars):\n{page_text}")
                
                return None
            
            # Clean up the card number (remove leading zeros, etc.)
            card_number = str(int(card_number))  # Converts "001" to "1"
            
            # Get card name - try multiple selectors
            card_name = None
            name_selectors = [
                'h1.entry-title',
                'h1',
                '.card-title',
                '.card-name',
                '.title',
                'h1.card-title',
                'h1.product-title',
                'h1.entry-title',
                'h1.title',
                'h1.product-name',
                'h1.product_title'
            ]
            
            for selector in name_selectors:
                name_elem = soup.select_one(selector)
                if name_elem:
                    card_name = name_elem.get_text(strip=True)
                    # Clean up the name (remove set name, card number, etc.)
                    card_name = re.sub(r'\s*[\[\{].*?[\]\}]', '', card_name)  # Remove anything in brackets
                    card_name = re.sub(r'\s*#\d+.*$', '', card_name)  # Remove card number at the end
                    card_name = card_name.strip()
                    if card_name:
                        break
            
            if not card_name:
                # If we still don't have a name, try to extract it from the URL
                name_part = last_part.split('-Card-')[0]  # Get part before "-Card-123"
                if name_part:
                    card_name = name_part.replace('-', ' ').title()
                else:
                    card_name = f"Card-{card_number}"
            
            # Get image URL - try multiple selectors and attributes
            img_url = None
            img_selectors = [
                'div.card-image img',
                '.card-image img',
                '.product-image img',
                '.card-img img',
                'img.card-image',
                'img.product-image',
                'img.wp-post-image',
                'img.attachment-full',
                'img.size-full',
                'img[src*="cards"]',
                'img[src*="card"]',
                'img[src*="image"]',
                'img[src*="images"]'
            ]
            
            for selector in img_selectors:
                img = soup.select_one(selector)
                if img:
                    img_url = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
                    if img_url and not img_url.startswith(('http://', 'https://')):
                        img_url = urljoin(self.base_url, img_url)
                    if img_url and img_url.endswith(('.jpg', '.jpeg', '.png', '.webp')):
                        break
            
            if not img_url:
                logger.warning(f"No image found on card page: {card_url}")
                return None
            
            # Clean up the image URL (remove query parameters, etc.)
            img_url = img_url.split('?')[0]
            
            # Clean up the card name for filename
            safe_name = re.sub(r'[^\w\s-]', '', card_name).strip().replace(' ', '-')
            
            return {
                'name': card_name,
                'number': card_number.zfill(3),  # Pad with leading zeros
                'img_url': img_url,
                'card_url': card_url,
                'set_code': set_info['code'],
                'set_name': set_info['name']
            }
            
        except Exception as e:
            logger.error(f"Error extracting details from card page {card_url}: {e}")
            return None

    def download_image(self, card: Dict[str, str]) -> bool:
        """Download a single card image."""
        try:
            # Create set directory if it doesn't exist
            set_dir = os.path.join(self.output_dir, card['set_code'])
            os.makedirs(set_dir, exist_ok=True)
            
            # Create filename: [set-code]-[number].png
            filename = f"{card['set_code']}-{card['number']}.png"
            filepath = os.path.join(set_dir, filename)
            
            # Create a unique identifier for this download to track progress
            download_id = f"{card['set_code']}-{card['number']}"
            
            # Skip if file already exists or was already downloaded in this session
            if os.path.exists(filepath) or download_id in self.downloaded_files:
                logger.debug(f"Skipping already downloaded: {filename}")
                return True
            
            logger.info(f"Downloading: {filename} from {card['img_url']}")
            
            # Download the image with retries
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = self.session.get(card['img_url'], stream=True, timeout=30)
                    response.raise_for_status()
                    
                    # Save the image
                    with open(filepath, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    
                    # Verify the file was downloaded correctly
                    if os.path.getsize(filepath) > 0:
                        self.downloaded_files.add(download_id)
                        self.save_progress()
                        return True
                    else:
                        os.remove(filepath)  # Remove empty file
                        raise Exception("Downloaded file is empty")
                        
                except Exception as e:
                    if attempt == max_retries - 1:  # Last attempt
                        logger.error(f"Failed to download {card['img_url']} after {max_retries} attempts: {e}")
                        if os.path.exists(filepath):
                            os.remove(filepath)
                        return False
                    
                    # Wait before retrying
                    time.sleep(2 ** attempt)  # Exponential backoff
            
            return False
            
        except Exception as e:
            logger.error(f"Error downloading {card.get('name', 'unknown')} ({card.get('img_url', 'no url')}): {e}")
            return False

    def create_zip_archive(self) -> str:
        """Create a zip archive of the downloaded images."""
        zip_path = os.path.join(os.path.dirname(self.output_dir), 'pokemon_cards.zip')
        
        logger.info(f"Creating zip archive: {zip_path}")
        
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Walk through the directory and add files to the zip
                for root, _, files in os.walk(self.output_dir):
                    for file in files:
                        if not file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                            continue
                            
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, self.output_dir)
                        zipf.write(file_path, arcname)
            
            logger.info(f"Successfully created zip archive: {zip_path} ({os.path.getsize(zip_path) / (1024*1024):.2f} MB)")
            return zip_path
            
        except Exception as e:
            logger.error(f"Error creating zip archive: {e}")
            return ""

def main():
    try:
        logger.info("Starting Pokémon Card Scraper")
        
        # Initialize scraper
        scraper = PokemonCardScraper()
        
        # Get all sets
        sets = scraper.get_sets()
        
        if not sets:
            logger.error("No sets found. The website structure might have changed.")
            return
        
        logger.info(f"Found {len(sets)} sets to process")
        
        # Process each set
        total_cards = 0
        successful_downloads = 0
        
        for set_info in sets:
            try:
                # Get cards for this set
                cards = scraper.get_cards_from_set(set_info)
                if not cards:
                    logger.warning(f"No cards found for set: {set_info['name']}")
                    continue
                
                total_cards += len(cards)
                logger.info(f"Downloading {len(cards)} cards from {set_info['name']}")
                
                # Download cards with progress bar
                with tqdm(total=len(cards), desc=f"{set_info['code']}", unit="card") as pbar:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                        futures = []
                        for card in cards:
                            futures.append(executor.submit(scraper.download_image, card))
                        
                        for future in concurrent.futures.as_completed(futures):
                            if future.result():
                                successful_downloads += 1
                            pbar.update(1)
                
                # Small delay between sets to be nice to the server
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error processing set {set_info['name']}: {e}")
                continue
        
        logger.info(f"\nDownloaded {successful_downloads} out of {total_cards} cards")
        
        # Create zip archive
        zip_path = scraper.create_zip_archive()
        
        if zip_path:
            logger.info(f"\nAll done! Cards have been downloaded to: {scraper.output_dir}")
            logger.info(f"Zip archive created at: {zip_path}")
        else:
            logger.error("Failed to create zip archive")
    
    except KeyboardInterrupt:
        logger.info("\nOperation cancelled by user")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
    finally:
        # Ensure we save progress even if the program crashes
        if 'scraper' in locals():
            scraper.save_progress()
        logger.info("Scraping completed")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        print(f"A critical error occurred. Please check the log file for details.")
        raise
