import orm
import asyncio
from models import User, Blog, Comment

loop = asyncio.get_event_loop()

async def test():
    await orm.create_pool(loop=loop, user='iamswf', password='iamswf', db='pure_blog')

    u = User(name='孙文飞', email='iamswf@163.com', passwd='sjdajf8', image='about:blank')

    await u.save()

loop.run_until_complete(test())
