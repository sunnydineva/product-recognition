
const camera = document.getElementById("camera");
const skuInput = document.getElementById("sku");
const statusText = document.getElementById("status");
const previewImages = document.getElementById("previewImages");
const previewActions = document.getElementById("previewActions");

const startCameraButton = document.getElementById("startCamera");
const recordButton = document.getElementById("record");
const retryRecording = document.getElementById("retryRecording");
const approveImages = document.getElementById("approveImages");

let stream = null;
let recording = false;
let currentSessionId = null;
let currentDetections = [];


// ---------- Actions ----------

async function handleStartCamera() {
    try {
        await openCamera();
    } catch (error) {
        statusText.textContent =
            "Неуспешно отваряне на камерата: " + error.message;
    }
}

async function handleRecord() {
    // Проверява SKU и видеоформата
    // Изчиства предишната сесия
    // Записва 12 секунди видео
    // Изпраща видеото към backend
    // Показва избраните снимки
    if (!stream || recording) return;

    const sku = skuInput.value.trim();

    if (!sku) {
        statusText.textContent = "Въведи баркод.";
        return;
    }

    let mimeType;

    try {
        mimeType = getSupportedMimeType();
    } catch (error) {
        statusText.textContent = error.message;
        return;
    }

    recording = true;
    recordButton.disabled = true;

    try {
        await clearPreviousPreview();

        const blob = await recordVideo(mimeType);

        statusText.textContent =
            "Изпращане и обработка на видеото...";

        const result = await requestPreview(blob, sku, mimeType);

        console.log("Preview result:", result);

        savePreviewSession(result);

        statusText.textContent =
            `Кадри: ${result.extracted_frames} | ` +
            `Открити: ${result.localized_frames} | ` +
            `Избрани: ${result.selected_frames}`;

    } catch (error) {
        statusText.textContent = error.message;
    } finally {
        recording = false;
        stopCamera();
    }
}

async function handleRetry() {
    if (recording) return;

    retryRecording.disabled = true;
    approveImages.disabled = true;

    try {
        await clearPreviousPreview();
        await openCamera();
    } catch (error) {
        statusText.textContent = error.message;
    } finally {
        retryRecording.disabled = false;
        approveImages.disabled = false;
    }
}

async function handleApprove() {
    if (recording) return;

    approveImages.disabled = true;

    try {
        const payload = buildApprovalPayload();
        const result = await requestApproval(payload);

        console.log("Approval result:", result);

        statusText.textContent =
            `Сървърът потвърди ${result.approved_count} снимки. ` +
            "Все още не са записани в базата.";

    } catch (error) {
        statusText.textContent = error.message;
    } finally {
        approveImages.disabled = false;
    }
}

// ---------- Recording ----------

function recordVideo(mimeType) {
    return new Promise((resolve, reject) => {
        const chunks = [];
        const recorder = new MediaRecorder(stream, { mimeType });

        recorder.addEventListener("dataavailable", event => {
            if (event.data.size > 0) {
                chunks.push(event.data);
            }
        });

        recorder.addEventListener("error", () => {
            reject(new Error("Грешка при запис."));
        });

        recorder.addEventListener("stop", () => {
            resolve(new Blob(chunks, { type: mimeType }));
        });

        recorder.start();

        statusText.textContent = "Записване...";

        setTimeout(() => {
            if (recorder.state === "recording") {
                recorder.stop();
            }
        }, 12000);
    });
}

function getSupportedMimeType() {
    if (!window.MediaRecorder) {
        throw new Error("Браузърът не поддържа запис на видео.");
    }

    const formats = [
        "video/webm;codecs=vp8",
        "video/webm",
        "video/mp4"
    ];

    const mimeType = formats.find(type =>
        MediaRecorder.isTypeSupported(type)
    );

    if (!mimeType) {
        throw new Error("Няма поддържан формат за запис.");
    }

    return mimeType;
}

// ---------- Camera ----------

async function openCamera() {
    stopCamera();

    stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" } },
        audio: false
    });

    camera.srcObject = stream;
    recordButton.disabled = false;
    statusText.textContent = "Камерата е готова.";
}

