#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import json
import logging
from aiohttp import web
from handlers import cookie2user


COOKIE_NAME = 'iamswfsession'


async def logger_factory(app, handler):
    async def logger(request):
        logging.info('Request: {} {}'.format(request.method, request.path))
        return await handler(request)
    return logger


async def auth_factory(app, handler):
    async def auth(request):
        logging.info('check user: %s %s' % (request.method, request.path))
        request.__user__ = None
        cookie_str = request.cookies.get(COOKIE_NAME)
        if cookie_str:
            user = await cookie2user(cookie_str)
            if user:
                logging.info('set current user: %s' % user.email)
                request.__user__ = user
        if (request.path.startswith('/manage/') and
                (request.__user__ is None or not request.__user__.admin)):
            return web.HTTPFound('/signin')
        return (await handler(request))
    return auth


async def response_factory(app, handler):
    async def response(request):
        logging.info('Response handler...')
        r = await handler(request)
        if isinstance(r, web.StreamResponse):
            return r
        if isinstance(r, bytes):
            resp = web.Response(body=r)
            resp.content_type = 'application/octet-stream'
            return resp
        if isinstance(r, str):
            if r.startswith('redirect:'):
                return web.HTTPFound(r[9:])
            resp = web.Response(body=r.encode('utf-8'))
            resp.content_type = 'text/html;charset=utf-8'
            return resp
        if isinstance(r, dict):
            template = r.get('__template__')
            if template is None:
                resp = web.Response(body=json.dumps(r, ensure_ascii=False, default=lambda o: o.__dict__).encode('utf-8'))
                resp.content_type = 'application/json;charset=utf-8'
                return resp
            else:
                resp = web.Response(body=app['__templating__']
                                    .get_template(template)
                                    .render(**r)
                                    .encode('utf-8'))
                resp.content_type = 'text/html;charset=utf-8'
                return resp
        # default:
        resp = web.Response(body=str(r).encode('utf-8'))
        resp.content_type = 'text/plain;charset=utf-8'
        return resp
    return response
