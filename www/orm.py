#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import aiomysql


def log(sql, args=()):
    logging.info('SQL: %s' % sql)


async def create_pool(loop, **kw):
    """
        创建全局连接池，以防频繁的打开和关闭数据库连接
    """
    logging.info('create database connection pool...')
    global __pool
    print(kw)
    __pool = await aiomysql.create_pool(
        host=kw.get('host', 'localhost'),
        port=kw.get('port', 3306),
        user=kw['user'],
        password=kw['password'],
        db=kw['db'],
        charset=kw.get('charset', 'utf8'),
        autocommit=kw.get('autocommit', True),
        maxsize=kw.get('maxsize', 10),
        minsize=kw.get('minsize', 1),
        loop=loop
    )


async def select(sql, args, size=None):
    log(sql, args)
    global __pool
    with await __pool as conn:
        cur = await conn.cursor(aiomysql.DictCursor)
        await cur.execute(sql.replace('?', '%s'), args or ())
        if size:
            rs = await cur.fetchmany(size)
        else:
            rs = await cur.fetchall()
        await cur.close()
        logging.info('rows returned: %s', len(rs))
        return rs


async def execute(sql, args):
    """
        增，删，改
    """
    log(sql)
    with await __pool as conn:
        cur = await conn.cursor()
        await cur.execute(sql.replace('?', '%s'), args)
        affected = cur.rowcount
        await cur.close()
        return affected


def create_args_string(num):
    L = []
    for n in range(num):
        L.append('?')
    return ', '.join(L)


class Field():
    def __init__(self, name, column_type, primary_key, default):
        self.name = name
        self.column_type = column_type
        self.primary_key = primary_key
        self.default = default

    def __str__(self):
        return '<{}, {}:{}>'.format(
            self.__class__.__name__, self.column_type, self.name)


class StringField(Field):
    def __init__(self, name=None, column_type='varchar(100)',
                 primary_key=False, default=None):
        super().__init__(name, column_type, primary_key, default)


class BooleanField(Field):
    def __init__(self, name=None, default=False):
        super().__init__(name, 'boolean', False, default)


class FloatField(Field):
    def __init__(self, name=None, primary_key=False, default=0.0):
        super().__init__(name, 'real', primary_key, default)


class TextField(Field):
    def __init__(self, name=None, default=None):
        super().__init__(name, 'text', False, default)


class ModelMetaclass(type):
    def __new__(cls, name, parents, attrs):
        # Model类不进行处理，直接返回
        if name == 'Model':
            return type.__new__(cls, name, parents, attrs)

        # 获取table名
        table_name = attrs.get('__table__', name)
        logging.info('found model: {} (table: {})'.format(name, table_name))

        mappings = {}
        fields = []
        primary_key = None
        for key, value in attrs.items():
            if isinstance(value, Field):
                logging.info('found mapping: {} ==> {}'.format(key, value))
                mappings[key] = value
                if value.primary_key:
                    primary_key = key
                else:
                    fields.append(key)
        if not primary_key:
            raise RuntimeError('Primary key not found')

        escaped_fields = list(map(lambda field: '`{}`'.format(field), fields))

        new_attrs = {}
        new_attrs['__mappings__'] = mappings  # 属性到列的映射关系
        new_attrs['__table__'] = table_name
        new_attrs['__primary_key__'] = primary_key
        new_attrs['__fields__'] = fields  # 除主键外的属性名
        # default select, select all fields from table
        # select `id`, `name`, `age` from `user`
        new_attrs['__select__'] = 'select `{}`, {} from `{}`'\
            .format(primary_key, ', '.join(escaped_fields), table_name)
        # default insert, insert an full field item into table
        # insert into `user` (`id`, `name`, `age`) values (?, ?, ?)
        new_attrs['__insert__'] = 'insert into `{}` (`{}`, {}) values ({})'\
            .format(table_name,
                    primary_key,
                    ', '.join(escaped_fields),
                    create_args_string(len(escaped_fields) + 1))
        # default update
        # update `user` set `name`=?, `age`=? where `id`=?
        new_attrs['__update__'] = 'update `{}` set {} where `{}`=?'\
            .format(table_name,
                    ', '.join(map(lambda field: '`{}`=?'.format(mappings.get(field).name or field), fields)),
                    primary_key)
        # default delete
        # delete from `user` where `id`=?
        new_attrs['__delete__'] = 'delete from `{}` where `{}`=?'\
            .format(table_name, primary_key)

        return type.__new__(cls, name, parents, new_attrs)


class Model(dict, metaclass=ModelMetaclass):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(
                "'Model' object has no attribute {}".format(key))

    def __setattr__(self, key, value):
        self[key] = value

    def getValue(self, key):
        return getattr(self, key, None)

    def getValueOrDefault(self, key):
        value = getattr(self, key, None)
        if value is None:
            field = self.__mappings__[key]
            if field.default is not None:
                value = field.default() if callable(field.default) else field.default
                logging.debug('using default value for %s: %s' % (key, str(value)))
                setattr(self, key, value)
        return value

    @classmethod
    async def find(cls, primary_key):
        """
            find object by primary key
        """
        res = await select('{} where `{}`=?'.format(
            cls.__select__, cls.__primary_key__), [primary_key], 1)
        if len(res) == 0:
            return None
        return cls(**res[0])

    @classmethod
    async def findAll(cls, where=None, args=None, **kw):
        ' find objects by where clause. '
        sql = [cls.__select__]
        if where:
            sql.append('where')
            sql.append(where)
        if args is None:
            args = []
        orderBy = kw.get('orderBy', None)
        if orderBy:
            sql.append('order by')
            sql.append(orderBy)
        limit = kw.get('limit', None)
        if limit is not None:
            sql.append('limit')
            if isinstance(limit, int):
                sql.append('?')
                args.append(limit)
            elif isinstance(limit, tuple) and len(limit) == 2:
                sql.append('?, ?')
                args.extend(limit)
            else:
                raise ValueError('Invalid limit value: %s' % str(limit))
        print(sql, args)
        rs = await select(' '.join(sql), args)
        return [cls(**r) for r in rs]

    @classmethod
    async def find_number(cls, selectField, where=None, args=None):
        """
            find number by select and where
        """
        sql = ['select {} _num_ from `{}`'.format(selectField, cls.__table__)]
        if where:
            sql.append('where')
            sql.append(where)
        rs = await select(', '.join(sql), args, 1)
        if len(rs) == 0:
            return None
        return rs[0]['_num_']

    async def save(self):
        args = [self.getValueOrDefault(self.__primary_key__)]
        args = args + list(map(self.getValueOrDefault, self.__fields__))
        rows = await execute(self.__insert__, args)
        if rows != 1:
            logging.warn(
                'failed to insert record: affected rows: {}'
                .format(rows))

    async def update(self):
        args = [self.getValue(self.__primary_key__)]
        args = args + list(map(self.getValue, self.__fields__))
        rows = await execute(self.__update__, args)
        if rows != 1:
            logging.warn(
                'faild to update by primary key: affected rows: {}'
                .format(rows))

    async def remove(self):
        args = [self.getValue(self.__primary_key__)]
        rows = await execute(self.__delete__, args)
        if rows != 1:
            logging.info(
                'faild to remove by primary key: affected rows: {}'
                .format(rows))
