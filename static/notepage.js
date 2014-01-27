jQuery(function($) {
    var viewport = $("#viewport");
    var canvas = $("#canvas");
    var edited_note = null;
    var drag, select;

    function getPixelsPerMicron() {
        var sizetest = $('<div id="sizetest" style="position: relative; ' +
                         'width: 100mm; height: 100mm; ' +
                         'left: -200mm; top: -200mm;"></div>');
        var width, height;
        
        // Create a dummy div that's 100mm x 100mm and see how many pixels
        // that takes up.  Using a div that's too small results in significant
        // rounding errors.

        sizetest.appendTo("#viewport")
        sizetest = $("#sizetest");
        width = parseInt(sizetest.css("width"));
        height = parseInt(sizetest.css("height"));

        // Remove our dummy div.
        sizetest.remove();

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
        var width = parseInt(noteDOM.css("width"));
        var height = parseInt(noteDOM.css("height"));

        if (pixelsPerMicron === undefined || pixelsPerMicron === null) {
            pixelsPerMicron = getPixelsPerMicron();
        }
        
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
        
        left = Math.round(parseInt(left) / pixelsPerMicron[0]);
        top = Math.round(parseInt(top) / pixelsPerMicron[1]);
        
        return [left, top];
    }

    function drawNote(note) {
        var domId, noteDOM, noteContentsDOM, style, converter;

        domId = "note-" + note.node_id;
        noteDOM = $("#" + domId);
        
        if (noteDOM.length == 0) {
            // New note; need to create it.
            $('<div class="note" id="' + domId + '">' +
              '<div class="note-contents"></div>' +
              '</div>').appendTo(canvas);
            noteDOM = $("#" + domId);
            noteDOM.data("note", note);
            noteContentsDOM = $(".note-contents", noteDOM);

            style = {'width': (0.001 * note.size_um[0]) + "mm",
                     'height': (0.001 * note.size_um[1]) + "mm",
                     'left': (0.001 * note.pos_um[0]) + "mm",
                     'top': (0.001 * note.pos_um[1]) + "mm",
                     'z-index': note.z_index}

            noteDOM.css(style);
            noteDOM.click(onNoteClick);
            noteDOM.dblclick(onNoteDoubleClick);
            noteContentsDOM.click(onNoteClick);
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

    drag = (function () {
        var dragNoteDOM = null;
        var dragNote = null;
        var dragLastX = 0;
        var dragLastY = 0;
        var start, stop, move;

        stop = function () {
            var note = dragNote;
            var pos_um;

            // Stop any drag operation currently in progress.
            if (! dragNoteDOM) {
                // Nothing being dragged.
                return false;
            }

            pos_um = getNotePositionInMicrons(dragNoteDOM);

            // Stop the drag action
            dragNoteDOM = null;
            dragNote = null;

            if (pos_um[0] === note.pos_um[0] &&
                pos_um[1] === note.pos_um[1]) {
                // The note didn't move; don't fire an update event.
                return false;
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
        
            return false;
        };

        start = function (e) {
            // Find the note being dragged.
            dragNoteDOM = $(e.target);

            if (! dragNoteDOM.is(".note")) {
                // The button was pressed on an element within the note.
                dragNoteDOM = dragNoteDOM.parents(".note");
            }

            dragNote = dragNoteDOM.data("note");
            dragLastX = e.clientX;
            dragLastY = e.clientY;
            return false;
        };

        move = function (e) {
            var deltaX, deltaY, left, top;

            if (! dragNoteDOM) {
                // Nothing is being dragged.
                return false;
            }

            if (e.which !== 1) {
                // Mouse button was released; stop dragging.
                return stop(e);
            }

            // Delta is the difference between the current position in the
            // client window and the last reported position.
            deltaX = e.clientX - dragLastX;
            deltaY = e.clientY - dragLastY;

            // Get the position of the target.  We use the truncating
            // "feature" of parseInt to get rid of the "px" suffix and
            // convert the string to an integer.
            left = parseInt(dragNoteDOM.css('left'));
            top = parseInt(dragNoteDOM.css('top'));

            // Modify the position by the delta.
            left += deltaX;
            top += deltaY;

            dragNoteDOM.css("left", left);
            dragNoteDOM.css("top", top);

            // Remember the last reported position.
            dragLastX = e.clientX;
            dragLastY = e.clientY;
        };

        return {'start': start, 'stop': stop, 'move': move};
    })();

    select = (function () {
        var add, clear, set, subtract, addTitlebar, removeTitlebar;

        addTitlebar = function (noteDOM) {
            var top, height;

            // Create controls for removing and resizing the note.
            $('<span class="note-control note-remove glyphicon ' +
              'glyphicon-remove-sign"></span>').prependTo(noteDOM);
            $('<span class="note-control note-resize glyphicon ' +
              'glyphicon-resize-full-2x"></span>').appendTo(noteDOM);
        };

        removeTitlebar = function (noteDOM) {
            // Remove the removing and resizing controls.
            noteDOM.children(".note-control").remove();
        };

        add = function (e) {
            var noteDOM = $(e.currentTarget);

            if (! noteDOM.is(".note")) {
                // Clicked on the content; find the note iself.
                noteDOM = noteDOM.parents(".note");
            }

            if (! noteDOM.hasClass("selected")) {
                noteDOM.addClass("selected");
                addTitlebar(noteDOM);
            }
        };

        clear = function (e) {
            var selection = $(".note.selected");
            selection.removeClass("selected");
            selection.each(function (index, noteDOM) {
                removeTitlebar($(noteDOM));
            });
        };

        set = function (e) {
            clear();
            add(e);
        };

        subtract = function (e) {
            var noteDOM = $(e.currentTarget);
            if (! noteDOM.is(".note")) {
                // Clicked on the content; find the note itself.
                noteDOM = noteDOM.parents(".note");
            }

            if (noteDOM.hasClass("selected")) {
                noteDOM.removeClass("selected");
                removeTitlebar(noteDOM);
            }
        }

        return {'add': add, 'clear': clear, 'set': set, 'subtract': subtract};
    })();

    function onCreateNoteSuccess(id, note) {
        notepage.children.push(note);
        drawNote(note);
    }

    function onUpdateNotepageSuccess(id, result_block) {
        var notepage_revision_id = result_block['notepage_revision_id'];
        var results = result_block['results'];
        var i, result, note, pos_um, size_um, z_index, contents_markdown;

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

    
    function onNoteClick(e) {
        if (e.button === 0) {
            console.log("handling event: target=" + e.currentTarget);

            // Primary (left) button click.

            if (e.shiftKey || e.ctrlKey) {
                // Shift or control: add the note to the selection.
                select.add(e);
            } else if (e.altKey || e.metaKey) {
                // Alt or meta: subtract the note from the selection.
                select.subtract(e);
            } else {
                // No modifiers; reset the selection.
                select.set(e);
            }

            // Don't allow the event to be sent to the standard (e.g. select)
            // handlers.
            return false;
        } else {
            console.log("Not handling event; target=" + e.target +
                        " currentTarget=" + e.currentTarget +
                        " button=" + e.button);
        }
    }

    function onCanvasClick(e) {
        if (e.button === 0) {
            // Primary (left) button click.

            // Remove the selection.
            select.clear(e);
        }
    }

    function onWindowMouseMove(e) {
        // Handle mouse motion events.  If a drag event is in progress, this
        // updates the position of the note on the canvas.
        return drag.move(e);
    }

    function onWindowMouseUp(e) {
        // If a drag event is in progress, stop it.
        return drag.stop(e);
    }

    function onWindowBlur(e) {
        // If a drag event is in progress, stop it.
        return drag.stop(e);
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
        editor.keydown(onNoteEditKeyDown);
        editor.trigger("focus");

        // Don't let this event bubble.
        return false;
    }

    function onNoteEditKeyDown(e) {
        var target = $(e.target);
        var text;

        if (e.which === 27) {
            // Escape -- cancel editing.
            target.parent().remove();
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
    // Resize the viewport so its height is the height of the document.
    viewport.height(window.innerHeight - viewport.offset().top - 20);

    // Bind the "Create note" link.
    $("#createNoteAction").click(function () {
        dozer.create_note(window.notepage.node_id, onCreateNoteSuccess, null);
    });

    canvas.click(onCanvasClick);

    // Bind motion events to allow dragging of notes.
    $(window).mousemove(onWindowMouseMove);
    $(window).mouseup(onWindowMouseUp);
    $(window).on("blur", onWindowBlur);

    // Add each note to the document.
    (function () {
        for (var i = 0; i < window.notepage.children.length; ++i) {
            var note = window.notepage.children[i];
            drawNote(note);
        }
    })();
});
