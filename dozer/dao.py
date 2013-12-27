from __future__ import absolute_import, print_function
from base64 import b64decode
from json import JSONEncoder
from logging import getLogger
import re
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import backref, composite, mapper, relationship
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm.session import object_session
from sqlalchemy.schema import (
    CheckConstraint, Column, ForeignKey, ForeignKeyConstraint, Index, MetaData,
    PrimaryKeyConstraint, Table, UniqueConstraint,
)
from sqlalchemy.types import Boolean, DateTime, CHAR, Integer, String, Text
from time import time
from urllib import quote_plus
from uuid import uuid4 as random_uuid

Base = declarative_base()

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

class UserDomain(Base):
    __tablename__ = "dz_user_domains"

    user_domain_id = Column(Integer, primary_key=True, nullable=False,
                            autoincrement=True)
    display_name = Column(String(32), nullable=False)
    description = Column(String(1000), nullable=False)
    domain_config = Column(Text, nullable=True)

NODE_TYPE_ID_FOLDER = 0
NODE_TYPE_ID_NOTEPAGE = 1
NODE_TYPE_ID_NOTE = 2

class NodeType(Base):
    __tablename__ = "dz_node_types"

    node_type_id = Column(Integer, primary_key=True, nullable=False,
                          autoincrement=True)
    node_type_name = Column(String(32), nullable=False)

class User(Base):
    __tablename__ = "dz_users"

    user_id = Column(Integer, primary_key=True, nullable=False,
                     autoincrement=True)
    user_domain_id = Column(Integer,
                            ForeignKey('dz_user_domains.user_domain_id'),
                            nullable=False)
    user_name = Column(String(256), nullable=True)
    home_folder = Column(String(256), nullable=True)
    display_name = Column(String(256), nullable=True)
    password_pbkdf2 = Column(CHAR(256), nullable=True)
    is_group = Column(Boolean, nullable=False)
    is_administrator = Column(Boolean, nullable=False)

    user_domain = relationship('UserDomain')

    __table_args__ = (
        UniqueConstraint("user_domain_id", "user_name"),
    )
    
    def __repr__(self):
        return ("<User user_id=%r user_domain_id=%r user_name=%r "
                "display_name=%r>" % (self.user_id, self.user_domain_id,
                                      self.user_name, self.display_name))
Index('i_dz_usr_domname', User.user_domain_id, User.user_name)

class LocalGroupMember(Base):
    __tablename__ = "dz_local_group_members"

    group_id = Column(Integer, ForeignKey('dz_users.user_id'), nullable=False)
    user_id = Column(Integer, ForeignKey('dz_users.user_id'), nullable=False)
    administrator = Column(Boolean, nullable=False)

    user = relationship("User", primaryjoin=(user_id==User.user_id),
                        remote_side=(User.user_id,),
                        backref="groups")
    group = relationship("User", primaryjoin=(group_id==User.user_id),
                         remote_side=(User.user_id,),
                         backref="group_members")
    
    __table_args__ = (
        PrimaryKeyConstraint("group_id", "user_id"),
    )
Index("i_dz_lgm_user_group", LocalGroupMember.user_id,
      LocalGroupMember.group_id)

class Node(Base):
    __tablename__ = "dz_nodes"

    node_id = Column(Integer, nullable=False, primary_key=True,
                     autoincrement=True)
    node_type_id = Column(Integer, ForeignKey('dz_node_types.node_type_id'),
                          nullable=False)
    parent_node_id = Column(Integer, ForeignKey('dz_nodes.node_id'),
                            nullable=True)
    node_name = Column(String(64), nullable=False)
    is_active = Column(Boolean, nullable=False)
    inherit_permissions = Column(Boolean, nullable=False)

    @property
    def full_name(self):
        if self.parent is not None:
            parent_full_name = self.parent.full_name
            if parent_full_name == "/":
                return "/" + self.node_name
            else:
                return parent_full_name + "/" + self.node_name
        else:
            return "/"

    @property
    def relurl(self):
        if self.parent is not None:
            node_suburl = quote_plus(self.node_name.encode("utf-8"))
            parent_relurl = self.parent.relurl
            if parent_relurl == "/":
                return "/" + node_suburl
            else:
                return parent_relurl + "/" + node_suburl
        else:
            return "/"
            

    parent = relationship(
        "Node",
        primaryjoin=(parent_node_id==node_id),
        remote_side=(node_id,),
        backref="children")

    __table_args__ = (
        UniqueConstraint("parent_node_id", "node_name"),
    )

    __mapper_args__ = {
        'polymorphic_on': node_type_id,
    }

    def __repr__(self):
        return ("<%s node_id=%r node_type_id=%r parent_node_id=%r "
                "node_name=%r is_active=%r inherit_permissions=%r>" % (
                    self.__class__.__name__, self.node_id, self.node_type_id,
                    self.parent_node_id, self.node_name, self.is_active,
                    self.inherit_permissions))
