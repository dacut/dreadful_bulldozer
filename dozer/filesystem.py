from __future__ import absolute_import, with_statement
import dozer.dao as dao
from dozer.exception import (
    FileNotFoundError, FilesystemConsistencyError, InvalidParameterError,
    InvalidPathNameError, PermissionDeniedError,)
from hashlib import sha256
import json
from logging import getLogger
from sqlalchemy.orm.exc import NoResultFound
from struct import pack
from uuid import uuid4 as random_uuid
import threading

# Permissions bits for documents and folders
PERM_ADMINISTRATE =     0x00000001
PERM_READ_DOCUMENT =    0x00000002
PERM_EDIT_DOCUMENT =    0x00000004
PERM_DELETE_DOCUMENT =  0x00000008

# Permissions bits for folders only
PERM_NAVIGATE =         0x00000010
PERM_LIST_CONTENTS =    0x00000020
PERM_CREATE_CHILD =     0x00000040
PERM_DELETE_FOLDER =    0x00000080
PERM_DELETE_ANY_CHILD = 0x00000100

# Special user/group ids
SYSTEM_USER_ID = 0
ALL_USERS_GROUP_ID = 1

# The default width and height of a note (76200 um == 3 inch).  This is the
# same size as a 3M Post-it(R) note.
DEFAULT_NOTE_WIDTH = 76200
DEFAULT_NOTE_HEIGHT = 76200

# Spacing to use to prevent overlap when trying to place new notes onto a
# notepage (6350 um == 0.25 inch).
NOTE_SPACING = 6350

log = getLogger("dozer.filesystem")

def get_root_folder():
    """\
Returns the root folder in the filesystem.
"""
    session = _request_db_session()
    root = session.query(dao.Folder).filter_by(
        node_id=0, parent_node_id=None, node_name='', is_active=1).one()

    return FilesystemNode._from_dao(root)

def get_node(path):
    """\
get_node(path[, session]) -> FilesystemNode

Retrieves the node with the specified path name.

The node must be accessible to the user -- that is, the parent folders must
be accessible.
"""
    log = getLogger("dozer.filesystem.get_node")
    session = _request_db_session()
    log.debug("get_node(path=%r)", path)

    if not isinstance(path, basestring) or path[0:1] != '/':
        log.error("Path %r isn't a string", path)
        raise InvalidPathNameError("path must be a string starting with '/'")

    node = get_root_folder()
    if path == "/":
        # Just return the root.  Splitting an empty string returns a list
        # containing an empty string, which isn't what we want.
        return node

    elements = path[1:].split("/")
    log.debug("elements: %r", elements)
    for el in elements:
        log.debug("node=%r; considering child %r", node, el)
        node = node.get_child(el)

    log.debug("Done. Returning node %r", node)

    return node

def stringify_permissions(permissions):
    """\
stringify_permissions(permissions) -> str

Convert a bitmap of permissions into the string permissions identifiers.
"""
    result = []
    g = globals()

    for perm_name in ("PERM_ADMINISTRATE", "PERM_READ_DOCUMENT",
                      "PERM_EDIT_DOCUMENT", "PERM_DELETE_DOCUMENT",
                      "PERM_NAVIGATE", "PERM_LIST_CONTENTS",
                      "PERM_CREATE_CHILD", "PERM_DELETE_FOLDER",
                      "PERM_DELETE_ANY_CHILD"):
        if permissions & g[perm_name] != 0:
            result.append(perm_name)

    return "|".join(result)

def create_folder(folder_name, inherit_permissions=True):
    """\
create_folder(folder_name, inherit_permissions=True) -> Folder

Create a folder with the specified name.  If inherit_permissions is True,
the new folder will inherit permissions from its parent.
"""
    if not isinstance(folder_name, basestring) or folder_name[:1] != '/':
        log.error("create_folder: invalid path %r", folder_name)
        raise InvalidPathNameError("folder_name must be a string starting "
                                   "with '/'")

    path, subfolder = folder_name.rsplit("/", 1)
    if path == "":
        path = "/"

    parent = get_node(path)
    return parent.create_subfolder(
        subfolder, inherit_permissions=inherit_permissions)

