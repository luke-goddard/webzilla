from urllib.parse import urlparse
import pytest

from aiohttp import web
from aiohttp.test_utils import make_mocked_request
from webzilla.spider.request_handler import RequestHandler

from webzilla.spider.response_handler import ResponseHandler
from webzilla.spider.queue import RequestQueue


@pytest.fixture
async def resp_handler():
    q = RequestQueue()
    return ResponseHandler(q)


async def web_handler(request):
    return web.Response(body=request.app["value"].encode("utf-8"))


@pytest.fixture
def cli(loop, aiohttp_client):
    app = web.Application()
    app.router.add_get("/", web_handler)
    return loop.run_until_complete(aiohttp_client(app))


async def test_request_handler_with_hrefs(resp_handler: ResponseHandler, cli):
    example_url = "http://www.example.com"
    example_href = b'<a href="http://www.example.com"></a>'
    cli.server.app["value"] = example_href.decode("utf-8")
    req_handler = RequestHandler(client=cli)
    resp = await req_handler.handle(urlparse("/"))
    await resp_handler.handle(urlparse("/"), resp)

    assert len(resp_handler.responses) == 1
    assert await resp_handler.queue.get_url() == urlparse(example_url)
