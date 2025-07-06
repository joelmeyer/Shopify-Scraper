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

load_dotenv()

URL_PATH = 'products.json?limit=200&page=1'
DB_PATH = 'data/products.db'

SHOPIFY_URLS = os.getenv('SHOPIFY_URLS', '').split(',')
PROXIES = [p for p in os.getenv('PROXIES', '').split(',') if p]
NOTIFY_WEBHOOK = os.getenv('NOTIFY_WEBHOOK', '')
ERROR_WEBHOOK = os.getenv('ERROR_WEBHOOK', '')

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

def getProxies():
    logger.debug('Entering getProxies')
    # Use proxies from env
    proxy = PROXIES.copy()
    logger.debug(f'Loaded {len(proxy)} proxies')
    return proxy
    
def getContent(url):
    logger.debug(f'Entering getContent for url: {url}')
    # Gets page conent from target website.
    proxy_list = getProxies()
    url_1 = (url + URL_PATH)
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.131 Safari/537.36'}
    condition = True
    while condition == True:
        if len(proxy_list) > 0:
            try:
                x = randint(0 , (len(proxy_list) - 1))
                proxy = proxy_list[x]
                proxy_dict = {'http': ('http://{}'.format(proxy)), 'https': ('https://{}'.format(proxy))}
                logger.debug(f'Trying proxy: {proxy}')
                webpage = requests.get(url_1, headers=headers, proxies=proxy_dict)
                products = json.loads((webpage.text))['products']
                logger.debug('Successfully fetched products with proxy')
                condition = False
            except Exception as e:
                logger.error(f'Error getting orignial products: {e}\n Sleeping 3 minutes...')
                time.sleep(180)
                continue
        else:
            try:
                logger.debug('No proxies, using localhost')
                webpage = requests.get(url_1, headers=headers)
                products = json.loads((webpage.text))['products']
                logger.debug('Successfully fetched products with localhost')
                condition = False
            except Exception as e:
                logger.error(f'Error getting original products: {e}\n Sleeping 3 minutes...')
                time.sleep(180)
                continue
    logger.debug('Exiting getContent')
    return products

def getProducts(url):
    logger.debug(f'Entering getProducts for url: {url}')
    # Adds all current products to a list.
    products = getContent(url)
    # Filter products to only those that are interesting
    interesting_products = [p for p in products if is_interesting(p)[0]]
    current_products = []
    # Track product availability by handle
    product_availability = {}
    # Initial population of product_availability
    for product in interesting_products: # Loops throught the 'title' handle to grab product names.
        handle = (product['handle'])
        current_products.append(handle)
        available = False
        # If variants exist, check the first one for availability, else False
        if product.get('variants') and len(product['variants']) > 0:
            available = product['variants'][0].get('available', False)
        product_availability[handle] = available
        
    logger.debug(f'Found {len(current_products)} interesting products')
    return current_products, product_availability

def is_interesting(product):
    # Check product_type
    product_type = get_alcohol_type(product)
    if product_type.lower() in ['bourbon','whiskey','scotch','other']:
        return True, product_type
    return False, product_type

def get_alcohol_type(product):
    # Lowercase all relevant fields for easier matching
    fields = [
        (product.get('product_type') or '').lower(),
        (product.get('title') or '').lower(),
        (product.get('body_html') or '').lower(),
        ' '.join(product.get('tags', [])).lower()
    ]
    text = ' '.join(fields)

    if 'bourbon' in text:
        return 'Bourbon'
    if 'scotch' in text:
        return 'Scotch'
    if 'whiskey' in text or 'whisky' in text:
        return 'Whiskey'
    if 'rye' in text:
        return 'Whiskey'
    if 'vodka' in text:
        return 'Vodka'
    if 'tequila' in text:
        return 'Tequila'
    if 'mezcal' in text:
        return 'Mezcal'
    if 'rum' in text:
        return 'Rum'
    if 'cognac' in text:
        return 'Cognac'
    if 'champagne' in text or 'sparkling' in text:
        return 'Champagne/Sparkling Wine'
    if any(w in text for w in ['wine', 'chardonnay', 'cabernet', 'sauvignon', 'merlot', 'rosé', 'pinot', 'malbec', 'blend', 'riesling']):
        return 'Wine'
    if 'liqueur' in text or 'aperitif' in text or 'cordial' in text:
        return 'Liqueur/Aperitif'
    if 'sake' in text:
        return 'Sake'
    if 'gin' in text:
        return 'Gin'
    if any(w in text for w in ['rtd', 'ready to drink', 'cocktail', 'margarita', 'martini', 'old fashioned', 'negroni', 'manhattan', 'long island', 'pina colada']):
        return 'RTD/Cocktail'
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
    event_type: 'available', 'unavailable', or 'new'
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
    conn.commit()
    conn.close()

