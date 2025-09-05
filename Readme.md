# Python Chat (Flask + Socket.IO)

A minimalist real-time chat app with a modern UI, built with Flask + Flask-SocketIO and vanilla JS.

## Features

- Realtime messaging (Socket.IO)
- Online users panel with avatars
- Automatic username assignment + rename with live avatar refresh
- Typing indicator
- Message timestamps + recent history for new joiners
- Dark / light theme toggle
- Small anti-spam throttle
- Docker-ready

## Tech

- Flask, Flask-SocketIO (eventlet)
- Vanilla JS, responsive CSS

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export SECRET_KEY="change-me"                        # Windows: set SECRET_KEY=change-me
python app.py