def create_notepage(notepage_name, inherit_permissions=True):
    """\
create_notepage(notepage_name, inherit_permissions=True) -> Notepage

Create a notepage with the specified name.  If inherit_permissions is True,
the new notepage will inherit permissions from its parent.
"""
    if not isinstance(notepage_name, basestring) or notepage_name[:1] != '/':
        log.error("create_notepage: invalid path %r", notepage_name)
        raise InvalidPathNameError("notepage_name must be a string starting "
                                   "with '/'")

    path, filename = notepage_name.rsplit("/", 1)
    if path == "":
        path = "/"

    parent = get_node(path)
    return parent.create_notepage(
        filename, inherit_permissions=inherit_permissions)

def create_note(notepage_name, x_pos_um=None, y_pos_um=None, width_um=None,
                height_um=None):
    """\
create_note(notepage_name, x_pos_um=None, y_pos_um=None, width_um=None,
            height_um=None) -> Note

Create a note for the specified notepage.
"""
    if not isinstance(notepage_name, basestring) or notepage_name[:1] != '/':
        raise InvalidParameterError("notepage_name must be a string starting "
                                    "with '/'")
    
    notepage = get_node(notepage_name)
    if not isinstance(notepage, Notepage):
        raise InvalidParameterError("Node is not a notepage: %r" %
                                    notepage_name)
    
    return notepage.create_note(x_pos_um=x_pos_um, y_pos_um=y_pos_um,
                                width_um=width_um, height_um=height_um)

context = threading.local()

def _request_user():
    global context
    if hasattr(context, 'user') and context.user is not None:
        return context.user

    import cherrypy
    return cherrypy.serving.request.user

def _request_user_id():
    user = _request_user()
    if user is None:
        return None
    else:
        return user.user_id

def _request_username():
    user = _request_user()
    if user is None:
        return "unauthenticated user"
    else:
        return user.display_name

def _request_db_session():
    global context
    if hasattr(context, 'db_session') and context.db_session is not None:
        return context.db_session

    import cherrypy
    return cherrypy.serving.request.db_session

def _expand_user(user):
    """\
_expand_user(user) -> set(user_id, group_id, group_id, ...)

Finds the ids of the user plus all of the groups the user belongs to
(directly or via group-group membership).
"""
    to_expand = [user]
    result = set()
    while to_expand:
        user = to_expand.pop()
        result.add(user.user_id)

        for group in user.groups:
            # Don't add the group if we've already traversed it (through
            # another link).
            if group.user_id not in result:
                to_expand.append(group)

    # Always add the all-users id to the id_set
    result.add(ALL_USERS_GROUP_ID)

    return result

