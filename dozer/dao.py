from __future__ import absolute_import, print_function
from json import JSONEncoder
from logging import getLogger
import re
from sqlalchemy import Column, DateTime, ForeignKey, Integer, MetaData, String, Table, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import backref, composite, mapper, relationship
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm.session import object_session
from sqlalchemy.schema import ForeignKeyConstraint, UniqueConstraint
from time import time
from uuid import uuid4 as random_uuid

Base = declarative_base()

class DatabaseSchemaError(RuntimeError):
    pass

class InvalidDocumentPermissionsError(RuntimeError):
    pass

class InvalidDocumentTypeError(RuntimeError):
    pass

log = getLogger("dozer.dao")

def to_bool(x):
    if isinstance(x, bool):
        return x
    else:
        return x.lower()[:1] in ("y", "t", "1")

def from_bool(x):
    if isinstance(x, basestring):
        if x.lower()[:1] in ('n', 'f', '0'):
            return 'N'
        else:
            return 'Y'
    else:
        return 'Y' if x else 'N'

def to_prim(obj):
    if isinstance(obj, dict):
        result = {}
        for key, value in obj.iteritems():
            result[key] = value
    elif isinstance(obj, (list, tuple)):
        result = []
        for el in obj:
            result.append(to_prim(el))
    elif isinstance(obj, (int, long, float, basestring)):
        return obj

    try:
        return obj.to_prim()
    except AttributeError:
        raise TypeError("Object %r cannot be converted to a primitive")

class JSONObjectEncoder(JSONEncoder):
    def default(self, obj):
        return to_prim(obj)
    
class Entity(object):
    def __init__(self, entity_domain, entity_id=None):
        super(Entity, self).__init__()
        self.entity_domain = entity_domain
        self.entity_id = entity_id
        return

    def __composite_values__(self):
        return (self.entity_domain, self.entity_id)

    def __repr__(self):
        return (self.entity_domain + "/" +
                (self.entity_id if self.entity_id is not None else "*"))

    def __eq__(self, other):
        return (isinstance(other, Entity) and
                self.entity_domain == other.entity_domain and
                self.entity_id == other.entity_id)

    def __ne__(self, other):
        return not self.__eq__(other)

    def to_prim(self):
        return {'entity_domain': self.entity_domain,
                'entity_id': self.entity_id}

    @classmethod
    def from_prim(cls, prim):
        return cls(entity_domain=prim.get('entity_domain'),
                   entity_id=prim.get('entity_id'))

class Point(object):
    def __init__(self, x, y):
        super(Point, self).__init__()
        self.x = x
        self.y = y
        return

    def __composite_values__(self):
        return (self.x, self.y)

    def __repr__(self):
        return "Point(%r, %r)" % (self.x, self.y)

    def __eq__(self, other):
        return (isinstance(other, Point) and
                self.x == other.x and
                self.y == other.y)
    
    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        return (self.x < other.x or
                (self.x == other.x and self.y < other.y))

    def __le__(self, other):
        return (self.x < other.x or
                (self.x == other.x and self.y <= other.y))
    
    def __gt__(self, other):
        return not self.__le__(other)

    def __ge__(self, other):
        return not self.__lt__(other)

    def to_prim(self):
        return (self.x, self.y)

    @classmethod
    def from_prim(cls, prim):
        return cls(prim[0], prim[1])

class Dimension(object):
    def __init__(self, width, height):
        super(Dimension, self).__init__()
        self.width = width
        self.height = height
        return

    def __composite_values__(self):
        return (self.width, self.height)

    def __repr__(self):
        return "Dimension(%r, %r)" % (self.width, self.height)

    def __eq__(self, other):
        return (isinstance(other, Dimension) and
                self.width == other.width and
                self.height == other.height)
    
    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        return (self.width < other.width or
                (self.width == other.width and self.height < other.height))

    def __le__(self, other):
        return (self.width < other.width or
                (self.width == other.width and self.height <= other.height))
    
    def __gt__(self, other):
        return not self.__le__(other)

    def __ge__(self, other):
        return not self.__lt__(other)

    def to_prim(self):
        return (self.width, self.height)

    @classmethod
    def from_prim(cls, prim):
        return cls(prim[0], prim[1])