function stopCamera() {
    if (stream) {
        stream.getTracks().forEach(track => track.stop());
        stream = null;
    }

    camera.srcObject = null;
    recordButton.disabled = true;
}


// ---------- Sessions ----------

async function deleteCurrentSession() {
    if (!currentSessionId) return;

    const response = await fetch(
        `/api/products/preview/${encodeURIComponent(currentSessionId)}`,
        { method: "DELETE" }
    );

    if (!response.ok && response.status !== 404) {
        throw new Error("Неуспешно изтриване на старата сесия.");
    }

    currentSessionId = null;
}

function clearPreview() {
    previewImages.replaceChildren();
    previewActions.hidden = true;
    currentDetections = [];
}

async function clearPreviousPreview() {
    await deleteCurrentSession();
    clearPreview();
}

function savePreviewSession(result) {
    currentSessionId = result.session_id ?? null;
    renderPreview(result.detections);
}

// ---------- Backend ----------

async function requestPreview(blob, sku, mimeType) {
    const extension = mimeType.includes("mp4") ? "mp4" : "webm";

    const formData = new FormData();
    formData.append("video", blob, `product.${extension}`);
    formData.append("sku", sku);

    const response = await fetch("/api/products/preview", {
        method: "POST",
        body: formData
    });

    const result = await response.json();

    if (!response.ok) {
        throw new Error(
            typeof result.detail === "string"
                ? result.detail
                : "Грешка при обработката"
        );
    }

    return result;
}

async function requestApproval(payload) {
    const response = await fetch("/api/products/approve", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
    });

    const result = await response.json();

    if (!response.ok) {
        throw new Error(
            typeof result.detail === "string"
                ? result.detail
                : "Грешка при одобрението"
        );
    }

    return result;
}

// ---------- Preview ----------

function renderPreview(detections) {
    clearPreview();

    currentDetections = detections;
    previewActions.hidden = detections.length === 0;

    detections.forEach((detection, index) => {
        previewImages.appendChild(
            createPreviewItem(detection, index)
        );
    });
}

function createPreviewItem(detection, index) {
    const container = document.createElement("div");
    container.style.display = "inline-block";
    container.style.width = "170px";
    container.style.margin = "10px";
    container.style.verticalAlign = "top";

    const image = document.createElement("img");
    image.src = detection.image;
    image.style.width = "160px";
    image.style.height = "160px";
    image.style.objectFit = "contain";

    const description = document.createElement("p");
    description.textContent =
        `Кадър: ${detection.timestamp_ms} ms | ` +
        `Качество: ${detection.quality_score}`;

    const label = document.createElement("label");

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = true;
    checkbox.dataset.index = String(index);
    checkbox.className = "crop-checkbox";

    label.appendChild(checkbox);
    label.appendChild(
        document.createTextNode(" Избери снимката")
    );

    container.append(image, description, label);

    return container;
}

function getSelectedImages() {
    const checked = [
        ...document.querySelectorAll(".crop-checkbox:checked")
    ];

    return checked.map(checkbox =>
        currentDetections[Number(checkbox.dataset.index)]
    );
}

function buildApprovalPayload() {
    const selectedImages = getSelectedImages();

    if (selectedImages.length === 0) {
        throw new Error("Избери поне една снимка или повтори записа.");
    }

    if (!currentSessionId) {
        throw new Error("Няма активна сесия. Направи нов запис.");
    }

    const imageIds = selectedImages.map(image => image.image_id);

    if (imageIds.some(id => !id)) {
        throw new Error("Липсва идентификатор на снимка.");
    }

    return {
        session_id: currentSessionId,
        image_ids: imageIds
    };
}

// ---------- Events ----------

startCameraButton.addEventListener("click", handleStartCamera);
recordButton.addEventListener("click", handleRecord);
retryRecording.addEventListener("click", handleRetry);
approveImages.addEventListener("click", handleApprove);

window.addEventListener("pagehide", stopCamera);
