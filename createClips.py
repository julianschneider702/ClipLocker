import gc
import os
import shutil
import threading
import time
import uuid
import base64
import json
import subprocess

import cv2
import yt_dlp
from scenedetect import open_video, SceneManager
from scenedetect.detectors import ContentDetector
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import time as time_module

from dash import html, dcc, Output, Input, State, no_update, ctx, ALL
from app import app
import app as appModule
from styles import *

# ── Globaler State ────────────────────────────────────────────────────────────
p4_progress  = {"current": 0, "total": 0, "status": "", "done": False, "error": None}
p4_pending   = []
p4_clips_dir = None
p4_source_video = None


def renderPage4(settings):
    return html.Div([

        # Topbar
        html.Div([
            html.Div("ClipLocker", style={
                **headerStyleSmall,
                "position": "absolute",
                "left": "50%",
                "transform": "translateX(-50%)",
                "pointerEvents": "none",
            }),
            html.Div([
                dcc.Input(
                    id="p4-output-folder-input",
                    type="text",
                    placeholder="Zielordner…",
                    value="rohmaterial_ablage",
                    style={**baseStyleInputPath, "flex": "1", "minWidth": "200px", "width": "30%", "fontSize": "15px"},
                ),
                html.Button(
                    "💾 Speichern",
                    id="p4-save-btn",
                    n_clicks=0,
                    style={**titleBtnStyle, "fontSize": "14px", "cursor": "pointer",
                           #"backgroundColor": "white",
                           "color": "black"},
                ),
                html.Span(id="p4-save-status",
                          style={"fontSize": "13px", "color": "lightgreen"}),
            ], style={"display": "flex", "gap": "10px", "alignItems": "center"}),
        ], style={
            "display": "flex", "justifyContent": "space-between", "alignItems": "center",
            "padding": "10px 20px", "borderBottom": "1px solid #333",
            "boxSizing": "border-box", "flexShrink": "0",
        }),

        # Eingabe + Fortschritt
        html.Div(id="p4-input-area", children=[
            html.Div([

                # Linke Spalte – Eingaben untereinander
                html.Div([
                    dcc.Input(
                        id="yt-url-input",
                        type="text",
                        placeholder="YouTube URL eingeben…",
                        value= "https://www.youtube.com/watch?v=YLslsZuEaNE",
                        style={**baseStyleInputPath, "width": "50%", "fontSize": "15px"},
                    ),
                    html.Div([
                        html.Label("Schwellwert:", style={"fontSize": "13px", "whiteSpace": "nowrap"}),
                        html.Div(
                            dcc.Slider(id="scene-threshold-slider", min=10, max=60,
                                       step=5, value=40,
                                       marks={10: "10", 60: "60"},
                                       tooltip={"placement": "bottom", "always_visible": False}),
                            style={"flex": "1"},
                        ),
                    ], style={"display": "flex", "gap": "10px", "alignItems": "center", "width": "50%"}),

                    dcc.Checklist(
                        id="p4-audio-checkbox",
                        options=[{"label": " Mit Ton", "value": "audio"}],
                        value=[],
                        style={"fontSize": "13px"},
                    ),
                    html.Div([
                        html.Label("Vorschau-Qualität:", style={"fontSize": "13px"}),
                        dcc.Dropdown(
                            id="p4-quality-dropdown",
                            options=[
                                {"label": "144p", "value": "256x144"},
                                {"label": "240p", "value": "426x240"},
                                {"label": "360p", "value": "640x360"},
                                {"label": "480p", "value": "854x480"},
                                {"label": "720p", "value": "1280x720"},
                                {"label": "Original", "value": "original"},
                            ],
                            value="640x360",
                            clearable=False,
                            style={"width": "130px", "color": "black"},
                        ),
                    ], style={"display": "flex", "gap": "8px", "alignItems": "center"}),

                    html.Hr(style={"border": "1px solid #ccc", "margin": "5px 0"}),

                    html.Div([
                        html.Label("Oder lokalen Ordner laden:",
                                   style={"fontSize": "13px", "whiteSpace": "nowrap"}),
                        dcc.Input(
                            id="p4-folder-input",
                            type="text",
                            placeholder="Ordnerpfad eingeben…",
                            style={**baseStyleInputPath, "flex": "1", "fontSize": "13px"},
                        ),
                        html.Button(
                            "📂 Laden",
                            id="p4-folder-btn",
                            n_clicks=0,
                            style={**titleBtnStyle, "fontSize": "13px", "cursor": "pointer"},
                        ),
                    ], style={"display": "flex", "gap": "8px", "alignItems": "center"}),

                ], style={"display": "flex", "flexDirection": "column",
                          "gap": "10px", "flex": "1"}),

                # Rechts – Start-Button
                html.Button(
                    "▶ Starten",
                    id="yt-start-btn",
                    n_clicks=0,
                    style={**titleBtnStyle, "fontSize": "15px", "cursor": "pointer",
                           #"alignSelf": "stretch"
                    },
                ),

            ], style={"display": "flex", "gap": "16px", "alignItems": "flex-start",
                      "padding": "16px 20px"}),

            html.Div(id="p4-progress-area", style={"padding": "0 20px 16px"}),
            dcc.Interval(id="p4-interval", interval=500, disabled=True),
        ]),

        # Clip-Strip (horizontal scrollbar, feste Höhe)
        html.Div(
            id="p4-strip",
            style={
                "display": "flex", "flexDirection": "row",
                "overflowX": "auto", "gap": "10px",
                "padding": "10px 16px", "height": "155px",
                "alignItems": "center",
                "borderBottom": "1px solid #333",
                #"backgroundColor": "#111",
                "flexShrink": "0",
            }
        ),

        # Detail + Trim
        html.Div(
            id="main-container",
            children=[
                # Große Ansicht + Action-Buttons
                html.Div([

                    html.Div([
                        html.Div(id="p4-selected-label",
                                 style={"fontWeight": "bold", "marginBottom": "14px",
                                        "fontSize": "14px", "color": "#ccc"}),

                        html.Div(id="p4-time-display",
                                 style={"fontSize": "13px", "color": "#555",
                                        "fontVariantNumeric": "tabular-nums",
                                        "marginBottom": "6px"}),
                        dcc.Interval(id="p4-time-interval", interval=100, disabled=True),

                        html.Div([
                            html.Button("◂", id="p4-prev-btn", n_clicks=0,
                                        style={**titleBtnStyle, "fontSize": "60px",
                                               "cursor": "pointer", "width": "100%", "padding": "10p"}),
                            html.Button("▸", id="p4-next-btn", n_clicks=0,
                                        style={**titleBtnStyle, "fontSize": "60px",
                                               "cursor": "pointer", "width": "100%", "padding": "10px"}),
                        ], style = {"display": "flex"}),

                        html.Hr(style={"border": "1px solid #ccc", "margin": "10px 0"}),

                        html.Button("🗑 Verwerfen", id="p4-discard-btn", n_clicks=0,
                                    style={**titleBtnStyle, "backgroundColor": lightRed,
                                           "fontSize": "13px", "cursor": "pointer",
                                           "width": "100%"}),

                        html.Button("✂ Clip trennen", id="p4-split-btn", n_clicks=0,
                                    style={**titleBtnStyle, "fontSize": "13px", "cursor": "pointer",
                                           "width": "100%", "marginTop": "6px"}),

                        html.Button("⊕ Mit nächstem zusammenführen",
                                    id="p4-merge-btn", n_clicks=0,
                                    style={**titleBtnStyle, "fontSize": "13px", "cursor": "pointer",
                                           "width": "100%"}),
                        html.Button("⏩ Erste 0.3s trimmen",
                                    id="p4-trim-03-btn", n_clicks=0,
                                    style={**titleBtnStyle, "fontSize": "13px", "cursor": "pointer",
                                           "width": "100%"}),
                    ], style={
                        "width": "210px", "flexShrink": "0",
                        "display": "flex", "flexDirection": "column",
                        "gap": "4px", "padding": "10px 14px",
                    }),

                    html.Div(id="p4-large-player", style={"flex": "1"}),

                ], style={"display": "flex", "gap": "16px", "padding": "16px 20px",
                          "alignItems": "flex-start"}),

                # Trim
                html.Div(
                    id="p4-trim-area",
                    style={"padding": "0 20px 20px", "display": "none"},
                    children=[
                        html.Div([

                            html.Div([
                                html.Button("◁ Trim Start", id="p4-trim-start-btn", n_clicks=0,
                                            style={**titleBtnStyle, "fontSize": "13px", "cursor": "pointer"}),
                                html.Div("Setzt Startpunkt auf aktuelle Abspielposition",
                                         style={"fontSize": "11px", "color": "#666"}),
                                html.Img(id="p4-frame-start", style={"width": "200px", "borderRadius": "4px",
                                                                     "marginTop": "6px"}),
                                html.Div(id="p4-trim-start-label",
                                         style={"fontSize": "11px", "color": "#666", "textAlign": "center"}),
                            ], style={"display": "flex", "flexDirection": "column",
                                      "alignItems": "center", "gap": "4px"}),

                            html.Div([
                                html.Button("Trim Ende ▷", id="p4-trim-end-btn", n_clicks=0,
                                            style={**titleBtnStyle, "fontSize": "13px", "cursor": "pointer"}),
                                html.Div("Setzt Endpunkt auf aktuelle Abspielposition",
                                         style={"fontSize": "11px", "color": "#666"}),
                                html.Img(id="p4-frame-end", style={"width": "200px", "borderRadius": "4px",
                                                                   "marginTop": "6px"}),
                                html.Div(id="p4-trim-end-label",
                                         style={"fontSize": "11px", "color": "#666", "textAlign": "center"}),
                            ], style={"display": "flex", "flexDirection": "column",
                                      "alignItems": "center", "gap": "4px"}),

                        ], style={"display": "flex", "gap": "60px", "justifyContent": "center"}),
                    ]
                ),

        ], style={"overflowY": "auto", "flex": "1", "display": "none"}),


    ], style={"display": "flex", "flexDirection": "column", "height": "100vh",
              #"backgroundColor": "#1a1a1a",
              #"color": "white"
             })



# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def extract_frame_b64(path: str, sec: float = 0.0, thumb_width: int = 160) -> str | None:
    try:
        cap = cv2.VideoCapture(path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        target_frame = int(sec * fps)

        # Sicherstellen dass wir nicht über Ende hinausgehen
        target_frame = min(target_frame, int(total_frames) - 1)
        if target_frame < 0:
            target_frame = 0

        cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
        ret, frame = cap.read()

        # Fallback: letzten lesbaren Frame versuchen
        if not ret and total_frames > 1:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(total_frames) - 2)
            ret, frame = cap.read()

        cap.release()
        if not ret:
            return None

        h, w = frame.shape[:2]
        scale = thumb_width / w
        small = cv2.resize(frame, (thumb_width, int(h * scale)),
                           interpolation=cv2.INTER_AREA)
        _, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 55])
        return base64.b64encode(buf).decode("utf-8")
    except Exception:
        return None

def add_thumbnail(entry: dict) -> dict:
    entry = dict(entry)
    entry["thumbnail"] = extract_frame_b64(entry["path"], 0.0)
    return entry


def get_duration(path: str) -> float:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", path],
            capture_output=True, text=True,
        )
        for s in json.loads(r.stdout).get("streams", []):
            if s.get("codec_type") == "video":
                return float(s.get("duration", 0))
    except Exception:
        pass
    return 0.0


