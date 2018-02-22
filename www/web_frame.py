#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import inspect
import asyncio
import logging
import functools
import os
from urllib import parse
from aiohttp import web
from apis import APIError


def get(path):
    """
        get decorator factory
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        wrapper.__method__ = 'GET'
        wrapper.__path__ = path
        return wrapper
    return decorator


def post(path):
    """
        post decorator factory
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        wrapper.__method__ = 'POST'
        wrapper.__path__ = path
        return wrapper
    return decorator


def get_named_kw_args(fn):
    """
        获取『命名关键字参数』名
    """
    args = []
    parameters = inspect.signature(fn).parameters
    for name, parameter in parameters.items():
        if parameter.kind == inspect.Parameter.KEYWORD_ONLY:
            args.append(name)
    return tuple(args)


def get_required_named_kw_args(fn):
    """
        获取默认值为空的『命名关键字参数』名
    """
    args = []
    parameters = inspect.signature(fn).parameters
    for name, parameter in parameters.items():
        if (parameter.kind == inspect.Parameter.KEYWORD_ONLY and
                parameter.default == inspect.Parameter.empty):
            args.append(name)
    return tuple(args)


def has_named_kw_args(fn):
    """
        判断是否含有『命名关键字参数』
    """
    parameters = inspect.signature(fn).parameters
    for parameter in parameters.values():
        if (parameter.kind == inspect.Parameter.KEYWORD_ONLY):
            return True
    return False


def has_var_kw_arg(fn):
    """
        判断是否含有『关键字参数』：**kwargs
    """
    parameters = inspect.signature(fn).parameters
    for name, parameter in parameters.items():
        if (parameter.kind == inspect.Parameter.VAR_KEYWORD):
            return True
    return False


def has_request_arg(fn):
    """
        判断是否有参数request
    """
    parameters = inspect.signature(fn).parameters
    for name in parameters.keys():
        if name == 'request':
            return True
    return False


class RequestHandler():
    """
        请求处理函数类
    """

    def __init__(self, app, fn):
        self._app = app
        self._func = fn
        self._has_request_arg = has_request_arg(fn)
        self._has_var_kw_args = has_var_kw_arg(fn)
        self._has_named_kw_args = has_named_kw_args(fn)
        self._named_kw_args = get_named_kw_args(fn)
        self._required_named_kw_args = get_required_named_kw_args(fn)

    async def __call__(self, request):
        kw = None
        if self._has_named_kw_args or self._has_var_kw_args:
            if request.method == 'POST':
                if not request.content_type:
                    return web.HTTPBadRequest('Missing Content-Type')
                # 仅针对常见的Content-Type做处理
                ct = request.content_type.lower()
                if ct.startswith('application/json'):
                    params = await request.json()
                    if not isinstance(params, dict):
                        return web.HTTPBadRequest('Json body format errro.')
                    kw = params
                elif (ct.startswith('application/x-www-form-urlencoded') or
                        ct.startswith('multipart/form-data')):
                    params = await request.post()
                    kw = dict(**params)  # TODO: 为什么上面的不需要浅拷贝，这里需要
                else:
                    return web.HTTPBadRequest(
                        'Unsupported Content-Type: {}'
                        .format(request.content_type))
            if request.method == 'GEt':
                qs = request.query_string
                if qs:
                    kw = {}
                    for k, v in parse.parse_qs(qs, True).items():
                        print(v)
                        kw[k] = v[0]  # TODO: 为什么将第一个元素取出来
        if not self._has_var_kw_args and self._has_named_kw_args:
            # remove unnamed kwargs
            tmp = dict()
            for name in self._named_kw_args:
                if kw is not None and name in kw:
                    tmp[name] = kw[name]
            kw = tmp
        if kw is None:
            kw = dict(**request.match_info)
        else:
            for k, v in request.match_info.items():
                if k in kw:
                    logging.warning(
                        'Duplicate between match_info and kwargs')
                kw[k] = v
        if self._has_request_arg:
            kw['request'] = request
        if self._required_named_kw_args:
            for name in self._required_named_kw_args:
                if name not in kw:
                    return web.HTTPBadRequest(
                        'Missing argument: {}'.format(name))
        try:
            res = await self._func(**kw)
            return res
        except APIError as e:
            return dict(error=e.error, data=e.data, message=e.message)


def add_route(app, fn):
    """
        注册单个URL处理函数
    """
    method = getattr(fn, '__method__', None)
    path = getattr(fn, '__path__', None)
    if method is None or path is None:
        raise ValueError('@get or @post is not defined in {}.'.format(str(fn)))
    if not asyncio.iscoroutine(fn) and not inspect.isgenerator(fn):
        fn = asyncio.coroutine(fn)
    app.router.add_route(method, path, RequestHandler(app, fn))


def add_routes(app, module_name):
    """
        注册一个模块内的所有URL处理函数
    """
    mod = __import__(module_name)
    for attr in dir(mod):
        if attr.startswith('_'):
            continue
        fn = getattr(mod, attr)
        if callable(fn):
            method = getattr(fn, '__method__', None)
            path = getattr(fn, '__path__', None)
            if method and path:
                add_route(app, fn)


def add_static(app):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    app.router.add_static('/static/', path)
    logging.info('add static {} => {}'.format('/static/', path))
