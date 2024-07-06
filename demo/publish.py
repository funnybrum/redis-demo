import os
import random
import time
import uuid

from datetime import datetime, timedelta

import redis

# Redis connection details (modify host and port if needed)
REDIS_HOST = os.getenv("REDIS_HOST", default="localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", default=6379))

TARGET_DURATION = timedelta(seconds=int(os.getenv("TARGET_DURATION", default=60)))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", default=1000))


def publisher():
    try:
        connection = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)
    except redis.ConnectionError:
        print("Error: Failed to connect to Redis server")
        exit(1)

    start_time = datetime.now()
    total_messages = 0

    try:
        while datetime.now() - start_time < TARGET_DURATION:
            p = connection.pipeline()
            for _ in range(BATCH_SIZE):
                p.publish(
                    "messages:published", f'{{"message_id": "{str(uuid.uuid4())}"}}'
                )
            p.execute()
            total_messages += BATCH_SIZE
            time.sleep(random.uniform(0.1, 0.5))
    except Exception as e:
        print(f"Error: {e}")
    finally:
        print(f"Total messages published: {total_messages}")


if __name__ == "__main__":
    publisher()
