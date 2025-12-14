"""
RabbitMQ Message Broker Client
"""

import json
from typing import Dict, Any, Optional, List, Callable
from loguru import logger

try:
    import aio_pika
    AIOPIKA_AVAILABLE = True
except ImportError:
    AIOPIKA_AVAILABLE = False


class MessageBroker:
    """RabbitMQ message broker client"""
    
    _connection = None
    _channel = None
    _exchanges: Dict[str, Any] = {}
    
    @classmethod
    async def connect(cls, url: str):
        """Establish connection to RabbitMQ"""
        if not AIOPIKA_AVAILABLE:
            logger.warning("aio-pika not installed, messaging disabled")
            return
        
        try:
            cls._connection = await aio_pika.connect_robust(url)
            cls._channel = await cls._connection.channel()
            logger.info("Connected to RabbitMQ")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
    
    @classmethod
    async def disconnect(cls):
        """Close connection"""
        if cls._channel:
            await cls._channel.close()
        if cls._connection:
            await cls._connection.close()
        logger.info("Disconnected from RabbitMQ")
    
    @classmethod
    async def ping(cls) -> bool:
        """Check connection health"""
        if not AIOPIKA_AVAILABLE:
            return True  # Skip if not available
        return cls._connection and not cls._connection.is_closed
    
    @classmethod
    async def publish(
        cls,
        exchange: str,
        routing_key: str,
        message: Dict[str, Any],
        durable: bool = True
    ):
        """Publish message to exchange"""
        if not AIOPIKA_AVAILABLE or not cls._channel:
            logger.debug(f"Skipping publish to {exchange}/{routing_key}")
            return
        
        if exchange not in cls._exchanges:
            cls._exchanges[exchange] = await cls._channel.declare_exchange(
                exchange,
                aio_pika.ExchangeType.TOPIC,
                durable=durable
            )
        
        body = json.dumps(message).encode()
        msg = aio_pika.Message(
            body=body,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json"
        )
        
        await cls._exchanges[exchange].publish(
            msg,
            routing_key=routing_key
        )
        
        logger.debug(f"Published message to {exchange}/{routing_key}")
    
    @classmethod
    async def consume(
        cls,
        queue_name: str,
        exchange: str,
        routing_keys: List[str],
        handler: Callable
    ):
        """Consume messages from queue"""
        if not AIOPIKA_AVAILABLE or not cls._channel:
            logger.warning("Cannot consume: RabbitMQ not available")
            return
        
        # Declare exchange
        exchange_obj = await cls._channel.declare_exchange(
            exchange,
            aio_pika.ExchangeType.TOPIC,
            durable=True
        )
        
        # Declare queue
        queue = await cls._channel.declare_queue(
            queue_name,
            durable=True
        )
        
        # Bind queue to exchange with routing keys
        for routing_key in routing_keys:
            await queue.bind(exchange_obj, routing_key)
        
        # Start consuming
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    try:
                        data = json.loads(message.body.decode())
                        await handler(data)
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
