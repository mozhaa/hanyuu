function create_anime(el) {
    let card = $(el).parent();
    let mal_id = card.data("mal-id");
    fetch(`/animes?mal_id=${mal_id}`, {
        method: "POST",
    }).then((response) => {
        if (response.ok) card.addClass("added");
        else
            response.text().then((text) => {
                console.log(text);
            });
    });
}