Index("i_dz_node_parent_id", Node.parent_node_id, Node.node_name)

class AccessControlEntry(Base):
    __tablename__ = "dz_access_control_entries"

    node_id = Column(Integer, ForeignKey("dz_nodes.node_id"), nullable=False)
    user_id = Column(Integer, ForeignKey("dz_users.user_id"), nullable=False)
    permissions = Column(Integer, nullable=False)
    
    node = relationship("Node", backref="permissions")
    user = relationship("User")

    __table_args__ = (
        PrimaryKeyConstraint("node_id", "user_id"),
    )
Index("i_dz_ace_userid", AccessControlEntry.user_id,
      AccessControlEntry.node_id)

class NoteDisplayPref(Base):
    __tablename__ = "dz_note_display_prefs"

    node_id = Column(Integer, ForeignKey('dz_nodes.node_id'), nullable=False)
    hashtag = Column(String(256), nullable=True)
    width_um = Column(Integer, nullable=True)
    height_um = Column(Integer, nullable=True)
    background_color = Column(String(32), nullable=True)
    font_family = Column(String(256), nullable=True)
    font_size_millipt = Column(Integer, nullable=True)
    font_weight = Column(String(32), nullable=True)
    font_slant = Column(String(32), nullable=True)
    font_color = Column(String(32), nullable=True)

    node = relationship("Node", backref="display_prefs")

    __table_args__ = (
        PrimaryKeyConstraint("node_id", "hashtag"),
    )

class Folder(Node):
    __tablename__ = "dz_folders"

    node_id = Column(Integer, ForeignKey('dz_nodes.node_id'),
                     nullable=False, primary_key=True)
    
    __mapper_args__ = {
        'polymorphic_identity': NODE_TYPE_ID_FOLDER,
    }

    def __repr__(self):
        return ("<Folder node_id=%r node_name=%r>" %
                (self.node_id, self.node_name))

class Notepage(Node):
    __tablename__ = "dz_notepages"

    node_id = Column(Integer, ForeignKey('dz_nodes.node_id'), nullable=False,
                     primary_key=True)
    current_revision_id_sha256 = Column(CHAR(64), nullable=True)
    snap_to_grid = Column(Boolean, nullable=True)
    grid_x_um = Column(Integer, nullable=True)
    grid_y_um = Column(Integer, nullable=True)
    grid_x_subdivisions = Column(Integer, nullable=True)
    grid_y_subdivisions = Column(Integer, nullable=True)

    __table_args__ = (
        CheckConstraint("grid_x_um IS NULL OR grid_x_um > 0"),
        CheckConstraint("grid_y_um IS NULL OR grid_y_um > 0"),
        CheckConstraint("grid_x_subdivisions IS NULL OR "
                        "grid_x_subdivisons > 0"),
        CheckConstraint("grid_y_subdivisions IS NULL OR "
                        "grid_y_subdivisons > 0"),
    )

    __mapper_args__ = {
        'polymorphic_identity': NODE_TYPE_ID_NOTEPAGE,
    }

