var dozer = (function () {
    var next_id = 0;

    function get_next_id() {
        var result = next_id;
        next_id += 1;
        return result;
    }
    
    function jsonrpc_result(id, succeeded, result, success, error) {
        if (succeeded) {
            // The AJAX call succeeded; let's see if the actual API call did.
            var result_id = result["id"],
                result_block = result["result"],
                error_block = result["error"];

            if (result_id !== id) {
                // What?  We got a different id back?
                error(id, {
                    "code": -32603,
                    "message": ("Internal JSONRPC error; server responded " +
                                "request id " + id + " with id " + result_id +
                                ".")
                });
            } else if (result_block === undefined) {
                // Ok, error has better not be undefined.
                if (error_block === undefined) {
                    // No result or error block -- not a valid response.
                    error(id, {
                        "code": -32603,
                        "message": ("Internal JSONRPC error; server did not " +
                                    "return a result or error block.")
                    });
                } else {
                    // Standard error.
                    error(id, error_block);
                }
            } else {
                success(id, result_block);
            }
        } else {
            // The AJAX call failed.  Pass this onto the error callback.
            var status_code = result["status_code"];
            var error_obj = result["error_obj"];

            error(id, {
                "code": -32000,
                "message": ("JSONRPC error: AJAX call failed: " + status_code),
                "data": error_obj
            });
        }
    }

    function jsonrpc_call(api, params, success, error) {
        var id = api + "_" + get_next_id();
        var ajaxRequest, xhr;

        ajaxRequest = {
            "url": "/jsonrpc",
            "data": {
                "jsonrpc": "2.0",
                "method": api,
                "params": params,
                "id": id,
            },
            "dataType": "json",
            "contentType": "application/json"
        };

        if (success !== undefined) {
            ajaxRequest["success"] = function (result, status_code, xhr) {
                jsonrpc_result(id, true, result, success, error);
            }
        }

        if (error !== undefined) {
            ajaxRequest["error"] = function (xhr, status_code, error_obj) {
                jsonrpc_result(id, false, {
                    "status_code": status_code,
                    "error_obj": error_obj
                }, success, error);
            }
        }

        xhr = jQuery.ajax(ajaxRequest);
        xhr["id"] = id;
        return xhr;
    }

    return {
        create_folder: function (node_name, success, error) {
            if (typeof(node_name) != "string") {
                throw {
                    "name": "TypeError",
                    "message": "node_name must be a string"
                };
            }

            jsonrpc_call("create_folder", {"node_name": node_name},
                         success, error);
        }
    }
}());
