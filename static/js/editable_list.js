function add_item(el) {
    let list = $(el).parents(".editable-list");
    let base_action = list.data("base-action");
    let anime_id = $("head").data("anime-id");
    let action = `${base_action}?parent_id=${anime_id}`;
    fetch(action, {
        method: "POST",
    }).then((response) => {
        if (response.ok)
            response.text().then((text) => {
                let new_item = $(text);
                list.append(new_item);
                $("body, html").animate({ scrollTop: new_item.offset().top }, 500);
            });
        else
            response.text().then((text) => {
                alert(text);
            });
    });
}

function delete_item(el) {
    let list = $(el).parents(".editable-list");
    let item = $(el).parents(".editable-list-item");
    let id = item.data("id");
    let base_action = list.data("base-action");
    fetch(`${base_action}/${id}`, {
        method: "DELETE",
    }).then((response) => {
        if (response.ok) item.remove();
        else
            response.text().then((text) => {
                alert(text);
            });
    });
}
