import pytest
from urllib.parse import urlparse

from aiohttp import web

from webzilla.spider import (
    AsyncRequestHandlerMixin,
    AsyncSpider,
    QueueMixin,
)

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
    resp_data = "<a href='/1'>test</a>"

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
