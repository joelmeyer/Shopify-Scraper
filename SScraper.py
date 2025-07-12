import time
import datetime
import json
import requests
import threading
from random import randint
from dhooks import Webhook, Embed
import sqlite3
import logging
import os
from logging.handlers import TimedRotatingFileHandler
from dotenv import load_dotenv
import math
import random

load_dotenv()

URL_PATH = 'products.json?limit=200&page=1'
DB_PATH = 'data/products.db'

SHOPIFY_URLS = os.getenv('SHOPIFY_URLS', '').split(',')
PROXIES = [p for p in os.getenv('PROXIES', '').split(',') if p]
NOTIFY_WEBHOOK = os.getenv('NOTIFY_WEBHOOK', '')
ERROR_WEBHOOK = os.getenv('ERROR_WEBHOOK', '')
PRODUCT_LIMIT = int(os.getenv('PRODUCT_LIMIT', '200'))
PRICE_DROP_THRESHOLD = float(os.getenv('PRICE_DROP_THRESHOLD', '0.1'))  # Default 10% drop

# Advanced anti-bot constants
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.131 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
]
ACCEPT_LANGUAGES = [
    'en-US,en;q=0.9',
    'en-GB,en;q=0.8',
    'en;q=0.7',
    'en-US;q=0.8,en;q=0.6',
]
REFERERS = [
    '',
    'https://www.google.com/',
    'https://www.bing.com/',
    'https://duckduckgo.com/'
]
MIN_SLEEP = 180
MAX_SLEEP = 300
JITTER = 30

