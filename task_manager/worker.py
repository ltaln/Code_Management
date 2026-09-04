import os
from pathlib import Path
from task_manager.service import Store, Worker

if __name__=='__main__':
    worker=Worker(Store(Path(os.environ.get('HH520_DATABASE','runtime/tasks.sqlite3'))))
    try:
        worker.run()
    except KeyboardInterrupt:
        worker.stop.set()
