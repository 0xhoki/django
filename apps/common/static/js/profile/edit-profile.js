$(document).ready(function () {
    var is_guest;

    if(typeof(IS_GUEST) === "undefined"){
        is_guest = false;
    }else{
        is_guest = IS_GUEST;
    }

    $('#avatar').hover(
        function () {
            var img_field = $("input[name='avatar']");
            if ((img_field.val().length || img_field.data('img'))) {
                var x1 = 10;
                var y1 = 10;
                var x2 = 230;
                var y2 = 150;
                var orig_w = $(this).attr('data-crop-orig-w');

                if (typeof orig_w !== 'undefined' && orig_w !== '') {
                    var x = $(this).attr('data-crop-x');
                    var y = $(this).attr('data-crop-y');
                    var w = $(this).attr('data-crop-w');
                    var h = $(this).attr('data-crop-h');
                    var scale = orig_w / 240;
                    x1 = x / scale;
                    y1 = y / scale;
                    x2 = x1 + w / scale;
                    y2 = y1 + h / scale;
                }

                $(this).imgAreaSelect({
                    x1: x1,
                    y1: y1,
                    x2: x2,
                    y2: y2,
                    aspectRatio: '3:2',
                    handles: true,
                    onSelectEnd: function (img, selection) {
                        $('input[name="x1"]').val(selection.x1);
                        $('input[name="y1"]').val(selection.y1);
                        $('input[name="x2"]').val(selection.x2);
                        $('input[name="y2"]').val(selection.y2);
                    }
                });
                $('.add-thumb').show();
            }
        }
    );

    $('.add-thumb, .add-thumb a').on("click", function (event) {
        event.preventDefault();
        $('.addmember-form').submit();
    });

    $(".kendo_editor").kendoEditor({encoded: false});

    $('.avatar-input').on('change', function () {
        var name = $(this).val().split('\\').pop();
        $(this).closest('div').find('a').text(name);
    });

    $(".multiple").each(function (index) {
        $(this).kendoMultiSelect();
    });

    $("#id_date_joined_board, #id_term_start, #id_term_expires").kendoDatePicker({
        format: "MMM. dd, yyyy"
    });
    $('.upload-link, .add-pic').click(function (event) {
        event.preventDefault();
        $('.avatar-input').trigger('click');
    });

    $("input[name='avatar']").change(function () {
        if (this.files && this.files[0]) {
            var reader = new FileReader();

            reader.onload = function (e) {
                $('#avatar').attr('src', e.target.result);
            };

            reader.readAsDataURL(this.files[0]);
        }
    });

    $(".btn.add-another").click(function () {
        $('#id_add_another').val('True');
    });

    var $is_current_profile = $('#current_user_profile_header');
    if ($is_current_profile.length) {
        var warning_text = $is_current_profile.attr('data-warning'),
            title_text = $is_current_profile.attr('data-title'),
            confirm_text = $is_current_profile.attr('data-confirm'),
            cancel_text = $is_current_profile.attr('data-cancel');

        $('#id_is_active').change(function () {
            if ($(this).val() != 'True') {
                show_swal_confirm(function () {
                    selectMe('id_is_active', 0, 1);
                });
            }
        });

        $('#id_is_admin').change(function () {
            if (!$(this).is(":checked")) {
                show_swal_confirm(function () {
                    $('#id_is_admin').prop('checked', true).change();
                    if(is_guest && $('#id_role').val()!=STAFF_ROLE_VALUE){
                        // NOTE: hard-code. should be fixed lateer. "2" means: staff
                        // Because of "selectMe" function.
                        selectMe('id_role', 2, 0);
                    }
                });
            }
        });

        function show_swal_confirm(cancel_callback) {
            swal({
                title: title_text,
                text: warning_text,
                type: 'warning',
                showCancelButton: true,
                confirmButtonClass: 'bg-primary',
                cancelButtonClass: 'bg-success',
                confirmButtonText: confirm_text,
                cancelButtonText: cancel_text
            }).then(
                function () {
                },
                cancel_callback
            );
        }
    }

    $('#id_role').change(function () {
        if(is_guest){
            if( $(this).val() == STAFF_ROLE_VALUE){
                $('.choose-admin').css('display', 'inline-block');
            }else{
                $('.choose-admin').css('display', 'none');
                if ($('#id_is_admin').is(":checked")) {
                    $('#id_is_admin').prop('checked', false).change();
                }
            }
        }
    }).change();

});
