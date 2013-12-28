jQuery(function($) {
    create_folder_in_flight = false;

    function onCreateFolderSuccess(id, result) {
    }

    function onCreateFolderError(id, error_block) {
    }

    function stricmp(a, b) {
        var alower = a.name.toLowerCase();
        var blower = b.name.toLowerCase();
        if (alower < blower) {
            return -1;
        } else if (alower > blower) {
            return 1;
        } else {
            return 0;
        }
    }

    function encodePathComponents(pathComponents) {
        var result = "";
        for (var i = 0; i < pathComponents.length; ++i) {
            var el = pathComponents[i];
            result += "/" + encodeURIComponent(el);
        }

        if (result === "") {
            result = "/";
        }
        
        return result;
    }

    var entityMap = {
        '&': "&amp;",
        '<': "&lt;",
        '>': "&gt;",
        '"': "&quot;",
        "'": "&#x27;"
    };

    function escapeHTML(s) {
        return String(s).replace(/[&<>"']/g, function (entity) {
            return entityMap[entity];
        });
    }

    function refresh() {
        var nEntries = 0;
        node_contents.sort(stricmp);
        $("tr.folderEntry").remove();
        
        for (var i = 0; i < node_contents.length; ++i) {
            var node = node_contents[i], nodeClass;
            var icon, target;

            nodeClass = node["class"];
            target = encodePathComponents(node.path_components);

            if (nodeClass === "Folder") {
                icon = "glyphicons_144_folder_open.png";
                target += "/";
            } else if (nodeClass === "Notepage") {
                icon = "glyphicons_039_notes.png";
            } else if (nodeClass === "Note") {
                icon = "glyphicons_309_comments.png";
            } else {
                nodeClass = "Unknown";
                icon = "glyphicons_036_file.png";
            }

            var row = ('<tr class="folderEntry">' +
                       '<td valign="center">' +
                       '<img src="/static/glyphicons/' + icon + '"></td>' +
                       '<td valign="center"><a href="/files' +
                       escapeHTML(target) + '">' + escapeHTML(node.name) +
                       '</a></td>' +
                       '<td valign="center">' + escapeHTML(nodeClass) +
                       '</td></tr>');
            nEntries += 1;
            
            $("#folderListSizeRow").before(row);
        }

        if (nEntries == 1) {
            $("#folderListSize").text("1 entry");
        } else {
            $("#folderListSize").text(nEntries + " entries");
        }
    }

    $("#createFolderAction").click(function () {
        var folderName = $("#folderName").val();
        dozer.create_folder(node.full_name + "/" + folderName,
                            onCreateFolderSuccess, onCreateFolderError);
    });

    refresh();
});
