from typing import Tuple, List
from urllib.parse import ParseResult, urljoin, urlparse

from aiohttp.client_reqrep import ClientResponse
from bs4 import BeautifulSoup

from webzilla.spider.queue import RequestQueue


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
