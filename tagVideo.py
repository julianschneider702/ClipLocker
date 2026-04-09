import base64
import io
import threading

import anthropic
import cv2, time
from PIL import Image

from app import app
import app as appModule
from db import readTagsFromDB, addToDB, fillDropdownsFromDB, loadDescriptionFromDB, updateClipInDB, loadEpochFromDB
from logger import log
from styles import *

from dash import html, dcc, Output, Input, State, no_update, ctx, ALL, MATCH
import os, sqlite3, shutil, requests, re
from PIL import Image as PILImage

#----------------#
DEBUG = False
#----------------#

MAX_LONG_SIDE = 1568
claudeResults = {}

allowed_images = [".jpg", ".jpeg", ".png", ".webp", ".avif"]
allowed_videos = [".mp4", ".mov", ".webm", ".avi"]


progress = {"current": 0, "total": 0}

def renderPage2_1(appSettings):
    global claudeResults
    claudeResults = {}
    global progress
    progress = {"current": 0, "total": 0}

    return html.Div(
        style={
            "display": "flex",
            "flexDirection": "column",
            "height": "100%",
            "padding": "20px",
            "boxSizing": "border-box",
            "gap": "15px",
        },
        children=[
            html.H1("ClipLocker", style=headerStyleSmall),

            renderTopPathInput(appSettings),

            html.Div(id="page2_1Content",
                     style={
                         "overflowY": "auto",
                         "flex": "1",
                         "minHeight": "0",
                     }

            )
        ]
    )

def renderPage2_2(claudeData, clips, appSettings):
    if not clips or not isinstance(clips, list):
        firstClip = None
    else:
        activeClips = [c for c in clips if claudeData and c["name"] in claudeData]
        firstClip = activeClips[0] if activeClips else None

    return html.Div(
        style={
            "display": "flex",
            "flexDirection": "column",
            "height": "100vh",
            "padding": "20px",
            "boxSizing": "border-box",
            "gap": "15px",
        },
        children=[
            html.Div(
                style={"display": "flex", "alignItems": "center", "marginBottom": "10px"},
                children=[
                    html.H1("ClipLocker", style=headerStyleSmall),
                ]
            ),

            html.Div(
                style={
                    "display": "flex",
                    "flex": "1",
                    "gap": "20px",
                },
                children=[
                    renderLeftPreviewAndButton(firstClip),
                    renderRightDropDowns(appSettings, claudeData, firstClip)
                ]
            )
        ]
    )

def renderTopPathInput(appSettings):

    return html.Div(
        style={
            "display": "flex",
            "alignItems": "center",
            "gap": "10px",
            "width": "100%",
            "marginBottom": "20px",
        },
        children=[
            html.Label(
                "Rohmaterialordner:",
                style={
                    "width": "20%",
                    "fontWeight": "bold"
                }
            ),

            dcc.Input(
                id="path-input",
                type="text",
                placeholder="Ordnerpfad eingeben...",
                value= appSettings["path"] + appSettings["raw"],
                style= baseStyleInputPath
            ),

            html.Button(
                "✓",
                id="path-button",
            ),

        ]
    )

@app.callback(
    Output("page2_1Content", "children"),
    Input("clips-store", "data"),
    prevent_initial_call=True,
)
def renderPage2_1Content(clips):
    if not clips:
        return no_update

    return html.Div(
        style={"display": "flex", "flexDirection": "column", "gap": "12px", "padding": "16px"},
        children=[
            # Button oben
            html.Button(
                "▶ Alle Analysieren",
                id="analyse-btn",
                disabled=True,
                style=analyseBtnStyle
            ),
            # Analyse Progress
            html.Div(
                id="analyse-area"
            ),

            # Grid darunter
            html.Div(
                style={
                    "display": "grid",
                    "gridTemplateColumns": "repeat(2, 1fr)",
                    "gap": "12px",
                },
                children=[renderClipCard(clip) for clip in clips]
            )
        ]
    )

@app.callback(
    Output("pathInput-store", "data"),
    Input("path-input", "value"),
)
def savePath(path):
    return path

@app.callback(
    Output("path-input", "style"),
    Input("path-input", "value"),
    prevent_initial_call=True
)
def colorPathLabelRed(value):
    newStyle = baseStyleInputPath.copy()
    newStyle["backgroundColor"] = red
    return newStyle

@app.callback(
    Output("path-input", "style", allow_duplicate=True),
    Output("path-button", "style"),
    Input("path-button", "n_clicks"),
    State("pathInput-store", "data"),
    prevent_initial_call=True
)
def checkPathAndShowAndHideButton(clicks, path):

    if path is None:
        return no_update, no_update

    newStylePath = baseStyleInputPath.copy()

    if os.path.isdir(path) and os.listdir(path):
        newStylePath["backgroundColor"] = green
        log("Pfad erfolgreich eingelesen.")
        return newStylePath, {"display": "none"}
    else:
        newStylePath["backgroundColor"] = red
        log("Ungültiger Pfad.", color="red")
        return newStylePath, no_update

