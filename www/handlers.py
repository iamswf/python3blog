#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import re
import hashlib
import json
from web_frame import get, post
from models import User, Blog, next_id
from apis import APIError, APIValueError
from aiohttp import web


COOKIE_NAME = 'iamswfsession'
_COOKIE_KEY = 'jdaklfd'


@get('/')
async def index(request):
    summary = 'this is a summary'
    blogs = [
        Blog(id='1', name='js入门', summary=summary,
                created_at=time.time() - 120),
        Blog(id='2', name='js函数式编程', summary=summary,
                created_at=time.time() - 3600),
        Blog(id='3', name='精通python', summary=summary,
                created_at=time.time() - 7200),
    ]
    return {
        '__template__': 'blogs.html',
        'blogs': blogs
    }


@get('/register')
def register():
    return {
        '__template__': 'register.html'
    }


@get('/api/users')
async def api_get_users():
    users = await User.findAll(orderBy='created_at desc')
    for u in users:
        print(u)
        u.passwd = '******'
    return dict(users=users)


def user2cookie(user, max_age):
    '''
        make cookie str by user
    '''
    expires = str(int(time.time()) + max_age)
    s = '{}-{}-{}-{}'.format(user.id, user.passwd, expires, _COOKIE_KEY)
    L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
    return '-'.join(L)


_RE_EMAIL = re.compile(
    r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')


@post('/api/users')
async def api_register_user(*, email, name, passwd):
    if not name or not name.strip():
        raise APIValueError('name')
    if not email or not _RE_EMAIL.match(email):
        raise APIValueError('email')
    if not passwd or not _RE_SHA1.match(passwd):
        raise APIValueError('passwd')
    users = User.findAll('email=?', [email])
    if len(users) > 0:
        raise APIError('register:failed', 'email', 'Email is already in use.')
    uid = next_id()
    sha1_passwd = '{}:{}'.format(uid, passwd)
    user = User(id=uid,
                name=name.strip(),
                email=email,
                passwd=hashlib.sha1(sha1_passwd.encode('utf-8').hexdigest()),
                image='http://www.gravatar.com/avatar/{}?d=mm&s=120'
                .format(hashlib.md5(email.encode('utf-8')).hexdigest()))
    await user.save()
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400, httponly=True))
    user.passwd = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r
