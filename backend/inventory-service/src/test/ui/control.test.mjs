import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import test from "node:test";
import vm from "node:vm";
const source = readFileSync(new URL("../../main/resources/static/ui/core.js", import.meta.url), "utf8");
const {request, adjustmentBody, createAdjustments} = await import(
    "data:text/javascript;base64," + Buffer.from(source).toString("base64"));
function storage() {
    const data = new Map();
    return {
        getItem: key => data.get(key) ?? null,
        setItem: (key, value) => data.set(key, value),
        removeItem: key => data.delete(key),
    };
}
const ok = value => ({ok: true, json: async () => value});

test("positive integer quantities only, trim optional note", () => {
    assert.deepEqual(adjustmentBody("INCREASE", "3", " shelf "), {
        operation: "INCREASE", quantity: 3, source: "MANUAL_UI", note: "shelf",
    });
    assert.equal(adjustmentBody("DECREASE", "1", " ").note, null);
    for (const n of ["", "0", "-1", "1.5", "NaN", "Infinity", "2147483648"]) {
        assert.throws(() => adjustmentBody("INCREASE", n, ""));
    }
    assert.throws(() => adjustmentBody("SET", 1, ""));
    assert.throws(() => adjustmentBody("INCREASE", 1, "a".repeat(2001)));
});
test("API requests use the same-origin inventory namespace", async () => {
    await request("/products?page=0", {}, async (url, options) => {
        assert.equal(url, "/api/inventory/v1/products?page=0");
        assert.equal(options.cache, "no-store");
        return ok({content: []});
    });
});
test("ambiguous network failure survives reload and retries exact key/body", async () => {
    const store = storage();
    const calls = [];
    const client = createAdjustments(store, async (url, options) => {
        calls.push({url, ...options});
        throw new Error("network unavailable");
    }, () => "fixed-idempotency-key");
    client.begin(7, adjustmentBody("INCREASE", "2", "test"));
    await assert.rejects(client.send());
    assert.throws(() => client.begin(7, adjustmentBody("INCREASE", "2", "")));
    const reloaded = createAdjustments(store, async (url, options) => {
        assert.equal(url, calls[0].url);
        assert.equal(options.body, calls[0].body);
        assert.deepEqual(options.headers, calls[0].headers);
        return ok({id: 12, quantityAfter: 2});
    });
    assert.equal((await reloaded.send()).id, 12);
    assert.equal(reloaded.pending, null);
    assert.equal(createAdjustments(store).pending, null);
});
test("double submit sends once", async () => {
    let resolve, calls = 0;
    const client = createAdjustments(storage(), () => {
        calls++;
        return new Promise(done => { resolve = done; });
    }, () => "key");
    client.begin(1, adjustmentBody("DECREASE", 1, ""));
    const first = client.send();
    await assert.rejects(client.send());
    assert.equal(calls, 1);
    resolve(ok({id: 1, quantityAfter: 0}));
    await first;
});
test("definite rejection clears pending; conflict/server errors retain it", async () => {
    for (const status of [400, 404, 422, 409, 500, 401]) {
        const client = createAdjustments(storage(), async () => ({ok: false, status}), () => "key");
        client.begin(1, adjustmentBody("DECREASE", 1, ""));
        await assert.rejects(client.send(), new RegExp(`HTTP ${status}`));
        assert.equal(!!client.pending, ![400, 404, 422].includes(status));
    }
});
test("storage failure prevents sending, malformed success preserves pending", async () => {
    const client = createAdjustments({
        getItem: () => null,
        setItem: () => { throw new Error("storage unavailable"); },
    }, () => assert.fail("must not send"), () => "key");
    assert.throws(() => client.begin(1, adjustmentBody("INCREASE", 1, "")));
    assert.equal(client.pending, null);
    const malformed = createAdjustments(storage(), async () => ok({}), () => "key");
    malformed.begin(1, adjustmentBody("INCREASE", 1, ""));
    await assert.rejects(malformed.send());
    assert.ok(malformed.pending);
});

test("UI safely renders metadata, pages history and confirms manual corrections", async () => {
    class Element {
        children = [];
        value = "";
        textContent = "";
        appendChild(child) { this.children.push(child); }
        replaceChildren() { this.children = []; }
        setAttribute() {}
        focus() {}
        set innerHTML(_) { assert.fail("Unsafe HTML rendering"); }
    }
    const elements = new Map();
    const el = id => {
        if (!elements.has(id)) elements.set(id, new Element());
        return elements.get(id);
    };
    const product = {id: 7, sku: "<img onerror=x>", name: "Test", note: "<script>x</script>",
        stock: {quantity: 9}, active: true};
    let confirmed = false, posts = 0;
    const requests = [];
    const flush = async () => { for (let i = 0; i < 12; i++) await Promise.resolve(); };
    const ctx = vm.createContext({
        document: {getElementById: el, createElement: () => new Element()},
        URLSearchParams, console, adjustmentBody,
        confirm: () => confirmed,
        sessionStorage: storage(),
        createAdjustments: store => createAdjustments(store, async () => {
            posts++;
            return ok({id: 12, quantityAfter: 10});
        }, () => "test-key"),
        request: async path => {
            requests.push(path);
            if (path === "/products/7") return product;
            return {content: path.includes("stock-movements") ? [] : [product],
                number: 0, first: true, last: true, totalPages: 1, totalElements: 1};
        },
    });
    const app = readFileSync(new URL("../../main/resources/static/ui/app.js", import.meta.url), "utf8")
        .replace(/^import .*;\n/, "");
    vm.runInContext(app, ctx);
    await flush();
    assert.equal(el("products").children[0].children[0].textContent, product.sku);
    assert.equal(el("products").children[0].children[2].textContent, product.note);
    el("products").children[0].children[5].children[0].onclick();
    await flush();
    assert.ok(requests.some(path => path.startsWith("/products/7/stock-movements?")));
    assert.equal(el("selectedStock").textContent, "Наличност: 9");
    el("operation").value = "INCREASE";
    el("quantity").value = "1";
    el("adjustForm").onsubmit({preventDefault() {}});
    await flush();
    assert.equal(posts, 0, "cancelled confirmation must not write");
    confirmed = true;
    el("adjustForm").onsubmit({preventDefault() {}});
    await flush();
    assert.equal(posts, 1);
    assert.match(el("adjustStatus").textContent, /Приложено в inventory/);
});
