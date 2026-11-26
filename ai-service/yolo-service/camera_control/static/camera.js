const camera = document.getElementById("camera");
const statusText = document.getElementById("status");

const startCameraButton = document.getElementById("startCamera");
const stopCameraButton = document.getElementById("stopCamera");

const overlay = document.getElementById("overlay");
const overlayContext = overlay.getContext("2d");

const captureCanvas = document.createElement("canvas");
const captureContext = captureCanvas.getContext("2d");

let stream = null;
let socket = null;
let cameraRunning = false;
let frameTimer = null;

// ---------- Tracking ----------

function connectTracking() {
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";

    socket = new WebSocket(
        `${protocol}//${location.host}/api/yolo/camera/ws`
    );

    const currentSocket = socket;

    currentSocket.addEventListener("open", () => {
        if (!cameraRunning || socket !== currentSocket) return;

        statusText.textContent = "Камерата работи. YOLO е свързан.";
        sendFrame(currentSocket);
    });

    currentSocket.addEventListener("message", event => {
        if (!cameraRunning || socket !== currentSocket) return;

        try {
            const result = JSON.parse(event.data);

            console.log("YOLO result:", result);

            if (result.error) {
                statusText.textContent = `YOLO error: ${result.error}`;
            } else {
                const count = result.detections?.length ?? 0;

                statusText.textContent =
                    `YOLO обработва кадри. Открити обекти: ${count}`;

                drawDetections(result);
            }
        } catch (error) {
            console.error("Tracking response error:", error);
            statusText.textContent = `Грешка при обработка: ${error.message}`;
        }

        frameTimer = setTimeout(() => {
            sendFrame(currentSocket);
        }, 100);
    });


    currentSocket.addEventListener("close", () => {
        if (cameraRunning && socket === currentSocket) {
            statusText.textContent = "YOLO връзката е прекъсната.";
        }
    });

    currentSocket.addEventListener("error", () => {
        if (cameraRunning && socket === currentSocket) {
            statusText.textContent = "Грешка във WebSocket връзката.";
        }
    });
}

function sendFrame(currentSocket) {
    if (
        !cameraRunning ||
        socket !== currentSocket ||
        currentSocket.readyState !== WebSocket.OPEN ||
        camera.videoWidth === 0
    ) {
        return;
    }

    const scale = Math.min(1, 640 / camera.videoWidth);

    captureCanvas.width = Math.round(camera.videoWidth * scale);
    captureCanvas.height = Math.round(camera.videoHeight * scale);

    captureContext.drawImage(
        camera,
        0,
        0,
        captureCanvas.width,
        captureCanvas.height
    );

    captureCanvas.toBlob(async blob => {
        if (
            !blob ||
            !cameraRunning ||
            socket !== currentSocket ||
            currentSocket.readyState !== WebSocket.OPEN
        ) {
            return;
        }

        try {
            const bytes = await blob.arrayBuffer();

            if (
                cameraRunning &&
                socket === currentSocket &&
                currentSocket.readyState === WebSocket.OPEN
            ) {
                currentSocket.send(bytes);
            }
        } catch (error) {
            console.error("Frame send error:", error);
        }
    }, "image/jpeg", 0.7);
}

function drawDetections(result) {
    overlay.width = result.width;
    overlay.height = result.height;

    overlayContext.clearRect(
        0, 0, overlay.width, overlay.height
    );

    overlayContext.lineWidth = 3;
    overlayContext.font = "18px sans-serif";

    for (const detection of result.detections) {
        const [x1, y1, x2, y2] = detection.bbox;

        overlayContext.strokeStyle = "#00ff66";
        overlayContext.fillStyle = "#00ff66";

        overlayContext.strokeRect(
            x1,
            y1,
            x2 - x1,
            y2 - y1
        );

        const label =
            `${detection.class_name} #${detection.track_id ?? "?"}`;

        overlayContext.fillText(
            label,
            x1,
            Math.max(20, y1 - 8)
        );
    }
}

function stopTracking() {
    cameraRunning = false;

    if (frameTimer !== null) {
        clearTimeout(frameTimer);
        frameTimer = null;
    }

    if (socket) {
        socket.close();
        socket = null;
    }

    overlayContext.clearRect(
        0, 0, overlay.width, overlay.height
    );
}

// ---------- Camera ----------

async function openCamera() {
    stopCamera();

    if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error(
            "Браузърът не поддържа камера или страницата не е отворена през HTTPS."
        );
    }

    stream = await navigator.mediaDevices.getUserMedia({
        video: {
            facingMode: {ideal: "environment"}
        },
        audio: false
    });

    camera.srcObject = stream;
    await camera.play();

    startCameraButton.disabled = true;
    stopCameraButton.disabled = false;

    cameraRunning = true;
    statusText.textContent = "Свързване с YOLO...";

    connectTracking();
}

function stopCamera() {
    stopTracking();

    if (stream) {
        stream.getTracks().forEach(track => track.stop());
        stream = null;
    }

    camera.srcObject = null;

    startCameraButton.disabled = false;
    stopCameraButton.disabled = true;

    statusText.textContent = "Камерата е спряна.";
}

// ---------- Actions ----------

async function handleStartCamera() {
    startCameraButton.disabled = true;
    statusText.textContent = "Отваряне на камерата...";

    try {
        await openCamera();
    } catch (error) {
        console.error("Camera error:", error);

        stopCamera();

        statusText.textContent =
            `Грешка: ${error.name} - ${error.message}`;
    }
}

function handleStopCamera() {
    stopCamera();
}

// ---------- Events ----------

startCameraButton.addEventListener("click", handleStartCamera);
stopCameraButton.addEventListener("click", handleStopCamera);

window.addEventListener("pagehide", stopCamera);
