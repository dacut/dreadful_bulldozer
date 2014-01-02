from __future__ import (absolute_import, print_function)
from base64 import b64decode, b64encode
import cherrypy
from datetime import datetime
import dozer.dao as dao
import dozer.filesystem as fs
import dozer.jsonrpc as jsonrpc
from dozer.exception import (
    FileNotFoundError, LoginDeniedError, PermissionDeniedError)
from functools import partial
from httplib import METHOD_NOT_ALLOWED
from logging import getLogger
from mako.lookup import TemplateLookup
from mako.runtime import Context
from mako.template import Template
from os.path import abspath, dirname, exists, isfile
import sqlalchemy.orm.exc
from sqlite3 import Connection
from sys import exit
from urllib import quote_plus as quote_url

log = getLogger("dozer.app")

@jsonrpc.expose
class DozerAPI(object):
    @jsonrpc.expose
    def create_folder(self, node_name=None, inherit_permissions=True):
        return fs.create_folder(folder_name=node_name,
                                inherit_permissions=inherit_permissions)

    @jsonrpc.expose
    def create_notepage(self, node_name=None, inherit_permissions=True):
        return fs.create_notepage(notepage_name=node_name,
                                  inherit_permissions=inherit_permissions)

    @jsonrpc.expose
    def create_note(self, notepage_name=None, x_pos_um=None, y_pos_um=None,
                    width_um=None, height_um=None):
        return fs.create_note(
            notepage_name=notepage_name, x_pos_um=x_pos_um, y_pos_um=y_pos_um,
            width_um=width_um, height_um=height_um)

    @jsonrpc.expose
    def list_folder(self, node_name=None):
        return fs.get_node(node_name).children

class DreadfulBulldozer(object):
    def __init__(self, server_root):
        super(DreadfulBulldozer, self).__init__()
        self.server_root = server_root
        self.template_dir = server_root + "/pages"
        self.template_lookup = TemplateLookup(directories=[self.template_dir])
        self.jsonrpc = jsonrpc.JSONRPC()
        self.jsonrpc.dozer = DozerAPI()
        return

    @cherrypy.expose
    def index(self, *args, **kw):
        page = Template(filename=self.template_dir + "/index.html",
                        lookup=self.template_lookup,
                        strict_undefined=True)
        cherrypy.serving.response.headers['Content-Type'] = "text/html"
        return page.render(app=self)

    @cherrypy.expose
    def login(self, username=None, password=None, redirect="/", logout=None,
              **kw):
        request = cherrypy.serving.request
        response = cherrypy.serving.response
        error_msg = None

        if request.method in ("POST", "PUT"):
            # See if we have a username/password combination
            if username is not None and password is not None:
                try:
                    cherrypy.tools.user_session.local_login(
                        username=username, password=password)
                    raise cherrypy.HTTPRedirect(redirect, 303)
                except LoginDeniedError:
                    error_msg = "Invalid username/password"

        if logout:
            cherrypy.tools.user_session.logout()
                
        page = Template(filename=self.template_dir + "/login.html",
                        lookup=self.template_lookup,
                        strict_undefined=True)
        response.headers['Content-Type'] = "text/html"
        return page.render(app=self, redirect=redirect, error_msg=error_msg)

    @cherrypy.expose
    def browse(self, *args, **kw):
        request = cherrypy.serving.request
        response = cherrypy.serving.response

        if request.method in ("POST", "PUT"):
            raise cherrypy.HTTPError(METHOD_NOT_ALLOWED)
        
        # Make sure we have a valid session.
        if request.user_session is None:
            # Redirect to the login page.
            raise cherrypy.HTTPRedirect("/login?redirect=" +
                                        quote_url("/browse"))
        
        home_folder = request.user.home_folder
        if home_folder is None:
            home_folder = "/"
        elif not home_folder.startswith("/"):
            home_folder = "/" + home_folder
        
        raise cherrypy.HTTPRedirect("/files" + home_folder)

    @cherrypy.expose
    def files(self, *args, **kw):
        request = cherrypy.serving.request
        response = cherrypy.serving.response

        if request.method in ("POST", "PUT"):
            # TODO: Handle file upload.
            raise cherrypy.HTTPError(500, "Unable to handle uploads right now")
        
        # Make sure we have a valid session.
        if request.user_session is None:
            # Redirect to the login page.
            raise cherrypy.HTTPRedirect(
                "/login?redirect=%s" % quote_url("/files/" + "/".join(args)))

        try:
            node = fs.get_node("/" + "/".join(args))
        except FileNotFoundError as e:
            raise cherrypy.HTTPError(404, str(e))
        except PermissionDeniedError as e:
            raise cherrypy.HTTPError(403, str(e))

        if isinstance(node, fs.Folder):
            template = "folder.html"
        elif isinstance(node, fs.Notepage):
            template = "notepage.html"
        elif isinstance(node, fs.Note):
            template = "note.html"

        page = Template(filename=self.template_dir + "/" + template,
                        lookup=self.template_lookup,
                        strict_undefined=True)
        response.headers['Content-Type'] = "text/html"
        return page.render(app=self, node=node)

    @cherrypy.expose
    def create(self, *args, **kw):
        if cherrypy.serving.request.method not in ("POST", "PUT"):
            raise cherrypy.HTTPError(405)

        document = dao.create_temp_document(
            cherrypy.serving.request.db_session,
            dao.Entity("dozer_user", "dacut"))

        cherrypy.serving.request.db_session.commit()
        
        raise cherrypy.HTTPRedirect(
            "/notepage" + document.full_name, 302)

        return ""

    @cherrypy.expose
    def notepage(self, *args, **kw):
        path = cherrypy.request.path_info.split("/")[1:]
        
        if len(path) <= 1:
            raise cherrypy.HTTPRedirect("/notepage/", 302)
        
        path = "/" + "/".join(path[1:])
        obj, remaining = dao.get_object_by_path(cherrypy.request.db_session, path)
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
                    400, "Invalid method %s" % cherrypy.serving.request.method)

    def fetch_document(self, doc):
        page = Template(filename=self.template_dir + "/notepage.html",
                        lookup=self.template_lookup,
                        strict_undefined=True)
        cherrypy.response.headers['Content-Type'] = "text/html"
        return page.render(document=doc)

    def get_session(self, session_token):
        cherrypy.serving.request.user_session = None
        cherrypy.serving.request.user = None