# Setup logging
LOG_DIR = 'logs'
os.makedirs(LOG_DIR, exist_ok=True)
log_formatter = logging.Formatter('%(asctime)s [%(threadName)s][Thread-%(thread)d][%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
log_file = os.path.join(LOG_DIR, 'scraper.log')
file_handler = TimedRotatingFileHandler(log_file, when='midnight', backupCount=7)
file_handler.setFormatter(log_formatter)
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
logger = logging.getLogger('scraper')
logger.setLevel(logging.DEBUG)
logger.handlers = []
logger.addHandler(file_handler)
logger.addHandler(console_handler)

db_lock = threading.Lock()

def getProxies():
    logger.debug('Entering getProxies')
    # Use proxies from env
    proxy = PROXIES.copy()
    logger.debug(f'Loaded {len(proxy)} proxies')
    return proxy
    
def fetch_all_products_with_paging(url, product_limit=PRODUCT_LIMIT, max_errors=3):
    """
    Fetch all products from a Shopify store using paging, with advanced anti-bot and error handling logic.
    Adds a random jitter between successful requests and uses a requests.Session for cookie and connection reuse.
    If too many errors occur, aborts and returns what was fetched so far.
    """
    logger.debug(f'Fetching all products with paging for url: {url}')
    proxy_list = getProxies()
    all_products = []
    page = 1
    per_page = 200
    site_429_count = 0
    max_429_skip = 5  # After this many 429s, skip site for 30 min
    session = requests.Session()  # Use a session for cookies and connection reuse
    error_count = 0
    while len(all_products) < product_limit:
        url_1 = f"{url}products.json?limit={per_page}&page={page}"
        condition = True
        products = []
        backoff = random.randint(MIN_SLEEP, MAX_SLEEP)  # Start with random 3-5 min
        headers = {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': random.choice(ACCEPT_LANGUAGES),
            'Referer': random.choice(REFERERS) or url,
            'Connection': 'keep-alive',
        }
        while condition:
            use_proxy = len(proxy_list) > 0
            try:
                if use_proxy:
                    x = randint(0, len(proxy_list) - 1)
                    proxy = proxy_list[x]
                    proxy_dict = {'http': f'http://{proxy}', 'https': f'https://{proxy}'}
                    logger.debug(f'Trying proxy: {proxy} (page {page})')
                    webpage = session.get(url_1, headers=headers, proxies=proxy_dict, timeout=30)
                else:
                    logger.debug(f'No proxies, using localhost (page {page})')
                    webpage = session.get(url_1, headers=headers, timeout=30)
                if webpage.status_code == 429:
                    logger.error(f'Non-200 response 429 for {url_1}: {webpage.text[:200]}')
                    site_429_count += 1
                    if site_429_count >= max_429_skip:
                        logger.error(f'Too many 429s for {url}. Skipping this site for 30 minutes.')
                        time.sleep(1800 + random.randint(0, JITTER))
                        site_429_count = 0
                    else:
                        logger.debug(f'Backing off for {backoff} seconds (exponential, with jitter)')
                        time.sleep(backoff + random.randint(0, JITTER))
                        backoff = min(backoff * 2, 1800)
                    error_count += 1
                    if error_count >= max_errors:
                        logger.error(f'Maximum error count ({max_errors}) reached in fetch_all_products_with_paging. Aborting.')
                        return all_products
                    continue
                elif webpage.status_code != 200:
                    logger.error(f'Non-200 response {webpage.status_code} for {url_1}: {webpage.text[:200]}')
                    time.sleep(random.randint(MIN_SLEEP, MAX_SLEEP))
                    error_count += 1
                    if error_count >= max_errors:
                        logger.error(f'Maximum error count ({max_errors}) reached in fetch_all_products_with_paging. Aborting.')
                        return all_products
                    continue
                try:
                    products = json.loads((webpage.text))['products']
                except Exception as e:
                    logger.error(f'JSON decode error for {url_1}: {e}\nResponse: {webpage.text[:200]}')
                    time.sleep(random.randint(MIN_SLEEP, MAX_SLEEP))
                    error_count += 1
                    if error_count >= max_errors:
                        logger.error(f'Maximum error count ({max_errors}) reached in fetch_all_products_with_paging. Aborting.')
                        return all_products
                    continue
                logger.debug(f'Successfully fetched {len(products)} products (page {page})')
                condition = False
            except Exception as e:
                logger.error(f'Error getting products (page {page})(url {url_1}): {e}\n Sleeping 3 minutes...')
                time.sleep(random.randint(MIN_SLEEP, MAX_SLEEP))
                error_count += 1
                if error_count >= max_errors:
                    logger.error(f'Maximum error count ({max_errors}) reached in fetch_all_products_with_paging. Aborting.')
                    return all_products
                continue
        if not products:
            logger.debug(f'No more products returned at page {page}. Stopping.')
            break
        all_products.extend(products)
        # Add jitter between successful requests
        sleep_jitter = random.randint(0, JITTER)
        logger.debug(f'Jitter sleep for {sleep_jitter} seconds after page {page}')
        time.sleep(sleep_jitter)
        if len(products) < per_page:
            logger.debug(f'Last page reached at page {page}.')
            break
        page += 1
    logger.debug(f'Exiting fetch_all_products_with_paging. Total products fetched: {len(all_products)}')
    return all_products

ALCOHOL_TYPES_PATH = os.path.join(os.path.dirname(__file__), 'alcohol_types.json')
ALCOHOL_TYPES_CACHE = None
ALCOHOL_TYPES_CACHE_MTIME = 0

def load_alcohol_types():
    global ALCOHOL_TYPES_CACHE, ALCOHOL_TYPES_CACHE_MTIME
    try:
        mtime = os.path.getmtime(ALCOHOL_TYPES_PATH)
        if ALCOHOL_TYPES_CACHE is None or mtime != ALCOHOL_TYPES_CACHE_MTIME:
            with open(ALCOHOL_TYPES_PATH, 'r', encoding='utf-8') as f:
                ALCOHOL_TYPES_CACHE = json.load(f)
            ALCOHOL_TYPES_CACHE_MTIME = mtime
            logger.debug(f'Reloaded alcohol_types.json with {len(ALCOHOL_TYPES_CACHE)} types (mtime={mtime})')
    except Exception as e:
        logger.error(f'Error loading alcohol_types.json: {e}')
        ALCOHOL_TYPES_CACHE = []
    return ALCOHOL_TYPES_CACHE

def get_alcohol_type(product):
    # Lowercase all relevant fields for easier matching
    fields = [
        (product.get('product_type') or '').lower(),
        (product.get('title') or '').lower(),
        (product.get('body_html') or '').lower(),
        ' '.join(product.get('tags', [])).lower()
    ]
    text = ' '.join(fields)
    for entry in load_alcohol_types():
        if any(keyword in text for keyword in entry.get('keywords', [])):
            return entry['type']
    return 'Other'

def send_webhook(webhook_type, content=None, embed=None):
    if webhook_type == 'notify':
        wh_url = NOTIFY_WEBHOOK
    elif webhook_type == 'error':
        wh_url = ERROR_WEBHOOK
    else:
        logger.error(f'Unknown webhook type: {webhook_type}')
        return
    if not wh_url:
        logger.error(f'Webhook URL for type {webhook_type} is not set.')
        return
    try:
        hook = Webhook(wh_url)
        if embed:
            hook.send(embed=embed)
        elif content:
            hook.send(content)
    except Exception as e:
        logger.error(f'Error sending {webhook_type} webhook: {e}')

def send_webhook_notification(product, url, event_type):
    """
    Send a Discord webhook notification for product events.
    event_type: 'available', 'unavailable', 'new', or 'price_reduced'
    """
    handle = product['handle']
    title = product.get('title', 'Unknown Product')
    link = f"{url}products/{handle}"
    image_url = None
    images = product.get('images', [])
    if images:
        try:
            image_url = images[0].get('src', None)
        except Exception:
            image_url = None
    variants = product.get('variants', [])
    price = variants[0].get('price', "0.00") if variants else "0.00"
    available = variants[0].get('available', False) if variants else False
    sizes_list = []
    for v in variants:
        sizes_list.append(f"Size {v.get('title', '')}:" + f"{url}cart/{v.get('id', '')}:1")
    if event_type == 'available':
        description = '***Product is now available!***'
        color = 0x00ff00
    elif event_type == 'unavailable':
        description = '***Product is now unavailable!***'
        color = 0xff0000
    elif event_type == 'new':
        description = '***New product found!***'
        color = 0x1e0f3
    elif event_type == 'price_reduced':
        drop_amt = product.get('price_drop_amount')
        drop_pct = product.get('price_drop_percent')
        description = f'***Product price reduced!***\nDrop: ${drop_amt:.2f} ({drop_pct:.1f}%)'
        color = 0x2563eb
    else:
        description = '***Product update***'
        color = 0xcccccc

    embed = Embed(description=description, color=color, timestamp='now')
    embed.add_field(name='Product Name', value=title)
    embed.add_field(name='Product Link', value=link)
    embed.add_field(name='Price', value=str(price))
    embed.add_field(name='Available', value=str(available))
    embed.add_field(name='ATC Links', value='\n'.join(sizes_list))
    embed.set_footer(text='Shopify Scraper', icon_url='https://pbs.twimg.com/profile_images/1122559367046410242/6pzYlpWd_400x400.jpg')
    if image_url:
        embed.set_thumbnail(image_url)
    embed.set_author(name='Shopify Crawler', icon_url='https://pbs.twimg.com/profile_images/1122559367046410242/6pzYlpWd_400x400.jpg')
    try:
        logger.debug(f'Sending {event_type} webhook notification')
        send_webhook('notify', embed=embed)
    except Exception as e:
        logger.error(f'Error sending {event_type} webhook: {e}')

def send_error_webhook(message):
    send_webhook('error', content=message)

def column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())

