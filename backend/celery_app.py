from celery import Celery
import os
import sys

# パス追加でダイレクト実行とパッケージ呼び出しの両方に対応
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from .config import settings
except ImportError:
    from config import settings

celery_app = Celery(
    "telesales_scoring",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Tokyo",
    enable_utc=True,
    task_track_started=True,
)

# タスクモジュールの自動登録（ルート起動・backend直下起動の両方に対応）
try:
    celery_app.autodiscover_tasks(["backend"], related_name="tasks", force=True)
except Exception:
    celery_app.autodiscover_tasks(["tasks"], force=True)
