from asyncio.queues import QueueEmpty
from asyncio import sleep, Queue, Task

from typing import List, Optional
from urllib.parse import ParseResult


class RequestQueue:

    """
    Simple FIFO Queue system used to schedule what URL need
    processesing next

    Attributes:
        _task: List[Task]: A list of async tasks
    """

    def __init__(self, scope_hostname_restrict=True):
        self._scope_hostname_restrict = scope_hostname_restrict
        self._queue: Queue[ParseResult] = Queue()
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
