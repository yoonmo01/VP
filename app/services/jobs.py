# app/services/jobs.py
import threading, time, uuid


class _Jobs:

    def __init__(self):
        self._lock = threading.Lock()
        self._store = {}  # job_id -> dict

    def create(self):
        job_id = str(uuid.uuid4())
        with self._lock:
            self._store[job_id] = {
                "status": "running",
                "created_at": time.time(),
                "preview": None,  # planner 프리뷰
                "result": None,
                "error": None,
            }
        return job_id

    def update(self, job_id, **data):
        with self._lock:
            if job_id in self._store:
                self._store[job_id].update(data)

    def done(self, job_id, result):
        self.update(job_id, status="done", result=result)

    def error(self, job_id, error):
        self.update(job_id, status="error", error=str(error))

    def get(self, job_id):
        with self._lock:
            return self._store.get(job_id, {"status": "not_found"})


jobs = _Jobs()
