#!/usr/bin/env python3
"""Digital remote for an Android TV / Google TV / Android "Smart TV", driven over adb.

    python3 remote.py                     # finds the TV on your network by itself
    python3 remote.py <TV_IP>             # or name it (port 5555 is added)
    python3 remote.py <TV_IP> --port 9000
    python3 remote.py <TV_IP> --probe     # prints what the TV is, to adapt the remote
    python3 remote.py emulator-5554       # an adb serial works too

Open the printed URL on your phone (same Wi-Fi). The URL carries a random token:
without it, nobody else on the network can send keys. Only needs Python 3: if adb is
missing, Google's platform-tools are downloaded once into ~/.tv-remote.
"""
import argparse
import io
import json
import os
import platform
import re
import secrets
import shlex
import shutil
import socket
import subprocess
import sys
import threading
import time
import unicodedata
import zipfile
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

HERE = os.path.dirname(os.path.abspath(__file__))

# Only these key codes can be sent, so the page can't run anything else on the TV.
KEYS = {
    "DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT", "DPAD_CENTER",
    "BACK", "HOME", "MENU", "SETTINGS", "SEARCH", "GUIDE", "INFO", "CAPTIONS",
    "TV_INPUT", "TV_INPUT_HDMI_1", "TV_INPUT_HDMI_2", "TV_INPUT_HDMI_3", "TV_INPUT_COMPOSITE_1", "TV",
    "VOLUME_UP", "VOLUME_DOWN", "VOLUME_MUTE",
    "CHANNEL_UP", "CHANNEL_DOWN", "LAST_CHANNEL",
    "PROG_RED", "PROG_GREEN", "PROG_YELLOW", "PROG_BLUE",
    "MEDIA_PLAY_PAUSE", "MEDIA_STOP", "MEDIA_NEXT", "MEDIA_PREVIOUS",
    "MEDIA_REWIND", "MEDIA_FAST_FORWARD",
    "POWER", "SLEEP", "WAKEUP", "ENTER", "DEL",
} | {str(n) for n in range(10)}
PACKAGE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+$")

# Friendly names for the app list; anything else shows its package name.
APP_NAMES = {
    "com.google.android.youtube.tv": "YouTube",
    "com.google.android.youtube.tvkids": "YouTube Kids",
    "com.google.android.youtube.tvmusic": "YouTube Music",
    "com.netflix.ninja": "Netflix",
    "com.netflix.mediaclient": "Netflix",
    "com.amazon.amazonvideo.livingroom": "Prime Video",
    "com.disney.disneyplus": "Disney+",
    "com.spotify.tv.android": "Spotify",
    "net.mbc.shahid.androidtv": "Shahid",
    "com.canal.android.canal": "myCANAL",
    "com.mxtech.videoplayer.television": "MX Player",
    "org.videolan.vlc": "VLC",
    "com.android.vending": "Play Store",
    "com.android.tv.settings": "Paramètres",
    "com.android.settings": "Paramètres",
    "com.google.android.tvlauncher": "Accueil Android TV",
    "com.ansub.tvhome": "TV Detox",
}


def target_of(arg):
    # Same rule as install.sh: an IP gets :5555 added; an adb serial is used as is.
    if re.fullmatch(r"\d+\.\d+\.\d+\.\d+:\d+", arg):
        return arg
    if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", arg):
        return arg + ":5555"
    return arg


ADB = "adb"
TOOLS = os.path.join(os.path.expanduser("~"), ".tv-remote")


