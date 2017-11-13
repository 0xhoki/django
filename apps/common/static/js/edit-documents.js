function delete_document(data){
    $('#item_' + data.doc_id).fadeOut(500, function(){
        var board_book = '<li><label for="id_board_book">' + gettext('Add Board Book') + '</label><input id="id_board_book" name="board_book" type="file"></li>';
        var agenda = '<li><label for="id_agenda">' + gettext('Add Agenda') + '</label><input id="id_agenda" name="agenda" type="file"></li>';
        var minutes = '<li><label for="id_minutes">' + gettext('Add Minutes') + '</label><input id="id_minutes" name="minutes" type="file"></li>';
        var closest_li = $(this).closest('.archives').parent();

        if (data.doc_type == '4') { closest_li.before(board_book); board_book_kendo_init(); }
        if (data.doc_type == '1') { closest_li.before(agenda); agenda_kendo_init(); }
        if (data.doc_type == '2') { closest_li.before(minutes); minutes_kendo_init(); }

        if ($(this).parent().children('.edit-uploader-block').length) $(this).parent().remove();
        else $(this).remove();
    });
}

function update_document(doc_id, doc_type){
    var item = $('#item_' + doc_id);

    // remove previous uploader-blocks for documents
    if (doc_type == '3') {
        var archives = item.closest('.archives');
        archives.find('.edit-block > .item').unwrap();
        archives.find('.edit-uploader-block').remove();
    }

    if (!item.next().is('.edit-uploader-block')) {
        item.wrap('<div class="edit-block">');
        var board_book = '<div class="edit-uploader-block"><label for="id_board_book">' + gettext('Edit Board Book') + '</label><input id="id_board_book" name="board_book" type="file"></div>';
        var agenda = '<div class="edit-uploader-block"><label for="id_agenda">' + gettext('Edit Agenda') + '</label><input id="id_agenda" name="agenda" type="file"></div>';
        var minutes = '<div class="edit-uploader-block"><label for="id_minutes">' + gettext('Edit Minutes') + '</label><input id="id_minutes" name="minutes" type="file"></div>';
        var temp_doc = '<div class="edit-uploader-block"><label for="id_temp_doc">' + gettext('Edit Document') + '</label><input id="id_temp_doc" name="other" type="file"></div>';
        if (doc_type == '1') { item.after(agenda); agenda_kendo_init(); }
        if (doc_type == '2') { item.after(minutes); minutes_kendo_init(); }
        if (doc_type == '3') { item.after(temp_doc); temp_doc_kendo_init(); }
        if (doc_type == '4') { item.after(board_book); board_book_kendo_init(); }
    }
}

function onBoardBookUpload(e) {
    var item_temp = $('#id_board_book');
    e.data = {'csrfmiddlewaretoken': csrftoken, 'type': item_temp.attr('name')};
    upload(e, item_temp)
}

function onAgendaUpload(e) {
    var item_temp = $('#id_agenda');
    e.data = {'csrfmiddlewaretoken': csrftoken, 'type': item_temp.attr('name')};
    upload(e, item_temp)
}

function onMinutesUpload(e) {
    var item_temp = $('#id_minutes');
    e.data = {'csrfmiddlewaretoken': csrftoken, 'type': item_temp.attr('name')};
    upload(e, item_temp)
}

function onDocsUpload(e) {
    e.data = {'csrfmiddlewaretoken': csrftoken, 'type': $('#id_other').attr('name')};
}

function onTempDocsUpload(e) {
    var item_temp = $('#id_temp_doc');
    e.data = {'csrfmiddlewaretoken': csrftoken, 'action': 'update', 'type': item_temp.attr('name')};
    upload(e, item_temp)
}

function onSuccess(e) {
    console.log("Status: " + e.response.status);
    console.log("Object pk: " + e.response.pk);
    var group = $(this.element).data('group');
    add_to_uploaded(e.response.pk, group);
    if (e.response.html) {
        var html = e.response.html;
        var type = e.response.type;
        if (type == 'other') type = 'temp_doc';
        var item_temp = $('#id_' + type).closest('.edit-uploader-block');
        item_temp.before(html);
    }
}

function add_to_uploaded(pk, group) {
    var uploaded = $("#id_uploaded");
    var value = uploaded.val();
    if (value) value += ',';
    uploaded.val(value + pk);
}

function upload(e, item_temp){
    var closest_edit_block_item = item_temp.closest('.edit-block').find('.item');
    var edit_item = closest_edit_block_item.find('.edit');
    var download_item = closest_edit_block_item.find('.download');
    var document_id = edit_item.attr('data-doc-id') || download_item.attr('data-doc-id');
    e.data['meeting'] = edit_item.attr('data-doc-meeting') || download_item.attr('data-doc-meeting');
    var request = $.ajax({
        url: DOC_DELETE_URL,
        type: "POST",
        data: {
            document_id: document_id,
            action: 'update'
        },
        success: function(response) {
            closest_edit_block_item.remove();
        }
    });
}
