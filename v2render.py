from celery import Celery

app = Celery('tasks', backend='rpc://guest@localhost//', broker='pyamqp://guest@localhost//')


@app.task
def add(x, y):
    return x + y
