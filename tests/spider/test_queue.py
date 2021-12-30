from urllib.parse import urlparse
import pytest

from webzilla.spider.queue import RequestQueue


def test_urls_in_queue_empty():
    q = RequestQueue()
    assert q.urls_in_queue == 0


@pytest.mark.asyncio
async def test_urls_in_queue_non_empty():
    q = RequestQueue()
    url = urlparse("http://www.test.com")
    await q.push_url(url)
    assert q.urls_in_queue == 1
    assert await q.get_url() == url


@pytest.mark.asyncio
async def test_multiple_urls():
    q = RequestQueue()

    url = urlparse("http://www.test.com")
    url2 = urlparse("http://www.testing.com")
    url3 = urlparse("http://www.testing.com/1")

    await q.push_url(url)
    await q.push_url(url2)

    assert q.urls_in_queue == 2
    assert await q.get_url() == url
    assert await q.get_url() == url2

    await q.push_url(url3)
    assert await q.get_url() == url3
    assert await q.get_url() is None


@pytest.mark.asyncio
async def test_push_duplicate_url():
    q = RequestQueue()
    url = urlparse("http://www.test.com")

    await q.push_url(url)
    assert q.urls_in_queue == 1
    await q.push_url(url)
    assert q.urls_in_queue == 1
