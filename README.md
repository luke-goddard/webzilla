# Webzilla 

A async libary and cmdline tool for web pentesting stuff

# Spider/Crawler

```python
from webzilla import AsyncSpider

async def start(url):
    async with AsyncSpider(url) as spider:
        async for url, response in spider.crawl():
            print(url)

loop = asyncio.get_event_loop()
loop.run_until_complete(
    start("https://www.somesite.com")
)
```