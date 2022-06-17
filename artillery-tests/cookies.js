/**
 * Manual cookie/session management. Not in use.
 */
 function setCookies(requestParams, context, ee, next) {
    context._enableCookieJar = false;
    if (requestParams.cookieJar) requestParams.cookieJar.removeAllCookiesSync();
    if (!requestParams.hasOwnProperty("headers")) requestParams.headers = {};
    const sessid = context.vars["_sessid"];
    const csrf = context.vars["_csrf"];
    requestParams.headers["Cookie"] = `sessionid=${sessid}; csrftoken=${csrf}`;
    console.log(requestParams.url, requestParams.headers["Cookie"])
    return next();
}
function simpleParseSetCookies(header) {
    if (typeof header === "undefined") return {};
    return header
        // Set-Cookie always begins with <cookie-name>=<cookie-value>; where the hanging semicolon is optional
        .map((cookie) => cookie.split(";")[0].split("="))
        .reduce((acc, cur) => {
            const [ name, value ] = cur;
            acc[name] = value;
            return acc;
        }, {});
}
function updateSession(requestParams, response, context, ee, next) {
    const cookies = simpleParseSetCookies(response.headers["set-cookie"]);
    if (cookies.hasOwnProperty("sessionid")) {
        context.vars["_sessid"] = cookies["sessionid"];
        // console.log("Update sess id");
    }
    if (cookies.hasOwnProperty("csrftoken")) {
        context.vars["_csrf"] = cookies["csrftoken"];
        // console.log("Update csrf");
    }
    return next();
}
module.exports = {
    setCookies,
    updateSession
}