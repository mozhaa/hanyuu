function add_new(el) {
    let action = $(el).data("action");
    fetch(action, {
        method: "POST",
    }).then((response) => {
        if (response.ok)
            response.text().then((text) => {
                $(el).parent().append(text);
                $("body, html").animate(
                    {
                        scrollTop: $(el).parent().children().last().offset().top,
                    },
                    500
                );
            });
        else
            response.text().then((text) => {
                alert(text);
            });
    });
}
