#!/usr/bin/env python3
# -*- coding: utf-8 -*-


class APIError(Exception):
    def __init__(self, error, data='', message=''):
        super().__init__(message)
        self.error = error
        self.data = data
        self.message = message


