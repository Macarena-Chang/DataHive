import aioredis
from fastapi import FastAPI, Request
from fastapi_limiter import FastAPILimiter
from models import TokenBlacklist

redis_connection = None

async def startup(app: FastAPI):
    global redis_connection
    redis_connection = await aioredis.from_url("redis://localhost")
    await FastAPILimiter.init(redis_connection)
    token_blacklist = TokenBlacklist(redis_connection)
    app.state.token_blacklist = token_blacklist

async def get_redis():
    return redis_connection

def get_token_blacklist(request: Request):
    return request.app.state.token_blacklist




