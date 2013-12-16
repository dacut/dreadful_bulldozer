from logging import getLogger
import cherrypy
from cherrypy._cptools import Tool

log = getLogger("dozer.transaction")

class TransactionTool(Tool):
    """\
A tool for wrapping a request within a database transaction.
"""
    def __init__(self, db_session_class):
        super(TransactionTool, self).__init__(
            point="before_handler", callable=self.__call__,
            name="Transaction", priority=20)
        self.db_session_class = db_session_class
        return

    def __call__(self):
        request = cherrypy.serving.request
        request.db_session = self.db_session_class()
        next_handler = request.handler

        def transaction_handler(*args, **kw):
            try:
                return next_handler(*args, **kw)
            except:
                request.db_session.rollback()
                raise
            else:
                request.db_session.commit()
            finally:
                request.db_session.close()
                del request.db_session

        request.handler = transaction_handler
        return
