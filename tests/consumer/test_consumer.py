import mock
import unittest


from demo.consumer.consumer import Consumer


class TestConsumer(unittest.TestCase):
    def _get_redis_mocks(self):
        redis_mock = mock.MagicMock()
        pubsub_mock = mock.MagicMock()

        redis_mock.pubsub.return_value = pubsub_mock

        pubsub_mock.get_message.side_effect = KeyboardInterrupt("Unit tests pressed CTRL+C")

        return redis_mock, pubsub_mock

    @mock.patch('demo.consumer.consumer.get_redis_client')
    def test_consumer_register(self, mocked_get_redis_client):
        mocked_redis, _ = self._get_redis_mocks()
        mocked_get_redis_client.return_value = mocked_redis

        consumer = Consumer("id_1", None)

        with self.assertRaises(KeyboardInterrupt):
            consumer.run()

        mocked_redis.lpush.assert_called_once_with("consumer:ids", "id_1")
        mocked_redis.lrem.assert_called_once_with("consumer:ids", value="id_1", count=0)

    @mock.patch('demo.consumer.consumer.get_redis_client')
    def test_consumer_subscribe(self, mocked_get_redis_client):
        mocked_redis, mocked_pubsub = self._get_redis_mocks()
        mocked_get_redis_client.return_value = mocked_redis

        consumer = Consumer("id_1", None)

        with self.assertRaises(KeyboardInterrupt):
            consumer.run()

        mocked_pubsub.subscribe.assert_called_once_with("messages:published")
        mocked_pubsub.close.assert_called_once()
