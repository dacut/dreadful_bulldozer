from __future__ import (absolute_import, print_function)
from ConfigParser import SafeConfigParser
from os.path import abspath, dirname, join as path_join
from sys import argv, path as sys_path

_root = None
_config_filename = None

def get_root():
    global _root
    if _root is None:
        _root = abspath(dirname(argv[0]))
    return _root

def set_root(root):
    global _root
    _root = root
    return

def get_config():
    from cherrypy.lib.reprconf import Config, Parser
    root = get_root()
    config_filename = get_config_filename()
    cp = Parser()
    return Config(cp.dict_from_file(config_filename))

def get_config_filename():
    global _config_filename
    if _config_filename is None:
        _config_filename = path_join(get_root(), "dozer.config")
    return _config_filename

def set_config_filename(filename):
    global _config_filename
    _config_filename = filename
    return
