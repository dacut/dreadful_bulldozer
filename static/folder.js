jQuery(function($) {
    function onCreateFolderSuccess(id, result) {
        node_contents.push(result);
        refresh();
        $("#createFolderDialog").modal('hide');
        $("#createFolderName").val("");
    }

    function onCreateFolderError(id, error_block) {
        $("#createFolderDialog").modal('hide');
        $("#createFolderName").val("");
    }

    function onCreateNotepageSuccess(id, result) {
        node_contents.push(result);
        refresh();
        $("#createNotepageDialog").modal('hide');
        $("#createNotepageName").val("");
    }

    function onCreateNotepageError(id, error_block) {
        $("#createNotepageDialog").modal('hide');
        $("#createNotepageName").val("");
    }

    function onRefreshFolderSuccess(id, result) {
        node_contents = result;
        refresh();
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
                       '<span class="dropdown">' +
                       '<a data-toggle="dropdown" href="#" id="fileMenu' + i
                       + '">' +
                       '<img src="/static/glyphicons/glyphicons_halflings_' +
                       '113_chevron-down.png" width="9px" height="6px">' +
                       '</a>' +
                       '<ul class="dropdown-menu" role="menu" ' +
                       'aria-labelledby="fileMenu' + i + '">' +
                       '<li role="presentation">' +
                       '<a role="menuitem" data-fileindex="' + i + '" ' +
                       'class="renameAction" ' +
                       'tabindex="-1" href="#">Rename</a>' +
                       '</li>' +
                       '<li role="presentation">' +
                       '<a role="menuitem" class="deleteAction" ' +
                       'tabindex="-1" href="#">Delete</a>' +
                       '</li>' +
                       '</ul></span>' +
                       '&nbsp;&nbsp;' +
                       '<img src="/static/glyphicons/' + icon +
                       '" width="18px" height="13px">' +
                       '</td>' +
                       '<td valign="center">' +
                       '<a href="/files' +
                       escapeHTML(target) + '">' + escapeHTML(node.name) +
                       '</a></td>' +
                       '<td valign="center">' + escapeHTML(nodeClass) +
                       '</td></tr>');
            nEntries += 1;
            
            $("#folderListSizeRow").before(row);
        }

        $(".renameAction").click(function (e) {
            console.log("click");
            console.log("rename: target=" + $(this).attr('data-fileindex'));
        });

        if (nEntries == 1) {
            $("#folderListSize").text("1 entry");
        } else {
            $("#folderListSize").text(nEntries + " entries");
        }
    }

    $("#createFolder").click(function () {
        $("#createFolderDialog").modal('show');
    });
    
    $("#createFolderDialog").on('shown.bs.modal', function (e) {
        $("#createFolderName").focus();
    });

    $("#createFolderName").keypress(function (e) {
        if (e.charCode === 13) {
            $("#createFolderAction").click();
            return false;
        }

        return true;
    });

    $("#createFolderAction").click(function () {
        var createFolderName = $("#createFolderName").val();
        dozer.create_folder(node.full_name + "/" + createFolderName,
                            onCreateFolderSuccess, onCreateFolderError);
    });

    $("#createNotepage").click(function () {
        $("#createNotepageDialog").modal('show');
    });

    $("#createNotepageDialog").on('shown.bs.modal', function(e) {
        $("#createNotepageName").focus();
    });

    $("#createNotepageName").keypress(function (e) {
        if (e.charCode == 13) {
            $("#createNotepageAction").click();
            return false;
        }

        return true;
    });

    $("#createNotepageAction").click(function () {
        var createNotepageName = $("#createNotepageName").val();
        dozer.create_notepage(node.full_name + "/" + createNotepageName,
                              onCreateNotepageSuccess, onCreateNotepageError);
    });

    $("#refreshFolderAction").click(function () {
        dozer.list_folder(node.full_name, onRefreshFolderSuccess, null);
    });

    refresh();
});