@app.callback(
    Output("clips-store", "data"),
    Output("currentClip-store", "data"),
    Input("path-button", "n_clicks"),
    State("pathInput-store", "data"),
    prevent_initial_call=True
)
def saveClips(clicks, path):
    if path is None:
        return no_update, no_update

    if os.path.isdir(path) and os.listdir(path):
        appModule.rawMediaFolder = path
    else:
        appModule.rawMediaFolder = None
        return no_update,  None

    media = []
    clipsLoadedCount = 0
    clipsNotLoadedCount = 0

    for i, filename in enumerate(os.listdir(path)):

        full_path = os.path.join(path, filename)

        if not os.path.isfile(full_path):
            continue

        name, ext = os.path.splitext(filename)
        ext = ext.lower()

        if ext in allowed_images:
            media.append({"name": name,
                          "extension": ext,
                          "type": "image"})
            clipsLoadedCount += 1

        elif ext in allowed_videos:
            media.append({"name": name,
                          "extension": ext,
                          "type": "video"})
            clipsLoadedCount += 1

        else:
            log("Unaerlaubtes Format entdeckt: ", name, ext, color="red")
            clipsNotLoadedCount += 1

    log("Clips erfolgreich geladen: ", clipsLoadedCount)
    if clipsNotLoadedCount > 0:
        log("Clips nicht geladen: ", clipsNotLoadedCount)

    return media, -1 if media else None

def renderClipCard(clip):
    return html.Div(
        id={"type": "clip-card", "name": clip["name"]},
        style={
            "borderRadius": "8px",
            "border": "1px solid #444",
            "backgroundColor": "#2a2a2a",
            "overflow": "hidden",
            "height": "390px",
        },
        children=[

            # Thumbnail
            html.Div(
                style={
                    "width": "100%",
                    "height": "305px",
                    "backgroundColor": "#1a1a1a",
                    "display": "flex",
                    "alignItems": "center",
                    "justifyContent": "center",
                    "position": "relative",
                },
                children=[
                    showClip(clip),

                    # Badge oben rechts
                    html.Span(
                        clip["type"],
                        style={
                            "position": "absolute",
                            "top": "6px",
                            "right": "6px",
                            "fontSize": "15px",
                            "padding": "2px 6px",
                            "borderRadius": "99px",
                            "backgroundColor": "#0F6E56",
                            "color": "#9FE1CB",
                        }
                    )
                ]
            ),

            # Body
            html.Div(
                style={"padding": "10px 12px",
                       "display": "flex",
                       "flexDirection":
                       "column", "gap": "8px"},
                children=[

                    # Dateiname
                    html.Div(
                        f"{clip['name']}{clip['extension']}",
                        style={"fontSize": "15px", "fontWeight": "500", "color": "#d4d4d4",
                               "overflow": "hidden", "textOverflow": "ellipsis", "whiteSpace": "nowrap"}
                    ),

                    # Buttons
                    html.Div(
                        style={
                            "display": "flex",
                            "justifyContent": "space-between",
                            "alignItems": "center",
                        },
                        children=[
                            html.Div(
                                style={"display": "flex", "gap": "8px"},
                                children=[
                                    html.Button("Haiku",
                                                id={"type": "haiku-btn", "name": clip["name"]},
                                                style= cardBtnStyle),
                                    html.Button("Sonnet",
                                                id={"type": "sonnet-btn", "name": clip["name"]},
                                                style= cardBtnStyle),
                                    html.Button("🚫", id={"type": "hide-btn", "name": clip["name"]},
                                                style= cardBtnStyle),
                                    createTimestampField(clip)
                                ]
                            ),
                        ]
                    )
                ]
            )
        ]
    )

def createTimestampField(clip):
    if clip["type"] == "video":
        return dcc.Input(
            id={"type": "timestamp-field", "name": clip["name"]},
            style = timestampStyle,
            type="text",
            placeholder="Timestamps",
        )
    # image timestamp ist unsichtbar
    return html.Div(
        id={"type": "timestamp-field", "name": clip["name"]},
        style={"display": "none"}
    )


@app.callback(
    Output("clip-settings-store", "data", allow_duplicate=True),
    Input({"type": "timestamp-field", "name": ALL}, "value"),
    State("clip-settings-store", "data"),
    prevent_initial_call=True,
)
def saveTimestamps(values, store):
    trigger = ctx.triggered_id

    if not trigger or not isinstance(trigger, dict):
        return store

    clipName = trigger["name"]
    text = ctx.triggered[0]["value"]
    settings = store.get(clipName, {"model": None, "hidden": False, "timestamps": []})

    if not text:
        settings["timestamps"] = []
        store[clipName] = settings
        return store

    if text and checkSyntaxTimestampField(text):
        settings["timestamps"] = [int(x.strip()) for x in text.split(",")]
        store[clipName] = settings

    return store


