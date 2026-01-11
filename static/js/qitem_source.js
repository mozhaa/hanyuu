(function() {
    function updatePathLink(form) {
        const platform = form.find('select[name="platform"]').val();
        const path = form.find('input[name="path"]').val();
        const link = form.find('.path-link');
        
        if (platform === 'yt-dlp') {
            link.attr('href', path);
        } else {
            link.removeAttr('href');
        }
    }
    
    $(document).ready(function() {
        $('select[name="platform"], input[name="path"]').on('input change', function() {
            updatePathLink($(this).closest('form'));
        });
        
        $('.path-link').each(function() {
            updatePathLink($(this).closest('form'));
        });
    });
})();
