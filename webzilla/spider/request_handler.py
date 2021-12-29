from logging import getLogger 
from urllib.parse import ParseResult
from aiohttp import ClientSession
from aiohttp.client import ClientTimeout
from aiohttp.client_reqrep import ClientResponse
from aiohttp.connector import TCPConnector

from webzilla.spider.exceptions import SkipUrlException

logger = getLogger(__name__)

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
