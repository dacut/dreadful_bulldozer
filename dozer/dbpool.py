from __future__ import (absolute_import, print_function)
from threading import Condition, RLock

class ConnectionPool(object):
    def __init__(self, create_function, min_size=1, max_size=None):
        super(ConnectionPool, self).__init__()
        self.create_function = create_function
        self.active = []
        self.idle = []
        self.lock = RLock()
        self.condition = Condition(self.lock)
        self.max_size = max_size

        with self.lock:
            while len(self.idle) < min_size:
                self.acquire_new_connection()

        return

    def acquire_new_connection(self):
        with self.lock:
            con = self.create_function()
            self.idle.append(con)
        return

    def acquire(self):
        with self.lock:
            while len(self.idle) == 0:
                if len(self.active) == self.max_size:
                    self.condition.wait()
                else:
                    self.acquire_new_connection()
            con = self.idle.pop(0)
            self.active.append(con)
            return ConnectionWrapper(con, self)

    def release(self, con):
        with self.lock:
            pos = self.active.index(con)
            del self.active[pos]
            self.idle.append(con)
            self.condition.notify_all()


class SQLitePool(object):
    def __init__(self, *args, **kw):
        super(SQLitePool, self).__init__()
        self.args = args
        self.kw = kw
        return

    def acquire(self):
        import sqlite3
        return ConnectionWrapper(sqlite3.connect(*self.args, **self.kw), self)

    def release(self, con):
        con.close()
        return

class ConnectionWrapper(object):
    def __init__(self, con, pool):
        super(ConnectionWrapper, self).__init__()
        self.con = con
        self.pool = pool
        return

    def __enter__(self):
        return self.con

    def __exit__(self, *args):
        self.pool.release(self.con)
        return
