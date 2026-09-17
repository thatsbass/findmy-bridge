"""Standalone Apple auth test using the FindMy.py library."""
import asyncio, logging, os, sys
logging.basicConfig(level=logging.INFO)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'python-service'))
# Use relative paths instead of a fixed local development path.

from config import Config
from scheduler import Worker
from store import KeysStore
from backend import PositionPusher

async def test():
    cfg = Config.load()
    cfg.validate()
    print(f"Account: {cfg.apple_id}")
    
    store = KeysStore(cfg.database_url)
    await store.connect()
    
    pusher = PositionPusher(cfg.backend_url, cfg.backend_api_key)
    
    worker = Worker(
        keys_store=store,
        pusher=pusher,
        apple_id=cfg.apple_id,
        apple_password=cfg.apple_password,
        interval_seconds=99999,
    )
    
    await worker._ensure_authenticated()
    print("Authenticated!")
    print(f"Account: {worker._account.account_name}")
    
    tags = await store.load_active_tags()
    print(f"Active tags: {len(tags)}")
    
    await worker._close_account()
    await store.close()

asyncio.run(test())
