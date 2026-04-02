# ============================================================
#  Project: Roblox Version Downloader
#  File: RobloxVersionDownloader.py
#  Author: HoangLong
#
#  Description:
#  A complete tool for downloading and installing Roblox Player from the official CDN — supports version selection, smart caching, and an intuitive interface.
#
#  License:
#  This file is part of a project licensed under the MIT License.
#  Copyright (c) 2026 HoangLong
# ============================================================

import os, sys, json, time, hashlib, zipfile
import threading, subprocess
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
import requests

try:
    import pygame
    PYGAME_OK = True
except ImportError:
    PYGAME_OK = False

try:
    import winreg
    WINREG_OK = True
except ImportError:
    WINREG_OK = False

# =============================================================================
#  CONSTANTS
# =============================================================================
APP_VERSION   = "1.1.0"
CDN_BASE      = "https://setup.rbxcdn.com"
CDN_FALLBACKS = [
    "https://setup-ak.rbxcdn.com",
    "https://setup-cf.rbxcdn.com",
    "https://roblox-setup.cachefly.net",
    "https://s3.amazonaws.com/setup.roblox.com",
]
VERSION_API   = "https://clientsettingscdn.roblox.com/v2/client-version/WindowsPlayer"
HISTORY_FILE  = Path(__file__).parent / "download_history.json"
SOUND_FILE    = Path(__file__).parent / "sound" / "music.mp3"
CHUNK         = 131072   # 128 KB
MAX_HISTORY   = 20
CONNECT_TO    = 12
READ_TO       = 60

APP_SETTINGS_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<Settings>
    <ContentFolder>content</ContentFolder>
    <BaseUrl>http://www.roblox.com</BaseUrl>
