#!/usr/bin/env python3
"""Digital remote for an Android TV / Google TV, driven over adb.

    python3 remote.py <TV_IP>             # serves the remote on http://<this computer>:8765
    python3 remote.py <TV_IP> --port 9000
    python3 remote.py emulator-5554       # an adb serial works too

Open the printed URL on your phone (same Wi-Fi). The URL carries a random token:
without it, nobody else on the network can send keys. Only needs Python 3 and adb.
"""
import argparse
import json
import os
import re
import secrets
import shlex
import socket
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))

# Only these key codes can be sent, so the page can't run anything else on the TV.
KEYS = {
    "DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT", "DPAD_CENTER",
    "BACK", "HOME", "MENU", "SETTINGS", "SEARCH", "GUIDE", "TV_INPUT", "CAPTIONS",
    "VOLUME_UP", "VOLUME_DOWN", "VOLUME_MUTE",
    "CHANNEL_UP", "CHANNEL_DOWN",
    "MEDIA_PLAY_PAUSE", "MEDIA_STOP", "MEDIA_NEXT", "MEDIA_PREVIOUS",
    "MEDIA_REWIND", "MEDIA_FAST_FORWARD",
    "POWER", "SLEEP", "WAKEUP", "ENTER", "DEL",
}
PACKAGE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+$")


def target_of(arg):
    # Same rule as install.sh: an IP gets :5555 added; an adb serial is used as is.
    if re.fullmatch(r"\d+\.\d+\.\d+\.\d+:\d+", arg):
        return arg
    if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", arg):
        return arg + ":5555"
    return arg


class TV:
    def __init__(self, serial):
        self.serial = serial

    def connect(self):
        if ":" in self.serial:
            subprocess.run(["adb", "connect", self.serial], capture_output=True, timeout=10)
        out = subprocess.run(["adb", "-s", self.serial, "get-state"],
                             capture_output=True, text=True, timeout=10)
        return (out.stdout + out.stderr).strip()

    def shell(self, command, timeout=10):
        out = subprocess.run(["adb", "-s", self.serial, "shell", command],
                             capture_output=True, text=True, timeout=timeout)
        if out.returncode != 0:
            raise RuntimeError((out.stderr or out.stdout).strip() or "adb failed")
        return out.stdout.replace("\r", "")

    def key(self, name, long_press=False):
        flag = "--longpress " if long_press else ""
        self.shell("input keyevent %sKEYCODE_%s" % (flag, name))

    def text(self, text):
        # input text reads %s as a space; everything else is quoted for the TV's shell.
        self.shell("input text " + shlex.quote(text.replace(" ", "%s")))

    def launch(self, package):
        self.shell("monkey -p %s -c android.intent.category.LEANBACK_LAUNCHER 1" % package)

    def apps(self):
        out = self.shell("cmd package query-activities --brief -a android.intent.action.MAIN"
                         " -c android.intent.category.LEANBACK_LAUNCHER")
        found = []
        for line in out.splitlines():
            line = line.strip()
            if "/" in line:
                package = line.split("/", 1)[0]
                if PACKAGE.match(package) and package not in found:
                    found.append(package)
        return sorted(found)


class Handler(BaseHTTPRequestHandler):
    tv = None
    token = None

    def log_message(self, fmt, *args):
        pass

    def reply(self, code, body, kind="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def authorized(self, query):
        given = self.headers.get("X-Token") or query.get("t", [""])[0]
        return secrets.compare_digest(given, self.token)

    def do_GET(self):
        url = urlparse(self.path)
        query = parse_qs(url.query)
        if not self.authorized(query):
            return self.reply(403, b"Missing or wrong token. Use the URL printed by remote.py.",
                              "text/plain; charset=utf-8")
        if url.path == "/":
            with open(os.path.join(HERE, "remote.html"), "rb") as f:
                return self.reply(200, f.read(), "text/html; charset=utf-8")
        if url.path == "/apps":
            try:
                return self.reply(200, {"apps": self.tv.apps()})
            except Exception as e:
                return self.reply(502, {"error": str(e)})
        self.reply(404, {"error": "not found"})

    def do_POST(self):
        url = urlparse(self.path)
        if not self.authorized(parse_qs(url.query)):
            return self.reply(403, {"error": "wrong token"})
        try:
            length = min(int(self.headers.get("Content-Length") or 0), 4096)
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return self.reply(400, {"error": "bad json"})
        try:
            if url.path == "/key":
                name = str(body.get("key", ""))
                if name not in KEYS:
                    return self.reply(400, {"error": "unknown key"})
                self.tv.key(name, bool(body.get("long")))
            elif url.path == "/text":
                text = str(body.get("text", ""))[:500]
                if text:
                    self.tv.text(text)
            elif url.path == "/launch":
                package = str(body.get("package", ""))
                if not PACKAGE.match(package):
                    return self.reply(400, {"error": "bad package name"})
                self.tv.launch(package)
            else:
                return self.reply(404, {"error": "not found"})
        except Exception as e:
            return self.reply(502, {"error": str(e)})
        self.reply(200, {"ok": True})


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def main():
    parser = argparse.ArgumentParser(description="Digital remote for an Android TV, over adb.")
    parser.add_argument("tv", help="TV IP (port 5555 added), IP:port, or an adb serial")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="0.0.0.0",
                        help="address to listen on (127.0.0.1 = this computer only)")
    parser.add_argument("--token", default=os.environ.get("REMOTE_TOKEN"),
                        help="fixed token instead of a random one (or set REMOTE_TOKEN)")
    args = parser.parse_args()

    try:
        subprocess.run(["adb", "version"], capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        sys.exit("adb is missing. Mac: brew install android-platform-tools · "
                 "Windows/Linux: https://developer.android.com/tools/releases/platform-tools")

    tv = TV(target_of(args.tv))
    state = tv.connect()
    if "unauthorized" in state:
        sys.exit('Your TV is asking "Allow debugging?". Press Allow, then run this again.')
    if state != "device":
        sys.exit("Can't reach %s (%s). Is the TV on, on this network, with debugging on?"
                 % (tv.serial, state or "no answer"))

    Handler.tv = tv
    Handler.token = args.token or secrets.token_urlsafe(12)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    shown = lan_ip() if args.host == "0.0.0.0" else args.host
    print("Remote for %s is ready. Open this on your phone (same Wi-Fi):" % tv.serial)
    print("  http://%s:%d/?t=%s" % (shown, args.port, Handler.token))
    print("Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