def init_db():
    with db_lock:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # Add columns if they do not exist
        c.execute('''CREATE TABLE IF NOT EXISTS products (
            id INTEGER,
            handle TEXT,
            title TEXT,
            available INTEGER,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            published_at TEXT,  -- ISO date string
            created_at TEXT,    -- ISO date string
            updated_at TEXT,    -- ISO date string
            vendor TEXT,
            url TEXT,
            price TEXT,
            original_json TEXT,
            input_url TEXT,
            alcohol_type TEXT,
            became_available_at TEXT,
            became_unavailable_at TEXT,
            date_added TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (id, input_url)
        )''')
        # Add columns if missing (for migrations)
        if not column_exists(c, 'products', 'became_available_at'):
            try:
                c.execute('ALTER TABLE products ADD COLUMN became_available_at TEXT')
            except Exception:
                pass
        if not column_exists(c, 'products', 'became_unavailable_at'):
            try:
                c.execute('ALTER TABLE products ADD COLUMN became_unavailable_at TEXT')
            except Exception:
                pass
        if not column_exists(c, 'products', 'date_added'):
            try:
                # SQLite does not allow non-constant defaults in ALTER TABLE, so add without default
                c.execute("ALTER TABLE products ADD COLUMN date_added TEXT")
            except Exception as e:
                logger.error(f'Error adding date_added column to products table {e}')
                pass
        conn.commit()
        conn.close()

