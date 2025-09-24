import os

BOT_NAME = "scraper"
SPIDER_MODULES = ["scraper.spiders"]
NEWSPIDER_MODULE = "scraper.spiders"
ROBOTSTXT_OBEY = False

# asyncio reactor required by scrapy-playwright
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

ITEM_PIPELINES = {
    "scraper.pipelines.PostgresPipeline": 300
}

# Tunables from env
CONCURRENT_REQUESTS = int(os.getenv("SCRAPY_CONCURRENT_REQUESTS", "8"))
DOWNLOAD_DELAY = float(os.getenv("SCRAPY_DOWNLOAD_DELAY", "0.5"))
PLAYWRIGHT_BROWSER_TYPE = os.getenv("PLAYWRIGHT_BROWSER_TYPE", "chromium")
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = int(os.getenv("PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT", "30000"))

# Optional: block images/media for performance at handler level in spider
DOWNLOADER_MIDDLEWARES = {
    'scraper.middlewares.RotatingProxyMiddleware': 543,
    'scrapy_playwright.middleware.PlaywrightMiddleware': 800,
}