@app.callback(
    Output({"type": "timestamp-field", "name": MATCH},"style", allow_duplicate=True),
    Input({"type": "timestamp-field", "name": MATCH},"value"),
    prevent_initial_call=True,
)
def colorTimestampField(text):
    if text is None or not text:
        return {**timestampStyle, "border": "1px solid" + grey}

    if checkSyntaxTimestampField(text):
        return {**timestampStyle, "border": "2px solid" + lightGreen}
    else:
        return {**timestampStyle, "border": "2px solid" + lightRed}

def checkSyntaxTimestampField(text):
    return bool(re.fullmatch(r"\d+(\s*,\s*\d+)*", text.strip()))         #nur zahlen mit kommas getrennt

#UI
@app.callback(
    Output({"type": "haiku-btn", "name": MATCH}, "style"),
    Output({"type": "sonnet-btn", "name": MATCH}, "style"),
    Output({"type": "hide-btn", "name": MATCH}, "style"),
    Output({"type": "timestamp-field", "name": MATCH},"style"),
    Output({"type": "clip-card", "name": MATCH}, "style"),
    Input({"type": "haiku-btn", "name": MATCH}, "n_clicks"),
    Input({"type": "sonnet-btn", "name": MATCH}, "n_clicks"),
    Input({"type": "hide-btn", "name": MATCH}, "n_clicks"),
    State("clip-settings-store", "data"),
    prevent_initial_call=True,
)
def updateClipDisplay(haiku, sonnet, hide, store):
    trigger = ctx.triggered_id
    clipName = trigger["name"]
    settings = store.get(clipName, {"model": None, "hidden": False})

    if trigger["type"] == "haiku-btn":
        return {**cardBtnStyle, "border": "1px solid " + blue}, cardBtnStyle, cardBtnStyle, no_update, cardStyleNormal
    if trigger["type"] == "sonnet-btn":
        return cardBtnStyle, {**cardBtnStyle, "border": "1px solid " + blue}, cardBtnStyle, no_update, cardStyleNormal
    if trigger["type"] == "hide-btn":
        hidden = not settings.get("hidden", False)
        cardStyle = cardStyleHidden if hidden else cardStyleNormal
        return no_update, no_update, no_update, no_update, cardStyle

    return no_update, no_update, no_update, no_update, cardStyleNormal

#STORE
@app.callback(
    Output("clip-settings-store", "data", allow_duplicate=True),
    Input({"type": "haiku-btn", "name": ALL}, "n_clicks"),
    Input({"type": "sonnet-btn", "name": ALL}, "n_clicks"),
    Input({"type": "hide-btn", "name": ALL}, "n_clicks"),
    State("clip-settings-store", "data"),
    prevent_initial_call=True,
)
def saveClipSettings(haiku, sonnet, hide, store):
    trigger = ctx.triggered_id
    if not trigger or not isinstance(trigger, dict):
        return store

    clipName = trigger["name"]
    settings = store.get(clipName, {"model": None, "hidden": False, "timestamps": []})

    if trigger["type"] == "haiku-btn":
        settings["model"] = "haiku"
    elif trigger["type"] == "sonnet-btn":
        settings["model"] = "sonnet"
    elif trigger["type"] == "hide-btn":
        settings["hidden"] = not settings.get("hidden", False)

    store[clipName] = settings
    return store


@app.callback(
    Output("analyse-btn","style", allow_duplicate=True),
    Output("analyse-btn","disabled", allow_duplicate=True),
    Input("clip-settings-store", "data"),
    State("clips-store", "data"),
    State("analyse-btn", "style"),
    prevent_initial_call=True,
)
def activateAnalyseBtn(settings, clips, currentStyle):
    if not clips:
        return no_update, no_update

    #wenn unsichtbar dann ignorieren
    if currentStyle and currentStyle.get("display") == "none":
        return no_update, no_update

    if settings is None or clips is None:
        return no_update, no_update

    for clip in clips:
        setting = settings.get(clip["name"], {})
        hidden = setting.get("hidden", False)

        if hidden:
            continue

        model = setting.get("model", None)
        timestamps = setting.get("timestamps", [])
        type = clip["type"]

        if type == "video":
            if model is None or len(timestamps) == 0:
                return analyseBtnStyle, True
        if type == "image":
            if model is None:
                return analyseBtnStyle, True

    log("Analyse-Button aktiviert")
    return {**analyseBtnStyle, "cursor": "pointer", "backgroundColor": "white", "color": "black"}, False


