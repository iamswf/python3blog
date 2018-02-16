#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import logging
from aiohttp import web


async def logger_factory(app, handler):
    async def logger(request):
        logging.info('Request: {} {}'.format(request.method, request.path))
        return await handler(request)
    return logger


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
                pass
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
