import asyncio
from .coinbase_generator import CoinbaseClient
from .kafka_producer import producer
import os
from dotenv import load_dotenv
load_dotenv()


async def main():
    api_key = os.getenv("COINBASE_API_KEY")
    api_secret = os.getenv("COINBASE_API_SECRET")

    if not api_key or not api_secret:
        print("🔥 Error: Please set COINBASE_API_KEY and COINBASE_API_SECRET in your .env file.")
        return

    client = CoinbaseClient(api_key, api_secret)
    await client.connect()
if __name__ == "__main__":
    try:
        print("🚀 Starting data generator...")
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nℹ️ Manually stopping the script. Flushing producer...")
        # Ensure all pending messages are sent before exiting.
        producer.flush()
        print("✅ Producer flushed.")
