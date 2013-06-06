from __future__ import (absolute_import, print_function)
import cherrypy
import dozer.dao as dao
from functools import partial
from logging import getLogger
from mako.lookup import TemplateLookup
from mako.runtime import Context
from mako.template import Template
from os.path import abspath, dirname, exists, isfile
import sqlalchemy.orm.exc
from sqlite3 import Connection
from sys import exit

log = getLogger("dozer.app")

def transactional(method):
    def wrapper(self, *args, **kw):
        cherrypy.request.session = self.session_class()
        try:
            return method(self, *args, **kw)
        except:
            cherrypy.request.session.rollback()
            raise
        else:
            cherrypy.request.session.commit()
        finally:
            cherrypy.request.session.close()

    wrapper.func_doc = method.func_doc
    wrapper.func_name = method.func_name
    return wrapper

class DreadfulBulldozer(object):
    def __init__(self, server_root, session_class):
        super(DreadfulBulldozer, self).__init__()
        self.server_root = server_root
        self.session_class = session_class
        self.template_dir = server_root + "/pages"
        self.template_lookup = TemplateLookup(directories=[self.template_dir])
        return

    @cherrypy.expose
    def index(self, *args, **kw):
        page = Template(filename=self.template_dir + "/index.html",
                        lookup=self.template_lookup,
                        strict_undefined=True)
        cherrypy.response.headers['Content-Type'] = "text/html"
        return page.render()

    @cherrypy.expose
    @transactional
    def notepage(self, *args, **kw):
        path = cherrypy.request.path_info.split("/")[1:]
        
        if len(path) <= 1:
            raise cherrypy.HTTPRedirect("/notepage/", 302)
        
        path = "/" + "/".join(path[1:])
        obj, remaining = dao.get_object_by_path(cherrypy.request.session, path)
        if obj is None:
            raise cherrypy.HTTPError(
                404, "Notepage %s does not exist" % (path,))
            
        if obj.document_type == "notepage":
            return self.handle_document(obj, remaining)
        elif obj.document_type == "folder":
            return self.handle_folder(obj)

        raise cherrypy.HTTPError(
            500, "Unknown document type %s" % (obj.document_type,))

    def handle_document(self, doc, remaining):
        remaining_elements = remaining.split("/")
        if len(remaining_elements) == 0:
            if cherrypy.request.method in ("GET", "HEAD"):
                return self.fetch_document(doc)
            elif cherrypy.request.method in ("POST", "PUT"):
                return self.put_document(doc)
            elif cherrypy.request.method in ("DELETE",):
                return self.delete_document(doc)
            else:
                raise cherrypy.HTTPError(
                    400, "Invalid method %s" % cherrypy.request.method)

    def fetch_document(self, doc):
        page = Template(filename=self.template_dir + "/notepage.html",
                        lookup=self.template_lookup,
                        strict_undefined=True)
        cherrypy.response.headers['Content-Type'] = "text/html"
        return page.render(document=doc)

    @cherrypy.expose
    @transactional
    def create(self, *args, **kw):
        if cherrypy.request.method not in ("POST", "PUT"):
            raise cherrypy.HTTPError(405)

        document = dao.create_temp_document(
            cherrypy.request.session,
            dao.Entity("dozer_user", "dacut"))

        cherrypy.request.session.commit()
        
        raise cherrypy.HTTPRedirect(
            "/notepage" + document.full_name, 302)

        return ""
