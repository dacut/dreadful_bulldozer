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

        style = {'width': (note.width_um * pixels_per_um),
                 'height': (note.height_um * pixels_per_um),
                 'left': (note.x_pos_um * pixels_per_um),
                 'top': (note.y_pos_um * pixels_per_um),
                 'z-index': note.z_index}

        domNode.css(style);

        console.log("Setting DOM css: " + JSON.stringify(style))

        // FIXME: Need to render Markdown into HTML.
        domNode.text(note.contents_markdown);
    }

    $("#createNoteAction").click(function () {
        console.log("create note clicked");
        dozer.create_note(node.full_name, onCreateNoteSuccess, null);
    });
});
