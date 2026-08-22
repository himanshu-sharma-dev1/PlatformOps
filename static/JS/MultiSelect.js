document.addEventListener("DOMContentLoaded", function () {
    var multipleSelects = document.querySelectorAll(".multiple_select");

    multipleSelects.forEach(function (select) {
        select.addEventListener("mousedown", function (e) {
            if (e.target.tagName === "OPTION" || e.target.type === "checkbox") {
                return;
            }
            this.classList.toggle("multiple_select_active");
        });

        select.addEventListener("blur", function () {
            this.classList.remove("multiple_select_active");
        });

        var options = select.querySelectorAll("option");
        options.forEach(function (option) {
            option.addEventListener("mousedown", function (e) {
                e.preventDefault();
                this.selected = !this.selected;
                this.parentNode.dispatchEvent(new Event("change", { bubbles: true }));
            });
        });
    });

    var myFilter = document.getElementById("user_group");
    myFilter.addEventListener("change", function () {
        var selectedOptions = Array.from(myFilter.options)
            .filter(function (option) {
                return option.selected;
            })
            .map(function (option) {
                return option.value;
            })
            .join(", ");

        var documentStyle = document.documentElement.style;
        if (selectedOptions !== "") {
            documentStyle.setProperty("--text", "'Selected: " + selectedOptions + "'");
        } else {
            documentStyle.setProperty("--text", "'Select values'");
        }
    });
});
