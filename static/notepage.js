jQuery(function($) {

    function onCreateNoteSuccess(id, note) {
        node_contents.push(note);
        drawNote(note);
    }

    function drawNote(note) {
        var domId, domNode, viewport, style;

        domId = "note-" + note.node_id;
        domNode = $("#" + domId);
        
        if (domNode.length == 0) {
            // New note; need to create it.
            viewport = $("#viewport");
            $('<div class="note" id="' + domId + '"></div>').appendTo(viewport);
            domNode = $("#" + domId);
        }

        style = {'width': (0.001 * note.width_um) + "mm",
                 'height': (0.001 * note.height_um) + "mm",
                 'left': (0.001 * note.x_pos_um) + "mm",
                 'top': (0.001 * note.y_pos_um) + "mm",
                 'z-index': note.z_index}

        domNode.css(style);

        console.log("Setting DOM css: " + JSON.stringify(style))

        // FIXME: Need to render Markdown into HTML.
        domNode.text(note.contents_markdown);

        domNode.mousedown(onNoteMouseDown);
        domNode.mouseup(onNoteMouseUp);
        domNode.mousemove(onNoteMouseMove);
        domNode.mouseleave(onNoteMouseLeave);
    }

    function onNoteMouseDown(e) {
        var target = $(e.target);
        if (e.button === 0) {
            target.data("dragging", [e.clientX, e.clientY]);
        }
    }

    function onNoteMouseUp(e) {
        var target = $(e.target);
        if (e.button === 0) {
            target.removeData("dragging");
        }
    }

    function onNoteMouseLeave(e) {
        var target = $(e.target);
        target.removeData("dragging");
    }

    function onNoteMouseMove(e) {
        var target = $(e.target);
        var start = target.data("dragging");
        var curLeft, curTop, newLeft, newTop;

        if (start) {
            curLeft = target.css('left');
            curTop = target.css('top');
            curLeft = Number(curLeft.substring(0, curLeft.length - 2));
            curTop = Number(curTop.substring(0, curTop.length - 2));
            var newLeft = curLeft + e.clientX - start[0];
            var newTop = curTop + e.clientY - start[1];

            console.log("dragging: clientX=" + e.clientX + ", clientY=" + e.clientY + ", target.left=" + target.css('left') + ", target.top=" + target.css('top') + ", start=" + start[0] + "," + start[1] + ", target.position=" + target.css('position') + ", new=" + newLeft + "," + newTop);

            target.css("left", newLeft);
            target.css("top", newTop);
            target.data("dragging", [e.clientX, e.clientY]);
        }
    }

    $("#createNoteAction").click(function () {
        console.log("create note clicked");
        dozer.create_note(node.full_name, onCreateNoteSuccess, null);
    });

    (function () {
        for (var i = 0; i < node_contents.length; ++i) {
            var note = node_contents[i];
            drawNote(note);
        }
    })();
});
