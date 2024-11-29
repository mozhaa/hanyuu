function add_item(el) {
    let list = $(el).closest(".editable-list");
    let item = $(el).closest(".editable-list-item");
    let parent_id = item.data("id") || $("head").data("anime-id");
    let base_action = list.data("base-action");
    let action = `${base_action}?parent_id=${parent_id}`;
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
    let list = $(el).closest(".editable-list");
    let item = $(el).closest(".editable-list-item");
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

function update_item(el) {
    let list = $(el).closest(".editable-list");
    let item = $(el).closest(".editable-list-item");
    let base_action = list.data("base-action");
    console.log(base_action);
    fetch(base_action, {
        method: "PUT",
        body: serialize_form($(el).closest("form")),
        headers: {
            "content-type": "application/json",
        },
    }).then((response) => {
        if (response.ok) console.log("Successfully updated");
        else
            response.text().then((text) => {
                alert(text);
            });
    });
}

function serialize_form(form) {
    let values = {};
    form.find(":input").each(function () {
        let name = $(this).attr("name");
        if (name === undefined) return;
        let type = $(this).attr("type");
        let val = $(this).val();
        values[name] = ["number", "range"].includes(type) ? val * 1 : val;
    });
    return JSON.stringify(values);
}
