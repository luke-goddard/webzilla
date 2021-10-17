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
                print(url.tourl())
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
from aiohttp.client_reqrep import ClientResponse
from aiohttp.connector import TCPConnector
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

SpiderFinding = AsyncGenerator[Tuple[ParseResult, Task[ClientResponse]], None]


class SkipUrlException(Exception):
    """
    This exception is raised when a user defined condition is
    raised that tells the crawler not to crawl the current URL
    """


def get_abs_url(new_url: str, base_url: ParseResult) -> ParseResult:
    """Helper function to make sure that new urls are absolute

    Args:
        new_url (str): The new URL
        base_url (ParseResult): The base URL

    Example:
        get_abs_url('/hi', urlparse('http://www.test.com')).geturl()
        > 'http://www.test.com/hi'

    Returns:
        ParseResult: [description]
    """
    parsed_url = urlparse((new_url))
    if not bool(parsed_url.netloc):
        new_url = urljoin(base_url.geturl(), new_url)
        return urlparse((new_url))

    return parsed_url


class AsyncRequestHandlerMixin:

    """Concreate implementation of the request handler protocol.
    This Mixin uses a context manager to create an aiohttp Client
    Session. This ClientSession is reused. for future requests
    """

    async def handle_request(self, url: ParseResult) -> ClientResponse:
        """Acutally sends the request to the server
        Args: url (ParseResult): The URL to send the HTTP request to
        Returns: ClientResponse: The HTTP response recived from the server
        """
        return await self._client.get(url.geturl(), ssl=False)

    async def __aenter__(self):
        """Opens a client session """
        con = TCPConnector(limit=50)
        self._client = ClientSession(connector=con)
        return self

    async def __aexit__(self, exc_type, exc_value, exc_tb):
        """Closes the client session """
        await self._client.close()

    def __await__(self):
        return self.__aenter__().__await__()


class QueueMixin:

    """
    Simple FIFO Queue system used to schedule what URL need
    processesing next

    Attributes:
        _task: List[Task]: A list of async tasks
    """

    _tasks: List[Task]

    def __init__(self, max_queue_size=100, *args, **kwargs):
        """
        Args:
            max_queue_size (int, optional): Maximum number of requests in queue
                                              before adding to queue blocks.
                                              Defaults to 100.
        """
        self._queue: asyncio.Queue[ParseResult] = asyncio.Queue(maxsize=max_queue_size)
        self._seen_urls = set()

    def _filter_tasks(self) -> int:
        """
        Filters all of the tasks in the task list, and removed the tasks
        that have allready completed.
        Returns:
            [int]: The number of tasks that have not been completed yet
        """
        self._tasks = list(filter(lambda t: not t.done(), self._tasks))
        return len(self._tasks)

    async def _get_next_url(self) -> Optional[ParseResult]:
        """Get's the next URL from the queue. If the queue is
        empty this function will block until all the tasks have
        finished.

        Returns:
            Optional[ParseResult]: The next url or None, if no work
            is left to be processed by the queue or the workers
        """
        try:
            return self._queue.get_nowait()
        except (QueueEmpty, Exception):
            num_active_tasks = self._filter_tasks()
            if num_active_tasks == 0:
                return None
            await sleep(0.1)
            return await self._get_next_url()

    async def _push_url(self, url: ParseResult) -> None:
        """Adds another URL to the queue if it's not been processed before
        Args:
            url (ParseResult): The absoulte url
        """
        if url in self._seen_urls:
            return

        self._seen_urls.add(url)
        await self._queue.put(url)


class AsyncSpider(QueueMixin, AsyncRequestHandlerMixin):

    unique_vault = True

    def __init__(self, url: str, restrict_scope_to_seed_hostname=True, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.restrict_scope_to_seed_hostname = restrict_scope_to_seed_hostname
        self.seed_url: ParseResult = urlparse(url)
        self._tasks: List[Task] = []

    async def handle_response(self, url, response) -> None:
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
            abs_url = get_abs_url(link, url)
            if abs_url.scheme in ["http", "https"]:
                await self._push_url(abs_url)

    async def _handle_response(self, url, response):
        """Handles the response but catches and logs errors"""
        try:
            self.handle_response(url, response)
        except Exception as e:
            logger.error(e)
            logger.exception(e)
            raise e

    async def pre_request(self, url: ParseResult):
        """Overideable method to do stuff before the request is handled"""

    async def _pre_request(self, url: ParseResult):
        if (
            self.restrict_scope_to_seed_hostname
            and url.hostname != self.seed_url.hostname
        ):
            raise SkipUrlException
        return self.pre_request(url)

    async def crawl(self) -> SpiderFinding:
        """Starts the crawling process and only ends when the queue is
        exhausted and when all the workers have finished handling the
        requests.

        Yields:
            Iterator[Tuple[ParseResult, ClientResponse]]: The parsed url and response
        """
        await self._push_url(self.seed_url)

        completed = 0
        while (next_url := await self._get_next_url()) is not None:

            task: Task[ClientResponse] = asyncio.create_task(
                self._request_lifecycle(next_url, self._queue)
            )
            self._tasks.append(task)
            yield next_url, task
            completed += 1

        await self._queue.join()

    async def _request_lifecycle(self, url: ParseResult, queue):
        try:
            await self.pre_request(url)
            response = await self.handle_request(url)
            await self.handle_response(url, response)
            return response
        except (aiohttp.ClientConnectionError, aiohttp.ClientError) as e:
            logger.warning(f"{url.geturl()} -> {e}")
        except SkipUrlException:
            pass
        finally:
            queue.task_done()
