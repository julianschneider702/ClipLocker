import settings as settings_manager
from tagVideo import *
from createMedia import renderPage3
from styles import *

app.clientside_callback(
    """
    function(children) {
        var terminal = document.getElementById('terminal');
        if (terminal) {
            terminal.scrollTop = terminal.scrollHeight;
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output("terminal", "style", allow_duplicate=True),
    Input("terminal", "children"),
    prevent_initial_call=True
)

app.clientside_callback(
    """
    function(n) {
        var panel = document.getElementById('settings-panel');
        if (panel.style.right === '0px') {
            panel.style.right = '-400px';
        } else {
            panel.style.right = '0px';
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output("settings-panel", "style", allow_duplicate=True),
    Input("settings-btn", "n_clicks"),
    prevent_initial_call=True,
)

app.clientside_callback(
    """
    function(n) {
        var panel = document.getElementById('settings-panel');
        panel.style.right = '-400px';
        return window.dash_clientside.no_update;
    }
    """,
    Output("settings-panel", "style"),
    Input("save-settings-btn", "n_clicks"),
    prevent_initial_call=True,
)

app.clientside_callback(
    """
    function(page) {
        const videos = document.querySelectorAll('video');
        videos.forEach(v => {
            v.pause();
            v.src = '';
            v.load();
        });
        return window.dash_clientside.no_update;
    }
    """,
    Output("search-results-panel", "data-dummy"),
    Input("search-page-store", "data"),
    prevent_initial_call=True,
)

def renderPage1():
    return html.Div(
            style={
                "display": "flex",
                "flexDirection": "column",
                "alignItems": "center",
                "justifyContent": "center",
                "height": "100%",
                "gap": "20px",
            },
            children=[
                html.H1(
                    "ClipLocker",
                    style=headerStyle
                ),
                html.Div(
                    style={"display": "flex", "gap": "20px", "marginTop": "20px"},
                    children=[
                        html.Button("Neue Clips taggen",   id="btn-page2", style=titleBtnStyle),
                        html.Button("Video-Clip Ordner erstellen", id="btn-page3", style=titleBtnStyle),
                    ]
                )
            ]
        )

def serveLayout():
    current_settings = settings_manager.load_settings()

    return html.Div(
        style={
            "display": "flex",
            "flexDirection": "column",
            "height": "100vh",
            # "backgroundColor": "#1e1e1e",
            "margin": "0",
            "padding": "0",
        },
        children=[

            html.Link(
                rel="stylesheet",
                href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;700&display=swap"
            ),

            #global
            dcc.Interval(id="log-interval", interval=1000),
            dcc.Store(id="app-settings-store", data=current_settings, storage_type="memory"),
            dcc.Store(id="page-store", data="page1", storage_type="memory"),
            dcc.Store(id="epoch-store", data="medieval", storage_type="memory"),
            dcc.Store(id="session-store", storage_type="session"),

            #Tag Clips
            dcc.Store(id="clips-store", data=[], storage_type="memory"),
            dcc.Store(id="pathInput-store", data=None, storage_type="memory"),
            dcc.Store(id="currentClip-store", data=None, storage_type="memory"),
            dcc.Store(id="clip-settings-store", data={}, storage_type="memory"),
            dcc.Store(id="claude-descriptions-store", data=None, storage_type="memory"),

            #Ordner erstellen
            dcc.Store(id="sentence-store", data=[], storage_type="memory"),
            dcc.Store(id="clips-per-sentence-store",data=[], storage_type="memory"),
            dcc.Store(id="selectedClips-store",data=[], storage_type="memory"),
            dcc.Store(id="selectedSentence-store", data=None, storage_type="memory"),
            dcc.Store(id="documentName-store",data=None, storage_type="memory"),
            dcc.Store(id="active-right-tab", data="suggestions", storage_type="memory"),
            dcc.Store(id="search-results-store", data=[], storage_type="memory"),
            dcc.Store(id="search-mode-store", data="and", storage_type="memory"),
            dcc.Store(id="search-page-store", data=0, storage_type="memory"),
            dcc.Store(id="placeholder-active-store", data=[], storage_type="memory"),
            dcc.Store(id="clip-usage-store", data={}, storage_type="memory"),
            dcc.Store(id="edit-tags-store", data=None, storage_type="memory"),
            dcc.Store(id="edit-tags-draft-store", data=None, storage_type="memory"),
            dcc.Store(id="edit-clip-id-store", data=None, storage_type="memory"),





            html.Div(
                style={"display": "flex", "justifyContent": "flex-end", "padding": "10px"},
                children=[
                    html.Button(
                        "⚙",
                        id="settings-btn",
                        style=titleBtnStyle,
                    ),
                ]
            ),
            html.Div(
                id="page-content",
                style={"display": "flex", "flexDirection": "column", "flex": "1", "overflow": "hidden",
                       "minHeight": "0", }
            ),

            html.Div(
                id="terminal",
                style=terminalStyle
            ),
            html.Div(
                id="settings-panel",
                style={
                    "position": "fixed",
                    "top": "0",
                    "right": "-400px",
                    "width": "400px",
                    "height": "100vh",
                    "backgroundColor": "#2a2a2a",
                    "borderLeft": "1px solid #444",
                    "zIndex": "1000",
                    "transition": "right 0.3s ease",
                    "padding": "20px",
                    "boxSizing": "border-box",
                },
                children=[
                    #html.H2("Paths", style={"color": "#d4d4d4"}),
                    html.Label("Path:", style={"color": "#d4d4d4"}),
                    dcc.Input(
                        id={"type": "settings-input", "key": "path"},
                        type="text",
                        style={**baseStyleInputPath, "marginBottom": "10px"},
                        value=current_settings.get("path", ""),
                    ),
                    html.Label("Datenbank:", style={"color": "#d4d4d4"}),
                    dcc.Input(
                        id={"type": "settings-input", "key": "db"},
                        type="text",
                        style={**baseStyleInputPath, "marginBottom": "10px"},
                        value=current_settings.get("db", ""),
                    ),
                    html.Label("Fotosammlung:", style={"color": "#d4d4d4"}),
                    dcc.Input(
                        id={"type": "settings-input", "key": "fs"},
                        type="text",
                        style={**baseStyleInputPath, "marginBottom": "10px"},
                        value=current_settings.get("fs", ""),
                    ),
                    html.Label("Raw-Folder:", style={"color": "#d4d4d4"}),
                    dcc.Input(
                        id={"type": "settings-input", "key": "raw"},
                        type="text",
                        style={**baseStyleInputPath, "marginBottom": "10px"},
                        value=current_settings.get("raw", ""),
                    ),
                    html.Label("Db-Backups:", style={"color": "#d4d4d4"}),
                    dcc.Input(
                        id={"type": "settings-input", "key": "backup"},
                        type="text",
                        style={**baseStyleInputPath, "marginBottom": "10px"},
                        value=current_settings.get("backup", ""),
                    ),
                    html.Button(
                        "Einstellungen speichern",
                        id="save-settings-btn",
                        style={**titleBtnStyle, "marginTop": "30px"},
                    ),
                ]
            )
        ]
    )


app.layout = serveLayout


@app.callback(
    Output("app-settings-store", "data"),
    Input("save-settings-btn", "n_clicks"),
    State({"type": "settings-input", "key": ALL}, "value"),
    State({"type": "settings-input", "key": ALL}, "id"),
    prevent_initial_call=True,
)
def save_settings_callback(n, values, ids):
    new_settings = {item["key"]: value for item, value in zip(ids, values)}
    saved_settings = settings_manager.save_settings(new_settings)
    return saved_settings

@app.callback(
    Output({"type": "settings-input", "key": ALL}, "value"),
    Input("app-settings-store", "data"),
    State({"type": "settings-input", "key": ALL}, "id"),
)
def sync_settings_inputs(appSettings, ids):
    return [appSettings.get(item["key"], "") for item in ids]


@app.callback(
    Output("page-store", "data"),
    Input("btn-page2", "n_clicks"),
    Input("btn-page3", "n_clicks"),
    prevent_initial_call=True
)
def switchPage(p2, p3):
    trigger = ctx.triggered_id
    if trigger == "btn-page2": return "page2_1"
    if trigger == "btn-page3": return "page3"

    return "page1"

@app.callback(
    Output("page-content", "children"),
    Output("terminal", "style"),
    Output("settings-btn", "style"),
    Input("page-store", "data"),
    State("claude-descriptions-store", "data"),
    State("clips-store", "data"),
    State("app-settings-store", "data"),
)
def renderPage(page, claudeData, clips, appSettings):
    if page == "page2_1":
        return renderPage2_1(appSettings), {**terminalStyle, "display": "block"} , {**titleBtnStyle, "display": "none"}
    if page == "page2_2":
        return renderPage2_2(claudeData, clips, appSettings), {**terminalStyle, "display": "block"}, {**titleBtnStyle, "display": "none"}
    if page == "page3":
        return renderPage3(appSettings), {**terminalStyle, "display": "none"}, {**titleBtnStyle, "display": "none"}
    return renderPage1(), {"display": "none"}, {**titleBtnStyle, "display": "block"}

if __name__ == "__main__":
    app.run(debug=True, dev_tools_hot_reload=False)