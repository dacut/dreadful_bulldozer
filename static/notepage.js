jQuery(function($) {

    var edited_note = null;

    function onCreateNoteSuccess(id, note) {
        window.notepage.children.push(note);
        drawNote(note);
    }

    function onUpdateNotepageSuccess(id, result_block) {
        var notepage_revision_id = result_block['notepage_revision_id'];
        var results = result_block['results'];
        var i, result, note, pos_um, size_um, z_index, contents_markdown;

        console.log("Successful update");

        window.notepage.revision_id = notepage_revision_id;
        
        for (i = 0; i < results.length; ++i) {
            result = results[i];
            note = getNoteById(result['note_id']);
            if (note === null) {
                console.log("onUpdateNotepageSuccess: cannot find note id " +
                            result['note_id']);
                continue;
            }

            pos_um = result['pos_um'];
            size_um = result['size_um'];
            z_index = result['z_index'];
            contents_markdown = result['contents_markdown'];

            if (pos_um !== undefined && pos_um !== null) {
                note.pos_um = pos_um;
            }

            if (size_um !== undefined && size_um !== null) {
                note.size_um = size_um;
            }

            if (z_index !== undefined && z_index !== null) {
                note.z_index = z_index;
            }

            if (contents_markdown !== undefined && contents_markdown !== null) {
                note.contents_markdown = contents_markdown;
            }

            drawNote(note);
        }

        return;
    }

    function onUpdateNotepageError(id) {
        console.log("Failed update");
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

            style = {'width': (0.001 * note.size_um[0]) + "mm",
                     'height': (0.001 * note.size_um[1]) + "mm",
                     'left': (0.001 * note.pos_um[0]) + "mm",
                     'top': (0.001 * note.pos_um[1]) + "mm",
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
        dozer.update_notepage(
            window.notepage.node_id,
            [{"action": "edit_note",
              "note_id": note.node_id,
              "revision_id": note.revision_id,
              "contents_markdown": text}],
            onUpdateNotepageSuccess,
            onUpdateNotepageError);
    }

    function stopDragging() {
        // Stop any drag operation currently in progress.
        var viewport = $("#viewport");
        var targetId = viewport.data("drag-target");
        var target, note, pos_um;

        if (targetId === undefined) {
            // Nothing being dragged.
            return;
        }

        target = $("#" + targetId);
        note = target.data('note');
        pos_um = getNotePositionInMicrons(target);
        viewport.removeData("drag-target");
        viewport.removeData("drag-last-x");
        viewport.removeData("drag-last-y");

        console.log("stopDragging: pos_um=" + JSON.stringify(pos_um) +
                    ", note.pos_um=" + JSON.stringify(note.pos_um));

        // Did we actually move the note?
        if (pos_um[0] === note.pos_um[0] && pos_um[1] === note.pos_um[1]) {
            console.log("Skipping update; no change in position.");
            return;
        }

        // Update the server with the new note position.
        dozer.update_notepage(
            window.notepage.node_id,
            [{"action": "edit_note",
              "note_id": note.node_id,
              "revision_id": note.revision_id,
              "pos_um": pos_um}],
            onUpdateNotepageSuccess,
            onUpdateNotepageError);
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
        var viewport = $("#viewport");
        var targetId = viewport.data("drag-target");
        var target, lastX, lastY, deltaX, deltaY, left, top;

        if (e.which != 1 && targetId !== undefined && targetId !== null) {
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

    function getPixelsPerMicron() {
        var sizetest = $('<div id="sizetest" style="position: relative; ' +
                         'width: 100mm; height: 100mm; ' +
                         'left: -200mm; top: -200mm;"></div>');
        var width, height;
        
        // Create a dummy div that's 100mm x 100mm and see how many pixels
        // that takes up.  Using a div that's too small results in significant
        // rounding errors.

        sizetest.appendTo("#viewport")
        width = $("#sizetest").css("width");
        height = $("#sizetest").css("height");

        console.log("width=" + width);

        width = Number(width.substring(0, width.length - 2));
        height = Number(height.substring(0, height.length - 2));

        // Remove our dummy div.
        $("#sizetest").remove();

        // We need to scale by 1e-5 to go from hundreds of mm to microns.
        return [1e-5 * width, 1e-5 * height];
    }

    function getNoteById(note_id) {
        var i, note;

        for (i = 0; i < window.notepage.children.length; ++i) {
            note = window.notepage.children[i];
            if (note.node_id == note_id) {
                return note;
            }
        }

        return null;
    }

    function getNoteSizeInMicrons(noteDOM, pixelsPerMicron) {
        var width = noteDOM.css("width");
        var height = noteDOM.css("height");

        if (pixelsPerMicron === undefined || pixelsPerMicron === null) {
            pixelsPerMicron = getPixelsPerMicron();
        }
        
        width = Number(width.substring(0, width.length - 2));
        height = Number(height.substring(0, height.length - 2));

        width = Math.round(width / pixelsPerMicron[0]);
        height = Math.round(height / pixelsPerMicron[1]);

        return [width, height];
    }
    
    function getNotePositionInMicrons(noteDOM, pixelsPerMicron) {
        var left = noteDOM.css("left");
        var top = noteDOM.css("top");

        if (left === undefined || top === undefined) {
            console.log("Failed to retrieve style information");
            return;
        }

        if (pixelsPerMicron === undefined || pixelsPerMicron === null) {
            pixelsPerMicron = getPixelsPerMicron();
        }
        
        left = Number(left.substring(0, left.length - 2));
        top = Number(top.substring(0, top.length - 2));

        left = Math.round(left / pixelsPerMicron[0]);
        top = Math.round(top / pixelsPerMicron[1]);
        
        return [left, top];
    }

    $("#createNoteAction").click(function () {
        console.log("create note clicked");
        dozer.create_note(window.notepage.node_id, onCreateNoteSuccess, null);
    });

    $(window).mousemove(onMouseMove);
    $(window).mouseup(stopDragging);
    $(window).on("blur", stopDragging);

    (function () {
        for (var i = 0; i < window.notepage.children.length; ++i) {
            var note = window.notepage.children[i];
            drawNote(note);
        }
    })();
});