class FilesystemNode(object):
    def __init__(self, dao, **kw):
        super(FilesystemNode, self).__init__()
        self._dao = dao
        if "parent" in kw:
            self._parent = kw['parent']

        return

    @property
    def node_id(self):
        return self._dao.node_id

    @property
    def name(self):
        return self._dao.node_name

    @property
    def full_name(self):
        return self._dao.full_name

    @property
    def path_components(self):
        return self._dao.path_components

    @property
    def inherit_permissions(self):
        return self._dao.inherit_permissions

    @property
    def parent(self):
        if not hasattr(self, "_parent"):
            parent_dao = self._dao.parent
            if parent_dao is not None:
                self._parent = FilesystemNode._from_dao(parent_dao)
            else:
                self._parent = None
        return self._parent

    @property
    def hierarchy(self):
        parent = self.parent

        if parent is None:
            result = []
        else:
            result = parent.hierarchy

        result.append(self)
        return result

    @property
    def json(self):
        return self._to_json()

    def access(self, desired_permissions):
        """\
node.access(desired_permissions) -> bool

Indicates whether the specified node can be accessed with the specified
permissions by the current user.

desired_permissions is a bitwise-xor of one or more of the following constants
indicating the desired mode:
    PERM_ADMINISTRATE       User is allowed to alter permissions on the
                            document or folder.

    PERM_READ_DOCUMENT      User can read the document. [1]

    PERM_EDIT_DOCUMENT      User can edit the document. [1]

    PERM_DELETE_DOCUMENT    User can delete the document. [1]

    PERM_NAVIGATE           User can navigate/traverse through the folder. [2]

    PERM_LIST_CONTENTS      User can enumerate entries in the folder. [2]

    PERM_CREATE_CHILD       User can create a document or folder within the
                            folder. [2]

    PERM_DELETE_FOLDER      User can delete the folder. [2]

    PERM_DELETE_ANY_CHILD   User can delete any document or folder within the
                            folder. [2]

[1] Meaningful only to documents.  Has no direct meaning on a folder, but
    can be inherited by documents within the folder.

[2] Applicable to folders only.  Not permitted on a document.
"""
        log = getLogger("dozer.filesystem.access")
        user = _request_user()

        log.debug("access(desired_permissions=%s) euser=%r",
                  stringify_permissions(desired_permissions),
                  user)

        if user is not None and user.user_id == SYSTEM_USER_ID:
            # System administrative task; always permit.
            log.debug("access shortcut by SYSTEM_USER_ID granted")
            return True

        # A set including the user's id plus all group ids the user belongs to.
        if user is not None:
            id_set = _expand_user(user)
        else:
            id_set = set()

        log.debug("Using effective id set %r", id_set)
        
        # Make sure this item has the proper permissions.
        return self._check_permissions(desired_permissions, id_set)

    def __repr__(self):
        full_name = self.full_name
        if full_name == "":
            full_name == "[root]"
        return "[%s %s]" % (self.__class__.__name__, full_name)

    def __hash__(self):
        return hash(self.full_name)

    @staticmethod
    def _from_dao(node, **kw):
        if node.node_type_id == dao.NODE_TYPE_ID_FOLDER:
            cls = Folder
        elif node.node_type_id == dao.NODE_TYPE_ID_NOTEPAGE:
            cls = Notepage
        elif node.node_type_id == dao.NODE_TYPE_ID_NOTE:
            cls = Note
        else:
            raise FilesystemConsistencyError(
                "Unknown node type id %d" % node.node_type_id)

        return cls(dao=node, **kw)

    def _get_hierarchy(self, node):
        """\
_get_hierarchy(node) -> [root, folder, folder, ..., node]

Returns the entire hierarchy of filesystem objects for the given node.
"""
        if node.parent is None:
            return [node]

        hierarchy = self._get_hierarchy(node.parent)
        hierarchy.append(node)
        return hierarchy
    
    def _check_permissions(self, desired_permissions, id_set):
        """\
_check_permissions(permissions, id_set) -> bool

Check whether the specified node allows all permissions to one or more
user/group ids in the id_set.
"""
        for ace in self._dao.permissions:
            if ace.user_id not in id_set:
                # This access control entry doesn't apply.
                continue

            if ace.permissions & desired_permissions == desired_permissions:
                # All permissions granted.
                return True

        # Does this node inherit its permissions?
        parent = self.parent
        if self.inherit_permissions and parent is not None:
            # Yes; see if the parent grants these permissions.
            return parent._check_permissions(desired_permissions, id_set)

        # Insufficient access
        return False

    def _get_children(self):
        raise NotImplementedError("Class %s does not implement _get_children" %
                                  self.__class__.__name__)
    @property
    def children(self):
        return self._get_children()

    def get_child(self, child_name):
        # The user must have PERM_NAVIGATE permission on this folder to see
        # the children.
        if not self.access(PERM_NAVIGATE):
            raise PermissionDeniedError(
                "%s does not have permission to navigate folder %s" %
                (_request_username(), self.full_name))
        
        try:
            dao_node = _request_db_session().query(dao.Node).filter_by(
                parent_node_id=self._dao.node_id,
                node_name=child_name,
                is_active=1).one()
        except NoResultFound:
            raise FileNotFoundError(
                "Folder %r does not have a child named %r" %
                (self.full_name, child_name))
        
        return self._create_child_node_from_dao(dao_node)

    def _create_child_node_from_dao(self, dao_node):
        """\
node._create_child_node_from_dao(dao) -> FilesystemNode

Create a Filesystem node object from a DAO.  The default implementation
simply calls FilesystemNode._from_dao(); special folders may perform other
actions.
"""
        return FilesystemNode._from_dao(dao_node, parent=self)

    def _to_json(self):
        return {
            'class': self.__class__.__name__,
            'node_id': self.node_id,
            'name': self.name,
            'full_name': self.full_name,
            'path_components': self.path_components,
            'inherit_permissions': self.inherit_permissions,
        }

