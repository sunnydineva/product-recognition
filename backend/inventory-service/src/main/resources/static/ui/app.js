import {request, adjustmentBody, createAdjustments} from "./core.js";

const el = id => document.getElementById(id);
let productPage = 0, historyPage = 0, query = "", selected = null;
let productVersion = 0, historyVersion = 0, selectionVersion = 0;
let adjustments;
let sending = false;

function status(id, message, kind = "") {
    el(id).textContent = message;
    el(id).className = kind;
}
function row(body, values) {
    const tr = document.createElement("tr");
    for (const value of values) {
        const td = document.createElement("td");
        td.textContent = value ?? "—";
        tr.appendChild(td);
    }
    body.appendChild(tr);
    return tr;
}
function pagination(prefix, page) {
    el(prefix + "Prev").disabled = page.first;
    el(prefix + "Next").disabled = page.last;
    el(prefix + "Page").textContent = page.totalPages
        ? `${page.number + 1} / ${page.totalPages}` : "0 / 0";
}
function lockAdjustment() {
    el("adjustFields").disabled = !adjustments || !!adjustments.pending || sending;
    el("retry").hidden = !adjustments?.pending;
    el("retry").disabled = sending;
    el("pendingHelp").hidden = !adjustments?.pending;
}

async function loadProducts() {
    const version = ++productVersion;
    status("productsStatus", "Зареждане…");
    el("products").replaceChildren();
    el("productsPrev").disabled = el("productsNext").disabled = true;
    try {
        const params = new URLSearchParams({page: productPage, size: 20, sort: "id,asc"});
        if (query) params.set("search", query);
        const page = await request(`/products?${params}`);
        if (version !== productVersion) return;
        for (const product of page.content) {
            const tr = row(el("products"), [product.sku, product.name, product.note,
                product.stock.quantity, product.active ? "Да" : "Не"]);
            const td = document.createElement("td");
            const button = document.createElement("button");
            button.type = "button";
            button.textContent = "Избери";
            button.setAttribute("aria-label", `Избери ${product.sku}`);
            button.onclick = () => selectProduct(product.id);
            td.appendChild(button);
            tr.appendChild(td);
        }
        pagination("products", page);
        status("productsStatus", page.content.length
            ? `Общо: ${page.totalElements}. Обновено: ${new Date().toLocaleTimeString("bg-BG")}`
            : "Няма продукти за показване.");
    } catch (error) {
        if (version === productVersion) status("productsStatus", `Неуспешно зареждане: ${error.message}`, "error");
    }
}

async function selectProduct(id, focus = true) {
    const version = ++selectionVersion;
    selected = null;
    ++historyVersion;
    el("detail").hidden = el("historySection").hidden = true;
    try {
        const product = await request(`/products/${id}`);
        if (version !== selectionVersion) return;
        selected = product;
        historyPage = 0;
        el("detail").hidden = el("historySection").hidden = false;
        el("selectedHeading").textContent = `${product.sku} — ${product.name}`;
        el("selectedStock").textContent = `Наличност: ${product.stock.quantity}`;
        el("quantity").value = "";
        el("note").value = "";
        lockAdjustment();
        if (focus) el("selectedHeading").focus();
        await loadHistory();
    } catch (error) {
        if (version === selectionVersion) status("productsStatus", `Неуспешен избор: ${error.message}`, "error");
    }
}

async function loadHistory() {
    if (!selected) return;
    const version = ++historyVersion;
    status("historyStatus", "Зареждане…");
    el("history").replaceChildren();
    el("historyPrev").disabled = el("historyNext").disabled = true;
    try {
        const params = new URLSearchParams({page: historyPage, size: 20});
        params.append("sort", "createdAt,desc");
        params.append("sort", "id,desc");
        const page = await request(`/products/${selected.id}/stock-movements?${params}`);
        if (version !== historyVersion) return;
        for (const movement of page.content) {
            row(el("history"), [movement.id, new Date(movement.createdAt).toLocaleString("bg-BG"),
                movement.quantityDelta > 0 ? `+${movement.quantityDelta}` : movement.quantityDelta,
                movement.quantityAfter, movement.source, movement.note]);
        }
        pagination("history", page);
        status("historyStatus", page.content.length ? `Движения: ${page.totalElements}` : "Няма записани движения.");
    } catch (error) {
        if (version === historyVersion) status("historyStatus", `Неуспешно зареждане: ${error.message}`, "error");
    }
}

async function sendAdjustment() {
    if (sending || !adjustments?.pending) return;
    const productId = adjustments.pending.productId;
    sending = true;
    lockAdjustment();
    status("adjustStatus", `Изпраща се ръчна корекция за inventory ID ${productId}…`);
    try {
        const movement = await adjustments.send();
        status("adjustStatus", `Приложено в inventory. Продукт ID ${productId}, движение #${movement.id}, наличност след движението: ${movement.quantityAfter}.`, "success");
        await loadProducts();
        if (selected?.id === productId) await selectProduct(productId, false);
    } catch (error) {
        const unknown = adjustments.pending;
        status("adjustStatus", unknown
            ? `Непотвърден резултат за продукт ID ${productId}: ${error.message}. Повторете същата заявка, не създавайте нова.`
            : `Корекцията е отхвърлена (${error.message}). Проверете продукта, количеството и наличността.`, "error");
    } finally {
        sending = false;
        lockAdjustment();
    }
}

el("searchForm").onsubmit = event => {
    event.preventDefault();
    query = el("search").value.trim();
    productPage = 0;
    loadProducts();
};
el("refresh").onclick = () => {
    loadProducts();
    if (selected) selectProduct(selected.id, false);
};
for (const [id, delta] of [["productsPrev", -1], ["productsNext", 1]]) {
    el(id).onclick = () => { productPage = Math.max(0, productPage + delta); loadProducts(); };
}
for (const [id, delta] of [["historyPrev", -1], ["historyNext", 1]]) {
    el(id).onclick = () => { historyPage = Math.max(0, historyPage + delta); loadHistory(); };
}
el("adjustForm").onsubmit = event => {
    event.preventDefault();
    if (!selected || !adjustments || adjustments.pending || sending) return;
    try {
        const body = adjustmentBody(el("operation").value, el("quantity").value, el("note").value);
        const verb = body.operation === "INCREASE" ? "Добавяне" : "Изваждане";
        if (!confirm(`${verb} на ${body.quantity} бр. за ${selected.sku} — ${selected.name}?\nТова променя реалната наличност.`)) return;
        adjustments.begin(selected.id, body);
        sendAdjustment();
    } catch (error) {
        status("adjustStatus", error.message, "error");
    }
};
el("retry").onclick = sendAdjustment;
try {
    adjustments = createAdjustments(sessionStorage);
    if (adjustments.pending) {
        status("adjustStatus", `Има непотвърдена корекция за inventory ID ${adjustments.pending.productId}. Проверете историята или повторете същата заявка.`, "error");
    }
} catch (error) {
    status("adjustStatus", `Ръчните корекции са блокирани: ${error.message}`, "error");
}
lockAdjustment();
loadProducts();
