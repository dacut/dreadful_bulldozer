import json
import cherrypy
import dozer.dao as dao
from logging import getLogger
from traceback import format_exc

log = getLogger("dozer.jsonrpc")
wirelog = getLogger("dozer.jsonrpc.wire")

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

def expose(f):
    f.jsonrpc = True
    return f

def to_json_default(obj):
    if isinstance(obj, set):
        return list(obj)

    try:
        return obj.json
    except AttributeError:
        log.error("to_json_default: serialization failed", exc_info=True)
        raise TypeError("Cannot serialize %r" % (obj,))
    except:
        log.error("to_json_default: serialization failed", exc_info=True)
        raise

def to_json(obj):
    return json.dumps(obj, default=to_json_default)

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
        request = cherrypy.serving.request

        if request.method not in ("POST", "PUT"):
            return to_json(
                create_error(
                    code=PARSE_ERROR,
                    message="Invalid HTTP method; must use POST or PUT"))

        data = cherrypy.request.rfile.read()
        wirelog.debug("%s: %r", request.request_line, data)

        try:
            json_data = json.loads(data)
        except Exception as e:
            log.error("json.loads of %r failed", data, exc_info=True)
            return to_json(
                create_error(
                    code=PARSE_ERROR,
                    message="Malformed JSON-RPC request"))

        log.debug("JSON-RPC request data: %r", json_data)
        
        if isinstance(json_data, list):
            # Batch request.
            result = [self._handle_request(el) for el in json_data]

            # Remove any null responses (from notifications)
            result = [el for el in request if el is not None]
        elif isinstance(json_data, dict):
            # Single requst
            result = self._handle_request(json_data)
        else:
            # Malformed
            log.error("Malformed JSON-RPC request: neither a list or dict: %r",
                      json_data)
            result = create_error(
                code=PARSE_ERROR,
                message="Malformed JSON-RPC request")
            
        return to_json(result)

    def _handle_request(self, request):
        jsonrpc = request.get("jsonrpc")
        method_name = request.get("method")
        params = request.get("params")
        id = request.get("id")
        log = getLogger("dozer.jsonrpc._handle_request")

        log.debug("handle_request: jsonrpc=%r method_name=%r params=%r id=%r",
                  jsonrpc, method_name, params, id)

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

        log.debug("method_parts: %r", method_parts)

        for part in method_parts:
            log.debug("current_object=%r; considering part %r", current_object,
                      part)
            next_object = getattr(current_object, part, None)

            if next_object is None or not hasattr(next_object, "jsonrpc"):
                log.error("next_object invalid: %r", next_object)
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

            cherrypy.serving.request.db_session.commit()

            return {
                'jsonrpc': "2.0",
                'id': id,
                'result': result,
            }                
        except Exception as e:
            log.error("Method call %s failed", method_name, exc_info=True)
            error_code = getattr(e, 'jsonrpc_error_code', INTERNAL_ERROR)
            cherrypy.serving.request.db_session.rollback()
            return create_error(code=error_code, message=str(e),
                                data=format_exc(), id=id)

    @staticmethod
    def _json_default(obj):
        if hasattr(obj, "json"):
            return obj.json
        
        raise TypeError("Unable to encode object %r" % (obj,))
