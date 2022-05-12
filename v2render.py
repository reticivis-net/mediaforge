import typing

from billiard.einfo import ExceptionInfo
from celery import Celery, Task

app = Celery('tasks', backend='rpc://guest@localhost//', broker='pyamqp://guest@localhost//')


class CallbackTask(Task):
    def on_success(self, retval: typing.Any, task_id: str, args: tuple, kwargs: dict):
        pass

    def on_failure(self, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo: ExceptionInfo):
        pass


@app.task(base=CallbackTask)  # this does the trick
def add(x, y):
    return x + y