</Settings>
"""

PACKAGE_MAP: dict = {
    "RobloxApp.zip":                     "",
    "redist.zip":                        "",
    "shaders.zip":                       "shaders",
    "ssl.zip":                           "ssl",
    "WebView2.zip":                      "",
    "WebView2RuntimeInstaller.zip":      "__webview2_installer__",  # handled separately
    "content-avatar.zip":                "content/avatar",
    "content-configs.zip":               "content/configs",
    "content-fonts.zip":                 "content/fonts",
    "content-sky.zip":                   "content/sky",
    "content-sounds.zip":                "content/sounds",
    "content-textures2.zip":             "content/textures",
    "content-models.zip":                "content/models",
    "content-platform-fonts.zip":        "PlatformContent/pc/fonts",
    "content-platform-dictionaries.zip": "PlatformContent/pc/shared_compression_dictionaries",
    "content-terrain.zip":               "PlatformContent/pc/terrain",
    "content-textures3.zip":             "PlatformContent/pc/textures",
    "extracontent-luapackages.zip":      "ExtraContent/LuaPackages",
    "extracontent-translations.zip":     "ExtraContent/translations",
    "extracontent-models.zip":           "ExtraContent/models",
    "extracontent-textures.zip":         "ExtraContent/textures",
    "extracontent-places.zip":           "ExtraContent/places",
}

C = {
    "bg":       "#0d0d1a",
    "panel":    "#13132b",
    "card":     "#1a1a35",
    "accent":   "#e8314a",
    "accent2":  "#5e3ec2",
    "fg":       "#e8e8f0",
    "muted":    "#7070a0",
    "success":  "#3ee88a",
    "warning":  "#f5c842",
    "error":    "#ff5566",
    "border":   "#2a2a50",
    "input_bg": "#0a0a18",
}

FONT_MONO = ("Consolas", 10)
FONT_UI   = ("Segoe UI", 10)


# =============================================================================
#  UTILITIES
# =============================================================================
def fmt_bytes(n: int) -> str:
    if n < 1024:          return f"{n} B"
    if n < 1_048_576:     return f"{n/1024:.1f} KB"
    if n < 1_073_741_824: return f"{n/1_048_576:.2f} MB"
    return f"{n/1_073_741_824:.2f} GB"

def fmt_speed(bps: float) -> str:
    if bps < 1024:      return f"{bps:.0f} B/s"
    if bps < 1_048_576: return f"{bps/1024:.1f} KB/s"
    return f"{bps/1_048_576:.2f} MB/s"

def md5_file(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def validate_hash(raw: str):
    h = raw.strip()
    if not h:
        return None
    if not h.startswith("version-"):
        h = "version-" + h
    parts = h.split("-")
    if len(parts) != 2 or len(parts[1]) != 16:
        return None
    if not all(c in "0123456789abcdefABCDEF" for c in parts[1]):
        return None
    return h

def load_history() -> list:
    try:
        if HISTORY_FILE.exists():
            d = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            return d if isinstance(d, list) else []
    except Exception:
        pass
    return []

def save_history(h: list):
    try:
        HISTORY_FILE.write_text(
            json.dumps(h[:MAX_HISTORY], indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    except Exception:
        pass

def fetch_latest_version():
    try:
        r = requests.get(VERSION_API, timeout=8)
        r.raise_for_status()
        return r.json().get("clientVersionUpload")
    except Exception:
        return None


# =============================================================================
#  BACKGROUND MUSIC
# =============================================================================
class MusicPlayer:
    def __init__(self):
        self._on = False
        if not PYGAME_OK:
            return
        try:
            pygame.mixer.init()
            if SOUND_FILE.exists():
                pygame.mixer.music.load(str(SOUND_FILE))
                pygame.mixer.music.set_volume(0.60)   # 60%
                pygame.mixer.music.play(loops=-1)
                self._on = True
        except Exception:
            pass

    @property
    def is_on(self):
        return self._on

    def toggle(self) -> bool:
        if not PYGAME_OK or not SOUND_FILE.exists():
            return False
        try:
            if self._on:
                pygame.mixer.music.pause()
                self._on = False
            else:
                pygame.mixer.music.unpause()
                self._on = True
            return True
        except Exception:
            return False

    def quit(self):
        if PYGAME_OK:
            try:
                pygame.mixer.quit()
            except Exception:
                pass


# =============================================================================
#  PARSE MANIFEST
# =============================================================================
def parse_manifest(text: str) -> list:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    packages = []
    i = 0
    # Skip first line if it is not a filename
    if lines and not ("." in lines[0]) and not lines[0].startswith("version"):
        i = 1
    elif lines and lines[0] in ("v0", "v1", "v2"):
        i = 1
    while i + 3 < len(lines):
        name   = lines[i]
        md5    = lines[i + 1]
        c_size = int(lines[i + 2]) if lines[i + 2].isdigit() else 0
        u_size = int(lines[i + 3]) if lines[i + 3].isdigit() else 0
        packages.append({"name": name, "md5": md5,
                         "compressed": c_size, "uncompressed": u_size})
        i += 4
    return packages


# =============================================================================
#  INSTALL WORKER
# =============================================================================
class InstallWorker:
    def __init__(self, vh, install_dir, cache_dir, cancel_evt,
                 progress_cb, log_cb, done_cb, error_cb):
        self.vh          = vh
        self.install_dir = install_dir
        self.cache_dir   = cache_dir
        self.cancel      = cancel_evt
        self._progress   = progress_cb   
        self._log        = log_cb        
        self._done       = done_cb       
        self._error      = error_cb      
        self._cdn        = CDN_BASE

    # ─── Entry ───────────────────────────────────────────────────────────────
    def run(self):
        try:
            self._main()
        except Exception as e:
            self._error("Unknown Error", str(e))

    def _main(self):
        self._log("Checking CDN...", C["warning"])
        self._cdn = self._pick_cdn()
        self._log(f"Using CDN: {self._cdn}", C["muted"])
        if self.cancel.is_set():
            return

        self._log("Downloading package list (manifest)...", C["warning"])
        url = f"{self._cdn}/{self.vh}-rbxPkgManifest.txt"
        manifest_text = self._fetch_text(url)
        if manifest_text is None:
            return  
        if self.cancel.is_set():
            return

        packages = parse_manifest(manifest_text)
        if not packages:
            self._error("Empty Manifest",
                        "Could not read the package list from CDN.\n"
                        "Try again or check the version hash.")
            return

        zips = [p for p in packages if p["name"].endswith(".zip")]
        total_bytes = sum(p["compressed"] for p in zips)
        self._log(f"Found {len(zips)} packages  ({fmt_bytes(total_bytes)})", C["muted"])

        self.install_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        downloaded = 0
        t_start    = time.time()

        for idx, pkg in enumerate(zips):
            if self.cancel.is_set():
                self._log("Cancelled.", C["muted"])
                return

            name       = pkg["name"]
            expected   = pkg["md5"]
            cache_path = self.cache_dir / f"{self.vh}-{name}"

            self._log(f"[{idx+1}/{len(zips)}]  {name}", C["warning"])

            # Check cache
            if cache_path.exists():
                if md5_file(cache_path).upper() == expected.upper():
                    self._log(f"  Cache OK, skipping download.", C["muted"])
                else:
                    cache_path.unlink()
                    self._log(f"  Cache corrupted, re-downloading.", C["warning"])

            if not cache_path.exists():
                ok = self._download_pkg(name, expected, cache_path,
                                        downloaded, total_bytes, t_start)
                if not ok:
                    return

            downloaded += pkg["compressed"]
            pct = downloaded / total_bytes * 100 if total_bytes else 0
            self._progress(pct, name, 100, 0, 0)

            # Extract
            if self.cancel.is_set():
                return
            self._log(f"  Extracting {name}...", C["muted"])
            try:
                self._extract(cache_path, name)
            except Exception as e:
                self._error("Extraction Error", f"{name}\n\n{e}")
                return

        if self.cancel.is_set():
            return

        # 5. Write AppSettings.xml
        self._write_app_settings()
        self._log("AppSettings.xml written.", C["muted"])

        # 6. Register protocol (Windows)
        self._register_protocol()

        self._done(self.install_dir)

    # ─── Pick CDN ─────────────────────────────────────────────────────────────
    def _pick_cdn(self) -> str:
        best, best_t = CDN_BASE, 9999.0
        for cdn in [CDN_BASE] + CDN_FALLBACKS:
            try:
                t0 = time.time()
                r  = requests.head(
                    f"{cdn}/{self.vh}-rbxPkgManifest.txt", timeout=5)
                if r.status_code in (200, 403, 404):
                    dt = time.time() - t0
                    if dt < best_t:
                        best, best_t = cdn, dt
            except Exception:
                pass
        return best

    # ─── Fetch text ─────────────────────────────────────────────────────────────
    def _fetch_text(self, url: str):
        try:
            r = requests.get(url, timeout=(CONNECT_TO, READ_TO))
            if r.status_code == 404:
                self._error("Version Not Found",
                            f"Hash does not exist on CDN:\n{self.vh}\n\n"
                            "Please check the version hash again.")
                return None
            r.raise_for_status()
            return r.text
        except requests.exceptions.ConnectionError:
            self._error("Connection Lost",
                        "Check your Internet connection and try again.")
            return None
        except requests.exceptions.Timeout:
            self._error("Timeout", "Server did not respond, please try again later.")
            return None
        except Exception as e:
            self._error("Network Error", str(e))
            return None

    # ─── Download a package ──────────────────────────────────────────────────────
    def _download_pkg(self, name, expected_md5, dest: Path,
                      done_bytes, total_bytes, t_start) -> bool:
        url = f"{self._cdn}/{self.vh}-{name}"
        tmp = dest.with_suffix(".part")

        try:
            r = requests.get(url, stream=True,
                             timeout=(CONNECT_TO, READ_TO))
            if r.status_code == 404:
                self._error("Package Not Found",
                            f"CDN does not have:\n{name}")
                return False
            r.raise_for_status()

            pkg_size = int(r.headers.get("content-length", 0))
            pkg_done = 0
            last_t   = time.time()
            last_b   = done_bytes

            with open(tmp, "wb") as f:
                for chunk in r.iter_content(chunk_size=CHUNK):
                    if self.cancel.is_set():
                        tmp.unlink(missing_ok=True)
                        return False
                    f.write(chunk)
                    pkg_done       += len(chunk)
                    now_bytes       = done_bytes + pkg_done
                    now             = time.time()
                    dt              = now - last_t
                    if dt >= 0.4:
                        speed   = (now_bytes - last_b) / dt
                        last_t  = now
                        last_b  = now_bytes
                        eta     = (total_bytes - now_bytes) / speed \
                                  if speed > 0 and total_bytes else 0
                        o_pct   = now_bytes / total_bytes * 100 \
                                  if total_bytes else 0
                        p_pct   = pkg_done / pkg_size * 100 \
                                  if pkg_size else 0
                        self._progress(o_pct, name, p_pct, speed, eta)

        except requests.exceptions.ConnectionError:
            tmp.unlink(missing_ok=True)
            self._error("Connection Lost", f"Connection dropped while downloading:\n{name}")
            return False
        except requests.exceptions.Timeout:
            tmp.unlink(missing_ok=True)
            self._error("Timeout", f"Timed out while downloading:\n{name}")
            return False
        except PermissionError:
            tmp.unlink(missing_ok=True)
            self._error("Write Permission Error",
                        f"Cannot write to:\n{dest.parent}\n\n"
                        "Try running as Administrator.")
            return False
        except Exception as e:
            tmp.unlink(missing_ok=True)
            self._error("Download Error", str(e))
            return False

        # Verify MD5
        actual = md5_file(tmp)
        if actual.upper() != expected_md5.upper():
            tmp.unlink(missing_ok=True)
            self._error("Checksum Failed",
                        f"Package corrupted during download:\n{name}\n\n"
                        f"Expected: {expected_md5}\n"
                        f"Received: {actual}\n\n"
                        "It will be re-downloaded next time.")
            return False

        tmp.replace(dest)
        return True

    # ─── Extract ─────────────────────────────────────────────────────────────
    def _extract(self, zip_path: Path, pkg_name: str):
        sub = PACKAGE_MAP.get(pkg_name, "")   # unknown package → root

        # WebView2RuntimeInstaller: run the installer, do not extract normally
        if sub == "__webview2_installer__":
            installer_dir = self.install_dir / "_webview2"
            installer_dir.mkdir(exist_ok=True)
            with zipfile.ZipFile(zip_path) as zf:
                for member in zf.namelist():
                    if member.lower().endswith(".exe"):
                        data = zf.read(member)
                        inst_exe = installer_dir / Path(member).name
                        inst_exe.write_bytes(data)
                        # Run silently if WebView2 is not installed
                        try:
                            subprocess.run(
                                [str(inst_exe), "/silent", "/install"],
                                timeout=120, check=False
                            )
                        except Exception:
                            pass
                        break
            return

        out_dir = self.install_dir / sub if sub else self.install_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(out_dir)

    # ─── AppSettings.xml ──────────────────────────────────────────────────────
    def _write_app_settings(self):
        (self.install_dir / "AppSettings.xml").write_text(
            APP_SETTINGS_XML, encoding="utf-8")

    # ─── Registry protocol ────────────────────────────────────────────────────
    def _register_protocol(self):
        if not WINREG_OK:
            return
        exe = self.install_dir / "RobloxPlayerBeta.exe"
        if not exe.exists():
            return
        try:
            for proto in ("roblox", "roblox-player"):
                key = winreg.CreateKey(
                    winreg.HKEY_CURRENT_USER,
                    rf"Software\Classes\{proto}"
                )
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ,
                                  f"URL:{proto} Protocol")
                winreg.SetValueEx(key, "URL Protocol", 0,
                                  winreg.REG_SZ, "")
                cmd = winreg.CreateKey(key, r"shell\open\command")
                winreg.SetValueEx(cmd, "", 0, winreg.REG_SZ,
                                  f'"{exe}" %1')
                cmd.Close()
                key.Close()
            self._log("Registered roblox-player:// protocol.", C["muted"])
        except Exception:
            pass   # not mandatory


# =============================================================================
#  USER INTERFACE
# =============================================================================
class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"Roblox Version Downloader  v{APP_VERSION}")
        self.root.geometry("720x820")
        self.root.resizable(False, True)
        self.root.configure(bg=C["bg"])

        icon = Path(__file__).parent / "icon.ico"
        if icon.exists():
            try:
                self.root.iconbitmap(str(icon))
            except Exception:
                pass

        self._history    = load_history()
        self._music      = MusicPlayer()
        self._worker_thr = None
        self._cancel_evt = threading.Event()

        _local = Path(os.environ.get("LOCALAPPDATA", Path.home()))
        self._base_dir  = _local / "Roblox" / "Versions"
        self._cache_dir = _local / "Roblox" / "Downloads"

        self._build_ui()
        self._refresh_history()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ─── Build UI ─────────────────────────────────────────────────────────────
    def _build_ui(self):
        # Header
        hdr = tk.Frame(self.root, bg=C["card"], pady=14)
        hdr.pack(fill="x")
        tk.Label(hdr, text="⬦  ROBLOX  VERSION  DOWNLOADER",
                 bg=C["card"], fg=C["accent"],
                 font=("Consolas", 14, "bold")).pack(side="left", padx=20)
        tk.Label(hdr, text=f"v{APP_VERSION}",
                 bg=C["card"], fg=C["muted"],
                 font=("Consolas", 9)).pack(side="right", padx=6)
        self._music_btn = tk.Button(
            hdr, text="🎵" if self._music.is_on else "🔇",
            bg=C["card"], fg=C["muted"], relief="flat",
            font=("Segoe UI", 12), cursor="hand2",
            command=self._toggle_music
        )
        self._music_btn.pack(side="right", padx=10)
        tk.Label(hdr, text="By HoangLong",
                 bg=C["card"], fg=C["accent2"],
                 font=("Segoe UI", 9, "italic")).pack(side="right", padx=(0, 4))

        # ── Scrollable body ───────────────────────────────────────────────────
        _outer = tk.Frame(self.root, bg=C["bg"])
        _outer.pack(fill="both", expand=True)

        _canvas = tk.Canvas(_outer, bg=C["bg"], highlightthickness=0,
                            bd=0)
        _vscroll = tk.Scrollbar(_outer, orient="vertical",
                                command=_canvas.yview,
                                bg=C["panel"], troughcolor=C["panel"])
        _canvas.configure(yscrollcommand=_vscroll.set)
        _vscroll.pack(side="right", fill="y")
        _canvas.pack(side="left", fill="both", expand=True)

        body = tk.Frame(_canvas, bg=C["bg"], padx=24, pady=16)
        _body_win = _canvas.create_window((0, 0), window=body, anchor="nw")

        def _on_body_configure(event):
            _canvas.configure(scrollregion=_canvas.bbox("all"))

        def _on_canvas_configure(event):
            _canvas.itemconfig(_body_win, width=event.width)

        body.bind("<Configure>", _on_body_configure)
        _canvas.bind("<Configure>", _on_canvas_configure)

        # Mouse wheel scroll
        def _on_mousewheel(event):
            _canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        _canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # ── Watermark footer ──────────────────────────────────────────────────
        _wm = tk.Label(self.root, text="By HoangLong",
                       bg=C["bg"], fg=C["border"],
                       font=("Segoe UI", 8))
        _wm.place(relx=1.0, rely=1.0, x=-8, y=-6, anchor="se")

        # ── Version Hash
        self._section(body, "VERSION HASH")
        hash_row = tk.Frame(body, bg=C["bg"])
        hash_row.pack(fill="x", pady=(4, 0))

        self._hash_var = tk.StringVar(value="version-xxxxxxxxxxxxxxxx")
        self._hash_var.trace_add("write", lambda *_: self._update_preview())

        tk.Entry(hash_row, textvariable=self._hash_var,
                 bg=C["input_bg"], fg=C["fg"], insertbackground=C["fg"],
                 font=("Consolas", 13), relief="flat",
                 highlightthickness=1,
                 highlightbackground=C["border"],
                 highlightcolor=C["accent"]
                 ).pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 6))

        tk.Button(hash_row, text="Latest",
                  bg=C["panel"], fg=C["muted"], relief="flat",
                  font=FONT_UI, cursor="hand2",
                  command=self._fetch_latest,
                  activebackground=C["accent2"], activeforeground="white"
                  ).pack(side="left", ipady=6, ipadx=10, padx=(0, 4))

        tk.Button(hash_row, text="✕",
                  bg=C["panel"], fg=C["muted"], relief="flat",
                  font=("Segoe UI", 11), cursor="hand2",
                  command=lambda: self._hash_var.set(""),
                  activebackground=C["error"], activeforeground="white"
                  ).pack(side="left", ipady=6, ipadx=8)

        self._preview_lbl = tk.Label(
            body, text="", bg=C["bg"], fg=C["muted"],
            font=("Consolas", 9), wraplength=660, justify="left"
        )
        self._preview_lbl.pack(fill="x", pady=(5, 0))

        # ── Install Directory
        self._section(body, "INSTALL DIRECTORY  (Versions)")
        dir_row = tk.Frame(body, bg=C["bg"])
        dir_row.pack(fill="x", pady=(4, 0))

        self._dir_lbl = tk.Label(
            dir_row, text=str(self._base_dir),
            bg=C["input_bg"], fg=C["fg"], font=("Consolas", 9),
            anchor="w", relief="flat",
            highlightthickness=1, highlightbackground=C["border"]
        )
        self._dir_lbl.pack(side="left", fill="x", expand=True, ipady=7, padx=(0, 6))

        tk.Button(dir_row, text="📁  Browse...",
                  bg=C["panel"], fg=C["fg"], relief="flat",
                  font=FONT_UI, cursor="hand2", command=self._choose_dir,
                  activebackground=C["accent2"], activeforeground="white"
                  ).pack(side="left", ipady=6, ipadx=12)

        # ── Progress
        self._section(body, "INSTALLATION PROGRESS")

        style = ttk.Style()
        style.theme_use("clam")
        for sname, col in [("Overall.Horizontal.TProgressbar", C["accent"]),
                            ("Pkg.Horizontal.TProgressbar", C["accent2"])]:
            style.configure(sname, troughcolor=C["input_bg"],
                            background=col, bordercolor=C["border"],
                            lightcolor=col, darkcolor=col, thickness=12)

        self._pbar_total_var = tk.DoubleVar()
        ttk.Progressbar(body, variable=self._pbar_total_var,
                        style="Overall.Horizontal.TProgressbar",
                        mode="determinate").pack(fill="x", pady=(4, 2))

        self._pbar_pkg_var = tk.DoubleVar()
        ttk.Progressbar(body, variable=self._pbar_pkg_var,
                        style="Pkg.Horizontal.TProgressbar",
                        mode="determinate").pack(fill="x")

        meta = tk.Frame(body, bg=C["bg"])
        meta.pack(fill="x", pady=(4, 0))

        self._pct_lbl   = tk.Label(meta, text="0%", bg=C["bg"],
                                    fg=C["accent"],
                                    font=("Consolas", 11, "bold"))
        self._speed_lbl = tk.Label(meta, text="", bg=C["bg"],
                                    fg=C["muted"], font=FONT_MONO)
        self._eta_lbl   = tk.Label(meta, text="", bg=C["bg"],
                                    fg=C["muted"], font=FONT_MONO)
        self._pct_lbl.pack(side="left")
        self._speed_lbl.pack(side="right", padx=4)
        self._eta_lbl.pack(side="right", padx=16)

        self._pkg_lbl = tk.Label(body, text="", bg=C["bg"], fg=C["muted"],
                                  font=("Consolas", 9), anchor="w")
        self._pkg_lbl.pack(fill="x", pady=(2, 0))

        # ── Log
        self._section(body, "LOG")
        log_frame = tk.Frame(body, bg=C["panel"],
                             highlightthickness=1,
                             highlightbackground=C["border"])
        log_frame.pack(fill="x", pady=(4, 0))

        self._log_widget = tk.Text(
            log_frame, height=8,
            bg=C["input_bg"], fg=C["fg"],
            font=("Consolas", 9), relief="flat",
            state="disabled", wrap="word"
        )
        scroll = tk.Scrollbar(log_frame, command=self._log_widget.yview,
                              bg=C["panel"], troughcolor=C["panel"])
        self._log_widget.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self._log_widget.pack(fill="both", expand=True)

        # ── Buttons
        btn_row = tk.Frame(body, bg=C["bg"])
        btn_row.pack(fill="x", pady=(14, 0))

        self._install_btn = tk.Button(
            btn_row, text="⬇  INSTALL ROBLOX PLAYER",
            bg=C["accent"], fg="white", relief="flat",
            font=("Segoe UI", 13, "bold"), cursor="hand2",
            activebackground="#c2263d", activeforeground="white",
            command=self._start_install
        )
        self._install_btn.pack(side="left", fill="x", expand=True,
                               ipady=13, padx=(0, 6))

        self._cancel_btn = tk.Button(
            btn_row, text="✕  Cancel",
            bg=C["panel"], fg=C["muted"], relief="flat",
            font=FONT_UI, cursor="hand2",
            activebackground=C["error"], activeforeground="white",
            command=self._cancel, state="disabled"
        )
        self._cancel_btn.pack(side="left", ipady=13, ipadx=20)

        # ── History
        self._section(body, "INSTALLATION HISTORY")
        self._hist_frame = tk.Frame(body, bg=C["panel"],
                                    highlightthickness=1,
                                    highlightbackground=C["border"])
        self._hist_frame.pack(fill="x", pady=(4, 20))

        self._update_preview()

    # ─── Section label ────────────────────────────────────────────────────────
    def _section(self, parent, text: str):
        f = tk.Frame(parent, bg=C["bg"])
        f.pack(fill="x", pady=(12, 2))
        tk.Label(f, text=text, bg=C["bg"], fg=C["accent2"],
                 font=("Consolas", 9, "bold")).pack(side="left")
        tk.Frame(f, bg=C["border"], height=1).pack(
            side="left", fill="x", expand=True, padx=(8, 0), pady=4)

    # ─── Preview ──────────────────────────────────────────────────────────────
    def _update_preview(self, *_):
        h = self._hash_var.get().strip()
        if h:
            self._preview_lbl.config(
                text=f"→ {CDN_BASE}/{h}-rbxPkgManifest.txt  (+all .zip packages)")
        else:
            self._preview_lbl.config(text="")

    # ─── Choose directory ─────────────────────────────────────────────────────
    def _choose_dir(self):
        d = filedialog.askdirectory(
            title="Select Versions folder (containing Roblox versions)",
            initialdir=str(self._base_dir)
        )
        if d:
            self._base_dir = Path(d)
            self._dir_lbl.config(text=str(self._base_dir))

    # ─── Fetch latest version ─────────────────────────────────────────────────
    def _fetch_latest(self):
        self._log_append("Fetching latest version...", C["warning"])
        def _do():
            v = fetch_latest_version()
            if v:
                self.root.after(0, lambda: self._hash_var.set(v))
                self.root.after(0, self._log_append,
                                f"Latest version: {v}", C["success"])
            else:
                self.root.after(0, self._log_append,
                                "Could not retrieve version! Check your network.",
                                C["error"])
        threading.Thread(target=_do, daemon=True).start()

    # ─── Music ─────────────────────────────────────────────────────────────────
    def _toggle_music(self):
        ok = self._music.toggle()
        if not ok:
            if not PYGAME_OK:
                messagebox.showinfo("Background Music",
                                    "pygame is not installed.\npip install pygame")
            else:
                messagebox.showinfo("Background Music",
                                    f"File not found:\n{SOUND_FILE}\n\n"
                                    "Place music.mp3 in the sound/ folder")
            return
        self._music_btn.config(text="🎵" if self._music.is_on else "🔇")

    # ─── Log ──────────────────────────────────────────────────────────────────
    def _log_append(self, msg: str, color: str = C["muted"]):
        self._log_widget.configure(state="normal")
        self._log_widget.insert(
            "end", f"[{time.strftime('%H:%M:%S')}]  {msg}\n")
        self._log_widget.see("end")
        self._log_widget.configure(state="disabled")

    # ─── Start installation ──────────────────────────────────────────────────
    def _start_install(self):
        raw = self._hash_var.get()
        vh  = validate_hash(raw)
        if vh is None:
            messagebox.showerror("Invalid Hash",
                "Version hash must be in the format:\n"
                "version-eb4648e9148d440c\n\n"
                "(16 hex characters after the dash)")
            return
        if vh != raw.strip():
            self._hash_var.set(vh)

        install_dir = self._base_dir / vh

        if install_dir.exists() and any(install_dir.iterdir()):
            if not messagebox.askyesno(
                "Already Exists",
                f"This version is already installed at:\n{install_dir}\n\n"
                "Reinstall (overwrite)?"
            ):
                return

        self._cancel_evt.clear()
        self._set_busy(True)
        self._reset_progress()
        self._log_append(f"▶ Starting installation of {vh}", C["warning"])

        worker = InstallWorker(
            vh          = vh,
            install_dir = install_dir,
            cache_dir   = self._cache_dir,
            cancel_evt  = self._cancel_evt,
            progress_cb = lambda *a: self.root.after(0, self._on_progress, *a),
            log_cb      = lambda m, c: self.root.after(0, self._log_append, m, c),
            done_cb     = lambda d: self.root.after(0, self._on_done, d),
            error_cb    = lambda t, m: self.root.after(0, self._on_error, t, m),
        )
        self._worker_thr = threading.Thread(target=worker.run, daemon=True)
        self._worker_thr.start()

    def _cancel(self):
        self._cancel_evt.set()
        self._log_append("Cancelling...", C["warning"])

    # ─── Callbacks from worker ────────────────────────────────────────────────
    def _on_progress(self, pct_total, pkg_name, pkg_pct, speed, eta):
        self._pbar_total_var.set(pct_total)
        self._pbar_pkg_var.set(pkg_pct)
        self._pct_lbl.config(text=f"{pct_total:.1f}%")
        self._pkg_lbl.config(text=f"  {pkg_name}  ({pkg_pct:.0f}%)")
        if speed > 0:
            self._speed_lbl.config(text=fmt_speed(speed))
        if eta > 0:
            m, s = divmod(int(eta), 60)
            self._eta_lbl.config(text=f"ETA {m:02d}:{s:02d}")

    def _on_done(self, install_dir: Path):
        self._pbar_total_var.set(100)
        self._pbar_pkg_var.set(100)
        self._pct_lbl.config(text="100%")
        self._log_append(f"✔  Done! → {install_dir}", C["success"])
        self._set_busy(False)

        vh = install_dir.name
        entry = {"hash": vh, "path": str(install_dir),
                 "time": time.strftime("%Y-%m-%d %H:%M")}
        self._history = [e for e in self._history if e["hash"] != vh]
        self._history.insert(0, entry)
        save_history(self._history)
        self._refresh_history()

        if messagebox.askyesno(
            "Installation Complete!",
            f"Roblox Player is ready!\n\n"
            f"Version: {vh}\n"
            f"Folder:  {install_dir}\n\n"
            "Open the installation folder?"
        ):
            self._open_folder(install_dir)

    def _on_error(self, title: str, msg: str):
        self._log_append(f"✘  {title}", C["error"])
        self._set_busy(False)
        messagebox.showerror(title, msg)

    # ─── History ──────────────────────────────────────────────────────────────
    def _refresh_history(self):
        for w in self._hist_frame.winfo_children():
            w.destroy()

        if not self._history:
            tk.Label(self._hist_frame, text="No history yet.",
                     bg=C["panel"], fg=C["muted"],
                     font=FONT_UI, pady=8).pack()
            return

        for e in self._history[:6]:
            row = tk.Frame(self._hist_frame, bg=C["panel"])
            row.pack(fill="x", padx=6, pady=2)

            tk.Label(row, text=e["hash"],
                     bg=C["panel"], fg=C["fg"],
                     font=("Consolas", 10), anchor="w"
                     ).pack(side="left", padx=4)
            tk.Label(row, text=e.get("time", ""),
                     bg=C["panel"], fg=C["accent2"],
                     font=("Consolas", 9)
                     ).pack(side="right", padx=4)
            tk.Button(row, text="📂",
                      bg=C["panel"], fg=C["muted"], relief="flat",
                      cursor="hand2",
                      command=lambda p=e.get("path", ""): \
                          self._open_folder(Path(p))
                      ).pack(side="right")
            tk.Button(row, text="↺",
                      bg=C["panel"], fg=C["accent"],
                      relief="flat", font=("Segoe UI", 11),
                      cursor="hand2",
                      command=lambda h=e["hash"]: self._hash_var.set(h)
                      ).pack(side="right")

    # ─── Misc ─────────────────────────────────────────────────────────────────
    def _reset_progress(self):
        self._pbar_total_var.set(0)
        self._pbar_pkg_var.set(0)
        self._pct_lbl.config(text="0%")
        self._speed_lbl.config(text="")
        self._eta_lbl.config(text="")
        self._pkg_lbl.config(text="")

    def _set_busy(self, state: bool):
        if state:
            self._install_btn.config(state="disabled",
                                     text="⏳  Installing...")
            self._cancel_btn.config(state="normal")
        else:
            self._install_btn.config(state="normal",
                                     text="⬇  INSTALL ROBLOX PLAYER")
            self._cancel_btn.config(state="disabled")

    def _open_folder(self, path: Path):
        if not path.exists():
            return
        try:
            if sys.platform == "win32":
                os.startfile(str(path))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception:
            pass

    def _on_close(self):
        if self._worker_thr and self._worker_thr.is_alive():
            if not messagebox.askyesno(
                "Installation In Progress",
                "Installation is not finished yet!\nExiting will cancel it. Exit anyway?"
            ):
                return
            self._cancel_evt.set()
        self._music.quit()
        self.root.destroy()


# =============================================================================
#  ENTRY POINT
# =============================================================================
def main():
    missing = []
    try:
        import requests
    except ImportError:
        missing.append("requests")

    if missing:
        msg = ("Missing libraries:\n\n" +
               "\n".join(f"  • {m}" for m in missing) +
               "\n\nRun the command:\n  pip install " + " ".join(missing))
        try:
            _r = tk.Tk()
            _r.withdraw()
            messagebox.showerror("Missing Libraries", msg)
            _r.destroy()
        except Exception:
            print(msg)
        sys.exit(1)

    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