def run_ffmpeg(*args) -> bool:
    result = subprocess.run(
        ["ffmpeg", "-y", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        print(f"[ffmpeg Fehler]:\n{result.stderr.decode()}")
        return False
    return True


def new_id() -> str:
    return uuid.uuid4().hex[:8]


def make_clip_entry(clip_id: str, path: str, start_orig: float = 0.0) -> dict:

    for _ in range(10):
        if os.path.exists(path) and os.path.getsize(path) > 0:
            break
        time.sleep(0.1)

    dur = round(get_duration(path), 3)
    thumb = extract_frame_b64(path, 0.0)

    return {
        "id":          clip_id,
        "path":        path,
        "duration":    dur,
        "start_orig":  start_orig,
        "trim_start":  0.0,
        "trim_end":    0.0,
        "thumbnail":   thumb,
        "ignored":     True,
    }

def check_nvenc_available() -> bool:
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-encoders"],
        capture_output=True, text=True
    )
    return "h264_nvenc" in result.stdout


NVENC_AVAILABLE = check_nvenc_available()
print(f"[Page4] h264_nvenc verfügbar: {NVENC_AVAILABLE}")

def cut_scene_single(args):
    i, ss, dur, video_path, clips_dir, quality, with_audio = args
    t = time_module.time()

    cid  = f"{i:04d}"
    path = os.path.join(clips_dir, f"{cid}.mp4")

    if quality == "original":
        vf_args    = []
        codec_args = ["-c", "copy"]
        audio_args = []
    else:
        w, h = quality.split("x")
        vf_args = ["-vf", f"scale={w}:{h}"]
        if NVENC_AVAILABLE:
            codec_args = ["-c:v", "h264_nvenc", "-preset", "fast"]
        else:
            codec_args = ["-c:v", "libx264", "-crf", "23", "-preset", "ultrafast"]
        audio_args = ["-c:a", "aac"] if with_audio else ["-an"]

    run_ffmpeg(
        "-ss", str(ss),
        "-i", video_path,
        "-t", str(max(0.1, dur - 0.1)),
        *vf_args,
        *codec_args,
        *audio_args,
        "-avoid_negative_ts", "make_zero",
        path
    )
    print(f"[cut_scene] Clip {i}: {time_module.time() - t:.1f}s")
    return i, cid, path, ss


def cut_all_scenes(scenes, video_path, clips_dir, quality, with_audio) -> list:
    args_list = [
        (i,
         round(start.get_seconds(), 3),
         round(end.get_seconds() - start.get_seconds(), 3),
         video_path, clips_dir, quality, with_audio)
        for i, (start, end) in enumerate(scenes)
    ]

    results = [None] * len(args_list)

    t_parallel = time_module.time()
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(cut_scene_single, a): a[0] for a in args_list}
        done_count = 0
        for future in as_completed(futures):
            i, cid, path, ss = future.result()
            results[i] = (i, cid, path, ss)
            done_count += 1
            print(f"[cut_all] {done_count}/{len(args_list)} fertig, kumulativ: {time_module.time() - t_parallel:.1f}s")

    return [r for r in results if r is not None]

def merge_short_scenes(scenes, min_duration: float) -> list:
    if min_duration <= 0:
        return scenes

    merged = []
    buffer_start = None
    buffer_end   = None

    for start, end in scenes:
        dur = end.get_seconds() - start.get_seconds()

        if buffer_start is None:
            buffer_start = start
            buffer_end   = end
            buffer_dur   = dur
        else:
            buffer_end  = end
            buffer_dur  = buffer_end.get_seconds() - buffer_start.get_seconds()

        if buffer_dur >= min_duration:
            merged.append((buffer_start, buffer_end))
            buffer_start = None
            buffer_end   = None

    # Letzten Rest anhängen falls vorhanden
    if buffer_start is not None:
        if merged:
            # Mit letztem Clip zusammenführen
            last_start, _ = merged[-1]
            merged[-1] = (last_start, buffer_end)
        else:
            merged.append((buffer_start, buffer_end))

    print(f"[Page4] Nach Merge: {len(merged)} Clips (war {len(scenes)})")
    return merged


