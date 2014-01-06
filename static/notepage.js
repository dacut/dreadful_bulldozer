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
        domNode.dblclick(onNoteDoubleClick);
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

        if (e.button === 0 && e.target === e.currentTarget) {
            console.log("mousedown: " + target.attr("id"));
            viewport.data("drag-target", target.attr("id"));
            viewport.data("drag-last-x", e.clientX);
            viewport.data("drag-last-y", e.clientY);

            // Don't let this event bubble.
            return false;
        }
    }

    function onNoteDoubleClick(e) {
        // Handle a double-click event on a note.  This starts editing the
        // note.
        var target = $(e.target), form, text, editor;
        console.log("double click: " + target.attr("id"));
        text = target.text();
        target.data("orig-text", text);
        target.text("");

        // Create an edit form in the interior.
        form = $('<form><textarea id="note-edit" cols="132" rows="60">' +
                 '</textarea></form>');
        form.appendTo(target);
        
        editor = $("#note-edit", form);
        editor.text(text);
        editor.keypress(onNoteEditKeypress);

        // Don't let this event bubble.
        return false;
    }

    function onNoteEditKeypress(e) {
        var target = $(e.target),
            note = target.parents(".note"),
            noteId = note.attr("id"),
            text;

        console.log("keypress: noteId=" + noteId + ", which=" + e.which + " meta=" + e.metaKey + " altkey=" + e.altKey);

        // Convert noteId into a numeric form.
        if (noteId.substring(0, 5) !== "note-") {
            // Yikes -- this shouldn't happen.
            console.log("Failed to convert note div into a numeric node it: " +
                        noteId);
            return true;
        }

        noteId = Number(noteId.substring(5));

        if ((e.altKey || e.metaKey) && (e.which === 10 || e.which === 13) ||
            e.which == 27)
        {
            // Done editing this box.  If Meta+Enter was pressed (which != 27),
            // save the changes.
            if (e.which !== 27) {
                text = target.val();

                // FIXME: Convert the text into Markdown.
                // FIXME: Submit the text changes to the server.
            } else {
                // Restore the original text.
                text = note.data("orig-text");
                note.removeData("orig-text");
            }
             
            // Remove the form.
            target.parent().remove();

            // Set the note text.
            note.text(text);
            return false;
        }

        // Normal key; ignore it, let it bubble up.
        return true;
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
