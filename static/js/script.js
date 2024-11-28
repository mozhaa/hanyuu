$(() => {
    $('*[data-href]').on('click', function() {
        window.location = $(this).data("href");
    });

    $('.add-button').each(function() {
        let card = $(this).parent();
        let mal_id = card.data("mal-id");
        $(this).click(function() { 
            fetch(`/anime?mal_id=${mal_id}`, {
                method: "POST",
            }).then(response => {
                if (response.ok)
                    card.addClass("added");
                else
                    response.text().then((text) => { console.log(text) })
            })
        });
    })

    $('.goto-button').each(function() {
        let card = $(this).parent();
        let mal_id = card.data("mal-id");
        $(this).click(function() { 
            window.location = `/anime/${mal_id}`;
        });
    })
});