def download_and_detect(url: str, threshold: float,
                        with_audio: bool = True, quality: str = "640x360",
                        temp_dir: str = None):
    global p4_progress, p4_pending, p4_clips_dir, p4_source_video

    session_dir = os.path.join(temp_dir, uuid.uuid4().hex)
    os.makedirs(session_dir, exist_ok=True)
    video_path = os.path.join(session_dir, "video.mp4")
    clips_dir  = os.path.join(session_dir, "clips")
    os.makedirs(clips_dir, exist_ok=True)

    p4_progress = {"current": 0, "total": 4, "status": "Lade Video herunter…",
                   "done": False, "error": None}
    p4_pending  = []
    t_start = time_module.time()

    try:
        # ── 1. Download ──────────────────────────────────────────────────────
        print(f"[Page4] Starte Download: {url}")

        fmt = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best" if with_audio \
              else "bestvideo[ext=mp4]/best[ext=mp4]/best"

        with yt_dlp.YoutubeDL({"format": fmt, "outtmpl": video_path,
                                "quiet": True, "no_warnings": True}) as ydl:
            ydl.download([url])

        if not os.path.exists(video_path):
            candidates = [f for f in os.listdir(session_dir)
                          if os.path.isfile(os.path.join(session_dir, f))]
            if candidates:
                os.rename(os.path.join(session_dir, candidates[0]), video_path)
            else:
                raise FileNotFoundError("Download fehlgeschlagen")

        size_mb = os.path.getsize(video_path) / 1024 / 1024
        print(f"[Page4] Download: {time_module.time() - t_start:.1f}s  ({size_mb:.1f} MB)")
        p4_progress.update(current=1, status="Szenenerkennung läuft…")

        # ── 2. Szenenerkennung ───────────────────────────────────────────────
        t1 = time_module.time()
        video = open_video(video_path, backend="pyav")
        sm    = SceneManager()
        sm.add_detector(ContentDetector(threshold=threshold))
        sm.detect_scenes(video, show_progress=False)
        scenes = sm.get_scene_list()
        del video
        gc.collect()

        scenes = merge_short_scenes(scenes, min_duration=3)

        print(f"[Page4] Szenenerkennung: {time_module.time() - t1:.1f}s  "
              f"(kumulativ: {time_module.time() - t_start:.1f}s)  "
              f"→ {len(scenes)} Szenen")

        if not scenes:
            p4_progress.update(status="Keine Szenen erkannt", done=True)
            return

        p4_progress.update(current=2, status=f"{len(scenes)} Szenen – schneide Clips…")

        # ── 3. Schneiden ─────────────────────────────────────────────────────
        t2 = time_module.time()
        results = cut_all_scenes(scenes, video_path, clips_dir, quality, with_audio)  # ← nur einmal

        print(f"[Page4] Schneiden: {time_module.time() - t2:.1f}s  "
              f"(kumulativ: {time_module.time() - t_start:.1f}s)  "
              f"→ {len(results)} Clips")

        p4_progress.update(current=3, status="Vorschaubilder werden erstellt…")

        # ── 4. Clip-Entries + Thumbnails ─────────────────────────────────────
        t3 = time_module.time()
        clips = []
        for i, cid, path, ss in results:
            if os.path.exists(path):
                clips.append(make_clip_entry(cid, path, start_orig=ss))
            else:
                print(f"[Page4] WARNUNG: {path} nicht gefunden")

        with ThreadPoolExecutor(max_workers=8) as executor:
            clips = list(executor.map(add_thumbnail, clips))

        print(f"[Page4] Thumbnails: {time_module.time() - t3:.1f}s  "
              f"(kumulativ: {time_module.time() - t_start:.1f}s)  "
              f"→ {len(clips)} Clips")

        p4_source_video = video_path
        appModule.rawMediaFolder = clips_dir
        p4_clips_dir = clips_dir
        p4_pending = clips

        time.sleep(0.2)
        p4_progress.update(current=4, status=f"Fertig – {len(clips)} Clips", done=True)
        print(f"[Page4] Gesamt: {time_module.time() - t_start:.1f}s")

    except Exception as e:
        print(f"[Page4] FEHLER: {e}")
        import traceback
        traceback.print_exc()
        p4_progress.update(error=str(e), done=True)

@app.callback(
    Output("p4-clips-store",      "data",     allow_duplicate=True),
    Output("p4-frame-start",      "src",      allow_duplicate=True),
    Output("p4-trim-start-label", "children", allow_duplicate=True),
    Input("p4-trim-03-btn",       "n_clicks"),
    State("p4-selected-store",    "data"),
    State("p4-clips-store",       "data"),
    prevent_initial_call=True,
)
def trimFirst03(n, selected_id, clips):
    if not n or not selected_id or not clips:
        return no_update, no_update, no_update

    clips = [dict(c) for c in clips]
    for clip in clips:
        if clip["id"] == selected_id:
            clip["trim_start"] = round(clip.get("trim_start", 0.0) + 0.3, 3)
            frame = extract_frame_b64(clip["path"], clip["trim_start"])
            src = f"data:image/jpeg;base64,{frame}" if frame else ""
            return clips, src, f"{clip['trim_start']:.2f}s"

    return no_update, no_update, no_update


@app.callback(
    Output("p4-selected-store", "data", allow_duplicate=True),
    Input("p4-prev-btn", "n_clicks"),
    Input("p4-next-btn", "n_clicks"),
    State("p4-selected-store", "data"),
    State("p4-clips-store",    "data"),
    prevent_initial_call=True,
)
def navigateClips(prev, next_, selected_id, clips):
    if not clips or not selected_id:
        return no_update

    trigger = ctx.triggered_id
    idx = next((i for i, c in enumerate(clips) if c["id"] == selected_id), None)
    if idx is None:
        return no_update

    if trigger == "p4-prev-btn":
        new_idx = max(0, idx - 1)
    else:
        new_idx = min(len(clips) - 1, idx + 1)

    return clips[new_idx]["id"]

@app.callback(
    Output("p4-clips-store",           "data", allow_duplicate=True),
    Output("p4-selected-store",        "data", allow_duplicate=True),
    Output("p4-trim-start-time-store", "data", allow_duplicate=True),
    Output("p4-trim-end-time-store",   "data", allow_duplicate=True),
    Output("p4-split-time-store",      "data", allow_duplicate=True),
    Output("main-container", "style", allow_duplicate=True),
    Input("page-store", "data"),
    prevent_initial_call=True,
)
def resetPage4Stores(page):
    if page != "page4":
        return [no_update] * 6

    global p4_pending, p4_clips_dir, p4_progress, p4_source_video

    # Temp-Ordner aufräumen
    if p4_source_video and os.path.exists(p4_source_video):
        try:
            session_dir = os.path.dirname(p4_source_video)
            shutil.rmtree(session_dir, ignore_errors=True)
            print(f"[Page4] Temp-Ordner gelöscht: {session_dir}")
        except Exception as e:
            print(f"[Page4] Aufräumen fehlgeschlagen: {e}")

    p4_pending      = []
    p4_clips_dir    = None
    p4_source_video = None
    p4_progress     = {"current": 0, "total": 0, "status": "", "done": False, "error": None}

    return [], None, None, None, None, {"overflowY": "auto", "flex": "1", "display": "none"}


# ── Callbacks ─────────────────────────────────────────────────────────────────

