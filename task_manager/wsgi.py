"""WSGI entry point; the durable worker runs as a separate process."""
import os
from pathlib import Path
from task_manager.service import Application, Store

application=Application(Store(Path(os.environ.get('HH520_DATABASE','runtime/tasks.sqlite3'))),os.environ.get('HH520_GATEWAY_TOKEN',''))