def find_adb():
    """adb from PATH, else a copy from an earlier run, else Google's platform-tools, downloaded once."""
    exe = "adb.exe" if os.name == "nt" else "adb"
    local = os.path.join(TOOLS, "platform-tools", exe)
    for candidate in (shutil.which("adb"), local):
        if candidate and os.path.isfile(candidate):
            return candidate
    system = {"Windows": "windows", "Darwin": "darwin", "Linux": "linux"}.get(platform.system())
    if not system:
        sys.exit("adb est introuvable : https://developer.android.com/tools/releases/platform-tools")
    url = "https://dl.google.com/android/repository/platform-tools-latest-%s.zip" % system
    print("adb introuvable, téléchargement des platform-tools de Google (environ 10 Mo)…")
    try:
        with urlopen(url, timeout=60) as response:
            zipfile.ZipFile(io.BytesIO(response.read())).extractall(TOOLS)
    except Exception as e:
        sys.exit("Impossible de télécharger adb (%s). Récupère-le sur "
                 "https://developer.android.com/tools/releases/platform-tools" % e)
    if os.name != "nt":
        os.chmod(local, 0o755)
    return local


def adb(*args, timeout=10):
    return subprocess.run([ADB, *args], capture_output=True, text=True, timeout=timeout)


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def find_tv():
    """A device adb already knows (USB, earlier connect), else a scan of the /24 for port 5555."""
    devices = [line.split()[0] for line in adb("devices").stdout.splitlines()[1:]
               if line.strip().endswith("device")]
    if len(devices) == 1:
        return devices[0]
    if len(devices) > 1:
        sys.exit("Plusieurs appareils sont connectés à adb, choisis-en un : " + ", ".join(devices))

    me = lan_ip()
    if me.startswith("127."):
        sys.exit("Pas de réseau trouvé. Donne l'IP de la TV : python3 remote.py <IP_TV>")
    prefix = me.rsplit(".", 1)[0]
    print("Recherche de la TV sur %s.0/24 (port 5555)…" % prefix)

    def open_5555(host):
        try:
            with socket.create_connection((host, 5555), timeout=0.5):
                return host
        except OSError:
            return None

    with ThreadPoolExecutor(64) as pool:
        hosts = [h for h in pool.map(open_5555, ("%s.%d" % (prefix, n) for n in range(1, 255)))
                 if h and h != me]
    if len(hosts) == 1:
        return hosts[0] + ":5555"
    if hosts:
        sys.exit("Plusieurs appareils répondent sur le port 5555, choisis-en un : " + ", ".join(hosts))
    sys.exit("Aucune TV trouvée : son accès adb (port 5555) est fermé ou la TV n'est pas sur ce réseau. "
             "Si tu connais son IP (réglages réseau de la TV) : python3 remote.py <IP_TV>")


def ascii_text(text):
    # input text only types ASCII: "é" becomes "e", anything else unknown is dropped.
    flat = unicodedata.normalize("NFKD", text)
    return "".join(c for c in flat if 32 <= ord(c) < 127)


