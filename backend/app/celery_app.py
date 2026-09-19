from celery import Celery

from app.config import settings

celery_app = Celery("mentra", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]

# Import so Celery registers the task on worker startup.
import app.tasks  # noqa: E402,F401
