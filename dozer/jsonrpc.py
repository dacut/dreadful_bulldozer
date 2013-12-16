import json
import cherrypy
import dozer.dao as dao
from traceback import format_exc

def create_error(code, message, data=None, id=None):
    error = {
        'code': code,
        'message': message,
    }

    if data is not None:
        error['data'] = data

    result = {
        'jsonrpc': "2.0",
        'id': id,
        'error': error,
    }

    return result

def expose_jsonrpc(f):
    f.jsonrpc = True
    return f

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

class InvalidParameterError(RuntimeError):
    jsonrpc_error_code = INVALID_PARAMS

class JSONRPC(object):
    @cherrypy.expose
    def default(self, *args, **kw):
        if cherrypy.request.method not in ("POST", "PUT"):
            return json.dumps(
                create_error(
                    code=PARSE_ERROR,
                    message="Invalid HTTP method; must use POST or PUT"))

        data = cherrypy.request.rfile.read()
        try:
            json_data = json.loads(data)
        except Exception as e:
            return json.dumps(
                create_error(
                    code=PARSE_ERROR,
                    message="Malformed JSON-RPC request"))
        
        if isinstance(json_data, list):
            # Batch request.
            result = [self._handle_request(el) for el in json_data]

            # Remove any null responses (from notifications)
            result = [el for el in request if el is not None]
        elif isinstance(json_data, dict):
            # Single requst
            result = self._handle_request(el)
        else:
            # Malformed
            result = create_error(
                code=PARSE_ERROR,
                message="Malformed JSON-RPC request")
            
        return json.dumps(result)
    
    def _handle_request(self, request):
        jsonrpc = request.get("jsonrpc")
        method_name = request.get("method")
        params = request.get("params")
        id = request.get("id")

        if jsonrpc not in (None, "2.0"):
            return create_error(
                code=INVALID_REQUEST,
                message="Invalid JSON-RPC request version %s" % (jsonrpc,),
                id=id)
        
        if params is not None and not isinstance(params, (list, dict)):
            return create_error(
                code=INVALID_REQUEST,
                message=("Invalid JSON-RPC request parameters; expected a "
                         "JSON object or array"),
                id=id)

        method_parts = method_name.split(".")
        current_object = self

        for part in method_parts:
            next_object = getattr(current_object, method_name, None)

            if next_object is None or not hasattr(next_object, "jsonrpc"):
                return create_error(
                    code=METHOD_NOT_FOUND,
                    message="Method %s not found" % (method_name,),
                    id=id)
            
            current_object = next_object

        try:
            if isinstance(params, list):
                result = current_object(*params)
            elif isinstance(params, dict):
                result = current_object(**params)
            else: #params is None
                result = current_object()

            return {
                'jsonrpc': "2.0",
                'id': id,
                'result': result,
            }
                
        except Exception as e:
            error_code = getattr(e, 'jsonrpc_error_code', INTERNAL_ERROR)
            return create_error(code=error_code, message=str(e),
                                data=format_exc(), id=id)

