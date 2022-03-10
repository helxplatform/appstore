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
/**
 * Set the X-CSRFToken header to the current `csrftoken` cookie value.
 * 
 * Required to be set on non-safe methods ^(?!GET|HEAD|OPTIONS|TRACE)$, e.g. POST.
 */
function setXCSRF(requestParams, context, ee, next) {
    const isRequiredMethod = (method) => !/^(GET|HEAD|OPTIONS|TRACE)$/i.test(method);
    if (!isRequiredMethod(requestParams.method)) return next();
    const baseURL = context.vars["target"] + "/";
    const cookies = requestParams.cookieJar.getCookiesSync(baseURL);
    const csrfCookie = cookies.find((c) => c.key === "csrftoken");
    const csrfToken = csrfCookie.value;
    if (!requestParams.hasOwnProperty("headers")) requestParams.headers = {};
    requestParams.headers["X-CSRFToken"] = csrfToken;
    if (requestParams.json) {
        requestParams.json["csrfmiddlewaretoken"] = csrfToken;
    }
    // console.log(requestParams);
    // console.log("==============================");

    return next();
}
function logUrl(requestParams, context, ee, next) {
    console.log(requestParams.method, requestParams.url);
    return next();
}

module.exports = {
    setXCSRF,
    logUrl,
    parseInitialApps,
    parseNewApps,
    getRandomApp,
    ...require("./cookies.js")
};