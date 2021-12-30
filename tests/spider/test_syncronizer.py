import pytest

from webzilla.spider.syncronizer import AsyncSpiderSyncronizer


@pytest.mark.parametrize("test_input", [(-10,), ("test",), ("0",), (0,), (1.2,)])
def test_sync_invalid_workers(test_input):
    with pytest.raises(AttributeError):
        AsyncSpiderSyncronizer(test_input)


def test_sync_waiting_for_response():
    sync = AsyncSpiderSyncronizer(10)
    assert not sync.workers_waiting_for_response()

    sync.sending_request(1)
    assert sync.workers_waiting_for_response()

    sync.finished_request(1)
    assert not sync.workers_waiting_for_response()