def load_product_availability(input_url):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, available FROM products WHERE input_url = ?', (input_url,))
    rows = c.fetchall()
    conn.close()
    return {id_: bool(available) for id_, available in rows}

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
        c.execute('''INSERT INTO products (id, handle, title, available, last_seen, published_at, created_at, updated_at, vendor, url, price, original_json, input_url, alcohol_type)
                     VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

def Main(url):
    logger.debug(f'Entering Main for url: {url}')
    # Initialize DB
    init_db()
    # Load product availability from DB for this input_url
    product_availability = load_product_availability(url)
    init_product_count = len(product_availability)
    logger.debug(f'{init_product_count} products loaded from DB for {url}')
    # Initial population of product_availability from getProducts (for new products)
    #current_products, _ = getProducts(url)
    #print(f'[Main][Thread-{threading.get_ident()}][DEBUG] Returned {len(current_products)} products')
    logger.debug(f'DB Returned {len(product_availability)} products availablity')
    proxies = getProxies()

    logger.debug('Webhook loaded')   
    loop_exceptions = 0 

    while True:
        try:
            # Monitors website for new products
            if len(proxies) > 0:
                # Grabs a random proxy from proxy list
                try:
                    x = randint(0, (len(proxies) - 1))
                    proxy = proxies[x]
                    proxy_dict = {'http': ('http://{}'.format(proxy)), 'https': ('https://{}'.format(proxy))}
                    logger.debug(f'Using proxy: {proxy}')
                except Exception as e:
                    logger.error(f'No proxies available. Exception: {e}')
                    pass
                try:
                    url_1 = (url + URL_PATH)
                    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.131 Safari/537.36'}
                    logger.debug('Requesting products with proxy')
                    webpage = requests.get(url_1, headers=headers, proxies=proxy_dict)
                    products = json.loads((webpage.text))['products']
                    logger.debug('Products fetched with proxy')
                except Exception as e:
                    logger.error(f'Proxies banned. Sleeping for 3 minutes... Exception: {e}')
                    time.sleep(180)
                    continue
            else:
                try:
                    url_1 = (url + URL_PATH)
                    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.131 Safari/537.36'}
                    logger.debug('Requesting products with localhost')
                    webpage = requests.get(url_1, headers=headers)
                    products = json.loads((webpage.text))['products']
                    logger.debug(f'{len(products)} Products fetched with localhost')
                except Exception as e:
                    logger.error(f'Local host banned. Sleeping for 3 minutes... Exception: {e}')
                    time.sleep(180)
                    continue

            # Filter products using is_interesting before tracking for availability and new product detection in Main.
            interesting_products = [p for p in products if is_interesting(p)[0]]
            new_products = []
            logger.debug(f'{len(interesting_products)} interesting products fetched with localhost')
            # --- Check for product availability changes ---
            for product in interesting_products:
                id_val = product.get('id')
                handle = product.get('handle', '')
                title = product.get('title', '')
                
                # If variants exist, check the first one for availability, else False
                available = False
                if product.get('variants') and len(product['variants']) > 0:
                    available = product['variants'][0].get('available', False)
                prev_available = product_availability.get(id_val)
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
                    # Only Send a webhook notification if DB has been initialized
                    if init_product_count > 0:
                        send_webhook_notification(product, url, 'new')
                # Update the tracked availability in memory and DB
                product_availability[id_val] = available
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

db_lock = threading.Lock()