class Style(object):
    def __init__(self, background_color=None, font_family=None,
                 font_size_millipt=None, font_weight=None, font_slant=None,
                 font_color=None):
        super(Style, self).__init__()
        self.background_color = background_color
        self.font_family = font_family
        self.font_size_millipt = font_size_millipt
        self.font_weight = font_weight
        self.font_slant = font_slant
        self.font_color = font_color
        return

    def __composite_values__(self):
        return (self.background_color, self.font_family,
                self.font_size_millipt, self.font_weight, self.font_slant,
                self.font_color,)

    def __repr__(self):
        attrs = []
        if self.background_color is not None:
            attrs.append("background_color=%r" % (self.background_color,))
        if self.font_family is not None:
            attrs.append("font_family=%r" % (self.font_family,))
        if self.font_size_millipt is not None:
            attrs.append("font_size_millipt=%r" % (self.font_size_millipt,))
        if self.font_weight is not None:
            attrs.append("font_weight=%r" % (self.font_weight,))
        if self.font_slant is not None:
            attrs.append("font_slant=%r" % (self.font_slant,))
        if self.font_color is not None:
            attrs.append("font_color=%r" % (self.font_color,))
        return "Style(%s)" % (",".join(attrs),)

    def __eq__(self, other):
        return (isinstance(other, Style) and
                self.background_color == other.background_color and
                self.font_family == other.font_family and
                self.font_size_millipt == other.font_size_millipt and
                self.font_weight == other.font_weight and
                self.font_slant == other.font_slant and
                self.font_color == other.font_color)

    def __ne__(self, other):
        return not self.__eq__(other)

    def to_prim(self):
        attrs = {}
        if self.background_color is not None:
            attrs["background_color"] = self.background_color
        if self.font_family is not None:
            attrs["font_family"] = self.font_family
        if self.font_size_millipt is not None:
            attrs["font_size_millipt"] = self.font_size_millipt
        if self.font_weight is not None:
            attrs["font_weight"] = self.font_weight
        if self.font_slant is not None:
            attrs["font_slant"] = self.font_slant
        if self.font_color is not None:
            attrs["font_color"] = self.font_color
        return attrs

    @classmethod
    def from_prim(cls, prim):
        return cls(background_color=prim.get("background_color"),
                   font_family=prim.get("font_family"),
                   font_size_millipt=prim.get("font_size_millipt"),
                   font_weight=prim.get("font_weight"),
                   font_slant=prim.get("font_slant"),
                   font_color=prim.get("font_color"))

class EntityDomain(Base):
    __tablename__ = "dz_entity_domains"

    entity_domain = Column(String(32), primary_key=True)
    display_name = Column(String(32), nullable=False)
    description = Column(String(1000), nullable=False)

metadata = MetaData()