class TV:
    def __init__(self, serial):
        self.serial = serial
        self.shell_proc = None
        self.lock = threading.Lock()
        self.state = ("unknown", 0.0)

    def connect(self):
        if ":" in self.serial:
            adb("connect", self.serial)
        out = adb("-s", self.serial, "get-state")
        return (out.stdout + out.stderr).strip()

    def online(self):
        # Checked at most every 3 s; reconnects by itself after the TV restarts or wakes.
        state, at = self.state
        if time.time() - at > 3:
            state = self.connect()
            if state != "device":
                self._close_shell()
            self.state = (state, time.time())
        return state

    def shell(self, command, timeout=10):
        out = adb("-s", self.serial, "shell", command, timeout=timeout)
        if out.returncode != 0:
            raise RuntimeError((out.stderr or out.stdout).strip() or "adb failed")
        return out.stdout.replace("\r", "")

    # Keys go through one long-lived adb shell, so each press skips adb's start-up time.
    def key(self, name, long_press=False):
        self._run_in_shell("input keyevent %sKEYCODE_%s" % ("--longpress " if long_press else "", name))

    def _run_in_shell(self, command):
        with self.lock:
            for _ in range(2):
                if self.shell_proc is None or self.shell_proc.poll() is not None:
                    self.shell_proc = subprocess.Popen(
                        [ADB, "-s", self.serial, "shell"], stdin=subprocess.PIPE,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True)
                try:
                    self.shell_proc.stdin.write(command + "\n")
                    self.shell_proc.stdin.flush()
                    return
                except OSError:
                    self.shell_proc = None

    def _close_shell(self):
        with self.lock:
            if self.shell_proc and self.shell_proc.poll() is None:
                self.shell_proc.kill()
            self.shell_proc = None

    def text(self, text):
        # input text reads %s as a space; everything else is quoted for the TV's shell.
        text = ascii_text(text)
        if text:
            self.shell("input text " + shlex.quote(text.replace(" ", "%s")))

    def launch(self, package):
        self.shell("monkey -p %s -c android.intent.category.LEANBACK_LAUNCHER 1" % package)

    def apps(self):
        # Android TV apps first; plain Android "Smart TVs" often only have phone-style launchers.
        found = []
        for category in ("LEANBACK_LAUNCHER", "LAUNCHER"):
            out = self.shell("cmd package query-activities --brief -a android.intent.action.MAIN"
                             " -c android.intent.category." + category)
            for line in out.splitlines():
                package = line.strip().split("/", 1)[0]
                if "/" in line and PACKAGE.match(package) and package not in found:
                    found.append(package)
        apps = [{"package": p, "name": APP_NAMES.get(p, p)} for p in found]
        return sorted(apps, key=lambda a: (a["name"] == a["package"], a["name"].lower()))

    def probe(self):
        props = {}
        for prop in ("ro.product.brand", "ro.product.manufacturer", "ro.product.model",
                     "ro.product.device", "ro.board.platform", "ro.build.version.release",
                     "ro.build.version.sdk", "ro.build.characteristics"):
            props[prop] = self.shell("getprop " + prop).strip()
        home = self.shell("cmd package resolve-activity --brief -a android.intent.action.MAIN"
                          " -c android.intent.category.HOME").strip().splitlines()
        props["home screen"] = home[-1] if home else "?"
        props["android tv"] = "yes" if "android.software.leanback" in self.shell(
            "pm list features") else "no (plain Android, a phone-style system)"
        inputs = re.findall(r"(?:id|inputId)=(\S*HDMI\S*)", self.shell("dumpsys tv_input"), re.I)
        props["hdmi inputs"] = ", ".join(sorted(set(i.rstrip(",}") for i in inputs))) or "none found"
        return props


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
        if url.path == "/status":
            return self.reply(200, {"state": self.tv.online()})
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
                self.tv.text(str(body.get("text", ""))[:500])
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


def main():
    parser = argparse.ArgumentParser(description="Digital remote for an Android TV, over adb.")
    parser.add_argument("tv", nargs="?",
                        help="TV IP (port 5555 added), IP:port, or an adb serial; found if left out")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="0.0.0.0",
                        help="address to listen on (127.0.0.1 = this computer only)")
    parser.add_argument("--token", default=os.environ.get("REMOTE_TOKEN"),
                        help="fixed token instead of a random one (or set REMOTE_TOKEN)")
    parser.add_argument("--probe", action="store_true",
                        help="print what the TV is (model, Android, inputs) and exit")
    args = parser.parse_args()

    global ADB
    ADB = find_adb()

    tv = TV(target_of(args.tv) if args.tv else find_tv())
    state = tv.connect()
    if "unauthorized" in state:
        sys.exit('La TV demande « Autoriser le débogage ? ». Choisis Autoriser, puis relance.')
    if state != "device":
        sys.exit("Impossible de joindre %s (%s). La TV est-elle allumée, sur ce réseau, avec le débogage actif ?"
                 % (tv.serial, state or "no answer"))

    if args.probe:
        for name, value in tv.probe().items():
            print("%-26s %s" % (name, value))
        return

    Handler.tv = tv
    Handler.token = args.token or secrets.token_urlsafe(12)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    shown = lan_ip() if args.host == "0.0.0.0" else args.host
    print("Télécommande prête pour %s. Ouvre cette adresse sur ton téléphone (même Wi-Fi) :" % tv.serial)
    print("  http://%s:%d/?t=%s" % (shown, args.port, Handler.token))
    print("Ctrl+C pour arrêter.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