@app.callback(
    Output("analyse-area", "children", allow_duplicate=True),
    Output("analyse-btn", "style"),
    Input("analyse-btn", "n_clicks"),
    State("clips-store", "data"),
    State("clip-settings-store", "data"),
    State("app-settings-store", "data"),
    prevent_initial_call=True,
)
def AnalyseBtnPressed(btn, clips, settings, appSettings):


    progressbar = html.Div([
    html.Label(
        "Fortschritt",
        style={"white-space": "nowrap"}
    ),
    html.Div(
        html.Div(
            id="bar-inner",
            style={
                "width": "0%",
                "height": "12px",
                "backgroundColor": "#378ADD",
                "borderRadius": "6px",
                "transition": "width 0.4s ease"
            }
        ),
        style={
            "flex": "1",
            "backgroundColor": "#eee",
            "borderRadius": "6px",
            "height": "12px",
            "overflow": "hidden"
        }
    ),
    html.Span("0%", id="pct-label"),
    dcc.Interval(id="progress-interval", interval=500)
], style={
    "display": "flex",
    "alignItems": "center",
    "gap": "16px"
})

    threading.Thread(target=createClaudePrompts, args=(clips, settings, appSettings)).start()

    return progressbar, {**analyseBtnStyle, "display": "none"}


@app.callback(
    Output("bar-inner", "style"),
    Output("pct-label", "children"),
    Output("progress-interval", "disabled"),
    Output("claude-descriptions-store", "data"),
    Input("progress-interval", "n_intervals"),
    prevent_initial_call=True,
)
def updateProgressBar(n):
    global progress, claudeResults

    total = progress["total"]
    current = progress["current"]

    pct = int((current / total) * 100) if total > 0 else 0
    fertig = current >= total and total > 0

    barStyle = {
        "width": f"{pct}%",
        "height": "12px",
        "backgroundColor": "#378ADD" if not fertig else "#90EE90",
        "borderRadius": "6px",
        "transition": "width 0.4s ease"
    }

    storeData = claudeResults if (fertig and claudeResults) else no_update

    return barStyle, f"{pct}%", fertig, storeData

def detect_image_media_type(image_path):
    with Image.open(image_path) as img:
        fmt = img.format.lower()

    media_type_map = {
        "jpeg": "image/jpeg",
        "jpg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
        "avif": "image/avif",
    }

    return media_type_map.get(fmt)


def createClaudePrompts(clips, settings, appSettings):
    if settings is None or clips is None:
        return no_update

    print("db-path_ ", appSettings["path"] + appSettings["db"])
    conn = sqlite3.connect(appSettings["path"] + appSettings["db"])
    database = conn.cursor()
    database.execute("SELECT tag_name FROM Tags")
    rows = database.fetchall()
    conn.close()

    tagList = rows

    client = anthropic.Anthropic(
        api_key="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")

    if DEBUG:
        activeClips = clips
    else:
        activeClips = [c for c in clips if not settings.get(c["name"], {}).get("hidden", False)]

    for clip in clips:
        if settings.get(clip["name"], {}).get("hidden", False):
            claudeResults[clip["name"]] = {"description": "", "tags": []}

    if not activeClips:
        progress["total"] = 1
        progress["current"] = 1
        return

    progress["total"] = len(activeClips)
    progress["current"] = 0

    for clip in activeClips:
        setting = settings.get(clip["name"], {})

        model = setting.get("model")
        model = "claude-haiku-4-5-20251001" if model == "haiku" else "claude-sonnet-4-6"

        clipType = clip["type"]
        clipName = clip["name"] + clip["extension"]

        if DEBUG:
            log("Debug-Active:", clip["name"], color="blue")
            claudeResults[clip["name"]] = {
                "description": "A concentrated archer in a forest draws a crossbow while standing alert among the trees. "
                               "Wearing a hooded cloak with fur collar and medieval armor, "
                               "the figure appears tense and ready for action. "
                               "The woodland setting with bare trees suggests a hunting or military operation during daytime.",
                "tags": ['concentrated', 'tense', 'archer', 'standing', 'hunting', 'forest', 'crossbow', 'bow', 'arrow', 'armor', 'clothes', 'daytime']
            }
        else:
            if clipType == "image":

                imagePath = os.path.join(appModule.rawMediaFolder, clipName)

                mediaType = detect_image_media_type(imagePath)
                if mediaType is None:
                    log(f"Unbekanntes Bildformat: {clipName}", color="red")
                    progress["current"] += 1
                    continue

                with open(imagePath, "rb") as f:
                    raw = f.read()

                    raw = resizeImage(raw)
                    imageData = base64.b64encode(raw).decode("utf-8")

                parsed = promptToClaude(
                    model=model, client=client, tagList=tagList, clipName=clipName,
                    mediaType=mediaType, imageData=imageData
                )
                log("Send Image Prompt to: ", model, " for: ", clip["name"])

            elif clipType == "video":
                timestamps = setting.get("timestamps", [])
                videoPath = os.path.join(appModule.rawMediaFolder, clipName)
                frames = extractFramesFromVideo(videoPath, timestamps)

                parsed = promptToClaude(
                    model=model, client=client, tagList=tagList, clipName=clipName,
                    frames=frames
                )
                log("Send Image Prompt to: ", model, " for: ", clip["name"])

            claudeResults[clip["name"]] = parsed

        progress["current"] += 1

