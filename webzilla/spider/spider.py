"""
WEBZILLA - A delightfull async libary for web pentesting stuff

File: spider.py
Project: webzilla
File Created: Saturday, 16th October 2021 5:43:06 pm
Author: Luke Goddard
Copyright 2021 Luke Goddard



Example:

    import asyncio
    from webzilla.spider import AsyncSpider

    async def start(url):
        async with AsyncSpider(url) as spider:
            async for url, response in spider.crawl():
                print(url.geturl())
                print(response.status)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(start(sys.argv[1]))
"""

import asyncio
import logging

from typing import AsyncGenerator, Optional, Tuple
from asyncio.tasks import Task
from urllib.parse import ParseResult, urlparse

import aiohttp
from aiohttp import ClientSession
from aiohttp.client_reqrep import ClientResponse

from webzilla.spider.queue import RequestQueue
from webzilla.spider.syncronizer import AsyncSpiderSyncronizer
from webzilla.spider.request_handler import RequestHandler
from webzilla.spider.response_handler import ResponseHandler
from webzilla.spider.exceptions import SkipUrlException

logger = logging.getLogger(__name__)


class AsyncSpider:

    """Async Spider"""

    def __init__(
        self,
        url: str,
        scope_hostname_restrict=True,
        workers=10,
        client: Optional[ClientSession] = None,
    ):
        self.workers = workers
        self.seed_url = urlparse(url)
        self.sync = AsyncSpiderSyncronizer(workers)
        self.queue = RequestQueue(scope_hostname_restrict=scope_hostname_restrict)
        self.request_handler = RequestHandler(client=client)
        self.response_handler = ResponseHandler(self.queue)
        self._active = False

    async def crawl(self):
        """
        Spawns the crawler workers and only finishes when the URL queue is exhausted or
        the stop method is called
        """
        await self.queue.push_url(self.seed_url)

        self._active = True
        workers = [
            asyncio.create_task(self._worker(x), name=f"spider-worker-{x}")
            for x in range(self.workers)
        ]

        for worker in workers:
            while not worker.done():
                if len(self.response_handler.responses) != 0:
                    yield self.response_handler.responses.pop()
                await asyncio.sleep(0.001)

        if self._active:
            await self.queue.join()

    def stop(self):
        """Kills the spider"""
        self._active = False

    async def _worker(self, worker_id: int):
        """Spawns the worker"""
        while self._active:
            next_url = await self.queue.get_url()
            response = None

            if next_url is None and self.sync.workers_waiting_for_response():
                # Don't kill yet because other requests can add to the queue
                await asyncio.sleep(0.01)
                continue

            if next_url is None and not self.sync.workers_waiting_for_response():
                # No other workers are making a request and the queue is empty
                # so we kill the worker
                break

            if next_url is None:
                continue
            
            response = await self._request_lifecycle(next_url, worker_id)

            if response is None:
                continue

            await self.response_handler.handle(next_url, response)
        return None

    async def _request_lifecycle(
        self, url: ParseResult, wid: int
    ) -> Optional[ClientResponse]:

        logger.debug(f"worker (id:{wid}): {url.geturl()}")
        self.sync.sending_request(wid)

        try:
            await self.request_handler.pre_request(url)
            response = await self.request_handler.handle(url)
            await self.response_handler.handle(url, response)
            return response
        except aiohttp.InvalidURL:
            logger.warning(f"Found dead url: {url}")
        except SkipUrlException as err:
            logger.debug(f"Skipping {url.geturl()} -> {err}")
        except (
            aiohttp.ClientConnectionError,
            aiohttp.ClientError,
            asyncio.TimeoutError,
        ) as err:
            logger.warning(f"{url.geturl()} -> {err.__class__}")
        finally:
            await self.queue.task_done()
            self.sync.finished_request(wid)

        return None

    async def __aenter__(self):
        """Opens a client session"""
        await self.request_handler.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_value, exc_tb):
        """Closes the client session"""
        await self.request_handler.__aexit__(exc_type, exc_value, exc_tb)

    def __await__(self):
        return self.request_handler.__aenter__().__await__()


SpiderFinding = AsyncGenerator[Tuple[ParseResult, Task[Optional[ClientResponse]]], None]


async def spawn_spider(url, workers=50, output=None):
    async with AsyncSpider(url, workers=workers) as spider:
        async for response, url in spider.crawl():
            logger.info(f"{response.status} -> {url}")
            if output:
                output.write(f"{url}\n")


def spawn_cmdline_spider(url, workers=50, output=None):
    fn = spawn_spider(url, workers=workers, output=output)
    asyncio.run(fn)
