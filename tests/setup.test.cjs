const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const page = fs.readFileSync(path.join(__dirname, "../MyDashboard/setup.html"), "utf8");
const script = page.match(/<script>([\s\S]*?)<\/script>/)[1];

function openPage() {
    const elements = {};
    for (const id of ["current", "city", "country", "search", "find", "save", "results", "selection", "message"]) {
        elements[id] = {
            value: "", disabled: false, textContent: "", children: [],
            appendChild(child) { this.children.push(child); }
        };
    }
    const requests = [];
    class XHR {
        constructor() { this.headers = {}; requests.push(this); }
        open(method, url) { this.method = method; this.url = url; }
        setRequestHeader(name, value) { this.headers[name] = value; }
        send(body) { this.body = body; }
        abort() {}
        respond(status, data) {
            this.status = status;
            this.responseText = JSON.stringify(data);
            this.readyState = 4;
            this.onreadystatechange();
        }
    }
    vm.runInNewContext(script, {
        document: {
            getElementById(id) { return elements[id]; },
            createElement() { return {}; }
        },
        XMLHttpRequest: XHR,
        setTimeout() { return 1; },
        clearTimeout() {}
    });
    requests[0].respond(200, {
        name: "Washington, DC", timezone: "America/New_York", saved: false
    });
    return { elements, requests };
}

test("city search requires selection and saves the selected result", () => {
    const { elements, requests } = openPage();
    assert.match(elements.current.textContent, /Default city: Washington, DC/);
    assert.equal(elements.save.disabled, true);
    elements.city.value = "Tokyo";
    elements.country.value = "JP";
    elements.search.onsubmit();
    assert.equal(requests[1].url, "/api/search?q=Tokyo&country=JP");
    const city = {
        name: "Tokyo", region: "Tokyo", country: "Japan",
        timezone: "Asia/Tokyo", latitude: 35.68, longitude: 139.69
    };
    requests[1].respond(200, { results: [city] });
    assert.equal(elements.save.disabled, true);
    elements.results.children[0].onclick();
    assert.equal(elements.save.disabled, false);
    elements.save.onclick();
    assert.equal(requests[2].method, "POST");
    assert.deepEqual(JSON.parse(requests[2].body), city);
    assert.ok(requests[2].headers["X-MyDashboard-Token"]);
    requests[2].respond(200, { ...city, display_name: "Tokyo" });
    assert.match(elements.current.textContent, /Saved city: Tokyo/);
    assert.match(elements.message.textContent, /Return to KUAL/);
});

test("empty results and failures never report a successful save", () => {
    const { elements, requests } = openPage();
    elements.city.value = "Nowhere";
    elements.search.onsubmit();
    requests[1].respond(200, { results: [] });
    assert.match(elements.message.textContent, /No cities found/);
    assert.equal(elements.save.disabled, true);
    elements.search.onsubmit();
    requests[2].respond(502, { error: "Check Wi-Fi" });
    assert.equal(elements.message.textContent, "Check Wi-Fi");
    assert.equal(elements.save.disabled, true);
});

test("new search discards an earlier selection and save failure stays visible", () => {
    const { elements, requests } = openPage();
    elements.city.value = "Tokyo";
    elements.search.onsubmit();
    requests[1].respond(200, {
        results: [{ name: "Tokyo", region: "Tokyo", country: "Japan", timezone: "Asia/Tokyo" }]
    });
    elements.results.children[0].onclick();
    elements.save.onclick();
    requests[2].respond(500, { error: "Could not save settings" });
    assert.equal(elements.message.textContent, "Could not save settings");
    assert.match(elements.current.textContent, /Default city/);
    elements.city.value = "London";
    elements.search.onsubmit();
    assert.equal(elements.save.disabled, true);
});