def load_product_availability(input_url):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, available, price FROM products WHERE input_url = ?', (input_url,))
    rows = c.fetchall()
    conn.close()
    # Return a dict: id -> {'available': bool, 'price': float or None}
    return {id_: {'available': bool(available), 'price': float(price) if price is not None else None} for id_, available, price in rows}

def update_product_in_db(id_val, handle, title, available, product, url):
    with db_lock:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        c = conn.cursor()
        published_at = str(product.get('published_at') or '')
        created_at = str(product.get('created_at') or '')
        updated_at = str(product.get('updated_at') or '')
        vendor = product.get('vendor')
        product_url = f"{url}products/{handle}"
        variants = product.get('variants', [])
        price = variants[0].get('price', "0.00") if variants else "0.00"
        original_json = json.dumps(product)
        input_url = url
        alcohol_type = get_alcohol_type(product)
        c.execute('''INSERT INTO products (id, handle, title, available, last_seen, published_at, created_at, updated_at, vendor, url, price, original_json, input_url, alcohol_type, date_added)
                     VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                     ON CONFLICT(id, input_url) DO UPDATE SET
                        handle=excluded.handle,
                        title=excluded.title,
                        available=excluded.available,
                        last_seen=CURRENT_TIMESTAMP,
                        published_at=excluded.published_at,
                        created_at=excluded.created_at,
                        updated_at=excluded.updated_at,
                        vendor=excluded.vendor,
                        url=excluded.url,
                        price=excluded.price,
                        original_json=excluded.original_json,
                        alcohol_type=excluded.alcohol_type''',
                  (id_val, handle, title, int(available), published_at, created_at, updated_at, vendor, product_url, price, original_json, input_url, alcohol_type))
        conn.commit()
        conn.close()

def update_availability_timestamps(product_id, input_url, became_available_at=None, became_unavailable_at=None):
    """
    Update only the became_available_at and/or became_unavailable_at columns for a product.
    """
    with db_lock:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        c = conn.cursor()
        if became_available_at is not None:
            c.execute('UPDATE products SET became_available_at = ? WHERE id = ? AND input_url = ?', (became_available_at, product_id, input_url))
        if became_unavailable_at is not None:
            c.execute('UPDATE products SET became_unavailable_at = ? WHERE id = ? AND input_url = ?', (became_unavailable_at, product_id, input_url))
        conn.commit()
        conn.close()

def get_random_sleep_time(min_seconds=240, max_seconds=360):
    """Return a random sleep time between min_seconds and max_seconds (inclusive)."""
    return randint(min_seconds, max_seconds)

def is_interesting(product):
    """
    Returns (True, product_type) if the product is interesting (alcohol type is bourbon, whiskey, scotch, or other), else (False, product_type).
    """
    product_type = get_alcohol_type(product)
    if product_type.lower() in ['bourbon', 'whiskey', 'scotch', 'other']:
        return True, product_type
    return False, product_type

