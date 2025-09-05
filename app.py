import os
import random
import time
from collections import deque, defaultdict
from datetime import datetime, timezone

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit

# --- App setup ---
app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-me-in-prod")
socketio = SocketIO(app, cors_allowed_origins="*")

# --- In-memory state (for demo; use Redis/DB in production) ---
users = {}  # sid -> {username, avatar, gender}
MAX_HISTORY = 150
message_history = deque(maxlen=MAX_HISTORY)
last_msg_time = defaultdict(lambda: 0.0)
MIN_SECONDS_BETWEEN_MSGS = 0.25

# --- Helpers ---
def _now_iso():
    return datetime.now(timezone.utc).isoformat()

def _build_avatar(username: str, gender: str | None = None) -> str:
    """Build avatar URL based on gender & username."""
    if not gender:
        gender = random.choice(["boy", "girl"])
    return f"https://avatar.iran.liara.run/public/{gender}?username={username}"

def _get_user(sid):
    return users.get(sid)

def _online_users_payload():
    return [{"username": u["username"], "avatar": u["avatar"]} for u in users.values()]

# --- Socket events ---
@socketio.on("connect")
def on_connect():
    username = f"User_{random.randint(1000, 9999)}"
    gender = random.choice(["boy", "girl"])
    avatar_url = _build_avatar(username, gender)

    users[request.sid] = {"username": username, "avatar": avatar_url, "gender": gender}

    emit("set_username", {"username": username})
    emit("message_history", {"messages": list(message_history)})

    emit("user_joined", {"username": username, "avatar": avatar_url}, broadcast=True)
    emit("online_users_list", {"users": _online_users_payload()}, broadcast=True)

    app.logger.info(f"{username} connected [{request.sid}]")

@socketio.on("disconnect")
def on_disconnect():
    user = users.pop(request.sid, None)
    if not user:
        return
    emit("user_left", {"username": user["username"]}, broadcast=True)
    emit("online_users_list", {"users": _online_users_payload()}, broadcast=True)
    app.logger.info(f"{user['username']} disconnected [{request.sid}]")

@socketio.on("send_message")
def on_send_message(data):
    now = time.time()
    if now - last_msg_time[request.sid] < MIN_SECONDS_BETWEEN_MSGS:
        return  # simple spam protection
    last_msg_time[request.sid] = now

    user = _get_user(request.sid)
    if not user:
        return

    msg_text = (data.get("message") or "").strip()
    if not msg_text:
        return

    message_data = {
        "username": user["username"],
        "avatar": user["avatar"],
        "message": msg_text,
        "timestamp": _now_iso(),
    }
    message_history.append(message_data)
    emit("new_message", message_data, broadcast=True)

@socketio.on("update_username")
def on_update_username(data):
    user = _get_user(request.sid)
    if not user:
        return
    old_username = user["username"]
    new_username = (data.get("username") or "").strip()
    if not new_username or new_username == old_username:
        return

    # Preserve gender
    user["username"] = new_username
    user["avatar"] = _build_avatar(new_username, user.get("gender"))

    emit(
        "username_updated",
        {
            "old_username": old_username,
            "new_username": new_username,
            "avatar": user["avatar"],
        },
        broadcast=True,
    )
    emit("online_users_list", {"users": _online_users_payload()}, broadcast=True)

    app.logger.info(f"Username changed {old_username} -> {new_username}")

@socketio.on("update_avatar_gender")
def on_update_avatar_gender(data):
    user = _get_user(request.sid)
    if not user:
        return
    gender = data.get("gender")
    if gender not in ("boy", "girl"):
        return

    user["gender"] = gender
    user["avatar"] = _build_avatar(user["username"], gender)

    emit(
        "avatar_updated",
        {"username": user["username"], "avatar": user["avatar"]},
        broadcast=True,
    )
    emit("online_users_list", {"users": _online_users_payload()}, broadcast=True)

    app.logger.info(f"{user['username']} updated avatar gender -> {gender}")

@socketio.on("typing")
def on_typing(data):
    user = _get_user(request.sid)
    if not user:
        return
    emit(
        "user_typing",
        {"username": user["username"], "isTyping": bool(data.get("isTyping"))},
        broadcast=True,
        include_self=False,
    )
@socketio.on("send_private_message")
def on_private_message(data):
    sender = users.get(request.sid)
    if not sender:
        return

    target_username = data.get("to")
    msg_text = (data.get("message") or "").strip()
    if not target_username or not msg_text:
        return

    # Find target user by username
    target_sid = None
    for sid, u in users.items():
        if u["username"] == target_username:
            target_sid = sid
            break

    if not target_sid:
        return  # target not online

    message_data = {
        "from": sender["username"],
        "to": target_username,
        "avatar": sender["avatar"],
        "message": msg_text,
        "timestamp": _now_iso(),
    }

    # Send to target
    emit("private_message", message_data, room=target_sid)
    # Send to self (so sender sees it in their DM window)
    emit("private_message", message_data, room=request.sid)

# --- Routes ---
@app.route("/")
def index():
    return render_template("index.html")

# --- Entrypoint ---
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
