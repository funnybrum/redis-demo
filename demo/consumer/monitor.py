import logging
import os
import time

from .common import get_redis_client

LOGLEVEL = os.environ.get('LOGLEVEL', 'INFO').upper()
MONITORING_INTERVAL = float(os.environ.get('MONITORING_INTERVAL', default=3))
OUTPUT_STREAM = os.getenv("OUTPUT_STREAM", default="messages:processed")

logger = logging.getLogger(__name__)
logging.basicConfig(level=LOGLEVEL)


def run(monitor_id: str) -> None:
    """
    Run a monitor. The monitor is responsible for printing statistics for the message consumption process on regular
    intervals.

    :param monitor_id: ID of the monitor process.
    """
    logging.debug(f"[{monitor_id}] Starting up.")
    client = get_redis_client()
    last_report_ts = 0
    last_stream_size = 0

    while True:
        now = time.time()
        if now > last_report_ts + MONITORING_INTERVAL:
            new_stream_size = client.xlen(OUTPUT_STREAM)
            if last_report_ts > 0:
                # Calculate the average number of messages processed in the last monitoring interval.
                messages_per_second = (new_stream_size - last_stream_size) / MONITORING_INTERVAL
                messages_per_second = round(messages_per_second)
                logger.info(
                    f"[monitor {monitor_id}] Processing {messages_per_second} messages per second. Total processed"
                    f" messages are {new_stream_size}")
            last_report_ts = now
            last_stream_size = new_stream_size
        else:
            time.sleep(0.1)
