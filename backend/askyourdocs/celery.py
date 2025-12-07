import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "askyourdocs.settings")

app = Celery("askyourdocs")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
# optional dev defaults
app.conf.update(task_track_started=True, task_time_limit=600)