class Folder(FilesystemNode):
    def create_subfolder(self, name, inherit_permissions=True,
                         owner_user_id=None):
        """\
folder.create_subfolder(name, inherit_permissions=True, owner_user_id=None)
  -> Folder

Create a Folder within this folder.  The current user must have
PERM_CREATE_CHILD permissions within this folder.

The new folder grants PERM_ADMINISTRATE, PERM_NAVIGATE, PERM_LIST_CONTENTS,
PERM_CREATE_CHILD, PERM_DELETE_FOLDER, and PERM_DELETE_ANY_CHILD to the
owner_user_id (defaults to the current user).
"""
        if not self.access(PERM_CREATE_CHILD):
            raise PermissionDeniedError(
                "No permission to create child folders")

        if not isinstance(name, basestring):
            raise InvalidParameterError("Folder name must be a string")

        if len(name) == 0:
            raise InvalidParameterError("Folder name cannot be empty")

        if "/" in name:
            raise InvalidParameterError(
                "Folder name cannot contain '/' characters: %r" % name)

        if "\0" in name:
            raise InvalidParameterError(
                "Folder name cannot contain NUL characters: %r" % name)

        if owner_user_id is None:
            owner_user_id = _request_user_id()

        folder_dao = dao.Folder(node_type_id=dao.NODE_TYPE_ID_FOLDER,
                                parent_node_id=self._dao.node_id,
                                node_name=name,
                                is_active=True,
                                inherit_permissions=inherit_permissions)
        session = _request_db_session()
        session.add(folder_dao)
        session.flush()

        ace = dao.AccessControlEntry(user_id=owner_user_id,
                                     node_id=folder_dao.node_id,
                                     permissions=(PERM_ADMINISTRATE |
                                                  PERM_NAVIGATE |
                                                  PERM_LIST_CONTENTS |
                                                  PERM_CREATE_CHILD |
                                                  PERM_DELETE_FOLDER |
                                                  PERM_DELETE_ANY_CHILD))
        session.add(ace)
        session.flush()

        return FilesystemNode._from_dao(folder_dao, parent=self)

    def create_notepage(self, name, inherit_permissions=True,
                        owner_user_id=None):
        """\
folder.create_notepage(name, inherit_permissions=True, owner_user_id=None)
  -> Notepage

Create a Notepage within this folder.  The current user must have
PERM_CREATE_CHILD permissions within this folder.

The new notepage grants PERM_ADMINISTRATE, PERM_READ_DOCUMENT,
PERM_EDIT_DOCUMENT, and PERM_DELETE_DOCUMENT to the owner_user_id (defaults
to the current user).
"""
        if not self.access(PERM_CREATE_CHILD):
            raise PermissionDeniedError(
                "No permission to create child notepages")

        if not isinstance(name, basestring) or len(name) == 0:
            raise InvalidParameterError("Notepage name cannot be empty")

        if "/" in name:
            raise InvalidParameterError(
                "Notepage name cannot contain '/' characters: %r" % name)

        if "\0" in name:
            raise InvalidParameterError(
                "Notepage name cannot contain NUL characters: %r" % name)
        
        if owner_user_id is None:
            owner_user_id = _request_user_id()
        
        notepage_dao = dao.Notepage(node_type_id=dao.NODE_TYPE_ID_NOTEPAGE,
                                    parent_node_id=self._dao.node_id,
                                    node_name=name,
                                    is_active=True,
                                    inherit_permissions=inherit_permissions)
        session = _request_db_session()
        session.add(notepage_dao)
        session.flush()

        ace = dao.AccessControlEntry(user_id=owner_user_id,
                                     node_id=notepage_dao.node_id,
                                     permissions=(PERM_ADMINISTRATE |
                                                  PERM_READ_DOCUMENT |
                                                  PERM_EDIT_DOCUMENT |
                                                  PERM_DELETE_DOCUMENT))
        session.add(ace)
        session.flush()

        return FilesystemNode._from_dao(notepage_dao, parent=self)

    def _get_children(self):
        # The user must have PERM_NAVIGATE and PERM_LIST_CONTENTS permissions
        # on this folder to see the children.
        if not self.access(PERM_LIST_CONTENTS | PERM_NAVIGATE):
            raise PermissionDeniedError(
                "%s does not have permission to list folder %s" %
                (_request_username(), self.full_name))
        
        if not hasattr(self, "_children"):
            self._children = set()
            dao_nodes = (_request_db_session().query(dao.Node).filter_by(
                parent_node_id=self._dao.node_id,
                is_active=1).all())
            for dao_node in dao_nodes:
                child_node = self._create_child_node_from_dao(dao_node)
                self._children.add(child_node)
        return self._children