class Document(Base):
    __tablename__ = "dz_documents"

    def __init__(self, *args, **kw):
        kw['_inherit_permissions'] = from_bool(
            kw.pop("inherit_permissions", False))
        super(Document, self).__init__(*args, **kw)
        return
    
    document_id = Column(Integer, primary_key=True, autoincrement=True)
    parent_document_id = Column(Integer)
    document_type = Column(String(16), nullable=False)
    document_name = Column(String(64), nullable=False)
    owner_entity_domain = Column(String(32), nullable=False)
    owner_entity_id = Column(String(256))
    owner = composite(Entity, owner_entity_domain, owner_entity_id)
    _inherit_permissions = Column("inherit_permissions", String(1),
                                  nullable=False)

    def get_inherit_permissions(self):
        return to_bool(self._inherit_permissions)
    def set_inherit_permissions(self, value):
        self._inherit_permissions = from_bool(value)
    inherit_permissions = property(
        get_inherit_permissions, set_inherit_permissions)

    parent = relationship('Document',
                          foreign_keys=[parent_document_id],
                          remote_side=[document_id],
                          backref="children")

    def get_full_name(self):
        if self.parent_document_id is not None:
            return self.parent.full_name + "/" + self.document_name
        else:
            return self.document_name

    full_name = property(get_full_name)

    __table_args__ = (
        UniqueConstraint("parent_document_id", "document_name"),
        ForeignKeyConstraint(['owner_entity_domain'],
                             ['dz_entity_domains.entity_domain']),
        ForeignKeyConstraint(['parent_document_id'],
                             ['dz_documents.document_id']),
    )

    def __repr__(self):
        return ("Document(document_id=%r, parent_document_id=%r, "
                "document_type=%r, document_name=%r, owner=%r, "
                "inherit_permissions=%r)" %
                (self.document_id, self.parent_document_id, self.document_type,
                 self.document_name, self.owner, self.inherit_permissions))

    def to_prim(self):
        return {'document_id': self.document_id,
                'parent_document_id': self.parent_document_id,
                'document_type': self.document_type,
                'document_name': self.document_name,
                'owner': self.owner,
                'inherit_permissions': self.inherit_permissions,
                'permissions': self.permissions,
                'notes': self.notes,
                'display_prefs': self.display_prefs}

class DocumentPermission(Base):
    __tablename__ = "dz_document_permissions"
    
    document_id = Column(Integer, ForeignKey('dz_documents.document_id'),
                         primary_key=True)
    list_index = Column(Integer, primary_key=True)
    entity_domain = Column(String(32),
                           ForeignKey('dz_entity_domains.entity_domain'),
                           nullable=False)
    entity_id = Column(String(256), nullable=True)
    permissions = Column(String(32))

    entity = composite(Entity, entity_domain, entity_id)
    document = relationship('Document',
                            backref=backref('permissions', order_by=list_index))

    __table_args__ = (
        UniqueConstraint("document_id", "entity_domain", "entity_id"),
    )

    def __repr__(self):
        return ("DocumentPermission(document_id=%r, list_index=%r, entity=%r, "
                "permissions=%r)" % (
                self.document_id, self.list_index, self.entity,
                self.permissions))

    def to_prim(self):
        return {'entity': self.entity,
                'permissions': self.permissions}

class DocumentDisplayPrefs(Base):
    __tablename__ = "dz_document_display_prefs"
    
    document_id = Column(Integer, ForeignKey("dz_documents.document_id"),
                         primary_key=True)
    _width = Column("width_pixels", Integer)
    _height = Column("height_pixels", Integer)
    _background_color = Column("background_color", String(32))
    _font_family = Column("font_family", String(256))
    _font_size_millipt = Column("font_size_millipt", Integer)
    _font_weight = Column("font_weight", String(32))
    _font_slant = Column("font_slant", String(32))
    _font_color = Column("font_color", String(32))    

    size = composite(Dimension, _width, _height)
    style = composite(Style, _background_color, _font_family,
                      _font_size_millipt, _font_weight, _font_slant,
                      _font_color)

    document = relationship("Document",
                            backref=backref("display_prefs"))

    def __repr__(self):
        return ("DocumentDisplayPrefs(document_id=%r, size=%r, style=%r)" %
                (self.document_id, self.size, self.style))

    def to_prim(self):
        return {'size': self.size,
                'style': self.style}

