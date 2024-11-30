function add_item(el) {
    let list = $(el).closest(".editable-list");
    let item = $(el).closest(".editable-list-item");
    let parent_id = item.data("id") || $("head").data("anime-id");
    let base_action = list.data("base-action");
    let action = `${base_action}?parent_id=${parent_id}`;
    fetch(action, {
        method: "POST",
    }).then((response) => {
        if (response.ok) {
            response.text().then((text) => {
                let new_item = $(text);
                list.append(new_item);
                bind_inputs();
                $("body, html").animate({ scrollTop: new_item.offset().top }, 500);
            });
        } else {
            response.text().then((text) => {
                alert(text);
            });
        }
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
    let base_action = list.data("base-action");
    fetch(base_action, {
        method: "PUT",
        body: serialize_form($(el).closest("form")),
        headers: {
            "content-type": "application/json",
        },
    }).then((response) => {
        if (response.ok) { 
            console.log("Successfully updated"); 
            $(el).closest("form").removeClass("unsaved");
        } else
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

function delete_anime() {
    let anime_id = $("head").data("anime-id");
    fetch(`/animes/${anime_id}`, {
        method: "DELETE",
    }).then((response) => {
        if (response.ok) window.location = "/";
        else
            response.text().then((text) => {
                alert(text);
            });
    });
}

function update_alias(el) {
    fetch("/animes", {
        method: "PUT",
        body: serialize_form($(el).closest("form")),
        headers: {
            "content-type": "application/json",
        },
    }).then((response) => {
        if (response.ok) { 
            console.log("Successfully updated"); 
            $(el).closest("form").removeClass("unsaved");
        }
        else
            response.text().then((text) => {
                alert(text);
            });
    });
}

function update_range(num_id, rng_id) {
    $(`#${rng_id}`).val($(`#${num_id}`).val());
}

function update_number(rng_id, num_id) {
    $(`#${num_id}`).val($(`#${rng_id}`).val());
}

function enforceMinMax(el) {
    // https://stackoverflow.com/a/59291891
    if (el.value != "") {
        if (parseInt(el.value) < parseInt(el.min)) {
            el.value = el.min;
        }
        if (parseInt(el.value) > parseInt(el.max)) {
            el.value = el.max;
        }
    }
}

function bind_inputs() {
    $(":input").each(function() {
        $(this).change(function() {
            $(this).closest("form").addClass("unsaved");
        })
    })
}

$(bind_inputs)