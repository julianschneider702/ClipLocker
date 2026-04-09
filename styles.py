red = "#F08080"
lightRed = "#D18180"
green = "#90EE90"
lightGreen = "#88C783"
grey = "#444"
blue = "#5A8BED"


titleBtnStyle = {
    "padding": "8px 20px",
    "cursor": "pointer",
    "backgroundColor": "#4a4a4a",
    "color": "white",
    "border": "1px solid #666",
    "borderRadius": "6px",
    "fontWeight": "bold",
    "fontSize": "20px",
}
cardBtnStyle = {
    "padding": "6px 14px",
    "cursor": "pointer",
    "backgroundColor": "#2a2a2a",
    "color": "#d4d4d4",
    "border": "1px solid #444",
    "borderRadius": "6px",
    "fontSize": "12px",
}
analyseBtnStyle = {**cardBtnStyle,
                   "fontSize": "17px",
                   "alignSelf": "flex-start",
                   "cursor": "not-allowed"
                   }
basePagingBtnStyle = {
        "padding": "8px 14px",
        "border": "1px solid #666",
        "borderRadius": "8px",
        "backgroundColor": "#2f2f2f",
        "color": "white",
        "cursor": "pointer",
    }
disabledPagingBtnStyle = {
        **basePagingBtnStyle,
        "opacity": "0.45",
        "cursor": "default",
}
selectClipBtnStyle = {
                "position": "absolute",
                "top": "3px",
                "right": "3px",
                "height": "32px",
                "width": "32px",
                "borderRadius": "6px",
                "border": "1px solid #666",
                "backgroundColor": "#2f2f2f",
                "color": "white",
                "fontWeight": "bold",
                "cursor": "pointer",
                "zIndex": "2",
            }

headerStyle = {
    "fontFamily": "'Rajdhani', sans-serif",
    "fontSize": "120px",
    "fontWeight": "700",
    "letterSpacing": "6px",
    "color": "#d4d4d4",
    "margin": "0",
}
headerStyleSmall = {
    "fontFamily": "'Rajdhani', sans-serif",
    "fontSize": "35px",
    "fontWeight": "700",
    "letterSpacing": "3px",
    "color": "#d4d4d4",
    "margin": "0",
    "textAlign": "center",
    "width": "100%",
}

terminalStyle = {
                "color": "#d4d4d4",
                "fontFamily": "monospace",
                "fontSize": "13px",
                "padding": "12px",
                "height": "300px",
                "overflowY": "auto",
                "borderRadius": "8px",
                "whiteSpace": "pre-wrap",
                "flexShrink": "0",
                "backgroundColor": "#1e1e1e",
                "display": "none",
            }
baseStyleInputPath = {"flex": "1",
                            "height": "30px",
                            "padding": "4px",
                          }
timestampStyle = {
    "padding": "6px 14px",
    "backgroundColor": "#2a2a2a",
    "color": "#d4d4d4",
    "border": "1px solid"+grey,
    "borderRadius": "6px",
    "fontSize": "14px",
    "width": "120px",
    "minWidth": "80px",
    "outline": "none",
}
cardStyleNormal = {"borderRadius": "8px", "border": "1px solid #444",
                       "backgroundColor": "#2a2a2a", "overflow": "hidden", "height": "390px"}
cardStyleHidden = {**cardStyleNormal,
                   "opacity": "0.3"}

baseSentenceStyle = {
                    "display": "block",
                    "border": "2px solid black",
                    "padding": "10px",
                    "marginTop": "10px",
                    "width": "100%",
                    }

clipStyle = {
    "width": "100%",
    "height": "100%",
    "objectFit": "cover",
    "display": "block",
}
clipFrameStyle = {
    "position": "relative",
    "width": "100%",
    "aspectRatio": "300 / 170",
    "overflow": "hidden",
    "borderRadius": "8px",
    "border": "3px solid black",
    "backgroundColor": "#111",
}
clipPlusBtnContainerStyle = {
    "width": "100%",
    "maxWidth": "300px",
}
miniClipStyle = {
                    "width": "200px",
                    "height": "120px",
                    "objectFit": "cover",
                    "border": "1px solid black",
                    "borderRadius": "8px",
                }
miniClipErrorStyle = {
                    "width": "140px",
                    "height": "90px",
                    "display": "flex",
                    "alignItems": "center",
                    "justifyContent": "center",
                    "border": "1px solid #666",
                    "borderRadius": "8px",
                    "fontSize": "13px",
                    "textAlign": "center",
                    "padding": "6px",
                }
miniClipFrameStyle = {
    "position": "relative",   # ← damit absolute Buttons korrekt verankert sind
    "width": "200px",
    "height": "150px",
    "flexShrink": "0",
    "borderRadius": "8px",
    "overflow": "hidden",
}

activeTabStyle = {
    "padding": "10px 18px",
    "border": "1px solid #666",
    "borderBottom": "none",
    "borderTopLeftRadius": "10px",
    "borderTopRightRadius": "10px",
    "backgroundColor": "#ffffff",
    "color": "black",
    "fontWeight": "bold",
    "cursor": "pointer",
    "marginRight": "4px",
    "position": "relative",
    "top": "1px",
}
inactiveTabStyle = {
    "padding": "10px 18px",
    "border": "1px solid #666",
    "borderBottom": "none",
    "borderTopLeftRadius": "10px",
    "borderTopRightRadius": "10px",
    "backgroundColor": "#d9d9d9",
    "color": "black",
    "fontWeight": "bold",
    "cursor": "pointer",
    "marginRight": "4px",
}

paginationContainerStyle = {"display": "none",
                            "justifyContent": "center",
                            "alignItems": "center",
                            "gap": "14px",
                            }


tagEditOverlayStyle = {
    "position": "fixed",
    "top": "0",
    "left": "0",
    "width": "100vw",
    "height": "100vh",
    "backgroundColor": "rgba(0, 0, 0, 0.35)",
    "display": "flex",
    "justifyContent": "center",
    "alignItems": "center",
    "zIndex": "9999",
}
tagEditModalStyle = {
    "width": "1000px",
    "maxWidth": "90vw",
    "minHeight": "500px",
    "backgroundColor": "white",
    "borderRadius": "16px",
    "padding": "24px",
    "boxShadow": "0 10px 30px rgba(0,0,0,0.25)",
}
pageContentBlurredStyle = {
    "filter": "blur(6px)",
    "pointerEvents": "none",
    "userSelect": "none",
}
pageContentNormalStyle = {}