class DocumentHashtagPrefs(Base):
    __tablename__ = "dz_document_hashtag_prefs"
    
    document_id = Column(Integer, ForeignKey("dz_documents.document_id"),
                         primary_key=True)
    list_index = Column(Integer, primary_key=True)
    hashtag = Column(String(256))
    _background_color = Column("background_color", String(32))
    _font_family = Column("font_family", String(256))
    _font_size_millipt = Column("font_size_millipt", Integer)
    _font_weight = Column("font_weight", String(32))
    _font_slant = Column("font_slant", String(32))
    _font_color = Column("font_color", String(32))    

    style = composite(Style, _background_color, _font_family,
                      _font_size_millipt, _font_weight, _font_slant,
                      _font_color)

    document = relationship("Document",
                            backref=backref("hashtag_prefs",
                                            order_by=list_index))

    __table_args__ = (
        UniqueConstraint("document_id", "hashtag"),
    )

    def __repr__(self):
        return ("DocumentHashtagPrefs(document_id=%r, list_index=%r, "
                "hashtag=%r, style=%r)" %
                (self.document_id, self.list_index, self.hashtag, self.style))

    def to_prim(self):
        return {'hashtag': self.hashtag,
                'style': self.style}

class SessionDocument(Base):
    __tablename__ = "dz_session_documents"
    
    session_id = Column(Integer, primary_key=True)
    document_id = Column(Integer, primary_key=True)
    revision_id = Column(Integer)

    __table_args__ = (
        ForeignKeyConstraint(['session_id'],
                             ['dz_sessions.session_id']),
        ForeignKeyConstraint(['document_id', 'revision_id'],
                             ['dz_document_revisions.document_id',
                              'dz_document_revisions.revision_id']),
    )

class DocumentRevision(Base):
    __tablename__ = "dz_document_revisions"

    document_id = Column(Integer, primary_key=True)
    revision_id = Column(Integer, primary_key=True)
    delta_to_previous = Column(Text)
    _editor_entity_domain = Column(String(32), nullable=False)
    _editor_entity_id = Column(String(256), nullable=True)
    edit_time = Column(DateTime, nullable=False)

    editor = composite(Entity, _editor_entity_domain, _editor_entity_id)

class Session(Base):
    __tablename__ = "dz_sessions"

    session_id = Column(Integer, primary_key=True)
    _user_entity_domain = Column(String(32), nullable=False)
    _user_entity_id = Column(String(256))
    established_time_utc = Column(DateTime, nullable=False)
    last_ping_time_utc = Column(DateTime, nullable=False)

    user = composite(Entity, _user_entity_domain, _user_entity_id)

class Note(Base):
    __tablename__ = "dz_notes"

    note_id = Column(Integer, primary_key=True)
    document_id = Column(Integer, nullable=False)
    contents_markdown = Column(Text)
    _x_pos = Column("x_pos_pixels", Integer, nullable=False)
    _y_pos = Column("y_pos_pixels", Integer, nullable=False)
    pos_pixels = composite(Point, _x_pos, _y_pos)
    _width = Column("width_pixels", Integer, nullable=False)
    _height = Column("height_pixels", Integer, nullable=False)
    size_pixels = composite(Dimension, _width, _height)
    _background_color = Column("background_color", String(32))
    _font_family = Column("font_family", String(256))
    _font_size_millipt = Column("font_size_millipt", Integer)
    _font_weight = Column("font_weight", String(32))
    _font_slant = Column("font_slant", String(32))
    _font_color = Column("font_color", String(32))
    style = composite(Style, _background_color, _font_family,
                      _font_size_millipt, _font_weight, _font_slant,
                      _font_color)

    document = relationship('Document',
                            backref=backref("notes"))
    __table_args__ = (
        ForeignKeyConstraint(['document_id'],
                             ['dz_documents.document_id']),
    )

    def to_prim(self):
        return {'note_id': self.note_id,
                'contents_markdown': self.contents_markdown,
                'pos_pixels': self.pos_pixels,
                'size_pixels': self.size_pixels,
                'style': self.style}

