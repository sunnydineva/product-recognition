export const API = "/api/inventory/v1";
const STORAGE_KEY = "inventory.pending-adjustment.v1";

export async function request(path, options = {}, fetcher = fetch) {
    const response = await fetcher(API + path, {cache: "no-store", ...options});
    if (!response.ok) {
        // Do not display server stack traces or HTML error bodies.
        const error = new Error(`HTTP ${response.status}`);
        error.status = response.status;
        throw error;
    }
    return response.json();
}

export function adjustmentBody(operation, quantity, note) {
    const amount = Number(quantity);
    if (!["INCREASE", "DECREASE"].includes(operation) ||
        !Number.isInteger(amount) || amount < 1 || amount > 2147483647) {
        throw new Error("Въведете положителен цял брой до 2147483647.");
    }
    if (note.length > 2000) throw new Error("Бележката е ограничена до 2000 символа.");
    return {operation, quantity: amount, source: "MANUAL_UI", note: note.trim() || null};
}

// One in-flight correction per tab. Save before sending, preserve the key and body
// on ambiguous failures, including a reload after the server committed a request.
export function createAdjustments(storage, fetcher = fetch, uuid = () => crypto.randomUUID()) {
    let pending = JSON.parse(storage.getItem(STORAGE_KEY) || "null");
    if (pending && (!Number.isSafeInteger(pending.productId) || pending.productId < 1 ||
        typeof pending.key !== "string" || typeof pending.body !== "string")) {
        throw new Error("Невалидна запазена заявка. Проверете историята преди нова корекция.");
    }
    let sending = false;
    return {
        get pending() { return pending; },
        begin(productId, body) {
            if (pending) throw new Error("Първо изяснете предишната корекция.");
            if (!Number.isSafeInteger(productId) || productId < 1) throw new Error("Невалиден продукт.");
            const next = {productId, key: uuid(), body: JSON.stringify(body)};
            storage.setItem(STORAGE_KEY, JSON.stringify(next));
            pending = next;
        },
        async send() {
            if (!pending || sending) throw new Error("Заявката липсва или вече се изпраща.");
            sending = true;
            try {
                const movement = await request(`/products/${pending.productId}/stock-adjustments`, {
                    method: "POST",
                    headers: {"Content-Type": "application/json", "Idempotency-Key": pending.key},
                    body: pending.body,
                }, fetcher);
                if (!Number.isSafeInteger(movement.id) || !Number.isSafeInteger(movement.quantityAfter)) {
                    throw new Error("Непълен отговор; резултатът трябва да се провери.");
                }
                storage.removeItem(STORAGE_KEY);
                pending = null;
                return movement;
            } catch (error) {
                // Validation/not-found are definite rejections. 409, 5xx, timeouts,
                // malformed responses, and auth failures retain the original request.
                if ([400, 404, 422].includes(error.status)) {
                    storage.removeItem(STORAGE_KEY);
                    pending = null;
                }
                throw error;
            } finally {
                sending = false;
            }
        },
    };
}
