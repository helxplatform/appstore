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
function getCSRFToken(requestParams, response, context, ee, next) {
    const cookies = simpleParseSetCookies(response.headers["set-cookie"]);
    if (cookies.hasOwnProperty("csrftoken")) {
        context.vars["csrf_token"] = cookies["csrftoken"];
    }
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
    let apps;
    try {
        apps = JSON.parse(response.body);
    } catch (e) {
        // It seems that authentication can be rejected at this step.
        return next(new Error(response.body));
    }
    const oldAppIds = context.vars["apps"].map((app) => app.sid);
    const spawnedApp = apps.filter((app) => !oldAppIds.includes(app.sid))[0];
    context.vars["spawned_app"] = spawnedApp;
    return next();
}
function getRandomApp(requestParams, response, context, ee, next) {
    const availableApps = Object.values(context.vars["available_apps"]);
    context.vars["random_app"] = availableApps[Math.floor(Math.random()*availableApps.length)];
    return next();
}

module.exports = {
    disableCookies,
    getCSRFToken,
    parseInitialApps,
    parseNewApps,
    getRandomApp
};