class Notepage(FilesystemNode):
    def _to_json(self):
        d = super(Notepage, self)._to_json()
        d['current_revision_id_sha256'] = self._dao.current_revision_id_sha256
        d['snap_to_grid'] = self._dao.snap_to_grid
        d['grid_x_um'] = self._dao.grid_x_um
        d['grid_y_um'] = self._dao.grid_y_um
        d['grid_x_subdivisions'] = self._dao.grid_x_subdivisions
        d['grid_y_subdivisions'] = self._dao.grid_y_subdivisions
        d['guides'] = [{'orientation': g.orientation,
                        'position_um': g.position_um}
                       for g in self._dao.guides]
        return d

    def create_note(self, x_pos_um=None, y_pos_um=None, width_um=None,
                    height_um=None):
        log.debug("notepage %r: create_note(x_pos_um=%r, y_pos_um=%r, "
                  "width_um=%r, height_um=%r)", self.full_name, x_pos_um,
                  y_pos_um, width_um, height_um)

        if (x_pos_um is not None and
            not isinstance(x_pos_um, (int, float, long))):
            log.error("create_note: invalid x_pos_um value %r", x_pos_um)
            raise InvalidParameterError("x_pos_um must be null or a number")

        if (y_pos_um is not None and
            not isinstance(y_pos_um, (int, float, long))):
            log.error("create_note: invalid x_pos_um value %r", x_pos_um)
            raise InvalidParameterError("y_pos_um must be null or a number")

        if (x_pos_um is None and y_pos_um is not None):
            log.error("create_note: y_pos_um is not None when x_pos_um is "
                      "None")
            raise InvalidParameterError("y_pos_um must be null if x_pos_um is "
                                        "null")
        
        if (x_pos_um is not None and y_pos_um is None):
            log.error("create_note: x_pos_um is not None when y_pos_um is "
                      "None")
            raise InvalidParameterError("x_pos_um must be null if y_pos_um is "
                                        "null")

        if (width_um is not None and
            not isinstance(width_um, (int, float, long))):
            log.error("create_note: invalid width_um value %r", width_um)
            raise InvalidParameterError("width_um must be null or a number")

        if (height_um is not None and
            not isinstance(height_um, (int, float, long))):
            log.error("create_note: invalid height_um value %r", height_um)
            raise InvalidParameterError("height_um must be null or a number")

        if not self.access(PERM_EDIT_DOCUMENT):
            raise PermissionDeniedError("No permission to edit notepage %s" %
                                        notepage_name)
        
        if width_um is None:
            width_um = DEFAULT_NOTE_WIDTH
        if height_um is None:
            height_um = DEFAULT_NOTE_HEIGHT
 
        if x_pos_um is None or y_pos_um is None:
            x_pos_um, y_pos_um = self._calculate_note_position()

        # The z-index will be one greater than all other note z-index values.
        try:
            z_index = 1 + max([child.z_index for child in self.children])
        except ValueError:
            # No children
            z_index = 0

        # Use a random UUID for the name
        note_name = str(random_uuid())
        note_dao = dao.Note(node_type_id=dao.NODE_TYPE_ID_NOTE,
                            parent_node_id=self._dao.node_id,
                            node_name=note_name,
                            is_active=True,
                            inherit_permissions=True,
                            contents_markdown="",
                            contents_hash_sha256=None,
                            x_pos_um=0,
                            y_pos_um=0,
                            width_um=DEFAULT_NOTE_WIDTH,
                            height_um=DEFAULT_NOTE_HEIGHT,
                            z_index=z_index)

        # We need to create the note object first without flushing the DAO
        # so we can compute its hash.
        note = FilesystemNode._from_dao(note_dao, parent=self)
        note.calculate_contents_hash_sha256()

        # Now we add the DAO
        note.write()

        # Invalidate our cache of children, if present.
        if hasattr(self, "_children"):
            del self._children

        return note

    @property
    def bounding_box(self):
        children = self.children
        if len(children) == 0:
            return (0, 0, 0, 0)

        first_child = children[0]
        left = first_child.x_pos_um
        top = first_child.y_pos_um
        right = left + first_child.width_um
        bottom = top + first_child.height_um

        for child in children[1:]:
            if child.x_pos_um < left:
                left = child.x_pos_um
            if child.y_pos_um < top:
                top = child.y_pos_um
            if child.x_pos_um + child.width_um > right:
                right = child.x_pos_um + child.width_um
            if child.y_pos_um + child.height_um > bottom:
                bottom = child.y_pos_um + child.height_um

        return (left, top, bottom, right)
        
    def _calculate_note_position(self):
        # By sorting the children by position, we can do a single loop through
        # the list of children (since we're always moving right+down) and not
        # perform a "while not changed" outer loop.  This changes the test from
        # a potention O(n^2) worst case to O(n) guaranteed case.
        children = sorted(
            self.children,
            key=lambda child: (child.x_pos_um, child.y_pos_um, child.name))
        x = y = 0

        for child in children:
            # Will we interfere with this child?
            if (x - NOTE_SPACING <= child.x_pos_um <= x + NOTE_SPACING and
                y - NOTE_SPACING <= child.y_pos_um <= y + NOTE_SPACING):
                # Yes; move down and to the right and try again.
                x += NOTE_SPACING
                y += NOTE_SPACING

        return (x, y)

    def _get_children(self):
        # The user must have PERM_READ_DOCUMENT permission on this notepage
        # to see the children.
        if not self.access(PERM_READ_DOCUMENT):
            raise PermissionDeniedError(
                "%s does not have permission to read notepage %s" %
                (_request_username(), self.full_name))
        
        if not hasattr(self, "_children"):
            self._children = set()
            dao_nodes = (_request_db_session().query(dao.Node).filter_by(
                parent_node_id=self._dao.node_id,
                is_active=1).all())
            for dao_node in dao_nodes:
                child_node = self._create_child_node_from_dao(dao_node)
                self._children.add(child_node)
        return self._children