def Main(url):
    logger.debug(f'Entering Main for url: {url}')
    # Initialize DB
    init_db()
    # Load product availability from DB for this input_url
    product_availability = load_product_availability(url)
    init_product_count = len(product_availability)
    logger.debug(f'{init_product_count} products loaded from DB for {url}')
    logger.debug(f'DB Returned {len(product_availability)} products availablity')
    proxies = getProxies()

    logger.debug('Webhook loaded')   
    loop_exceptions = 0 

    while True:
        try:
            # Monitors website for new products
            products = fetch_all_products_with_paging(url)
            # Filter products using is_interesting before tracking for availability and new product detection in Main.
            interesting_products = [p for p in products if is_interesting(p)[0]]
            new_products = []
            brandnewproducts = 0
            logger.debug(f'{len(interesting_products)} interesting products fetched with paging')
            # --- Check for product availability changes ---
            for product in interesting_products:
                id_val = product.get('id')
                handle = product.get('handle', '')
                title = product.get('title', '')
                # If variants exist, check the first one for availability, else False
                available = False
                if product.get('variants') and len(product['variants']) > 0:
                    available = product['variants'][0].get('available', False)
                # --- Price drop notification logic ---
                price = 0.0
                try:
                    price = float(product['variants'][0]['price']) if product.get('variants') and len(product['variants']) > 0 else 0.0
                except Exception:
                    price = 0.0
                prev_price = None
                prev_available = None
                prev_info = product_availability.get(id_val)
                if prev_info is not None:
                    prev_available = prev_info.get('available')
                    prev_price = prev_info.get('price')
                # --- End price drop logic ---
                if prev_available is not None and not prev_available and available:
                    logger.debug(f'Product became available: {product["title"]} ({handle})')
                    new_products.append(id_val)
                    send_webhook_notification(product, url, 'available')
                    now = datetime.datetime.utcnow().isoformat()
                    update_availability_timestamps(id_val, url, became_available_at=now)
                elif prev_available is not None and prev_available and not available:
                    logger.debug(f'Product became UNAVAILABLE: {product["title"]} ({handle})')
                    new_products.append(id_val)
                    send_webhook_notification(product, url, 'unavailable')
                    now = datetime.datetime.utcnow().isoformat()
                    update_availability_timestamps(id_val, url, became_unavailable_at=now)
                elif prev_available is None:
                    logger.debug(f'New product detected: {product["title"]} ({handle})')
                    new_products.append(id_val)
                    brandnewproducts += 1
                    # Only Send a webhook notification if DB has been initialized and we haven't sent 5 notifications already
                    if init_product_count > 0 and brandnewproducts <= 15:
                        send_webhook_notification(product, url, 'new')
                elif prev_price is not None and price < prev_price:
                    percent_drop = (prev_price - price) / prev_price
                    if percent_drop >= PRICE_DROP_THRESHOLD:
                        logger.debug(f'Product price reduced: {product["title"]} ({handle}) {prev_price} -> {price} ({percent_drop*100:.1f}% drop)')
                        # Add price drop info to product for notification
                        product['price_drop_amount'] = prev_price - price
                        product['price_drop_percent'] = percent_drop * 100
                        send_webhook_notification(product, url, 'price_reduced')
                # Update the tracked availability in memory and DB
                product_availability[id_val] = {'available': available, 'price': price}
                update_product_in_db(id_val, handle, title, available, product, url)
            # --- End availability check ---
            logger.debug(f'Scraping target$* {url} new/changed products: {len(new_products)}')
            sleep_time = get_random_sleep_time(240, 360)
            logger.debug(f'sleeping for {sleep_time} seconds')
            time.sleep(sleep_time)
            loop_exceptions = 0  # Reset exception counter after successful iteration
        except Exception as e:
            if loop_exceptions > 5:
                logger.error(f'Main loop has encountered too many exceptions ({loop_exceptions}). Exiting...')
                send_error_webhook(f'Main loop has encountered too many exceptions last exception was ({e}). Exiting...')
                break
            logger.error(f'Error in Main loop: {e}')
            logger.debug('Sleeping for 5 seconds before retrying...')
            time.sleep(5)
            loop_exceptions += 1
            continue
if __name__ == "__main__":
    logger.info('SScraper 1.0')
    #choice = input('Enter any key to initialize scraper$* (Press \'Q\' to quit) ')
    #choice = (choice.lower())
    #if choice == ('q'):
    #    exit()
         
    # Grab links from text file to initialize threads.
    urls = [u.strip() for u in SHOPIFY_URLS if u.strip()]

    # Initializes threads to monitor multiple websites at once.
    for x in range(len(urls)):
        logger.debug(f'Initializing threads for url: {urls[x]}')
        #proxy_threads = threading.Thread(target=getProxies, name='getProxy Thread {}'.format(x))
        #content_threads = threading.Thread(target=getContent, name='getContent Thread {}'.format(x), args= (urls[x],))
        #product_threads = threading.Thread(target=getProducts, name='getProduct Thread {}'.format(x), args= (urls[x],))
        main_threads = threading.Thread(target=Main, name='Main Thread {}'.format(x), args= (urls[x],))
        #content_threads.start()
        #product_threads.start()
        main_threads.start()
        logger.debug(f'{main_threads.name} initialized')
    send_error_webhook(f'SScraper 1.0 initialized with {len(urls)} URLs')