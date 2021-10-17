import asyncio
from asyncio.queues import QueueEmpty
from asyncio.tasks import Task, sleep
import logging
from typing import Any, List, Optional, Protocol, Set, Union
from urllib.parse import ParseResult, urljoin, urlparse

from aiohttp import ClientSession
import aiohttp
from tqdm import tqdm
from aiohttp.client_exceptions import InvalidURL
from aiohttp.connector import TCPConnector

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class SkipUrlException(Exception):
    pass


class RequestHandlerProtocol(Protocol):
    async def handle_request(self, url: ParseResult):
        pass


class AsyncRequestHandlerMixin(RequestHandlerProtocol):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__()

    async def handle_request(self, url: ParseResult):
        return await self._client.get(url.geturl(), ssl=False)

    async def __aenter__(self):
        con = TCPConnector(limit=50)
        self._client = ClientSession(connector=con)
        return self

    async def __aexit__(self, exc_type, exc_value, exc_tb):
        await self._client.close()

    def __await__(self):
        return self.__aenter__().__await__()


class VaultMixin:
    unique_vault: bool
    _vault: List[Any]
    _unique_vault: Set[Any]

    def add_to_vault(self, element):
        if self.unique_vault:
            self._unique_vault.add(element)
        else:
            self._vault.append(element)

    def dump_vault(self) -> Union[List[Any], Set[Any]]:
        if self.unique_vault:
            return self._unique_vault
        return self._vault


class QueueMixin:

    _task: List[Task]

    def __init__(self, max_queue_size=100, *args, **kwargs):
        self._queue: asyncio.Queue[ParseResult] = asyncio.Queue(maxsize=max_queue_size)
        self._seen_urls = set()

    def _filter_tasks(self):
        self._tasks = list(filter(lambda t: not t.done(), self._tasks))
        return len(self._tasks)

    async def _get_next_url(self) -> Optional[ParseResult]:
        try:
            return self._queue.get_nowait()
        except (QueueEmpty, Exception):
            num_active_tasks = self._filter_tasks()
            if num_active_tasks == 0:
                return None
            await sleep(0.1)
            return await self._get_next_url()

    async def _push_url(self, abs_url: ParseResult):
        if abs_url in self._seen_urls:
            return

        self._seen_urls.add(abs_url)
        return await self._queue.put(abs_url)


class _Spider(VaultMixin, QueueMixin, AsyncRequestHandlerMixin):

    unique_vault = True

    def __init__(
        self, url: str, restrict_scope_to_seed_hostname, *args, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        self.restrict_scope_to_seed_hostname = restrict_scope_to_seed_hostname
        self.seed_url: ParseResult = urlparse(url)
        self._tasks: List[Task] = []

    async def handle_response(self, url, response):
        text = await response.read()
        soup = BeautifulSoup(text, "html.parser")

        anchors = soup.find_all(href=True)
        hrefs = [anchor.get("href") for anchor in anchors]

        for link in hrefs:
            abs_url = self.get_abs_url(link, url)
            if abs_url.scheme in ["http", "https"]:
                await self._push_url(abs_url)

    async def _handle_response(self, url, response):
        try:
            self.handle_response(url, response)
        except Exception as e:
            logger.error(e)
            logger.exception(e)
            raise e

    async def pre_request(self, url: ParseResult):
        if (
            self.restrict_scope_to_seed_hostname
            and url.hostname != self.seed_url.hostname
        ):
            raise SkipUrlException

    async def crawl(self):
        await self._push_url(self.seed_url)

        completed = 0
        with tqdm(
            total=1, unit="requests", desc="Crawling " + self.seed_url.hostname
        ) as pbar:
            while (next_url := await self._get_next_url()) is not None:
                task_response = asyncio.create_task(
                    self._request_lifecycle(next_url, self._queue)
                )
                self._tasks.append(task_response)
                yield next_url, task_response
                tqdm.write(next_url.geturl())
                pbar.update(1)
                completed += 1
                pbar.total = self._queue.qsize() - completed

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

    def get_abs_url(self, new_url: str, base_url: ParseResult) -> ParseResult:
        parsed_url = urlparse((new_url))
        if not bool(parsed_url.netloc):
            new_url = urljoin(base_url.geturl(), new_url)
            return urlparse((new_url))

        return parsed_url


class AsyncSpider(_Spider, AsyncRequestHandlerMixin):
    pass


if __name__ == "__main__":

    async def start(url):
        async with AsyncSpider(
            url, max_queue_size=200, restrict_scope_to_seed_hostname=True
        ) as spider:
            async for url, response in spider.crawl():
                pass

    import sys

    try:
        logging.basicConfig(level=logging.ERROR)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(start(sys.argv[1]))
        print("Completed")
    except KeyboardInterrupt:
        print("Finishing early")
