from dash import Dash, html, dcc
import diskcache
from dash import DiskcacheManager
from flask import send_from_directory, abort


cache = diskcache.Cache("./cache")
app = Dash(__name__, background_callback_manager=DiskcacheManager(cache), suppress_callback_exceptions=True)
server = app.server
app.title = "ClipLocker"
app.update_title = None

rawMediaFolder = None

@server.route("/media/<path:filename>")
def serve_media(filename):
    global rawMediaFolder
    if not rawMediaFolder:
        abort(404)
    return send_from_directory(rawMediaFolder, filename)