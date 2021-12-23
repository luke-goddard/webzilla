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

from typing import AsyncGenerator, List, Optional, Tuple
from asyncio.queues import QueueEmpty
from asyncio.tasks import Task, sleep
from urllib.parse import ParseResult, urljoin, urlparse

import aiohttp
from aiohttp import ClientSession
from aiohttp.client import ClientTimeout
from aiohttp.client_reqrep import ClientResponse
from aiohttp.connector import TCPConnector
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

SpiderFinding = AsyncGenerator[Tuple[ParseResult, Task[Optional[ClientResponse]]], None]


class SkipUrlException(Exception):
    """
    This exception is raised when a user defined condition is
    raised that tells the crawler not to crawl the current URL
    """


class RequestHandler:

    """Concreate implementation of the request handler protocol.
    This Mixin uses a context manager to create an aiohttp Client
    Session. This ClientSession is reused. for future requests
    """

    def __init__(self, client: ClientSession = None):
        self._client = client

    async def set_client(self, client: ClientSession):
        """Used to make testing easier by injecting a mock client"""
        if self._client is not None:
            await self._client.close()

        self._client = client

    async def pre_request(self, url: ParseResult):
        """Overideable method to do stuff before the request is handled"""

    async def _pre_request(self, url: ParseResult):
        if url.scheme is None:
            raise SkipUrlException("No schema")
        return await self.pre_request(url)

    async def handle(self, url: ParseResult) -> ClientResponse:
        """Acutally sends the request to the server
        Args: url (ParseResult): The URL to send the HTTP request to
        Returns: ClientResponse: The HTTP response recived from the server
        """
        if self._client is None:
            raise AssertionError("Please use Spider as a context manager")

        if url.scheme is None:
            logger.debug("Schema is none")
            raise SkipUrlException("No Scheme")

        response = await self._client.get(url.geturl(), ssl=False)
        return response

    async def __aenter__(self):
        """Opens a client session"""
        if self._client is not None:
            return self

        timeout = ClientTimeout(total=5, connect=4, sock_connect=4, sock_read=4)
        con = TCPConnector(limit=1000)
        self._client = ClientSession(
            connector=con, timeout=timeout, cookies={"boop": "boop"}
        )
        return self

    async def __aexit__(self, exc_type, exc_value, exc_tb):
        """Closes the client session"""
        await self._client.close()

    def __await__(self):
        return self.__aenter__().__await__()


class RequestQueue:

    """
    Simple FIFO Queue system used to schedule what URL need
    processesing next

    Attributes:
        _task: List[Task]: A list of async tasks
    """

    def __init__(self, scope_hostname_restrict=True):
        self._scope_hostname_restrict = scope_hostname_restrict
        self._queue: asyncio.Queue[ParseResult] = asyncio.Queue()
        self._seen_urls = set()
        self._tasks: List[Task] = []

    @property
    def urls_in_queue(self) -> int:
        """The number of URL in the queue that have not been processed"""
        return self._queue.qsize()

    async def task_done(self):
        """Mark a task as being done"""
        return self._queue.task_done()

    async def join(self):
        """Join the queue"""
        return await self._queue.join()

    def filter_tasks(self) -> int:
        """
        Filters all of the tasks in the task list, and removed the tasks
        that have allready completed.
        Returns:
            [int]: The number of tasks that have not been completed yet
        """
        self._tasks = list(filter(lambda t: not t.done(), self._tasks))
        return len(self._tasks)

    async def get_url(self) -> Optional[ParseResult]:
        """Get's the next URL from the queue. If the queue is
        empty this function will block until all the tasks have
        finished.

        Returns:
            Optional[ParseResult]: The next url or None, if no work
            is left to be processed by the queue or the workers
        """
        try:
            return self._queue.get_nowait()
        except QueueEmpty:
            num_active_tasks = self.filter_tasks()
            if num_active_tasks == 0:
                return None
            await sleep(0.1)
            return await self.get_url()

    async def push_url(self, url: ParseResult) -> None:
        """Adds another URL to the queue if it's not been processed before
        Args:
            url (ParseResult): The absoulte url
        """
        if url in self._seen_urls:
            return

        self._seen_urls.add(url)
        self._queue.put_nowait(url)


class ResponseHandler:
    def __init__(self, queue: RequestQueue):
        self.queue = queue
        self.responses: List[Tuple[ClientResponse, str]] = []

    async def handle(self, url: ParseResult, response: ClientResponse) -> None:
        """Overidable method for doing things with the response.
        The default implementation just parses the HTML and find
        new URLs to add to the queue

        Args:
            url (ParsedResult): The url for the response
            response (ClientResponse): The HTTP resposne from the webserver

        Returns: None
        """
        text = await response.read()
        soup = BeautifulSoup(text, "html.parser")

        anchors = soup.find_all(href=True)
        hrefs = [anchor.get("href") for anchor in anchors]

        for link in hrefs:
            abs_url = urlparse(urljoin(url.geturl(), link))
            await self.queue.push_url(abs_url)

        self.responses.append((response, url.geturl()))


class AsyncSpider:

    """
    Async Spider
    """

    def __init__(
        self,
        url: str,
        scope_hostname_restrict=True,
        workers=10,
        client: Optional[ClientSession] = None,
    ):
        self.workers = workers
        self.seed_url = urlparse(url)
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
            asyncio.create_task(self._worker(), name=f"spider-worker-{x}")
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

    async def _worker(self):
        """Spawns the worker"""
        while self._active:
            next_url = await self.queue.get_url()

            if next_url is None:
                break

            response = await self._request_lifecycle(next_url)

            if response is None:
                continue

            await self.response_handler.handle(next_url, response)
        return None

    async def _request_lifecycle(self, url: ParseResult) -> Optional[ClientResponse]:
        try:
            await self.request_handler.pre_request(url)
            response = await self.request_handler.handle(url)
            await self.response_handler.handle(url, response)
            return response
        except (aiohttp.ClientConnectionError, aiohttp.ClientError) as err:
            logger.warning(f"{url.geturl()} -> {err}")
            return None
        except SkipUrlException as err:
            logger.debug(f"Skipping {url.geturl()} -> {err}")
            return None
        finally:
            await self.queue.task_done()

    async def __aenter__(self):
        """Opens a client session"""
        await self.request_handler.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_value, exc_tb):
        """Closes the client session"""
        await self.request_handler.__aexit__(exc_type, exc_value, exc_tb)

    def __await__(self):
        return self.request_handler.__aenter__().__await__()


async def _example_usage(url):
    async with AsyncSpider(url, workers=300) as spider:
        async for response, url in spider.crawl():
            logger.info(f"{response.status} -> {url}")


def spawn_cmdline_spider(url):
    asyncio.run(_example_usage(url))
