from __future__ import (absolute_import, print_function)
from base64 import b64decode, b64encode
import cherrypy
from datetime import datetime
import dozer.dao as dao
import dozer.filesystem as fs
import dozer.jsonrpc as jsonrpc
from dozer.exception import (
    FileNotFoundError, InvalidParameterError, LoginDeniedError,
    PermissionDeniedError)
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
    def create_note(self, notepage_id=None, pos_um=None, size_um=None):
        notepage = fs.FilesystemNode.get_node_by_id(notepage_id)
        if not isinstance(notepage, fs.Notepage):
            raise InvalidParameterError(
                "notepage_id %r does not refer to a notepage", notepage_id)

        return notepage.create_note(pos_um=pos_um, size_um=size_um)

    @jsonrpc.expose
    def update_notepage(self, notepage_id=None, updates=None):
        if not isinstance(updates, (list, tuple)):
            raise InvalidParameterError(
                "updates must be a list of update objects")

        notepage = fs.FilesystemNode.get_node_by_id(notepage_id)
        if not isinstance(notepage, fs.Notepage):
            raise InvalidParameterError(
                "notepage_id %r does not refer to a notepage", notepage_id)

        # Running change log.
        changes = []
        
        # Updated notes
        results = []

        for update_id, update in enumerate(updates):
            action = update.get('action')
            if action is None:
                raise InvalidParameterError(
                    "update %d does not have an action", update_id)

            update['update_id'] = update_id
            
            if action == "edit_note":
                change, result = self._edit_note(notepage, update)
                changes.append(change)
                results.append(result)
            else:
                raise InvalidParameterError(
                    "update %d has invalid action %r", update_id, action)
        # end for
        
        notepage.update(changes)
        return {
            'notepage_revision_id': notepage.revision_id,
            'results': results
        }

    @jsonrpc.expose
    def list_folder(self, node_name=None):
        return fs.get_node(node_name).children

    def _edit_note(self, notepage, update):
        change = {}
        result = {}

        update_id = update['update_id']
            
        note_id = update.get('note_id')
        if note_id is None:
            raise InvalidParameterError(
                "update %d action edit_note does not have a note_id",
                update_id)

        revision_id = update.get('revision_id')
        if revision_id is None:
            raise InvalidParameterError(
                "update %d action edit_note does not have a "
                "revision_id", update_id)

        note = fs.FilesystemNode.get_node_by_id(note_id)
        if not isinstance(note, fs.Note):
            raise InvalidParameterError(
                "update %d action edit_note node_id %d does not refer "
                "to a note", update_id, note_id)

        change['action'] = 'edit_note'
        change['note_id'] = note_id
        result['note_id'] = note_id

        pos_um = update.get('pos_um')
        if pos_um is not None:
            change['pos_um'] = [note.pos_um, pos_um]
            result['pos_um'] = pos_um
            note.pos_um = pos_um

        size_um = update.get('size_um')
        if size_um is not None:
            change['size_um'] = [note.size_um, size_um]
            result['size_um'] = size_um
            note.size_um = size_um

        z_index = update.get('z_index')
        if z_index is not None:
            change['z_index'] = [note.z_index, z_index]
            result['z_index'] = z_index
            note.z_index = z_index

        contents_markdown = update.get('contents_markdown')
        if contents_markdown is not None:
            change['contents_markdown'] = [
                note.contents_markdown, contents_markdown]
            result['contents_markdown'] = contents_markdown
            note.contents_markdown = contents_markdown

        note.update()
        result['revision_id'] = note.revision_id
        return change, result

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

