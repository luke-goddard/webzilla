class AsyncSpiderSyncronizer:
    def __init__(self, workers: int):
        self.status = self._init_list(workers)
    
    def _init_list(self, workers: int):
        if not isinstance(workers, int) or workers <= 0:
            raise AttributeError('Workers must be a positive integer')

        return [False] * workers

    def sending_request(self, worker: int):
        self.status[worker] = True

    def finished_request(self, worker: int):
        self.status[worker] = False

    def workers_waiting_for_response(self):
        return any(self.status)
