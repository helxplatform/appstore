/**
 * Parse an array of Set-Cookie values into a simple cookieName -> cookieValue map.
 * 
 * @param {string[]} header - Set-Cookie header values (without Set-Cookie: prefixes). As in response.headers['set-cookie'].
 */
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
    // if (typeof context.vars["csrf_token"] === "undefined") context.vars["csrf_token"] = "";
    if (cookies.hasOwnProperty("sessionid")) {
        context.vars["session_id"] = cookies["sessionid"];
        console.log("Update sess id");
    }
    if (cookies.hasOwnProperty("csrftoken")) {
        context.vars["csrf_token"] = cookies["csrftoken"];
        console.log("Update csrf");
    }
    return next();
}
function countApps(requestParams, response, context, ee, next) {
    // Set app_count context variable from GET /api/v1/instances/
    if (!context.vars.hasOwnProperty("app_count")) context.vars["app_count"] = [];
    context.vars["app_count"].push(JSON.parse(response.body).length);
    console.log(context.vars["app_count"]);
    return next();
}
function disableCookies(requestParams, context, ee, next) {
    context._enableCookieJar = false;
    if (requestParams.cookieJar) requestParams.cookieJar.removeAllCookiesSync();
    return next();
}
function parseInitialApps(requestParams, response, context, ee, next) {
    const apps = JSON.parse(response.body);
    context.vars["apps"] = apps;
    return next();
}
function parseNewApps(requestParams, response, context, ee, next) {
    const apps = JSON.parse(response.body);
    const oldAppIds = context.vars["apps"].map((app) => app.sid);
    const spawnedApp = apps.filter((app) => !oldAppIds.includes(app.sid))[0];
    context.vars["spawned_app"] = spawnedApp;
    return next();
}
module.exports = {
    disableCookies,
    updateSession,
    countApps,
    parseInitialApps,
    parseNewApps
};