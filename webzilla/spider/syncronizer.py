class AsyncSpiderSyncronizer:
    def __init__(self, workers: int):
        self.status = [False for x in range(workers)]

    def sending_request(self, worker: int):
        self.status[worker] = True

    def finished_request(self, worker: int):
        self.status[worker] = False

    def workers_waiting_for_response(self):
        return any(self.status)