def extractFramesFromVideo(videoPath, timestamps):
    """timestamps = Liste von Sekunden, z.B. [10, 45, 120]"""
    cap = cv2.VideoCapture(videoPath)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frames = []

    for sec in timestamps:
        frameIndex = int(sec * fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frameIndex)
        ret, frame = cap.read()

        if ret:
            _, buffer = cv2.imencode(".jpg", frame)
            raw = resizeImage(buffer.tobytes())
            imageData = base64.b64encode(raw).decode("utf-8")
            frames.append(imageData)

    cap.release()
    return frames

def promptToClaude(model, client, tagList, clipName, retries=3, mediaType=None, imageData=None, frames=None):

    isHaiku = model == "claude-haiku-4-5-20251001"
    isVideo = frames is not None

    intro = (
        f"{'You must follow the decision process strictly and in order.' + chr(10) + chr(10) if isHaiku else ''}"
        f"{'Analyze these video frames from the same clip carefully. ' if isVideo else 'Analyze this image carefully. '}"
        f"{'Identify what is consistently visible across the frames and describe the scene as a whole.' if isVideo else ''}\n\n"
    )

    decisionProcess = (
        f"Select only clearly visible tags from this list: {tagList}\n\n"

        f"Follow this decision process in order:\n\n"

        f"1. {'Are the frames' if isVideo else 'Is the image'} too dark or low quality to identify details clearly?\n"
        f"   → Describe only what is unambiguously visible, even if that is "
        f"just one object or one material. Write fewer than 3 sentences if "
        f"necessary. Never describe shapes or details you cannot clearly "
        f"distinguish.\n\n"

        f"2. {'Do the frames show' if isVideo else 'Is it'} a WIDE PANORAMA with multiple distinct horizontal zones?\n"
        f"   → Identify the zone with the most visible detail and describe "
        f"only that zone. Apply rules 3–5 to that zone only.\n\n"

        f"3. Are PEOPLE clearly visible?\n"
        f"   → Describe what they are doing, with what objects, in what setting\n\n"

        f"4. Are only OBJECTS visible?\n"
        f"   → Describe what they are, their material, arrangement and condition\n\n"

        f"5. Is only a PLACE visible?\n"
        f"   → Describe the space, its structure, materials and notable features\n\n"

        f"Write exactly 3 sentences unless rule 1 applies. Rules:\n"
        f"- Only describe what is CLEARLY visible\n"
        f"- Infer role or occupation only when clearly supported by the combination "
        f"of visible tools, clothing and setting – name the inferred role directly, "
        f"do not describe the evidence that led to it\n"
        f"- If unsure about any detail, omit it – incomplete is better than wrong\n"
        f"{'- Only describe what is consistent across multiple frames' + chr(10) if isVideo else ''}"
        f"- Name materials when identifiable: stone, timber, clay, straw, "
        f"wool, iron, leather, thatch\n"
        f"- Name actions precisely: stacking, burning, cooking, building, "
        f"grinding, carrying, weaving\n"
        f"- Name objects precisely: hearth, beam, rafter, wall, roof, "
        f"chimney, vessel, tool\n"
        f"- No filler words, no art style, no storytelling\n"
        f"{'- Do not include the total number of frames or refer to the frame number while describing' + chr(10) if isVideo else ''}"
        f"- Build the description around the selected tags – they must appear as "
        f"load-bearing parts of the sentence, not appended at the end\n\n"

        f"Reply in EXACTLY this format:\n"
        f"DESCRIPTION: [your sentences]\n"
        f"TAGS: tag1, tag2, tag3\n\n"
        f"{'The examples show only the required format and sentence structure. Do not reuse their vocabulary or content.' + chr(10) + chr(10) if isHaiku else ''}"
    )

    # Haiku bekommt alle 5 Beispiele, Sonnet nur 2
    examplesFull = (
        f"Examples:\n"
        f"DESCRIPTION: A peasant woman cooks over an indoor fireplace, stirring "
        f"a kettle that hangs above the flames on an iron chain. A second peasant "
        f"carries firewood toward the fire across a stone interior with a low "
        f"ceiling. A food container and jug sit on a wooden table along the wall.\n"
        f"TAGS: indoor-fireplace, fire, cooking, carrying, peasant, kettle, "
        f"firewood, interior\n\n"

        f"DESCRIPTION: A lumberjack stacks split firewood in horizontal rows "
        f"beneath a wooden overhang, with cut cross-sections showing dry grain. "
        f"An iron axe rests against the outer stack beside scattered wood chips "
        f"on the ground. Several layers of seasoned firewood fill the sheltered "
        f"storage area.\n"
        f"TAGS: firewood, axe, lumberjack\n\n"

        f"DESCRIPTION: A narrow corridor runs between two thick stone walls with "
        f"arched openings along one side and an uneven flagstone floor. A guard "
        f"stands near the far archway holding a spear, partially lit by a wall-"
        f"mounted torch. The vaulted ceiling and thick masonry indicate a castle "
        f"interior.\n"
        f"TAGS: corridor, castle, interior, guard, standing, spear, torch\n\n"

        f"DESCRIPTION: A large barn interior with high rafters and a dirt floor "
        f"contains grain bundles hanging from the beams and a barrel stacked "
        f"against the timber wall. A peasant crouches near the far wall, "
        f"harvesting grain into a sack with a scythe resting beside them. "
        f"Scattered straw covers the floor around the storage area.\n"
        f"TAGS: barn, interior, grain, barrel, peasant, crouching, "
        f"harvesting, scythe\n\n"

        f"DESCRIPTION: A stone wall and the lower half of a wooden beam are "
        f"visible in low light.\n"
        f"TAGS: wall, interior\n"
    )

    examplesShort = (
        f"Examples:\n"
        f"DESCRIPTION: A peasant woman cooks over an indoor fireplace, stirring "
        f"a kettle that hangs above the flames on an iron chain. A second peasant "
        f"carries firewood toward the fire across a stone interior with a low "
        f"ceiling. A food container and jug sit on a wooden table along the wall.\n"
        f"TAGS: indoor-fireplace, fire, cooking, carrying, peasant, kettle, "
        f"firewood, interior\n\n"

        f"DESCRIPTION: A stone wall and the lower half of a wooden beam are "
        f"visible in low light.\n"
        f"TAGS: wall, interior\n"
    )

    basePrompt = intro + decisionProcess + (examplesFull if isHaiku else examplesShort)

    if imageData:
        imageContent = [{
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": mediaType,
                "data": imageData
            }
        }]
    elif frames:
        imageContent = [{
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": frame
            }
        } for frame in frames]
    else:
        raise ValueError(f"Weder imageData noch frames übergeben für {clipName}")

    for attempt in range(retries):
        try:
            message = client.messages.create(
                model=model,
                max_tokens=250,
                messages=[{
                    "role": "user",
                    "content": [
                        *imageContent,
                        {
                            "type": "text",
                            "text": basePrompt
                        }
                    ]
                }]
            )
            parsed = parseClaudeResponse(message.content[0].text, clipName)
            if parsed:
                return parsed

            log(f"Format falsch bei {clipName}, Versuch {attempt + 1}/{retries}", color="orange")

        except anthropic.APIStatusError as e:
            if e.status_code == 529:
                waitTime = 10 * (attempt + 1)
                log(f"API überlastet, warte {waitTime}s... (Versuch {attempt + 1}/{retries})", color="orange")
                time.sleep(waitTime)
            else:
                raise

    log(f"FEHLER: {clipName} nach {retries} Versuchen fehlgeschlagen.", color="red")
    return {"error": "Ungültiges Format"}

