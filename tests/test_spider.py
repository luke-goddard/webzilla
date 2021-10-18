import aiohttp
from aiohttp.client_reqrep import ClientResponse
import pytest
from urllib.parse import ParseResult, urlparse

from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from webzilla.spider import (
    AsyncRequestHandlerMixin,
    AsyncSpider,
    QueueMixin,
    SkipUrlException,
    get_abs_url,
)


###########################################################################
################################# ABS_URL #################################
###########################################################################


@pytest.mark.parametrize(
    "base_url,parsed_url,expected",
    [
        (
            "http://www.test.com/1",
            urlparse("http://www.test.com"),
            "http://www.test.com/1",
        ),
        (
            "/1",
            urlparse("http://www.test.com"),
            "http://www.test.com/1",
        ),
        (
            "/1",
            urlparse("http://www.test.com/1"),
            "http://www.test.com/1",
        ),
        (
            "/1&id=1",
            urlparse("http://www.test.com/1"),
            "http://www.test.com/1&id=1",
        ),
        (
            "/1&id=1",
            urlparse("http://www.test.com/1"),
            "http://www.test.com/1&id=1",
        ),
    ],
)
def test_abs_url(base_url, parsed_url, expected):
    abs_url = get_abs_url(base_url, parsed_url)
    assert abs_url.geturl() == expected


def test_abs_url_invalid_schema():
    with pytest.raises(SkipUrlException):
        get_abs_url("test", urlparse("file://www.foobar.com"))


###########################################################################
########################## ASYNC REQUEST HANDLER ##########################
###########################################################################


@pytest.mark.asyncio
async def test_request_handler_context():
    rh = AsyncRequestHandlerMixin()
    async with rh:
        assert not rh._client.closed
    assert rh._client.closed


###########################################################################
############################# TEST QUEUE MIXIN ############################
###########################################################################


@pytest.mark.asyncio
async def test_queue_mixin():
    url = urlparse("http://test.com")
    q = QueueMixin(max_queue_size=10)
    q._tasks = []

    # Push item to queue
    assert q._queue.maxsize == 10
    assert q.urls_in_queue == 0
    await q.push_url(url)

    # get item from queue
    assert q.urls_in_queue == 1
    assert url == await q.get_url()
    assert q.urls_in_queue == 0

    # handle empty queue
    assert await q.get_url() is None


###########################################################################
############################ TEST ASYNC SPIDER ############################
###########################################################################


async def test_async_spider(aiohttp_raw_server, aiohttp_client):
    resp_data = "<a href='/1'/>"

    async def handler(request):
        return web.Response(text=resp_data)

    raw_server = await aiohttp_raw_server(handler)
    client = await aiohttp_client(raw_server)

    count = 0
    async with AsyncSpider("/") as spider:
        await spider.set_client(client)
        async for url, task_response in spider.crawl():
            response = await task_response
            assert response is not None
            assert url
            count += 1

    assert count == 2