class Note(FilesystemNode):
    def _to_json(self):
        d = super(Note, self)._to_json()
        d['z_index'] = self.z_index
        d['contents_markdown'] = self.contents_markdown
        d['x_pos_um'] = self.x_pos_um
        d['y_pos_um'] = self.y_pos_um
        d['width_um'] = self.width_um
        d['height_um'] = self.height_um
        return d

    def _get_z_index(self):
        return self._dao.z_index
    def _set_z_index(self, value):
        if not isinstance(value, (int, long, float)):
            raise InvalidParameterError("z_index must be a number")
        self._dao.z_index = int(value)
        self._dao.contents_hash_sha256 = None
        return
    z_index = property(_get_z_index, _set_z_index)

    def _get_contents_markdown(self):
        return self._dao.contents_markdown
    def _set_contents_markdown(self, value):
        if not isinstance(value, basestring):
            raise InvalidParameterError("contents_markdown must be a string")
        self._dao.contents_markdown = value
        self._dao.contents_hash_sha256 = None
        return
    contents_markdown = property(_get_contents_markdown,
                                 _set_contents_markdown)
    
    def _get_contents_hash_sha256(self):
        return self._dao.contents_hash_sha256

    def calculate_contents_hash_sha256(self):
        hasher = sha256()
        # Start by hashing the content length and content
        hasher.update(pack("<i", len(self.contents_markdown)))
        hasher.update(self.contents_markdown)

        # And the x/y pos, width, height, and z-index
        hasher.update(pack("<qqqqi", self.x_pos_um, self.y_pos_um,
                           self.width_um, self.height_um, self.z_index))

        # FIXME: Add in display preferences
        digest = hasher.hexdigest()
        self._dao.contents_hash_sha256 = digest
        return digest

    def _get_x_pos_um(self):
        return self._dao.x_pos_um
    def _set_x_pos_um(self, value):
        if not isinstance(value, (int, long, float)):
            raise InvalidParameterError("x_pos_um must be a number")

        self._dao.x_pos_um = int(value)
        self._dao.contents_hash_sha256 = None
        return
    x_pos_um = property(_get_x_pos_um, _set_x_pos_um)

    def _get_y_pos_um(self):
        return self._dao.y_pos_um
    def _set_y_pos_um(self, value):
        if not isinstance(value, (int, long, float)):
            raise InvalidParameterError("y_pos_um must be a number")

        self._dao.y_pos_um = int(value)
        self._dao.contents_hash_sha256 = None
        return
    y_pos_um = property(_get_y_pos_um, _set_y_pos_um)

    def _get_width_um(self):
        return self._dao.width_um
    def _set_width_um(self, value):
        if not isinstance(value, (int, long, float)):
            raise InvalidParameterError("width_um must be a number")

        self._dao.width_um = int(value)
        self._dao.contents_hash_sha256 = None
        return
    width_um = property(_get_width_um, _set_width_um)

    def _get_height_um(self):
        return self._dao.height_um
    def _set_height_um(self, value):
        if not isinstance(value, (int, long, float)):
            raise InvalidParameterError("height_um must be a number")

        self._dao.height_um = int(value)
        self._dao.contents_hash_sha256 = None
        return
    height_um = property(_get_height_um, _set_height_um)

    def write(self):
        # The user must have PERM_EDIT_DOCUMENT permission on the notepage.
        if not self.parent.access(PERM_EDIT_DOCUMENT):
            raise PermissionDeniedError(
                "%s does not have permission to edit notepage %s" %
                (_request_username(), self.parent.full_name))
        
        self.calculate_contents_hash_sha256()
        session = _request_db_session()
        session.add(self._dao)
        session.flush()
        return
        

# Local variables:
# mode: Python
# tab-width: 8
# indent-tabs-mode: nil
# End:
# vi: set expandtab tabstop=8