@app.callback(
    Output("p4-progress-area", "children"),
    Output("p4-interval",      "disabled",     allow_duplicate=True),
    Input("yt-start-btn",      "n_clicks"),
    State("yt-url-input",           "value"),
    State("scene-threshold-slider", "value"),
    State("p4-audio-checkbox",    "value"),
    State("p4-quality-dropdown",  "value"),
    State("app-settings-store",     "data"),
    prevent_initial_call=True,
)
def startDownload(n, url, threshold, audio, quality, settings):
    if not url or not n:
        return no_update, no_update

    with_audio = "audio" in (audio or [])
    temp_path = settings["path"] + settings["temp"]

    threading.Thread(
        target=download_and_detect,
        args=(url.strip(), threshold, with_audio, quality, temp_path),
        daemon=True,
    ).start()

    bar = html.Div([
        html.Label("Fortschritt", style={"whiteSpace": "nowrap", "color": "#ccc"}),
        html.Div(
            html.Div(id="p4-bar-inner", style={
                "width": "0%", "height": "12px",
                #"backgroundColor": "#378ADD",
                "borderRadius": "6px",
                "transition": "width 0.4s ease",
            }),
            style={"flex": "1", "backgroundColor": "#ddd", "borderRadius": "6px",
                   "height": "12px", "overflow": "hidden"},
        ),
        html.Span("0%", id="p4-pct-label", style={"color": "#ccc"}),
        html.Span("", id="p4-status-label",
                  style={"fontSize": "13px", "color": "#aaa", "marginLeft": "8px"}),
    ], style={"display": "flex", "alignItems": "center", "gap": "16px"})

    return bar, False





# Split
app.clientside_callback(
    """
    function(n) {
        const video = document.querySelector('video');
        if (!video) return window.dash_clientside.no_update;
        return video.currentTime;
    }
    """,
    Output("p4-split-time-store", "data"),
    Input("p4-split-btn", "n_clicks"),
    prevent_initial_call=True,
)


app.clientside_callback(
    "function(n) { const v = document.querySelector('video'); return v ? v.currentTime : 0; }",
    Output("p4-trim-start-time-store", "data"),
    Input("p4-trim-start-btn", "n_clicks"),
    prevent_initial_call=True,
)

app.clientside_callback(
    "function(n) { const v = document.querySelector('video'); return v ? v.currentTime : 0; }",
    Output("p4-trim-end-time-store", "data"),
    Input("p4-trim-end-btn", "n_clicks"),
    prevent_initial_call=True,
)

app.clientside_callback(
    """
    function(n) {
        const v = document.querySelector('video');
        if (!v) return '0.000s';
        const t = v.currentTime;
        const d = v.duration || 0;
        return t.toFixed(3) + 's  /  ' + d.toFixed(3) + 's';
    }
    """,
    Output("p4-time-display", "children"),
    Input("p4-time-interval", "n_intervals"),
    prevent_initial_call=True,
)

@app.callback(
    Output("p4-time-interval", "disabled"),
    Input("p4-selected-store", "data"),
)
def toggleTimeInterval(selected):
    return selected is None

@app.callback(
    Output("p4-clips-store",      "data",     allow_duplicate=True),
    Output("p4-frame-start",      "src",     allow_duplicate=True),
    Output("p4-trim-start-label", "children",     allow_duplicate=True),
    Input("p4-trim-start-time-store", "data"),
    State("p4-selected-store",    "data"),
    State("p4-clips-store",       "data"),
    prevent_initial_call=True,
)
def applyTrimStart(current_time, selected_id, clips):
    if current_time is None or not selected_id or not clips:
        return no_update, no_update, no_update

    clips = [dict(c) for c in clips]
    for clip in clips:
        if clip["id"] == selected_id:
            clip["trim_start"] = round(current_time, 3)
            frame = extract_frame_b64(clip["path"], current_time)
            src = f"data:image/jpeg;base64,{frame}" if frame else ""
            return clips, src, f"{current_time:.2f}s"

    return no_update, no_update, no_update


@app.callback(
    Output("p4-clips-store",    "data",     allow_duplicate=True),
    Output("p4-frame-end",      "src",     allow_duplicate=True),
    Output("p4-trim-end-label", "children",     allow_duplicate=True),
    Input("p4-trim-end-time-store", "data"),
    State("p4-selected-store",  "data"),
    State("p4-clips-store",     "data"),
    prevent_initial_call=True,
)
def applyTrimEnd(current_time, selected_id, clips):
    if current_time is None or not selected_id or not clips:
        return no_update, no_update, no_update

    clips = [dict(c) for c in clips]
    for clip in clips:
        if clip["id"] == selected_id:
            dur = clip["duration"]
            clip["trim_end"] = round(dur - current_time, 3)
            frame = extract_frame_b64(clip["path"], current_time)
            src = f"data:image/jpeg;base64,{frame}" if frame else ""
            return clips, src, f"{current_time:.2f}s"

    return no_update, no_update, no_update


@app.callback(
    Output("p4-bar-inner",      "style"),
    Output("p4-pct-label",      "children"),
    Output("p4-status-label",   "children"),
    Output("p4-interval",       "disabled"),
    Output("p4-clips-store",    "data"),
    Output("p4-selected-store", "data", allow_duplicate=True),
    Output("p4-input-area",     "style"),
    Output("main-container", "style"),
    Input("p4-interval", "n_intervals"),
    prevent_initial_call=True,
)
def updateProgress(n):
    empty_detail = (html.Div(), "", {"display": "none"}, "", "", "", "")

    total  = p4_progress["total"]
    cur    = p4_progress["current"]
    done   = p4_progress["done"]
    error  = p4_progress["error"]
    status = p4_progress["status"]
    pct    = int((cur / total) * 100) if total > 0 else 0

    if error:
        bar = {"width": "100%", "height": "12px",
               "backgroundColor": "red", "borderRadius": "6px"}
        return (bar, "Fehler", error, True,
                no_update, no_update, no_update, no_update)

    bar = {
        "width":           f"{pct}%",
        "height":          "12px",
        "backgroundColor": "#90EE90" if done else "#378ADD",
        "borderRadius":    "6px",
        "transition":      "width 0.4s ease",
    }

    if done and p4_pending:
        first   = p4_pending[0]
        first_id = first["id"]

        # Detail für ersten Clip direkt mitrendern
        dur     = first["duration"]
        player  = html.Video(
            src=f"/media/{first_id}.mp4",
            controls=True,
            style={"width": "100%", "maxHeight": "380px", "borderRadius": "8px"},
        )
        label   = f"Clip #1  ·  {dur:.2f}s"
        f_start = extract_frame_b64(first["path"], 0.0)
        f_end   = extract_frame_b64(first["path"], dur)
        src_s   = f"data:image/jpeg;base64,{f_start}" if f_start else ""
        src_e   = f"data:image/jpeg;base64,{f_end}"   if f_end   else ""

        return (bar, f"{pct}%", status, True,
                p4_pending, p4_pending[0]["id"], {"display": "none"},
                {"overflowY": "auto", "flex": "1", "display": "block"})

    return bar, f"{pct}%", status, False, no_update, no_update, no_update, no_update


