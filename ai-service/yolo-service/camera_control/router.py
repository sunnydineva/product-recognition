import asyncio
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse
from starlette.responses import StreamingResponse

from camera_control.manager import camera_manager
from detection.preview import PREVIEW_PATH

from fastapi import WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool

from camera_control.browser_camera import BrowserCameraSession

router = APIRouter()

STATIC_DIR = Path(__file__).resolve().parent / "static"


@router.get("/camera", include_in_schema=False)
async def camera_page():
    return FileResponse(STATIC_DIR / "camera.html")


@router.get("/camera.js", include_in_schema=False)
async def camera_javascript():
    return FileResponse(
        STATIC_DIR / "camera.js",
        media_type="application/javascript",
    )


@router.get("/camera/status", include_in_schema=False)
@router.get("/api/yolo/camera/status", tags=["Camera"],
            summary="Състояние на сървърния camera worker",
            description="Връща текущото състояние на управлявания camera процес. "
                        "Не стартира камера и не описва браузърните WebSocket сесии.")
async def camera_status():
    return camera_manager.status()


@router.post("/camera/start", include_in_schema=False)
@router.post("/api/yolo/camera/start", tags=["Camera"],
             summary="Стартиране на сървърната камера",
             description="Стартира camera worker процес чрез CameraManager. "
                         "Операцията използва реалната камера на сървъра и може да задейства "
                         "детекция и последващо разпознаване. Не стартира камерата на браузъра.")
def camera_start():
    """Start the camera worker."""
    return camera_manager.start()


@router.post("/camera/stop", include_in_schema=False)
@router.post("/api/yolo/camera/stop", tags=["Camera"],
             summary="Спиране на сървърната камера",
             description="Спира camera worker процеса чрез CameraManager. "
                         "Не затваря отделните браузърни WebSocket сесии.")
def camera_stop():
    """Stop the camera worker."""
    return camera_manager.stop()


async def generate_camera_stream():
    """
    Continuously stream the latest camera preview as MJPEG.

    Reads frames produced by the separate camera worker
    without opening the physical camera a second time.
    """
    while True:
        if camera_manager.status()["status"] != "running":
            break

        try:
            image_bytes = PREVIEW_PATH.read_bytes()
        except OSError:
            await asyncio.sleep(0.1)
            continue

        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + image_bytes + b"\r\n")

        await asyncio.sleep(0.1)


@router.get("/camera/stream", include_in_schema=False)
@router.get("/api/yolo/camera/stream", tags=["Camera"],
            summary="MJPEG preview от сървърната камера",
            description="Връща multipart/x-mixed-replace поток от JPEG кадрите на работещия worker. "
                        "Не отваря камерата повторно и не я стартира автоматично; потокът приключва "
                        "при спрян worker. За браузърна камера използвай WebSocket "
                        "/api/yolo/camera/ws: изпраща двоични изображения до 2 MiB и връща JSON "
                        "резултати от tracking. WebSocket не е HTTP OpenAPI операция.",
            response_class=StreamingResponse)
async def camera_stream():
    """Expose the live camera preview as an MJPEG HTTP stream."""
    return StreamingResponse(
        generate_camera_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store"},
    )


@router.websocket("/camera/ws")
@router.websocket("/api/yolo/camera/ws")
async def camera_websocket(websocket: WebSocket):
    """Receive browser frames and return YOLO tracking results."""
    await websocket.accept()

    session = None

    try:
        session = await run_in_threadpool(BrowserCameraSession)

        while True:
            image_bytes = await websocket.receive_bytes()

            # print(
            #     f"[WEBSOCKET] Received frame: {len(image_bytes)} bytes",
            #     flush=True,
            # )

            if len(image_bytes) > 2 * 1024 * 1024:
                await websocket.close(
                    code=1009,
                    reason="Frame too large",
                )
                return

            try:
                result = await run_in_threadpool(
                    session.process_frame,
                    image_bytes,
                )
            except ValueError as error:
                await websocket.send_json(
                    {
                        "error": str(error),
                    }
                )
                continue

            await websocket.send_json(result)

    except WebSocketDisconnect:
        pass

    finally:
        if session is not None:
            await run_in_threadpool(session.close)
