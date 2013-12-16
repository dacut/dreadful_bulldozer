from cStringIO import StringIO
from base64 import b64encode
import dozer.dao as dao

class DatabaseSchemaError(RuntimeError):
    pass

class InvalidPathNameError(RuntimeError):
    pass

class PermissionDeniedError(RuntimeError):
    pass

class InvalidDocumentTypeError(RuntimeError):
    pass

class LoginDeniedError(RuntimeError):
    pass


def validate_and_split_path(path):
    if isinstance(path, (list, tuple)):
        for el in path:
            if el in ("", ".", ".."):
                raise InvalidPathNameError(
                    "Path contains illegal path element %r: %r" %
                    (el, "/" + "/".join(path)))
        return list(path)
    
    if not isinstance(path, basestr):
        raise TypeError("Cannot handle path of type %s" %
                        type(basestr).__name__)

    orig_path = path
    while path.startswith("/"):
        path = path[1:]

    result = []
    start = 0
    
    while start < len(path):
        next_slash = path.find("/", start)
        if next_slash == -1:
            element = path[start:]
            if element in (".", ".."):
                raise InvalidPathNameError(
                    "Path contains illegal path element %r: %r" %
                    (element, orig_path))
            result.append(element)
            break

        element = path[start:next_slash]
        if element in (".", ".."):
            raise InvalidPathNameError(
                "Path contains illegal path element %r: %r" %
                (element, orig_path))
        
        result.append(element)
        start = next_slash + 1

        # Merge any neighboring slashes, e.g. a/b//c -> a/b/c
        while start < len(path) and path[start] == '/':
            start += 1
    
    return result

def create_folder(db_session, path, owner_user_id, permissions=None,
                  inherit_permissions=False):
    path_list = validate_and_split_path(path)
    if len(path_list) == 0:
        raise PermissionDeniedError("Cannot create root folder")

    # Make sure the user has permissions to navigate each subfolder.
    check_permissions(db_session, path_list[:-1], owner, permissions="N")

def check_folder_permissions(folder, desired_permissions, all_ids):
    for p in folder.permissions:
        if p.user_id not in all_ids:
            # This permission entry doesn't apply.
            continue

        if all([dp in p.permissions for dp in desired_permissions]):
            # All permissions granted.
            return True

    # Does this folder inherit its permissions?
    if folder.inherit_permissions == "Y" and folder.parent_node_id is not None:
        return check_folder_permissions(
            folder.parent, desired_permissions, all_ids)

    # Cannot navigate this folder.
    return False

def can_navigate(folder, all_ids):
    return check_folder_permissions(folder, "N", all_ids)

def check_permissions(db_session, path, user_id, desired_permissions,
                      user_group_ids=None):
    if user_group_ids is None:
        user_group_ids = get_group_ids_for_user(db_session, user_id)

    all_ids = [user_id] + user_group_ids

    parent_folder = get_root_folder(db_session)

    # Make sure the root folder is accessible
    if not can_navigate(parent_folder, all_ids):
        raise PermissionDeniedError("Permission denied: /")
    
    # Make sure we can navigate each folder up to the last.
    path_list = validate_and_split_path(path)
    current_path = ""

    for path_el in path_list[:-1]:
        current_path += "/" + path_el
        folder = parent_folder.children.filter_by(node_name=path_el).one()
        
        # Make sure the child folder is accessible
        if not can_navigate(folder, all_ids):
            raise PermissionDeniedError("Permission denied: %s" % current_path)
        
        parent_folder = folder

    # Make sure the last directory has the desired permissions
    current_path += "/" + path_list[-1]
    folder = parent_folder.children.filter_by(node_name=path_list[-1]).one()
    if not check_folder_permissions(folder, desired_permissions, all_ids):
        raise PermissionDeniedError("Permission denied: %s" % current_path)
    
    return True

def get_root_folder(db_session):
    return db_session.query(dao.Folder).filter_by(
        node_id=0, parent_node_id=None, node_name=None, is_active='Y').one()
