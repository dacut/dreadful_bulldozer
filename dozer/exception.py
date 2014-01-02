class DozerError(RuntimeError):
    jsonrpc_error_code = 1

class LoginDeniedError(DozerError):
    jsonrpc_error_code = 2

class FilesystemError(DozerError):
    jsonrpc_error_code = 3

class PermissionDeniedError(DozerError):
    jsonrpc_error_code = 4

class FileNotFoundError(DozerError):
    jsonrpc_error_code = 5

class InvalidPathNameError(DozerError):
    jsonrpc_error_code = 6

class FilesystemConsistencyError(DozerError):
    jsonrpc_error_code = 7

class InvalidParameterError(DozerError):
    jsonrpc_error_code = 8
