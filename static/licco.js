// Common functions only

var licco_formatdate = function() { return function(dateLiteral, render) { var dateStr = render(dateLiteral); return dateStr == "" ? "" : dayjs(dateStr).format("MMM/D/YYYY")}};
var licco_formatdatetime = function() { return function(dateLiteral, render) { var dateStr = render(dateLiteral); return dateStr == "" ? "" : dayjs(dateStr).format("MMM/D/YYYY HH:mm:ss")}};
var licco_prec7float = function() {
    return function(numLiteral, render) {
        let numStr = render(numLiteral);
        if (numStr === "") {
            return ""
        }
        let num = _.toNumber(numStr);
        return num.toFixed(7);
    }
};


var licco_musrdr = function(tmpl, data) {
    data.FormatDateTime = licco_formatdatetime;
    data.FormatDate = licco_formatdate;
    data.prec7float = licco_prec7float;
    return Mustache.render(tmpl, data);
}

const licco_validations = {
    "notempty": function(elem) { return _.isEmpty($(elem).val()) }
}
var licco_validate_form = function() {
    let ret = true;
    $("#global_mdl_holder").find(".errormsg").empty().addClass("d-none");
    $("#global_mdl_holder").find("[data-validation]").removeClass("is-invalid");
    _.each($("#global_mdl_holder").find("[data-validation]"), function(elem){
        _.each($(elem).attr("data-validation").split(" "), function(validation){
            if(licco_validations[validation](elem)) {
                $(elem).addClass("is-invalid");
                ret = false;
                return false;
            }
        })
    })
    return ret;
}

let licco_helptlbr = function(elem) {
    if(elem.find(".help").length < 1) {
        elem.append(`<span class="icn help"><i class="fa-solid fa-question fa-lg" title="Machine Configuration Database help ( on confluence)"></i></span>`);
        elem.find(".help").on("click", function() { window.open("https://confluence.slac.stanford.edu/display/PCDS/Machine+Configuration+Database+Guide", "_blank").focus(); })
      }
}

let showToast = function(url, data) {
    $.ajax(url)
    .done(function(tmpl){
        Mustache.parse(tmpl);
        $("#global_toast_holder").empty().append(Mustache.render(tmpl, data));
        bootstrap.Toast.getOrCreateInstance($("#global_toast_holder").find(".toast")[0]).show();
    })
}