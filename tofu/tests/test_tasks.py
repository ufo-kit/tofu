import time
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

from tofu import tasks


class FakeTask:
    def set_properties(self, **kwargs):
        self.properties = kwargs


class ConcurrentCallDetector:
    def __init__(self):
        self.active = 0
        self.maximum_active = 0
        self.lock = Lock()

    def get_task(self, name):
        with self.lock:
            self.active += 1
            self.maximum_active = max(self.maximum_active, self.active)

        time.sleep(0.01)

        with self.lock:
            self.active -= 1

        return FakeTask()


def test_get_task_serializes_plugin_manager_access(monkeypatch):
    manager = ConcurrentCallDetector()
    monkeypatch.setattr(tasks, 'PLUGIN_MANAGER', manager)

    with ThreadPoolExecutor(max_workers=8) as pool:
        created = list(pool.map(lambda _: tasks.get_task('task', value=1), range(8)))

    assert manager.maximum_active == 1
    assert all(task.properties == {'value': 1} for task in created)