def parseClaudeResponse(response, clipName):
    if response is None:
        return None

    descMatch = re.search(r"DESCRIPTION:\s*(.+?)(?=TAGS:|$)", response, re.DOTALL)
    tagsMatch = re.search(r"TAGS:\s*(.+?)$", response, re.DOTALL)

    if not descMatch or not tagsMatch:
        log(f"FEHLER: Ungültiges Format bei {clipName}: {response}", color="red")
        return None

    description = descMatch.group(1).strip()
    tags = [t.strip() for t in tagsMatch.group(1).split(",") if t.strip()]

    if not description or not tags:
        log(f"FEHLER: Leere Description oder Tags bei {clipName}", color = "red")
        return None

    return {
        "description": description,
        "tags": tags
    }

def resizeImage(imageBytes: bytes) -> bytes:
    img = PILImage.open(io.BytesIO(imageBytes))

    w, h = img.size
    longSide = max(w, h)

    if longSide <= MAX_LONG_SIDE:
        return imageBytes  # kein Resize nötig

    scale = MAX_LONG_SIDE / longSide
    newW = int(w * scale)
    newH = int(h * scale)

    img = img.resize((newW, newH), PILImage.LANCZOS)

    buffer = io.BytesIO()
    fmt = img.format if img.format else "JPEG"
    img.save(buffer, format=fmt)
    return buffer.getvalue()


@app.callback(
    Output("page-store", "data", allow_duplicate=True),
    Output("currentClip-store", "data", allow_duplicate=True),
    Input("claude-descriptions-store", "data"),
    State("clips-store", "data"),
    State("page-store", "data"),
    prevent_initial_call=True
)
def switchToPage2_2(data, clips, page):
    if data is None or not clips or page == "page2_2":
        return no_update, no_update

    # Index des ersten analysierten Clips finden
    firstIndex = next(
        (i for i, c in enumerate(clips) if c["name"] in data),
        0
    )
    return "page2_2", firstIndex