class NoteHashtag(Base):
    __tablename__ = "dz_note_hashtags"
    
    note_id = Column(Integer, primary_key=True)
    hashtag = Column(String(256), primary_key=True)

    note = relationship('Note', foreign_keys=[note_id], backref='hashtags')

    __table_args__ = (
        ForeignKeyConstraint(['note_id'],
                             ['dz_notes.note_id']),
    )

    def to_prim(self):
        return self.hashtag


def check_permissions(document, owner=None, document_type=None,
                      permissions=None, inherit_permissions=None):
    if (document_type is not None and
        document_type != document.document_type):
        raise InvalidDocumentTypeError(
            "Expected %r to be a %s instead of %s" %
            (document.document_name, document_type, document.document_type))

    if owner is not None and document.owner != owner:
        raise InvalidDocumentPermissionsError(
            "Incorrect ownership for %r: expected %s instead of %s" %
            (document.document_name, owner, document.owner))

    if permissions is not None:
        doc_permissions = sorted(document.permissions,
                                 key=lambda dp: dp.list_index)
        if len(permissions) != len(doc_permissions):
            raise InvalidDocumentPermissionsError(
                "Expected %d permissions for %r instead of %d" %
                (len(permissions), document.document_name,
                 len(doc_permissions)))
        
        for i in xrange(len(permissions)):
            expected = permissions[i]
            actual = doc_permissions[i]
            
            if (expected.entity != actual.entity or
                expected.permissions != actual.permissions):
                raise InvalidDocumentPermissionsError(
                    "Incorrect permission %d for %r: expected %s instead "
                    "of %s" % (i, document.document_name, expected, actual))

    if (inherit_permissions is not None and
        to_bool(document.inherit_permissions) != to_bool(inherit_permissions)):
        if inherit_permissions:
            msg = "permissions are not inherited but should be"
        else:
            msg = "permissions are inherited but should not be"

        raise InvalidDocumentPermissionsError(
            "Incorrect permissions for %r: %s" % (
                document.document_name, msg))

    return True

def create_document(parent, document_name, owner=None, document_type='notepage',
                    permissions=None, inherit_permissions=None):
    assert parent is not None
    assert parent.document_id is not None
    document = Document(
        parent_document_id=parent.document_id,
        document_name=document_name,
        owner=owner if owner is not None else parent.owner,
        document_type=document_type,
        inherit_permissions=(
            inherit_permissions if inherit_permissions is not None
            else True))
    session = object_session(parent)
    session.add(document)
    session.flush()

    log.debug("Added document %r", document)

    assert document.document_id is not None

    if permissions is not None:
        for list_index, permission in enumerate(permissions):
            permission.document_id = document.document_id
            permission.list_index = list_index
            session.add(permission)

    session.flush()
    return document

def get_object(parent, document_name, owner=None, document_type=None,
               permissions=None, inherit_permissions=None, create=False):
    if "/" in document_name:
        raise ValueError("Document name cannot contain '/'")

    session = object_session(parent)

    try:
        document = object_session(parent).query(Document).filter_by(
            parent_document_id=parent.document_id,
            document_name=document_name).one()
        check_permissions(document, owner, document_type, permissions,
                          inherit_permissions)
        return document
    except NoResultFound:
        if not create:
            return None

    return create_document(parent, document_name, owner=owner,
                           document_type=document_type,
                           permissions=permissions,
                           inherit_permissions=inherit_permissions)

def get_object_by_path(session, path):
    """\
get_object_by_path(session, path) -> (object, path_remaining)

Find the object denoted by path.

If the document does not exist, None is returned along with the entire path.

If we find a document, it is returned along with the remaining unused path
elements.

If all objects encountered are folders, the object returned is the folder
referenced and the remaining path is None.
"""

    if not path.startswith("/"):
        log.info("path does not start with / -- returning null")
        return None

    path_elements = path[1:].split("/")
    obj = get_root_folder(session)

    for i, path_element in enumerate(path_elements):
        log.debug("get_object_by_path: obj.full_name=%s obj.document_type=%r "
                  "path_element=%r",
                  obj.full_name, obj.document_type, path_element)
        if path_element == '':
            log.debug("Skipping empty path element")
            continue

        child = get_document(obj, path_element)
        if child is None:
            log.info("%s does not have a child named %s" %
                     (doc.full_name, path_element))
            return (None, path)
        if child.document_type != 'folder':
            return (child, "/".join(path_elements[i+1:]))

        obj = child

    return (obj, "")

