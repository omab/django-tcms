$(function(){
    function _toggle(link) {
        if (link && link.attr('id')) {
            var id = link.attr('id').replace('link_', 'container_');
            link.children('.label').toggle();
            $('#' + id).slideToggle();
            link.parent('h2').toggleClass('collapsed');
            return id.replace('container_', '');
        }
    }

    $('.collapse').click(function(e) {
        e.preventDefault();
        document.location.hash = _toggle($(this));
    });

    $('.warning').click(function(e) {
        if (!confirm("This action can not be undone, proceed?")) {
            e.preventDefault();
        }
    });

    if (typeof CKEDITOR != "undefined") {
        $('.richedit').click(function(e) {
            e.preventDefault();
            var link = $(this),
                tid = 'textarea#' + link.attr('id').replace('text_', '');

            try {
                $(tid).ckeditorGet().destroy();
                link.html('Rich editor');
            } catch(err) {
                link.prev(tid).ckeditor({customConfig: ckeditorConfig,
                                         height: '200',
                                         width: '90%',
                                         toolbar: 'tCMS'})
                              .end()
                    .html('Plain editor');
            }
        });
    }
			
    $('a.file-preview').fancybox({'titleShow': false});

    $('#toggler').click(function(e) {
        $(this).parents('table').find('input[type="checkbox"]')
                                .attr('checked', $(this).attr('checked'));
    });

    $('.value-form').ajaxForm({
        dataType: 'json',
        iframe: true,
        data: {'is_ajax': true},
        beforeSubmit: function(data, form, options) {
            form.find('.loading').show();
        },
        success: function(data, status, xhr, form) {
            form.find('.loading').hide();
            if (data.status == 'error') {
                $.each(data.errors, function(idx, error) {
                    form.find('#id_' + error.field)
                            .parent('.form-row')
                                .addClass('errors')
                                .find('.errorlist')
                                    .html('<li>' + error.messages.join('</li><li>') + '</li>')
                                    .fadeIn(550);
                });
            } else {
                form.find('.form-row').removeClass('errors');
                form.find('.errorlist').html('').hide();
                form.find('.saved').fadeIn(550, function(){ $(this).fadeOut(4000); });
            }
        }
    });

    if (document.location.hash) {
        $.each(document.location.hash.replace('#', '').split(','),
               function(idx, hash) {
                    if (hash) {
                        hash = hash.split('-');
                        for (var i=2; i <= hash.length; i++) {
                            _toggle($('#link_' + hash.slice(0, i).join('-')));
                        }
                    }
               });
    }
});