def renderLeftPreviewAndButton(firstClip, editMode=False):
    buttons = [
        html.Button(
            "Speichern" if editMode else "In DB integrieren und weiter zum Nächsten Clip",
            id="db-button",
            style={"padding": "12px", "fontSize": "16px", "cursor": "pointer", "marginBottom": "15px"}
        )
    ]
    if not editMode:
        buttons.append(html.Button(
            "Überspringen",
            id="skip-button",
            style={"padding": "12px", "fontSize": "16px", "cursor": "pointer"}
        ))
    else:
        # Platzhalter damit Dash nicht über fehlende IDs klagt
        buttons.append(html.Button(
            "Überspringen",
            id="skip-button",
            style={"display": "none"}
        ))

    return html.Div(
        style={
            "width": "50%",
            "display": "flex",
            "flexDirection": "column",
            "alignItems": "left",
            "justifyContent": "flex-start",
            "marginRight": "20px",
        },
        children=[
            html.Div(
                id="content-panel",
                style={
                    "width": "99%",
                    "height": "300px",
                    "display": "flex",
                    "alignItems": "center",
                    "justifyContent": "center",
                    "overflow": "hidden",
                    "marginBottom": "30px",
                },
                children=[showClip(firstClip)] if firstClip else []
            ),
            *buttons
        ]
    )

def renderRightDropDowns(appSettings, claudeData=None, firstClip=None, editMode=False, editClipId=None):
    tagList = readTagsFromDB(appSettings)

    if editMode and editClipId is not None:
        # Tags direkt aus DB laden
        filledValues = fillDropdownsFromDB(editClipId, tagList, appSettings)
        description = loadDescriptionFromDB(editClipId, appSettings)
        epochValue = loadEpochFromDB(editClipId, appSettings)
    else:
        # Normaler Page2-Modus: Claude-Data verwenden
        claudeTags = []
        if claudeData and firstClip and firstClip["name"] in claudeData:
            claudeTags = claudeData[firstClip["name"]].get("tags", [])
        filledValues = fillDropdowns(
            [{"name": k} for k in tagList.keys()], claudeTags, appSettings
        ) if claudeTags else [None] * len(tagList)

        description = ""
        if claudeData and firstClip and firstClip["name"] in claudeData:
            description = claudeData[firstClip["name"]].get("description", "")

        epochValue = "medieval" #default

    return html.Div(
        style={"width": "50%", "display": "flex", "flexDirection": "column",
               "gap": "15px", "justifyContent": "flex-start"},
        children=[
            html.Div([
                html.Label("Epoche", style={"fontWeight": "bold"}),
                dcc.Dropdown(
                    id="epoch-dropdown",
                    options=[
                        {"label": "⬜ Epochenlos", "value": None},
                        {"label": "🏰 Medieval", "value": "medieval"},
                        {"label": "🏛️ Rome", "value": "rome"},
                    ],
                    value=epochValue,
                    clearable=False,
                    style={"width": "50%"},
                )
            ], style={"paddingBottom": "15px", "marginBottom": "5px", "borderBottom": "2px solid #555"}),
            *[
                html.Div([
                    html.Label(list_name),
                    dcc.Dropdown(
                        id={"type": "dropdown", "name": list_name},
                        options=[{"label": x, "value": x} for x in values],
                        value=filled,
                        multi=True,
                        maxHeight=500,
                    )
                ])
                for (list_name, values), filled in zip(tagList.items(), filledValues)
            ],
            dcc.Textarea(
                id="tag-sentence",
                style={
                    "fontFamily": "monospace", "fontSize": "15px", "padding": "12px",
                    "height": "200px", "overflowY": "auto", "borderRadius": "8px",
                    "whiteSpace": "pre-wrap", "backgroundColor": "#c1cdcd", "border": "1px solid black"
                },
                value=description,
                spellCheck=False,
            )
        ]
    )

