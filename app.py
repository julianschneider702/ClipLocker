import os
import threading

import cv2
from dash import Dash, html, dcc
import diskcache
from dash import DiskcacheManager
from flask import send_from_directory, abort, Response

cache = diskcache.Cache("./cache")
app = Dash(__name__, background_callback_manager=DiskcacheManager(cache), suppress_callback_exceptions=True)
server = app.server
app.title = "ClipLocker"
app.update_title = None

rawMediaFolder = None


thumb_cache = {}
thumb_lock  = threading.Lock()


@server.route("/media/<path:filename>")
def serve_media(filename):
    global rawMediaFolder
    if not rawMediaFolder:
        abort(404)
    return send_from_directory(rawMediaFolder, filename)


@server.route("/media/thumb/<path:filename>")
def serve_thumb(filename):
    global rawMediaFolder
    if not rawMediaFolder:
        abort(404)

    # .jpg Endung entfernen um den echten Dateinamen zu bekommen
    base = filename.rsplit(".", 1)[0]

    for ext in [".mp4", ".mov", ".webm", ".avi"]:
        full_path = os.path.join(rawMediaFolder, base + ext)
        if os.path.exists(full_path):
            break
    else:
        abort(404)

    with thumb_lock:
        if filename not in thumb_cache:
            cap = cv2.VideoCapture(full_path)
            ret, frame = cap.read()
            cap.release()
            if not ret:
                abort(404)
            # Auf 240px skalieren
            h, w = frame.shape[:2]
            scale = 240 / w
            small = cv2.resize(frame, (240, int(h * scale)),
                               interpolation=cv2.INTER_AREA)
            _, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 60])
            thumb_cache[filename] = bytes(buf)

    return Response(thumb_cache[filename], mimetype="image/jpeg")