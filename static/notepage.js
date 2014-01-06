jQuery(function($) {

    var edited_note = null;

    function onCreateNoteSuccess(id, note) {
        node_contents.push(note);
        drawNote(note);
    }

    function drawNote(note) {
        var domId, noteDOM, noteContentsDOM, viewport, style, converter;

        domId = "note-" + note.node_id;
        noteDOM = $("#" + domId);
        
        if (noteDOM.length == 0) {
            // New note; need to create it.
            viewport = $("#viewport");
            $('<div class="note" id="' + domId + '">' +
              '<div class="note-contents"></div>' +
              '</div>').appendTo(viewport);
            noteDOM = $("#" + domId);
            noteDOM.data("note", note);
            noteContentsDOM = $(".note-contents", noteDOM);

            style = {'width': (0.001 * note.width_um) + "mm",
                     'height': (0.001 * note.height_um) + "mm",
                     'left': (0.001 * note.x_pos_um) + "mm",
                     'top': (0.001 * note.y_pos_um) + "mm",
                     'z-index': note.z_index}

            noteDOM.css(style);
            noteDOM.mousedown(onNoteMouseDown);
            noteDOM.dblclick(onNoteDoubleClick);
            noteContentsDOM.mousedown(onNoteMouseDown);
        } else {
            noteContentsDOM = $(".note-contents", noteDOM);
        }

        // Convert the raw text into HTML.
        converter = Markdown.getSanitizingConverter();
        noteContentsDOM.html(
            converter.makeHtml(note.contents_markdown));

        // Make sure the contents are visible.
        noteContentsDOM.css("display", "block");
    }

    function updateNote(note, text) {
        // FIXME: Update the note contents on the server.
        note.contents_markdown = text;
        drawNote(note);
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
        var noteDOM = $(e.target), viewport = $("#viewport");

        if (! noteDOM.is(".note")) {
            // Mouse down on an inner item; select the note div.
            noteDOM = noteDOM.parents(".note");
        }

        if (e.button === 0 && e.target === e.currentTarget) {
            viewport.data("drag-target", noteDOM.attr("id"));
            viewport.data("drag-last-x", e.clientX);
            viewport.data("drag-last-y", e.clientY);

            // Don't let this event bubble.
            return false;
        }
    }

    function onNoteDoubleClick(e) {
        // Handle a double-click event on a note.  This starts editing the
        // note.
        var noteDOM = $(e.target), form, editor;

        if (! noteDOM.is(".note")) {
            // Clicked on the contents div; set noteDOM to the enclosing
            // note div.
            noteDOM = noteDOM.parents(".note");
        }

        edited_note = noteDOM.data("note");
        console.log("edited_note=" + JSON.stringify(edited_note));

        // Remove the display-only contents while editing.
        $(".note-contents", noteDOM).css("display", "none");

        // Create an edit form in the interior.
        form = $('<form><textarea id="note-edit" cols="132" rows="60">' +
                 '</textarea></form>');
        form.appendTo(noteDOM);
        editor = $("#note-edit", form);

        // Populate the value of the note with the contents.
        editor.text(edited_note.contents_markdown);

        // Watch keypresses for Alt+Enter or Escape, which terminate the
        // editing process.
        editor.keypress(onNoteEditKeypress);

        editor.trigger("focus");

        // Don't let this event bubble.
        return false;
    }

    function onNoteEditKeypress(e) {
        var target = $(e.target),
            text;

        if (e.which === 27) {
            // Escape -- cancel editing.
            drawNote(edited_note);
            edited_note = null;
            return false;
        }

        if ((e.altKey || e.metaKey) && (e.which === 10 || e.which === 13)) {
            // Alt+Enter pressed -- save changes.
            
            // Get the text entered.
            text = target.val();

            // Remove the form.
            target.parent().remove();

            // Update the note.
            updateNote(edited_note, text);

            edited_note = false;
            return false;
        }

        // Normal key; ignore it, let it bubble up.
        return true;
    }

    function onMouseMove(e) {
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

    $(window).mousemove(onMouseMove);
    $(window).mouseup(stopDragging);
    $(window).on("blur", stopDragging);

    (function () {
        for (var i = 0; i < node_contents.length; ++i) {
            var note = node_contents[i];
            drawNote(note);
        }
    })();
});
