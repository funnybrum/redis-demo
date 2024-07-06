# Summary
Redis offers message broadcasting capabilities via the [Pub/Sub channels](
https://redis.io/docs/latest/develop/interact/pubsub/). TThe provided code demonstrates how these messages can be broadcast to multiple consumers.Messages are processed
and sent to a [stream](https://redis.io/docs/latest/develop/data-types/streams/). Each message is processed and sent to
the stream at most once.

The implementation is based on the provided [requirements](https://docs.google.com/document/d/1CbaXnYu11RQdnowVuTlBUliX3XvpgwqR3A3HRAAXdBY/edit?usp=sharing).

# Running the demo
## Running a local Redis instance
To be able to run the demo a Redis server is required. The simplest option is to run a local one using the following
command:

Prerequisite: [Docker Engine](https://docs.docker.com/engine/install/).
```
docker run -d --name redis-server -p 6379:6379 redis:latest
```

## Prepare the environment
The following commands will prepare and activate a virtual environment capable of running the demo. 
```
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## Running the consumers
The Pub/Sub demo requires the consumers to be up and running before the publisher is started. This can be done  with the
following commands.
```
export REDIS_HOST=localhost             # optional, default is 'localhost'
export CONSUMERS_COUNT=3                # optional, default is 2

. .venv/bin/activate
python3 ./demo/consume.py
```

The following environment variables can be used to customize consumers behavior.
 - `REDIS_HOST` specifies the host where the Redis server is running, default is 'localhost'.
 - `REDIS_PORT` specifies the port that the Redis server is listening to, default is 6379.
 - `CONSUMERS_COUNT` sets the desired number of consumer processes.
 - `PROCESSING_BATCH_SIZE` sets the desired batch size that messages will be processed at. Low number reduce latency, high number (100-1000) improve performance. Default is 100.
 - `LOGLEVEL` sets the desired log level. Default is INFO.
 - `INPUT_CHANNEL` sets the input channel that the consumers should listen to, default is messages:published.
 - `OUTPUT_STREAM` sets the output stream that processed messages should be published to, default is messages:processed.
 - `MONITORING_INTERVAL` sets the interval for printing the monitoring messages, default is 3.
 - `CONSUMERS_LIST` sets the Redis list that will contain all consumer IDs, default is 'consumer:ids'

## Running the publisher
The publisher publishes messages to a Redis channel. The process runs for a pre-defined period. Messages are published
in batches and there is a small delay (0.1 - 0.5 seconds) between publishing these batches.

To run the message publishing process execute the following command:
```
. .venv/bin/activate
python3 ./demo/publish.py
```

The following environment variables can be used to customize the publishing process:
 - `REDIS_HOST` specifies the host where the Redis server is running, default is 'localhost'.
 - `REDIS_PORT` specifies the port that the Redis server is listening to, default is 6379.
 - `TARGET_DURATION` specifies the number of seconds that the publisher should run for, default is 60.
 - `BATCH_SIZE` set number of messages that the producer will publish in each batch.

## Running the tests
The project tests can be executed with the following command:

```
. .venv/bin/activate
pip install -r test-requirements.txt
python3 -m unittest
```

Note: Tests are below the bare minimum. If high unit test coverage is required, more tests should be added.
Note 2: The implementation is not test friendly. It would be wise to refactor it for easier testing.
Note 3: Integration tests can easily be added using the [fakeredis](https://pypi.org/project/fakeredis/) library.

# Implementation notes

## Terminating the process
Consumption/publishing process can be terminated using CTRL+C. This can be improved by including a "kill switch" behind
a redis key or automated logic to terminate consumers if there is no message consumed in 60 seconds.

## Consumer IDs list
The mechanism used for keeping the consumer IDs in a Redis list has flaws:
 - If network connectivity is lost the consumer ID will remain in the list.
 - The `finally` blocked won't execute in all cases, i.e. a `kill -9` command.

This can be improved by replacing the Redis list with separate keys. Each consumer will publish a key with a predefined
common prefix and suffix containing its ID to indicate its presence. The keys will have short TTL defined on them.
Consumers are responsible for updating the TTL at regular intervals if they are still connected to the Redis server.

The above will require a simple logic to extract the list of active consumers. That logic can be incorporated as part of
the monitoring process and the list of consumers can be printed along with the message processing statistics.

## An approach for conditional guaranteed delivery
The implemented approach may fail to deliver specific messages if there is a network issue. Let's consider the case when
we have a consumer on a different host from the Redis server and there is a network issue resulting in the consumer
losing  connectivity with the server. If the consumer has acquired locks for messages, but has not yet published them
when this happens, the messages will be lost.

The following idea should provide a conditional delivery guarantee. The condition is that at least one consumer should
not lose connectivity with the Redis server.

The following approach should be able to provide that guarantee:
1) Try to acquire a lock for the message
2) If successful 
   - Open a pipeline 
   - Publish the message to the stream via the pipeline
   - Publish an ACK message with TTL = 1/2 lock TTL that the message is published to the stream
   - Execute the pipeline and if all is successful - remove the message from the local list of messages to be process
3) If unsuccessful
   - Check if there is an ACK message and if so - remove the message from the local list
4) Repeat from 1 on next message processing iteration

## Performance
Quick tests showed that we don't get linear performance improvement by scaling the number of clients. In fact with 2
consumers the speed is better compared to the case with 10 consumers. I haven't looked deeper into this, but I think
that the limiting factor is the network I/O operations.

We might be able to improve the performance if we use different mechanisms for acquiring locks. This needs to be
explored. IIRC I saw guidance somewhere on the internet, that proposed to use ordered sets for that purpose.

## Distributed consumers
With the current implementation we can launch the consumers on multiple hosts, but I would not consider this as
a distributed system. A distributed system should provide:
 - Centralised control plane for managing the system (changing the consumers count, killing the consumers)
 - Load balancing mechanism
 - Automated scale up/down

The following is an approach for implement such system.

For the control plane we'll use a centralised system configuration behind a Redis key. Each member in the distributed
system will pull that configuration and act based on the settings it gets from it.

Members will be implemented by an orchestration process. There will be a single orchestration process for each host
participating in the system. When the process is started it will register itself in the control plane. The orchestration
process will be responsible for starting and stopping the consumers.

Load balancing will be accomplished by splitting the numbers of the consumers on the different hosts in the  system.
With 10 hosts participating in the system and 50 consumers desired each host will be running 5 consumers.

The automated scale up/down process will be accomplished by monitoring the throughput or the number of unprocessed
messages and increasing/decreasing the consumer count based on it.
