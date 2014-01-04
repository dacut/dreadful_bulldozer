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
    }

    function stopDragging() {
        // Stop any drag operation currently in progress.
        // FIXME: Need to update the server with the new note position.
        var viewport = $("#viewport");
        viewport.removeData("drag-target");
        viewport.removeData("drag-last-x");
        viewport.removeData("drag-last-y");
    }
    
    function onNoteMouseDown(e) {
        // Handle a mousedown event on a note.  This starts dragging the note.
        var target = $(e.target), viewport = $("#viewport");
        if (e.button === 0) {
            console.log("mousedown: " + target.attr("id"));
            viewport.data("drag-target", target.attr("id"));
            viewport.data("drag-last-x", e.clientX);
            viewport.data("drag-last-y", e.clientY);
        }
    }

    function onViewportMouseMove(e) {
        // Handle a mouse motion event on the viewport.  If a drag event is in
        // progress, this updates the position of the note on the viewport.
        var viewport = $("#viewport"),
            targetId = viewport.data("drag-target"),
            target, lastX, lastY, deltaX, deltaY, left, top;

        if (e.which != 1) {
            // Mouse button was released, but we didn't receive the mouseup
            // event (pointer outside of window).  Go ahead and release the
            // drag now.
            stopDragging();
            return;
        }

        if (targetId !== undefined && targetId !== null) {
            target = $("#" + targetId);

            console.log("mousemove: drag-target=" + targetId + " button=" + e.button + " which=" + e.which);

            lastX = viewport.data("drag-last-x");
            lastY = viewport.data("drag-last-y");

            // Delta is the difference between the current position in the
            // client window and the last reported position.
            deltaX = e.clientX - lastX;
            deltaY = e.clientY - lastY;

            // Get the position of the target and remove the 'px' suffix.
            left = target.css('left');
            top = target.css('top');
            left = Number(left.substring(0, left.length - 2));
            top = Number(top.substring(0, top.length - 2));
            
            // Modify the position by the delta.
            left += deltaX;
            top += deltaY;

            target.css("left", left);
            target.css("top", top);

            // Remember the last reported position.
            viewport.data("drag-last-x", e.clientX);
            viewport.data("drag-last-y", e.clientY);
        }
    }

    $("#createNoteAction").click(function () {
        console.log("create note clicked");
        dozer.create_note(node.full_name, onCreateNoteSuccess, null);
    });

    $("#viewport").mousemove(onViewportMouseMove);
    $(window).mouseup(stopDragging);
    $(window).on("blur", stopDragging);

    (function () {
        for (var i = 0; i < node_contents.length; ++i) {
            var note = node_contents[i];
            drawNote(note);
        }
    })();
});
