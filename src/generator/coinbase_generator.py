import asyncio
import websockets
import json
import time
import hmac
import hashlib
from kafka.errors import KafkaError
from .kafka_producer import producer

class CoinbaseClient:
    def __init__(self, api_key, api_secret):
        # --- Coinbase WebSocket Configuration ---
        self.COINBASE_WS_URL = "wss://ws-feed.exchange.coinbase.com"
        self.KAFKA_TOPIC = 'crypto-btc-usd-raw'
        self.API_KEY = api_key
        self.API_SECRET = api_secret
    
    def _create_signature(self, timestamp, method, request_path, body=''):
        """
        Creates the required HMAC-SHA256 signature for authenticated requests.
        """
        message = f"{timestamp}{method}{request_path}{body}"
        signature = hmac.new(
            self.API_SECRET.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    async def connect(self):
        """
        Connects to Coinbase, sends an authenticated subscription request,
        and forwards messages to Kafka.
        """
        while True:
            try:
                async with websockets.connect(self.COINBASE_WS_URL) as websocket:
                    print("✅ Connected to Coinbase WebSocket.")

                    timestamp = str(int(time.time()))
                    signature = self._create_signature(
                        timestamp, 'GET', '/users/self/verify')

                    # This is the authenticated subscription message
                    auth_subscription_message = {
                        "type": "subscribe",
                        "product_ids": ["BTC-USD"],
                        "channels": ["level2", "matches"],
                        # --- Authentication Parts ---
                        "signature": signature,
                        "key": self.API_KEY,
                        "timestamp": timestamp,
                    }

                    await websocket.send(json.dumps(auth_subscription_message))
                    print(
                        f"▶️ Authenticated and subscribed. Pushing to Kafka topic: '{self.KAFKA_TOPIC}'")

                    while True:
                        message_str = await websocket.recv()
                        message_json = json.loads(message_str)

                        # Filter out subscription confirmations
                        if 'product_id' in message_json:
                            print(message_json)
                            producer.send(self.KAFKA_TOPIC, key=message_json['product_id'].encode(
                                'utf-8'), value=message_json)

            except websockets.ConnectionClosed as e:
                print(f"❌ Connection closed: {e}. Reconnecting...")
                await asyncio.sleep(5)
            except Exception as e:
                print(f"🔥 An error occurred: {e}. Reconnecting...")
                await asyncio.sleep(5)
            except KafkaError as e:
                print(f"Error with kafka : {e}. Retrying in 5 seconds")
                await asyncio.sleep(5)