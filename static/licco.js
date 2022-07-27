// Common functions only

var licco_timezone = "America/Los_Angeles";
var licco_formatdate = function() { return function(dateLiteral, render) { var dateStr = render(dateLiteral); return dateStr == "" ? "" : moment(dateStr).tz(licco_timezone).format("MMM/D/YYYY")}};
var licco_formatdatetime = function() { return function(dateLiteral, render) { var dateStr = render(dateLiteral); return dateStr == "" ? "" : moment(dateStr).tz(licco_timezone).format("MMM/D/YYYY HH:mm:ss")}};
