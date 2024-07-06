import json
import logging
import os
import time
import types

import redis

from .common import get_redis_client

INPUT_CHANNEL = os.getenv("INPUT_CHANNEL", default="messages:published")
OUTPUT_STREAM = os.getenv("OUTPUT_STREAM", default="messages:processed")
LOGLEVEL = os.environ.get('LOGLEVEL', 'INFO').upper()
PROCESSING_BATCH_SIZE = int(os.environ.get('PROCESSING_BATCH_SIZE', 100))
CONSUMERS_LIST = os.environ.get("CONSUMERS_LIST", default="consumer:ids")

logging.basicConfig(level=LOGLEVEL)
logger = logging.getLogger(__name__)


class Consumer(object):
    """
    A Redis channel consumer.

    The consumer reads messages from the channel, process them and publishes them to a Redis stream. Each message is
    consumed at most once.
    """
    def __init__(self, consumer_id: str, message_processor: types.FunctionType):
        self._consumer_id = consumer_id
        self._message_processor = message_processor
        self._client = get_redis_client()
        self._pubsub = None
        self._messages = []

    def _acquire_locks(self) -> list[int]:
        """
        Attempt to acquire locks for publishing the messages. Locks are used to prevent duplicate message
        processing.

        :return A list of message indexes that we've managed to acquire the locks for.
        """
        message_ids = [message["message_id"] for message in self._messages]
        lock_pipeline = self._client.pipeline()
        for message_id in message_ids:
            lock_id = f"lock-{message_id}"
            lock_pipeline.set(lock_id, value=self._consumer_id, ex=60, nx=True)
            lock_pipeline.get(lock_id)
        results = lock_pipeline.execute()
        get_results = results[1::2]

        # A lock is successful if the value for that key is equal to our consumer ID.
        acquired_locks = [idx for idx, get_result in enumerate(get_results) if get_result == self._consumer_id]
        return acquired_locks

    def _publish_message(self, locked_messages: list[int]) -> None:
        """
        Publish the messages.

        :param locked_messages: List of indexes for the messages that should be published.
        """
        publish_pipeline = self._client.pipeline()
        for idx in locked_messages:
            payload = self._messages[idx]
            publish_pipeline.xadd(OUTPUT_STREAM, payload)
        publish_pipeline.execute()

    def _process_messages(self) -> None:
        """
        Attempt to acquire a "lock" for each of the messages. If successful - publish the messages to the destination
        stream.
        """
        logger.debug(f"[{self._consumer_id}] Processing {len(self._messages)} messages.")
        locked_messages = self._acquire_locks()

        # Process only the messages that we've managed to lock.
        for idx in locked_messages:
            self._message_processor(self._messages[idx])
            self._messages[idx]["consumer_id"] = self._consumer_id

        logger.debug(f"[{self._consumer_id}] Stream publishing lock acquired for {len(locked_messages)} messages.")

        if locked_messages:
            self._publish_message(locked_messages)
            logger.debug(f"[{self._consumer_id}] Messages published to target stream.")

        self._messages = []

    def _subscribe(self) -> None:
        self._pubsub = self._client.pubsub(ignore_subscribe_messages=True)
        self._pubsub.subscribe(INPUT_CHANNEL)
        self._client.lpush(CONSUMERS_LIST, self._consumer_id)
        logger.debug(f"[{self._consumer_id}] Subscribed.")

    def _unsubscribe(self) -> None:
        self._pubsub.close()
        self._client.lrem(CONSUMERS_LIST, value=self._consumer_id, count=0)
        logger.debug(f"[{self._consumer_id}] Unsubscribed.")

    def run(self) -> None:
        """
        Run the consumer.
        """
        logger.debug(f"[{self._consumer_id}] Starting up.")
        self._subscribe()
        try:
            while True:
                try:
                    message = self._pubsub.get_message()
                    if message:
                        self._messages.append(json.loads(message['data']))
                        if len(self._messages) >= PROCESSING_BATCH_SIZE:
                            self._process_messages()
                    else:
                        if self._messages:
                            self._process_messages()

                        # Note: Reduce the sleep to reduce the consumption latency. Low values will increase CPU usage
                        # during periods with no messages.
                        time.sleep(0.1)
                except redis.ConnectionError:
                    self._unsubscribe()
                    time.sleep(3)
                    self._subscribe()
        finally:
            self._unsubscribe()
