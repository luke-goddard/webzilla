from urllib.parse import urlparse
import pytest
from aiohttp import web

from webzilla.spider.request_handler import RequestHandler


async def previous(request):
    return web.Response(body=request.app["value"].encode("utf-8"))


@pytest.fixture
def cli(loop, aiohttp_client):
    app = web.Application()
    app.router.add_get("/", previous)
    return loop.run_until_complete(aiohttp_client(app))


async def test_get_value(cli):
    cli.server.app["value"] = "Hello"
    handler = RequestHandler(client=cli)
    url = urlparse("/")
    response = await handler.handle(url)
    assert await response.text() == "Hello"
