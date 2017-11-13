$(document).ready(function(){
    var inputAddress = $('#location');
    var geocoder = new google.maps.Geocoder();

    function makeMapLink() {
        geocoder.geocode({'address' : inputAddress.text()}, function(result, status){
            if (result.length > 0) {
                var location = result[0].geometry.location;
                var url = 'https://www.google.com/maps/?z=15&q=loc:' + location.lat() + ',' + location.lng();
                console.log("Geocoder result", result, url);

                $('.location-link').attr('href', url).show();

                var mapObj = new GMaps({
                    el: '#map',
                    lat: location.lat(),
                    lng: location.lng(),
                    mapTypeControl: false,
                    draggable: false,
                    scaleControl: false,
                    scrollwheel: false,
                    navigationControl: false,
                    streetViewControl: false,
                    disableDefaultUI: true,
                    zoom: 10

                });
                mapObj.addMarker({
                    lat: location.lat(),
                    lng: location.lng()
                });
            }
        });
    }

    makeMapLink();

    // add this event to calendar
    $('.add-to-cal').click(function () {

        // check disabled
        if( $(this).is('[disabled=disabled]') ){
            show_alert(WARNING, 'Please enable to add calendar');
            return;
        }

        // get POST data
        var meeting_id = $('#meeting_id').val();
        var connect_type = '';
        if( $(this).hasClass('google') ){
            connect_type = 'google';
        }else if( $(this).hasClass('office') ){
            connect_type = 'office';
        }else if( $(this).hasClass('ical') ){
            connect_type = 'ical';
        }else{
            return
        }

        // send ajax request
        $.ajax({
            url: '/add-to-calendar/',
            method: 'POST',
            data:{
                'meeting_id': meeting_id,
                'connect_type': connect_type,
                'csrfmiddlewaretoken': csrftoken
            },
            success: function (resp) {

                $('#alert-board .message').html(resp.msg);

                if(resp.result === 'success'){
                    show_alert(SUCCESS, resp.msg);
                }else{
                    show_alert(FAIL, resp.msg);
                }
            },
            error: function (resp) {
                show_alert(FAIL, 'Something was wrong !');
            }

        });
    });

    $(".roster-collapse").click(function () {
        $(".roster-content").slideToggle();
        var $i = $(".roster-collapse i");
        if ( $i.hasClass('fa-chevron-up') ){
            $i.removeClass('fa-chevron-up').addClass('fa-chevron-down');
        }else if( $i.hasClass('fa-chevron-down') ){
            $i.removeClass('fa-chevron-down').addClass('fa-chevron-up');
        }
    });

    $(".radio-lbl").change(function () {
        var $radio = $(this);
        // console.log($('input[name="meeting_attendance_565"]:checked').val());

        $.ajax({
            url: window.location.pathname,
            type: 'POST',
            data: {
                user: $radio.attr("data-user-id"),
                present: $radio.attr("data-present-value"),
                meeting: $('#meeting_id').val()
            }
        }).then(
            function (resp) {
                if (resp==='success') {
                    show_alert(SUCCESS, "Successfully set attendance.");
                }else{
                    show_alert(FAIL, resp);
                    $radio.find('input').prop('checked', false);
                }
            },
            function (error) {
                show_alert(FAIL, "Unable to set/change Attendance. Something went wrong.");
                $radio.find('input').prop('checked', false);
                console.log(error);
            }
        );

    });
});
