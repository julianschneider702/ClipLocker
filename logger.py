from app import  app

from dash import Input, Output, html

log_buffer = []

@app.callback(
    Output("session-store", "data"),
    Input("session-store", "data"),
)
def clearTerminalOnLoad(data):
    log_buffer.clear()
    return True

@app.callback(
    Output("terminal", "children"),
    Input("log-interval", "n_intervals"),
)
def updateTerminal(n):
    return [
        html.Div(msg, style={"color": color})
        for msg, color in log_buffer
    ]

def log(*args, color=None):
    msg = " ".join(str(a) for a in args)
    log_buffer.append((msg, color or "#d4d4d4"))
    if len(log_buffer) > 100:
        log_buffer.pop(0)