class NotepageGuide(Base):
    __tablename__ = "dz_notepage_guides"
    
    node_id = Column(Integer, ForeignKey('dz_notepages.node_id'),
                     nullable=False, primary_key=True)
    orientation = Column(CHAR(1), nullable=False)
    position_um = Column(Integer, nullable=False)
    
    notepage = relationship("Notepage", backref="guides")

    __table_args__ = (
        CheckConstraint("orientation IN ('H', 'V')"),
    )

class NotepageRevision(Base):
    __tablename__ = "dz_notepage_revisions"

    node_id = Column(Integer, ForeignKey('dz_notepages.node_id'),
                     nullable=False)
    revision_id_sha256 = Column(CHAR(64), nullable=False)
    previous_revision_id_sha256 = Column(
        CHAR(64), ForeignKey('dz_notepage_revisions.revision_id_sha256'),
        nullable=True)
    delta_to_previous = Column(Text, nullable=True)
    editor_user_id = Column(Integer, nullable=False)
    edit_time_utc = Column(DateTime, nullable=True)

    notepage = relationship("Notepage", backref='revisions')
    previous_revision = relationship('NotepageRevision')
    
    __table_args__ = (
        PrimaryKeyConstraint("node_id", "revision_id_sha256"),
        UniqueConstraint("node_id", "previous_revision_id_sha256"),
    )
Index("i_dz_nprev_prev", NotepageRevision.node_id,
      NotepageRevision.previous_revision_id_sha256)

class Note(Node):
    __tablename__ = "dz_notes"

    node_id = Column(Integer, ForeignKey('dz_nodes.node_id'), nullable=False,
                     primary_key=True)
    on_top_of_node_id = Column(Integer,
                               ForeignKey('dz_notes.node_id'),
                               nullable=True)
    contents_markdown = Column(Text, nullable=True)
    contents_hash_sha256 = Column(CHAR(64), nullable=True)
    x_pos_um = Column(Integer, nullable=False)
    y_pos_um = Column(Integer, nullable=False)

    on_top_of_node = relationship(
        "Note",
        primaryjoin=(on_top_of_node_id==node_id))

    __mapper_args__ = {
        'polymorphic_identity': NODE_TYPE_ID_NOTE,
    }

class NoteHashtag(Base):
    __tablename__ = "dz_note_hashtags"

    node_id = Column(Integer, ForeignKey('dz_notes.node_id'), nullable=False)
    hashtag = Column(String(256), nullable=False)
    
    note = relationship("Note", backref="hashtags")

    __table_args__ = (
        PrimaryKeyConstraint("node_id", "hashtag"),
    )

class Session(Base):
    __tablename__ = "dz_sessions"

    session_id = Column(CHAR(64), nullable=False, primary_key=True)
    user_id = Column(Integer, ForeignKey('dz_users.user_id'), nullable=False)
    established_time_utc = Column(DateTime, nullable=False)
    last_ping_time_utc = Column(DateTime, nullable=False)

    user = relationship("User", backref="sessions")
Index("i_dz_sess_uid", Session.user_id, Session.last_ping_time_utc.desc())

class SessionSecret(Base):
    __tablename__ = "dz_session_secrets"

    session_secret_id = Column(Integer, nullable=False, primary_key=True,
                               autoincrement=True)
    secret_key_base64 = Column(CHAR(44), nullable=False)
    valid_from_utc = Column(DateTime, nullable=False)
    accept_until_utc = Column(DateTime, nullable=True)

    @property
    def secret_key(self):
        return b64decode(self.secret_key_base64)
Index("i_dz_ssec_valid", SessionSecret.valid_from_utc.desc())

class SessionNotepage(Base):
    __tablename__ = "dz_session_notepages"

    session_id = Column(CHAR(64), ForeignKey('dz_sessions.session_id'),
                        nullable=False)
    node_id = Column(Integer, nullable=False)
    revision_id_sha256 = Column(CHAR(64), nullable=False)

    session = relationship("Session", backref="notepages")
    
    __table_args__ = (
        PrimaryKeyConstraint("session_id", "node_id"),
        ForeignKeyConstraint(
            ["node_id", "revision_id_sha256"],
            ["dz_notepage_revisions.node_id",
             "dz_notepage_revisions.revision_id_sha256"]),
    )
