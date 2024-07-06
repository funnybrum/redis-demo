import os

from redis.client import Redis
from redis.backoff import ExponentialBackoff
from redis.retry import Retry

REDIS_HOST = os.getenv("REDIS_HOST", default="localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", default=6379))
LOGLEVEL = os.environ.get('LOGLEVEL', 'INFO').upper()


def get_redis_client() -> Redis:
    """
    Get a Redis client. Client is preconfigured based on the 'REDIS_HOST' and 'REDIS_PORT' environment variables.

    :returns: A Redis client.
    """
    return Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        retry=Retry(ExponentialBackoff(), 3),
        retry_on_error=[ConnectionError, TimeoutError],
        decode_responses=True,
    )