@app.callback(
    Output("p4-strip", "children"),
    Input("p4-clips-store",    "data"),
    Input("p4-selected-store", "data"),
    prevent_initial_call=True,
)
def renderStrip(clips, selected_id):
    if not clips:
        return []

    cards = []
    for i, clip in enumerate(clips):
        cid    = clip["id"]
        is_sel = cid == selected_id
        thumb  = clip.get("thumbnail")

        thumb_el = (
            html.Img(
                src=f"data:image/jpeg;base64,{thumb}",
                style={"width": "100%", "height": "90px",
                       "objectFit": "cover", "borderRadius": "4px"},
            ) if thumb else
            html.Div("–", style={"height": "90px", "display": "flex",
                                 "alignItems": "center", "justifyContent": "center"})
        )

        ts = clip.get("trim_start", 0.0)
        te = clip.get("trim_end", 0.0)
        eff = clip["duration"] - ts - te

        ignored = clip.get("ignored", True)

        border = (
            "4px solid #22c55e" if is_sel and not ignored else
            "4px solid #ADFF2F" if is_sel and ignored else
            "2px solid #22c55e" if not ignored else
            "2px solid #aaa"
        )

        opacity = "1" if not ignored else "0.35"

        cards.append(
            html.Div(
                id={"type": "p4-strip-item", "clip_id": cid},
                n_clicks=0,
                children=[
                    thumb_el,
                    html.Div(
                        f"#{i + 1}   {clip.get('start_orig', 0):.1f}s  ·  {eff:.1f}s",
                        style={"fontSize": "11px", "color": "#aaa",
                               "textAlign": "center", "marginTop": "4px"},
                    ),
                ],
                style={
                    "minWidth":        "110px",
                    "maxWidth":        "110px",
                    "cursor":          "pointer",
                    "opacity": opacity,
                    "border": border,
                    "borderRadius":    "6px",
                    #"backgroundColor": "#2a2a2a" if is_sel else "#1e1e1e",
                    "padding":         "4px",
                    "flexShrink":      "0",
                },
            )
        )

    return cards

# p4-discard-btn Label dynamisch – neuer Callback:
@app.callback(
    Output("p4-discard-btn", "children"),
    Output("p4-discard-btn", "style"),
    Input("p4-selected-store", "data"),
    Input("p4-clips-store",    "data"),
    prevent_initial_call=True,
)
def updateDiscardBtn(selected_id, clips):
    if not selected_id or not clips:
        return "🗑 Verwerfen", {**titleBtnStyle, "backgroundColor": lightRed,
                                "fontSize": "13px", "cursor": "pointer", "width": "100%"}
    clip = next((c for c in clips if c["id"] == selected_id), None)

    if clip and clip.get("ignored", True):  # ← default True
        return "✓ Behalten", {**titleBtnStyle, "backgroundColor": "#22c55e",
                              "fontSize": "13px", "cursor": "pointer", "width": "100%"}
    return "✗ Verwerfen", {**titleBtnStyle, "backgroundColor": lightRed,
                           "fontSize": "13px", "cursor": "pointer", "width": "100%"}


