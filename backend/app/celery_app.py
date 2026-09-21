from celery import Celery

from app.config import settings


def _broker_url() -> str:
    """Celery refuses a `rediss://` URL that doesn't say what to do about certificates —
    `ValueError: A rediss:// URL must have parameter ssl_cert_reqs`. Hosted Redis (Upstash, and
    therefore Fly's Redis) is TLS-only, so a deploy hits this the moment the worker starts.

    start.sh backgrounds the worker, so that failure is silent: the API keeps accepting /learn
    requests and enqueuing work that nothing ever consumes, and the UI just waits forever.
    Appending the parameter here rather than requiring it in the env var means one less way for
    the deploy to look healthy while doing nothing.
    """
    url = settings.redis_url
    if url.startswith("rediss://") and "ssl_cert_reqs" not in url:
        return f"{url}{'&' if '?' in url else '?'}ssl_cert_reqs=required"
    return url


celery_app = Celery("parallax", broker=_broker_url(), backend=_broker_url())
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]

# Import so Celery registers the task on worker startup.
import app.tasks  # noqa: E402,F401
