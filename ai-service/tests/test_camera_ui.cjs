// Minimal DOM/socket stubs; no dependencies, camera or network.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

class Element {
    constructor() { this.children = []; this.textContent = ""; }
    appendChild(child) { this.children.push(child); }
    replaceChildren() { this.children = []; }
    addEventListener() {}
    getContext() { return {clearRect() {}}; }
    set innerHTML(_) { throw new Error("Unsafe HTML rendering"); }
}
const elements = new Map();
let timers = 0;
class Socket {
    constructor() { this.listeners = {}; }
    addEventListener(name, fn) { this.listeners[name] = fn; }
    close() {}
}
const context = vm.createContext({
    document: {
        getElementById(id) {
            if (!elements.has(id)) elements.set(id, new Element());
            return elements.get(id);
        },
        createElement() { return new Element(); },
    },
    window: {addEventListener() {}},
    location: {protocol: "https:", host: "offline"},
    WebSocket: Socket, console,
    setTimeout() { timers++; return timers; }, clearTimeout() {},
});
vm.runInContext(fs.readFileSync(path.join(__dirname,
    "../yolo-service/camera_control/static/camera.js"), "utf8"), context);
const run = code => vm.runInContext(code, context);
const body = elements.get("recognitionResults");
const html = fs.readFileSync(path.join(__dirname,
    "../yolo-service/camera_control/static/camera.html"), "utf8");
for (const heading of ["Track ID", "SKU", "Име", "Бележка", "Сходство (%)", "Статус", "Час"]) {
    assert.match(html, new RegExp(`<th scope="col">${heading.replace(/[()%]/g, "\\$&")}</th>`));
}
run("renderRecognitionEvents([], true)");
assert.equal(body.children[0].children[0].colSpan, 7);
run(`renderRecognitionEvents(Array.from({length: 70}, (_, track_id) =>
    ({track_id, status: "sent", time: "2026-11-26T12:00:00Z"})))`);
assert.equal(body.children.length, 50);
assert.equal(body.children[49].children[0].textContent, "20");
assert.equal(body.children[49].children[5].textContent, "Изпратено");
run(`renderRecognitionEvents([{track_id: 69, status: "matched",
    sku: "<img onerror=alert(1)>", name: "<b>Product</b>", note: "<script>x</script>",
    similarity: .875, time: "2026-11-26T12:00:01Z"}])`);
assert.equal(body.children.length, 50);
assert.equal(body.children[0].children[0].textContent, "69");
assert.equal(body.children[0].children[1].textContent, "<img onerror=alert(1)>");
assert.equal(body.children[0].children[2].textContent, "<b>Product</b>");
assert.equal(body.children[0].children[3].textContent, "<script>x</script>");
assert.equal(body.children[0].children[4].textContent, "87.5%");
assert.equal(body.children[0].children[5].textContent, "Разпознато");
assert.equal(body.children[0].className, "recognition-matched");
const unchangedRow = body.children[0];
run("renderRecognitionEvents([]); renderRecognitionEvents(undefined)");
assert.equal(body.children[0], unchangedRow);
run('renderRecognitionEvents([null, {track_id: 1, status: "__proto__"}])');
assert.equal(body.children[0], unchangedRow);
assert.equal(body.children.length, 50);
assert.equal(timers, 0);
run("cameraRunning = true; connectTracking(); oldSocket = socket");
assert.equal(body.children.length, 1);
run(`socket.listeners.message({data: JSON.stringify({error: "test",
    recognition_events: [{track_id: 1, status: "unknown"}]})})`);
assert.equal(body.children[0].children[5].textContent, "Непознато");
assert.equal(timers, 1); // Only the pre-existing frame-response scheduling.
run("stopTracking()");
assert.equal(body.children[0].children[5].textContent, "Непознато");
run("cameraRunning = true; connectTracking()");
run(`oldSocket.listeners.message({data: JSON.stringify({
    recognition_events: [{track_id: 1, status: "matched", sku: "stale"}]})})`);
assert.equal(body.children[0].children[0].colSpan, 7);
assert.equal(timers, 1);
console.log("Camera UI: metadata columns, bounds, safe text, correlation, reset, stale socket and pacing passed");
