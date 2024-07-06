import logging
import os
import time
import uuid

from multiprocessing import Process

from .consumer import Consumer
from .message_processor import message_processor
from .monitor import run as run_monitor

CONSUMERS_COUNT = int(os.getenv("CONSUMERS_COUNT", default=2))
LOGLEVEL = os.environ.get('LOGLEVEL', 'INFO').upper()


logging.basicConfig(level=LOGLEVEL)
logger = logging.getLogger(__name__)

_monitor_process: Process = None
_consumer_processes: list[Process] = []


def _verify_monitor_process() -> None:
    """
    Verify if the monitor process is running. If the process is not running - spawns a new monitoring process.
    """
    global _monitor_process
    if _monitor_process and _monitor_process.is_alive():
        # The monitor process is up and running
        return

    # Monitor process is not up and running
    logger.info("Starting a monitoring process")
    monitor_id = f"monitor-{uuid.uuid4()}"
    _monitor_process = Process(target=run_monitor, args=(monitor_id,))
    _monitor_process.start()


def _update_consumer_process_list() -> None:
    """
    Remove dead processes from the list of consumer processes.
    """
    global _consumer_processes
    _consumer_processes = [p for p in _consumer_processes if p.is_alive()]


def _launch_consumer_process() -> None:
    """
    Launch a new consumer process and add it to the list of consumer processes.
    """
    logger.info("Starting a consumer process")
    consumer_id = f"consumer-{uuid.uuid4()}"
    consumer = Consumer(consumer_id=consumer_id, message_processor=message_processor)
    consumer_process = Process(target=consumer.run)
    consumer_process.start()
    _consumer_processes.append(consumer_process)


def run() -> None:
    """
    Start a process for monitoring the consumers throughput and maintain the desired number of running consumers.
    """
    while True:
        _verify_monitor_process()
        _update_consumer_process_list()
        while len(_consumer_processes) < CONSUMERS_COUNT:
            _launch_consumer_process()
        time.sleep(1)