@app.callback(
    Output("content-panel", "children"),
    Output("currentClip-store", "data", allow_duplicate=True),
    Output({"type": "dropdown", "name": ALL}, "value"),
    Output("tag-sentence", "value"),
    Input("db-button", "n_clicks"),
    Input("skip-button", "n_clicks"),
    State("clips-store", "data"),
    State("currentClip-store", "data"),
    State({"type": "dropdown", "name": ALL}, "value"),
    State({"type": "dropdown", "name": ALL}, "id"),
    State("claude-descriptions-store", "data"),
    State("epoch-store", "data"),
    State("app-settings-store", "data"),
    State("page-store", "data"),
    State("edit-clip-id-store", "data"),
    State("tag-sentence", "value"),
    prevent_initial_call=True,
)
def buttonPressed(dbButton, skipButton, clips, lastClipIndex, values, dropdownIds,
                  claudeData, epoch, appSettings, page, editClipId, tagSentence):

    trigger = ctx.triggered_id

    if trigger == "db-button" and not dbButton:
        return no_update, no_update, [no_update for _ in values], no_update
    if trigger == "skip-button" and not skipButton:
        return no_update, no_update, [no_update for _ in values], no_update

    editMode = page == "page3"

    if editMode:
        if trigger == "db-button":

            updateClipInDB(editClipId, values, dropdownIds, appSettings, epoch, tagSentence)

        return no_update, no_update, [no_update for _ in values], no_update

    # ── Page2-Modus ────────────────────────────────────────────────────────
    if lastClipIndex == "Nothing to show" or not clips:
        return no_update, no_update, [no_update for _ in values], no_update

    if not any(x is not None for x in values) and trigger == "db-button":
        clip = clips[lastClipIndex]
        if not (claudeData and clip["name"] in claudeData):
            log("ABBRUCH: keine tags ausgewählt", color="red")
            return no_update, no_update, [no_update for _ in values], no_update
    if lastClipIndex is None:
        lastClipIndex = -1

    nextClipIndex = lastClipIndex + 1

    if trigger == "db-button":
        clip = clips[lastClipIndex]
        clipID = addToDB(values, clip, claudeData, appSettings, epoch)
        if clipID is not None:
            moveToMediaFolder(clip, clipID, appSettings)
        else:
            return no_update, no_update, [no_update for _ in values], no_update

    if nextClipIndex < len(clips):
        clip = clips[nextClipIndex]

        if claudeData and clip["name"] in claudeData:
            clipTags = claudeData[clip["name"]].get("tags", [])
            description = claudeData[clip["name"]].get("description", "")
            newValues = fillDropdowns(dropdownIds, clipTags, appSettings)
        else:
            description = ""
            newValues = clearDropDowns(values)

        return showClip(clip), nextClipIndex, newValues, description

    else:
        return html.Div(
            "Keine Clips mehr",
            style={
                "width": "100%", "height": "300px",
                "display": "flex", "alignItems": "center", "justifyContent": "center",
                "fontWeight": "bold", "fontSize": "26px",
                "border": "3px solid black", "backgroundColor": "#F08080",
                "boxSizing": "border-box",
            }
        ), "Nothing to show", clearDropDowns(values), ""


def showClip(clip):

    src = f"/media/{clip['name']}{clip['extension']}"
    style = {
        "maxWidth": "100%",
        "maxHeight": "100%",
    }

    if clip["type"] == "image":
        return html.Img(
            src=src,
            style=style
        )
    else:
        return html.Video(
            src=src,
            controls=True,
            style=style
        )

def fillDropdowns(dropdownIds, tags, appSettings):
    """Liest aus DB welcher Tag zu welcher Kategorie gehört und füllt Dropdowns"""

    conn = sqlite3.connect(appSettings["path"] + appSettings["db"])
    cursor = conn.cursor()
    placeholders = ",".join("?" * len(tags))
    cursor.execute(f"SELECT tag_name, category FROM Tags WHERE tag_name IN ({placeholders})", tags)
    rows = cursor.fetchall()
    conn.close()



    # category → liste von tags
    categoryMap = {}
    for tag_name, category in rows:
        if category not in categoryMap:
            categoryMap[category] = []
        categoryMap[category].append(tag_name)

    # für jedes Dropdown den passenden Wert setzen
    result = []
    for dropdownId in dropdownIds:
        category = dropdownId["name"]
        result.append(categoryMap.get(category, None))

    return result

def clearDropDowns(values):
    output = []
    for value in values:
        output.append(None)
    return output

def moveToMediaFolder(clip, clipID, appSettings):


    if appModule.rawMediaFolder is None:
        log("FEHLER: Kein Rohmaterialordner gefunden.", color="red")
        return False

    os.makedirs(appSettings["path"] + appSettings["fs"], exist_ok=True)

    filename = f"{clip['name']}{clip['extension']}"

    src = os.path.join(appModule.rawMediaFolder, filename)
    dst = os.path.join(appSettings["path"] + appSettings["fs"], f"{clipID}{clip['extension']}")

    if os.path.exists(dst):
        log("FEHLER: Datei existiert im Ziel bereits:", dst, color = "red")
        return False

    try:
        shutil.move(src, dst)
        log("Datei verschoben von: ", src)
        log("Zu: ", dst)
        log("-----------------------------------")
        return True
    except (FileNotFoundError, PermissionError) as e:
        log(f"FEHLER: Verschieben fehlgeschlagen: {e}", color="red")
        return False

@app.callback(
    Output("claude-descriptions-store", "data", allow_duplicate=True),
    Input("tag-sentence", "n_blur"),   # ← statt value
    State("tag-sentence", "value"),    # ← value als State
    State("claude-descriptions-store", "data"),
    State("currentClip-store", "data"),
    State("clips-store", "data"),
    prevent_initial_call=True,
)
def saveDescription(n_blur, value, claudeData, currentIndex, clips):
    if value is None or claudeData is None or currentIndex is None or not clips:
        return no_update

    clip = clips[currentIndex]
    if clip["name"] not in claudeData:
        return no_update

    log("Beschreibung aktualisiert")
    claudeData[clip["name"]]["description"] = value
    return claudeData

@app.callback(
    Output("epoch-store", "data"),
    Input("epoch-dropdown", "value"),
    prevent_initial_call=True,
)
def saveEpoch(value):
    return value