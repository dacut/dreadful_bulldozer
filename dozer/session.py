from __future__ import absolute_import, print_function
from base64 import b64decode, b64encode
from datetime import datetime
import dozer.dao as dao
import hashlib
import hmac
from logging import getLogger
import cherrypy
from cherrypy._cptools import Tool
from passlib.hash import pbkdf2_sha512

log = getLogger("dozer.session")

class UserSessionTool(Tool):
    """\
A tool for converting session data between tokenized HTTP cookies and
DAO objects.
"""
    def __init__(self, session_cookie_name="dzsession",
                 session_token_secret=None):
        super(UserSessionTool, self).__init__(
            point="before_handler", callable=self.__call__, name="UserSession",
            priority=80)
        if session_token_secret is None:
            with open("/dev/urandom", "rb") as fd:
                session_token_secret = fd.read(32)
        self.session_cookie_name = session_cookie_name
        self.session_token_secret = session_token_secret
        return

    def get_session_from_request(self):
        """\
Read the appropriate HTTP cookie header and decode the session.  If the session
data is valid, this will set cherrypy.serving.request.user_session to the
corresponding dozer.dao.Session object and cherrypy.serving.request.user to
the corresponding dozer.dao.User object.

If the session data is not valid, this will set those attributes to None.
"""
        request = cherrypy.serving.request

        request.user_session = None
        request.user = None

        session_token = request.cookie.get(self.session_cookie_name)
        if session_token is not None:
            user_session = self.get_session(session_token)
            if session is not None:
                request.user_session = user_session
                request.user = user_session.user
        return

    def get_session(self, session_token):
        """\
Convert a session token into a session object.

The session token is a base-64 encoded string composed of:
    A 4-byte version identifier ("stv1")
    A 44-byte session id (32-byte base-64 encoded binary data)
    A 32-byte HMAC-SHA256 hash authenticating the session id
Total length is 80 bytes (108 base-64 encoded characters).
"""
        db_session = cherrypy.serving.request.db_session

        try:
            session_token_raw = b64decode(session_token)
        except:
            log.warning("Invalid session token (base64 decode failed): %r",
                        session_token, exc_info=True)
            return None

        if len(session_token_raw) != 80:
            log.warning("Invalid session token (length should be 80 instead "
                        "of %d): %r", len(session_token_raw),
                        session_token)
            return None

        version = session_token[:4]
        session_id = session_token[4:48]
        digest = session_token[48:]

        if version != "stv1":
            log.warning("Invalid session token (expected version 'stv1' "
                        "instead of %r): %r", version, session_token)
            return None

        hasher = hmac.new(self.session_token_secret, session_id,
                          hashlib.sha256)
        if digest != hasher.digest():
            log.warning("Invalid session token (expected digest %r instead "
                        "of %r): %r", digest, hasher.digest(), session_token)
            return None

        try:
            user_session = db_session.query(dao.Session).filter_by(
                session_id=session_id).one()
        except:
            log.warning("Invalid session token: Unknown session id %r",
                        session_id, exc_info=True)
            return None

        log.info("Session authenticated: session_id=%r user_id=%r", session_id,
                 user_session.user_id)

        # Update the last_ping_time of this session
        user_session.last_ping_time = datetime.utcnow()
        db_session.add(user_session)
        return user_session

    def session_to_token(self, session_id):
        """\
Convert a session id to a session token, suitable for placement in a cookie.
"""
        if len(session_id) != 44:
            raise ValueError("session_id must be a 44 character base64-encoded "
                             "identifier")
        hasher = hmac.new(self.session_token_secret, session_id,
                          hashlib.sha256)
        return b64encode("stv1" + session_id + hasher.digest())

    def __call__(self):
        self.get_session_from_request()
        return

    # This is a password hash used to compare against when a username is
    # unknown.  This helps avoid timing attacks (bots which might scrape
    # for valid usernames).
    #
    # This hash was created using 256 bytes of data from /dev/urandom, whose
    # original contents were discarded.
    PBKDF2_INVLAID_PASSWORD = (
        '$pbkdf2-sha512$12000$JCTkPMe4N8bYG0PofW9NKQ$MRJCaxiLRZYGpo5nKjxGTF2'
        'wFv1RBTyIewFOzVmnlGL3UjKFMOCfDaYmpfEWeprZVz59saOIhPPahtcnxsLfKw'
    )

    def local_login(self, user_name, password):
        """\
Check whether the specified username/password combination is a valid local
login; if so, create a new session for this user.
"""
        db_session = cherrypy.serving.request.db_session
        user = db_session.query(dao.User).filter_by(
            user_domain_id=0, user_name=user_name).one()

        if user is None:
            # Attempt to validate against a random password.  This helps prevent
            # timing attacks.
            expected_password = PBKDF2_INVALID_PASSWORD
        else:
            expected_password = user.password_pbkdf2

        if not pbkdf2_sha512.verify(password, expected_password):
            raise LoginDeniedError("Invalid username/password combination.")

        return create_session(db_session, user.user_id)

    def create_session(self, user_id):
        """\
Create a new session for the specified user.
"""
        response = cherrypy.serving.response

        with open("/dev/urandom", "rb") as fd:
            session_id = b64encode(fd.read(32))
        now = datetime.utcnow()
        session = dao.Session(session_id=session_id, user_id=user_id,
                          established_time_utc=now,
                          last_ping_time_utc=now)
        db_session.add(session)

        response.cookie[self.session_cookie_name] = \
            self.session_to_token(session_id)

        return session
