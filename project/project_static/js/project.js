$(document).ready(function() {
    $.fn.popover.defaults = $.extend($.fn.popover.defaults, {
        html: true,
        title: 'data-popover-title',
        content: function() {
            return $(this).children('div').html();
        },
        offset: 10
    });
    $('.rel_popover').popover();
    $('.rel_popover_left').popover({
        placement: 'left'
    });

    var extra_editor = $('#extra-editor');
    if (extra_editor.length) {
        // Ajaxify post for the extra editor

        function close_editor() {
            // close the editor
            extra_editor.animate({
                opacity: 0
            }, 'fast', function() {
                $(this).hide();
            });
        } // close

        var actions = {
            '/private/notes/delete/': 'Deleting note',
            '/private/notes/save/': 'Saving note',
            '/private/tags/delete/': 'Deleting tags',
            '/private/tags/save/': 'Saving tags',
        };

        var overlay = $('<div id="extra-ajax-overlay" />');
        extra_editor.append(overlay);

        // manage submit of forms
        extra_editor.delegate('form', 'submit', function(ev) {
            var form = $(this);

            // if an allowed action ?
            var post_url = form.attr('action');
            if (!actions[post_url]) {
                return true;
            }

            // display the ovjerlay
            overlay.text(actions[post_url]+'…');
            overlay.show().animate({
                opacity: 0.5
            }, 'fast', function() {
                $(this).addClass('displayed');
            });

            // simple post of the query
            $.ajax({
                type: 'POST',
                url: post_url,
                data: form.serialize(),
                context: extra_editor,
                dataType: 'text html'
            }) // base ajax

            // action on success
            .success(function(data, text_status, xhr) {
                // parse html
                var j_data = $(data);
                // find interesting parts
                var new_body = j_data.find('.modal-body');
                var new_messages = j_data.find('ul.messages');
                if (!new_body.length) {
                    // action if we want to close
                    close_editor();
                    var messages = $('#container .messages');
                    if (messages.length) {
                        messages.replaceWith(new_messages);
                    } else {
                        $('#container').prepend(new_messages);
                    }
                } else {
                    // action if we stay in the window
                    new_body.prepend(new_messages);
                    extra_editor.find('.modal-body').replaceWith(new_body);
                }
            }) // success

            .error(function(xhr, text_status) {
                alert("We couldn't save your data : " + text_status);
            }) // error

            .complete(function() {
                // when done, hide the overlay
                overlay.removeClass('displayed').animate({
                    opacity: 0
                }, 'fast', function() {
                    $(this).hide();
                });
            }); // complete

            return false;
        }); // form submit

        // manage note save buttons
        extra_editor.delegate('#note-save-form input[type=submit]', 'click', function() {
            var button = $(this),
                form = button.parents('form'),
                hidden = form.find('input[type=hidden][name=submit-close]');
            if (button.attr('name') == 'submit-close') {
                if (!hidden.length) {
                    hidden = $('<input />').attr('type', 'hidden').attr('name', 'submit-close').attr('value', button.val());
                    form.append(hidden);
                }
            } else if (hidden.length) {
                hidden.remove();
            }
        }); // note-save-form click;

        // manage close buttons
        extra_editor.find('.close, .modal-footer .btn').click(function() {
            close_editor();
            return false;
        });

    } // if extra_editor
});
