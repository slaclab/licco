import logging
import os

from pymongo import MongoClient

logger = logging.getLogger(__name__)

def create_mongo_client(mongodb_url: str = "", timeout: int = 5000):
    if not mongodb_url:
        mongodb_url = os.environ.get("MONGODB_URL", None)

    if not mongodb_url:
        logger.info("Connecting to MongoDB on localhost:27017")
        
    client = MongoClient(host=mongodb_url, tz_aware=True, serverSelectionTimeoutMS=timeout)
    
    # ping the client to confirm that mongodb is running and the configuration is correct
    # (will raise ConnectionFailure otherwise)
    client.admin.command('ping')
    
    return client