@app.callback(
    Output("p4-selected-store", "data"),
    Input({"type": "p4-strip-item", "clip_id": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def selectClip(clicks):
    triggered = ctx.triggered_id
    print(f"[selectClip] triggered={triggered}, value={ctx.triggered[0]['value']}")
    if not triggered or ctx.triggered[0]["value"] in (None, 0):
        return no_update
    print(f"[selectClip] → gibt zurück: {triggered['clip_id']}")
    return triggered["clip_id"]

@app.callback(
    Output("p4-large-player",     "children"),
    Output("p4-selected-label",   "children"),
    Output("p4-trim-area",        "style"),
    Output("p4-frame-start",      "src"),
    Output("p4-frame-end",        "src"),
    Output("p4-trim-start-label", "children"),
    Output("p4-trim-end-label",   "children"),
    Input("p4-selected-store",    "data"),   # ← Input
    Input("p4-clips-store",       "data"),   # ← Input statt State
    prevent_initial_call=True,
)
def renderDetail(selected_id, clips):
    print(f"[renderDetail] selected_id={selected_id}, clips count={len(clips) if clips else 0}")

    empty = (html.Div(), "", {"display": "none"}, "", "", "", "")
    if not selected_id or not clips:
        print(f"[renderDetail] → early return, selected_id={selected_id}, clips={bool(clips)}")
        return empty

    clip = next((c for c in clips if c["id"] == selected_id), None)
    print(f"[renderDetail] → clip gefunden: {clip is not None}")
    if not clip:
        return empty

    print(f"[renderDetail] → path={clip['path']}, existiert={os.path.exists(clip['path'])}")

    trigger = ctx.triggered_id
    if trigger == "p4-clips-store":
        changed = next((c for c in clips if c["id"] == selected_id), None)
        if changed and (changed.get("trim_start", 0) != 0 or
                        changed.get("trim_end", 0) != 0):
            return no_update, no_update, no_update, no_update, no_update, no_update, no_update

    idx = next(i for i, c in enumerate(clips) if c["id"] == selected_id)
    dur = clip["duration"]
    ts  = clip.get("trim_start", 0.0)
    te  = clip.get("trim_end",   0.0)

    player = html.Video(
        src=f"/media/{selected_id}.mp4",
        controls=True,
        autoPlay=True,
        style={"width": "100%", "maxHeight": "380px", "borderRadius": "8px"},
    )

    label = f"Clip #{idx + 1}  ·  {round(dur - ts - te, 2):.2f}s"
    f_start = extract_frame_b64(clip["path"], ts)
    f_end = extract_frame_b64(clip["path"], min(dur - te, dur - 0.01))
    src_s   = f"data:image/jpeg;base64,{f_start}" if f_start else ""
    src_e   = f"data:image/jpeg;base64,{f_end}"   if f_end   else ""
    label_s = f"{ts:.2f}s"       if ts > 0 else ""
    label_e = f"{dur - te:.2f}s" if te > 0 else ""

    return (player, label,
            {"padding": "0 20px 20px", "display": "block"},
            src_s, src_e, label_s, label_e)



@app.callback(
    Output("p4-clips-store",    "data", allow_duplicate=True),
    Input("p4-discard-btn",     "n_clicks"),
    State("p4-selected-store",  "data"),
    State("p4-clips-store",     "data"),
    prevent_initial_call=True,
)
def toggleIgnoreClip(n, selected_id, clips):
    if not n or not selected_id or not clips:
        return no_update

    clips = [dict(c) for c in clips]
    for clip in clips:
        if clip["id"] == selected_id:
            clip["ignored"] = not clip.get("ignored", False)
            break
    return clips


@app.callback(
    Output("p4-clips-store",      "data",     allow_duplicate=True),
    Output("p4-selected-store",   "data",     allow_duplicate=True),
    Output("p4-split-time-label", "children"),
    Input("p4-split-time-store",  "data"),
    State("p4-selected-store",    "data"),
    State("p4-clips-store",       "data"),
    prevent_initial_call=True,
)
def splitClip(split_sec, selected_id, clips):
    if split_sec is None or not selected_id or not clips:
        return no_update, no_update, no_update

    idx  = next((i for i, c in enumerate(clips) if c["id"] == selected_id), None)
    if idx is None:
        return no_update, no_update

    clip      = clips[idx]
    split_sec = float(split_sec)
    dur       = clip["duration"]

    if split_sec <= 0 or split_sec >= dur:
        return no_update, no_update

    clips_dir = os.path.dirname(clip["path"])
    id_a, id_b = new_id(), new_id()
    path_a = os.path.join(clips_dir, f"{id_a}.mp4")
    path_b = os.path.join(clips_dir, f"{id_b}.mp4")

    run_ffmpeg("-i", clip["path"], "-t", str(split_sec), "-c", "copy", path_a)
    run_ffmpeg("-ss", str(split_sec), "-i", clip["path"], "-c", "copy", path_b)

    entry_a = make_clip_entry(id_a, path_a, start_orig=clip.get("start_orig", 0.0))
    entry_b = make_clip_entry(id_b, path_b,
                              start_orig=round(clip.get("start_orig", 0.0) + split_sec, 3))
    entry_a["from_file"] = True  # NEU
    entry_b["from_file"] = True

    new_clips = clips[:idx] + [entry_a, entry_b] + clips[idx + 1:]
    return new_clips, id_a, f"Split bei {split_sec:.2f}s"


@app.callback(
    Output("p4-clips-store",    "data", allow_duplicate=True),
    Output("p4-selected-store", "data", allow_duplicate=True),
    Input("p4-merge-btn",       "n_clicks"),
    State("p4-selected-store",  "data"),
    State("p4-clips-store",     "data"),
    prevent_initial_call=True,
)
def mergeClips(n, selected_id, clips):
    if not n or not selected_id or not clips:
        return no_update, no_update

    idx = next((i for i, c in enumerate(clips) if c["id"] == selected_id), None)
    if idx is None or idx >= len(clips) - 1:
        return no_update, no_update

    clip_a    = clips[idx]
    clip_b    = clips[idx + 1]
    clips_dir = os.path.dirname(clip_a["path"])

    list_path = os.path.join(clips_dir, f"_concat_{uuid.uuid4().hex[:6]}.txt")
    with open(list_path, "w") as f:
        f.write(f"file '{clip_a['path']}'\n")
        f.write(f"file '{clip_b['path']}'\n")

    mid       = new_id()
    mid_path  = os.path.join(clips_dir, f"{mid}.mp4")
    run_ffmpeg(
        "-f", "concat", "-safe", "0",
        "-i", list_path,
        "-c:v", "libx264", "-crf", "18",  # ← statt -c copy
        "-c:a", "aac",
        mid_path
    )
    os.remove(list_path)

    entry = make_clip_entry(mid, mid_path,
                            start_orig=clip_a.get("start_orig", 0.0))
    entry["from_file"] = True
    new_clips = clips[:idx] + [entry] + clips[idx + 2:]
    return new_clips, mid


@app.callback(
    Output("p4-save-status",        "children"),
    Input("p4-save-btn",            "n_clicks"),
    State("p4-clips-store",         "data"),
    State("p4-output-folder-input", "value"),
    State("app-settings-store",     "data"),
    prevent_initial_call=True,
)
def saveClips(n, clips, output_folder, settings):
    print(f"[saveClips] n={n}, clips={len(clips) if clips else None}, "
          f"output_folder={output_folder}, settings={bool(settings)}")

    if not n or not clips or not output_folder:
        return no_update

    print("saving...")

    try:
        path = settings["path"] + output_folder
        os.makedirs(path, exist_ok=True)
    except Exception as e:
        return f"Fehler beim Erstellen des Ordners: {e}"

    saved     = 0
    errors    = 0
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    source_ok = (
        p4_source_video is not None and
        os.path.exists(p4_source_video)
    )

    for i, clip in enumerate(clips):
        if clip.get("ignored", True):
            continue

        ts         = clip.get("trim_start", 0.0)
        te         = clip.get("trim_end",   0.0)
        dur        = round(clip["duration"] - ts - te, 3)
        start_orig = clip.get("start_orig", 0.0)
        from_file  = clip.get("from_file",  False)
        clip_path  = clip["path"]
        dst        = os.path.join(path, f"{timestamp}_{i + 1:04d}.mp4")

        if dur <= 0:
            print(f"[saveClips] Clip {i}: Dauer {dur}s ≤ 0, übersprungen")
            errors += 1
            continue

        print(f"[saveClips] Clip {i}: start_orig={start_orig}, ts={ts}, "
              f"te={te}, dur={dur}, from_file={from_file}, source_ok={source_ok}")

        # ── Entscheidung: Original oder Clip-Datei ───────────────────────────
        # Original nutzen wenn:
        # - Originalvideo vorhanden
        # - Clip stammt direkt aus dem Original (nicht gesplittet/gemergt)
        # - start_orig > 0 (erster Clip beginnt bei 0, der kann auch direkt kopiert werden)
        use_original = (
            source_ok and
            not from_file and
            start_orig >= 0  # alle unveränderten Original-Clips
        )

        # Lokaler Ordner: start_orig ist immer 0 für alle Clips → nie Original nutzen
        # da Original-Zeitstempel unbekannt
        if source_ok and not from_file:
            # Prüfen ob es ein lokaler Ordner ist (alle start_orig == 0)
            all_zero = all(c.get("start_orig", 0.0) == 0.0 for c in clips
                          if not c.get("from_file", False))
            if all_zero:
                use_original = False

        if use_original:
            # ── Aus Originalvideo schneiden ──────────────────────────────────
            ss        = start_orig + ts
            pre_seek  = max(0.0, ss - 2.0)
            fine_seek = round(ss - pre_seek, 3)

            fps = 30
            one_frame = round(1 / fps, 4)

            if ts > 0 or te > 0:
                ok = run_ffmpeg(
                    "-ss", str(pre_seek),
                    "-i",  p4_source_video,
                    "-ss", str(fine_seek),
                    "-t",  str(max(0.01, dur - one_frame)),
                    "-c:v", "libx264", "-crf", "18",
                    "-c:a", "aac",
                    "-avoid_negative_ts", "make_zero",
                    dst
                )
            else:
                ok = run_ffmpeg(
                    "-ss", str(start_orig),
                    "-i",  p4_source_video,
                    "-t",  str(dur),
                    "-c:v", "libx264", "-crf", "18",
                    "-c:a", "aac",
                    "-avoid_negative_ts", "make_zero",
                    dst
                )
        else:
            # ── Direkt aus Clip-Datei schneiden / kopieren ───────────────────
            if not os.path.exists(clip_path):
                print(f"[saveClips] Clip {i}: Datei nicht gefunden: {clip_path}")
                errors += 1
                continue

            if ts > 0 or te > 0:
                ok = run_ffmpeg(
                    "-ss", str(ts),
                    "-i",  clip_path,
                    "-t",  str(dur),
                    "-c:v", "libx264", "-crf", "18",
                    "-c:a", "aac",
                    "-avoid_negative_ts", "make_zero",
                    dst
                )
            else:
                try:
                    shutil.copy2(clip_path, dst)
                    ok = True
                except Exception as e:
                    print(f"[saveClips] Kopieren fehlgeschlagen: {e}")
                    ok = False

        if ok:
            saved += 1
            print(f"[saveClips] Clip {i}: ✓ gespeichert")
        else:
            errors += 1
            print(f"[saveClips] Clip {i}: ✗ Fehler")

    msg = f"✓ {saved} Clips gespeichert → {path}"
    if errors:
        msg += f"  ({errors} Fehler)"
    return msg


@app.callback(
    Output("p4-clips-store",    "data",  allow_duplicate=True),
    Output("p4-selected-store", "data",  allow_duplicate=True),
    Output("p4-input-area",     "style", allow_duplicate=True),
    Output("main-container",    "style", allow_duplicate=True),
    Input("p4-folder-btn",      "n_clicks"),
    State("p4-folder-input",    "value"),
    prevent_initial_call=True,
)
def loadFolder(n, folder_path):
    global p4_source_video, p4_clips_dir

    if not n or not folder_path:
        return no_update, no_update, no_update, no_update

    if not os.path.isdir(folder_path):
        return no_update, no_update, no_update, no_update

    # Originalvideo suchen
    source_video = None
    for ext in [".mp4", ".mov", ".webm", ".avi"]:
        candidate = os.path.join(folder_path, f"video{ext}")
        if os.path.exists(candidate):
            source_video = candidate
            break

    p4_source_video = source_video

    # Clips-Unterordner suchen
    clips_dir = os.path.join(folder_path, "clips")
    if not os.path.isdir(clips_dir):
        return no_update, no_update, no_update, no_update

    VIDEO_EXT = [".mp4", ".mov", ".webm", ".avi"]
    files = sorted([
        f for f in os.listdir(clips_dir)
        if os.path.splitext(f)[1].lower() in VIDEO_EXT
    ])

    if not files:
        return no_update, no_update, no_update, no_update

    appModule.rawMediaFolder = clips_dir
    p4_clips_dir  = clips_dir
    p4_source_video = source_video  # None wenn nicht vorhanden – saveClips fängt das ab

    clips = []
    for i, filename in enumerate(files):
        path = os.path.join(clips_dir, filename)
        name = os.path.splitext(filename)[0]
        entry = make_clip_entry(name, path, start_orig=0.0)
        entry["thumbnail"] = extract_frame_b64(path, 0.0)
        clips.append(entry)

    print(f"[Page4] {len(clips)} Clips geladen, Originalvideo: {source_video}")

    return (
        clips,
        clips[0]["id"] if clips else None,
        {"display": "none"},
        {"overflowY": "auto", "flex": "1", "display": "block"},
    )