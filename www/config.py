#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
    config
'''

import config_default


class Dict(dict):
    '''
        dict support x.y style
    '''

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError('Dict object has no attribute {}'.format(key))

    def __setattr__(self, key, value):
        self[key] = value


def merge(target, source):
    res = dict(**target)
    for k, v in source.items():
        if isinstance(v, dict):
            res[k] = merge(res[k], v)
        else:
            res[k] = v
    return res


def toDict(d):
    D = Dict()
    for k, v in d.items():
        D[k] = toDict(v) if isinstance(v, dict) else v
    return D


configs = config_default.configs
try:
    import config_override
    configs = merge(configs, config_override.configs)
except ImportError:
    pass
configs = toDict(configs)
