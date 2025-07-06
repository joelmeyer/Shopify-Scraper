# Shopify-Scraper
A web crawler that monitors multiple shopify based websites in real time for new products &amp; restocks. 

Important
- Must use proxies if monitiring multiple websites to avoid bans
- Make sure shopify websites /products.json isn't blocked
- Set proxies, discord webhook, & websites in a .env file (see exampleenv.txt)

Required Modules
- requests
- Json
- threading
- random
- time
- datetime
- dhooks
- python-dotenv

Example run command
- docker run --env-file .env -v $(pwd)/data:/app/data -it shopifyscraper