def get_root_folder(session):
    return session.query(Document).filter_by(
        parent_document_id=None,
        document_name="",
        owner_entity_domain="system",
        owner_entity_id="system",
        document_type='folder').one()

def get_temp_folder(session):
    root = get_root_folder(session)
    permissions = [
        DocumentPermission(document_id=None, list_index=0,
                           entity=Entity("users", None), permissions="N")
    ]
    tmp = get_object(root, "tmp", owner=Entity("system", "system"),
                     document_type="folder", permissions=permissions,
                     inherit_permissions=False, create=True)
    return tmp

def get_domain_temp_folder(session, domain):
    log.debug("get_domain_temp_folder(%r, %r)" % (session, domain))

    owner = Entity(domain, None)
    permissions = [
        DocumentPermission(
            document_id=None, list_index=0, entity=Entity("users", None),
            permissions="N"),
    ]
    tmp = get_temp_folder(session)
    dtf = get_object(
        tmp, document_name=domain, document_type='folder',
        owner=Entity('system', 'system'),
        inherit_permissions=False, permissions=permissions, create=True)
    assert not dtf.inherit_permissions
    log.debug("get_domain_temp_folder(%r, %r) -> %r" % (session, domain, dtf))
    return dtf

def get_user_temp_folder(session, owner):
    log.debug("get_user_temp_folder(%r, %r)" % (session, owner))
    domain_folder = get_domain_temp_folder(session, owner.entity_domain)

    if owner.entity_id is None:
        return domain_folder

    permissions = [
        DocumentPermission(
            document_id=None, list_index=0, entity=owner,
            permissions="ACDLNS"),
        DocumentPermission(
            document_id=None, list_index=1, entity=Entity("users", None),
            permissions=""),
    ]

    utf = get_object(domain_folder, document_name=owner.entity_id,
                     document_type="folder", permissions=permissions,
                     owner=owner, inherit_permissions=False, create=True)

    log.debug("get_user_temp_folder(%r, %r) -> %r" % (session, owner, utf))

    return utf

UNTITLED_NOTEPAGE_RE = re.compile(r"Untitled Notepage(?: ([0-9]+))?")
def create_temp_document(session, owner):
    folder = get_user_temp_folder(session, owner)
    assert folder is not None

    # Find the highest numbered "Untitled Notepage ##" document
    untitled_documents = (
        object_session(folder).query(Document.document_name)
        .filter(Document.document_name.like("Untitled Notepage%"))
        .filter(Document.parent_document_id == folder.document_id)
        .all())

    last_id = None
    for doc_name in untitled_documents:
        m = UNTITLED_NOTEPAGE_RE.match(doc_name)
        if m is None:
            log.error("Untitled notepage RE didn't match document named %r",
                      doc_name)
            continue

        if m.group(1) is None:
            my_id = 0
        else:
            my_id = int(m.group(1))

        last_id = my_id if last_id is None else max(last_id, my_id)

    if last_id is None:
        tmp_name = "Untitled Notepage"
    else:
        tmp_name = "Untitled Notepage %d" % (last_id + 1,)

    return create_document(folder, document_name=tmp_name,
                           owner=owner, document_type="notepage",
                           inherit_permissions=True)

def get_object_chain(session, target):
    result = [target]
    current = target.parent
    while current is not None:
        result.append(current)
        current = current.parent
    
    result.reverse()
    return result
