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

# Powered by WEAO API
import os, sys, json, time, hashlib, zipfile
import threading, subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

try:
    import winreg
    WINREG_OK = True
except ImportError:
    WINREG_OK = False

try:
    import pygame
    PYGAME_OK = True
except ImportError:
    PYGAME_OK = False

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QFileDialog, QTextEdit,
    QProgressBar, QScrollArea, QFrame, QCheckBox, QMessageBox,
    QSizePolicy, QSpacerItem, QToolButton, QComboBox,
    QDialog, QListWidget, QListWidgetItem, QDialogButtonBox, QSlider
)
from PySide6.QtCore import Qt, Signal, QThread, QObject, QTimer, QSize
from PySide6.QtGui import QFont, QColor, QPalette, QIcon, QPixmap, QFontDatabase, QCursor

APP_VERSION   = "1.2.0"
CDN_BASE      = "https://setup.rbxcdn.com"
CDN_FALLBACKS = [
    "https://setup-ak.rbxcdn.com",
    "https://setup-cf.rbxcdn.com",
    "https://roblox-setup.cachefly.net",
    "https://s3.amazonaws.com/setup.roblox.com",
]
VERSION_API        = "https://clientsettingscdn.roblox.com/v2/client-version/WindowsPlayer"
VERSION_API_STUDIO = "https://clientsettingscdn.roblox.com/v2/client-version/WindowsStudio"
WEAO_CURRENT_API   = "https://weao.xyz/api/versions/current"
WEAO_PAST_API      = "https://weao.xyz/api/versions/past"
WEAO_HEADERS       = {"User-Agent": "WEAO-3PService"}
HISTORY_FILE  = Path(__file__).parent / "download_history.json"
SOUND_FILE    = Path(__file__).parent / "sound" / "music.mp3"
CHUNK         = 131072
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
    "WebView2RuntimeInstaller.zip":      "__webview2_installer__",
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

PALETTE = {
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

UNSAFE_DIRS = {
    "C:\\Windows", "C:\\Windows\\System32", "C:\\Program Files",
    "C:\\Program Files (x86)", "C:\\", "/", "/usr", "/etc", "/bin",
    "/System", "/Library",
}


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

def is_unsafe_dir(path: Path) -> bool:
    resolved = str(path.resolve())
    for unsafe in UNSAFE_DIRS:
        if resolved.lower() == unsafe.lower():
            return True
    for unsafe in UNSAFE_DIRS:
        if resolved.lower().startswith(unsafe.lower() + os.sep):
            if unsafe.lower() not in (
                "c:\\program files\\roblox", "c:\\program files (x86)\\roblox"
            ):
                risky = {"c:\\windows", "c:\\windows\\system32",
                         "c:\\", "/", "/usr", "/etc", "/bin", "/system", "/library"}
                if unsafe.lower() in risky:
                    return True
    return False

def load_history() -> list:
    try:
        if HISTORY_FILE.exists():
            d = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            return d if isinstance(d, list) else []
    except Exception:
        pass
    return []

def save_history(entries: list):
    try:
        HISTORY_FILE.write_text(
            json.dumps(entries[:MAX_HISTORY], indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    except Exception:
        pass

def fetch_latest_version(channel: str = "player") -> str | None:
    try:
        api = VERSION_API if channel == "player" else VERSION_API_STUDIO
        r = requests.get(api, timeout=8)
        r.raise_for_status()
        return r.json().get("clientVersionUpload")
    except Exception:
        return None

def create_desktop_shortcut(target_exe: Path, version_hash: str):
    if sys.platform != "win32":
        return False
    try:
        import winshell
        desktop = Path(winshell.desktop())
        lnk_path = desktop / f"Roblox {version_hash}.lnk"
        with winshell.shortcut(str(lnk_path)) as link:
            link.path = str(target_exe)
            link.description = f"Roblox Player {version_hash}"
            link.working_directory = str(target_exe.parent)
        return True
    except ImportError:
        try:
            ps = (
                f'$s=(New-Object -COM WScript.Shell).CreateShortcut('
                f'"{Path.home() / "Desktop" / f"Roblox {version_hash}.lnk"}");'
                f'$s.TargetPath="{target_exe}";'
                f'$s.WorkingDirectory="{target_exe.parent}";'
                f'$s.Save()'
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                timeout=15, check=False, capture_output=True
            )
            return True
        except Exception:
            return False
    except Exception:
        return False


class MusicPlayer:
    def __init__(self):
        self._on     = False
        self._volume = 0.60
        if not PYGAME_OK:
            return
        try:
            pygame.mixer.init()
            if SOUND_FILE.exists():
                pygame.mixer.music.load(str(SOUND_FILE))
                pygame.mixer.music.set_volume(self._volume)
                pygame.mixer.music.play(loops=-1)
                self._on = True
        except Exception:
            pass

    @property
    def is_on(self):
        return self._on

    @property
    def volume(self):
        return self._volume

    def set_volume(self, v: float):
        self._volume = max(0.0, min(1.0, v))
        if PYGAME_OK:
            try:
                pygame.mixer.music.set_volume(self._volume)
            except Exception:
                pass

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


def parse_manifest(text: str) -> list:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    packages = []
    i = 0
    if lines and not ("." in lines[0]) and not lines[0].startswith("version"):
        i = 1
    elif lines and lines[0] in ("v0", "v1", "v2"):
        i = 1
    while i + 3 <= len(lines):
        name   = lines[i]
        md5    = lines[i + 1]
        c_size = int(lines[i + 2]) if lines[i + 2].isdigit() else 0
        u_size = int(lines[i + 3]) if lines[i + 3].isdigit() else 0
        packages.append({"name": name, "md5": md5,
                         "compressed": c_size, "uncompressed": u_size})
        i += 4
    return packages


class WorkerSignals(QObject):
    progress  = Signal(float, str, float, float, float)
    log       = Signal(str, str)
    done      = Signal(object)
    error     = Signal(str, str)


class InstallWorker(QThread):
    def __init__(self, vh, install_dir, cache_dir, cancel_evt,
                 register_protocol: bool, install_webview2: bool,
                 create_shortcut: bool):
        super().__init__()
        self.vh               = vh
        self.install_dir      = install_dir
        self.cache_dir        = cache_dir
        self.cancel           = cancel_evt
        self.register_protocol = register_protocol
        self.install_webview2  = install_webview2
        self.create_shortcut   = create_shortcut
        self._cdn             = CDN_BASE
        self.signals          = WorkerSignals()

    def run(self):
        try:
            self._main()
        except Exception as e:
            self.signals.error.emit("Unknown Error", str(e))

    def _main(self):
        self.signals.log.emit("Checking CDN...", PALETTE["warning"])
        self._cdn = self._pick_cdn()
        self.signals.log.emit(f"Using CDN: {self._cdn}", PALETTE["muted"])
        if self.cancel.is_set():
            return

        self.signals.log.emit("Downloading package list (manifest)...", PALETTE["warning"])
        url = f"{self._cdn}/{self.vh}-rbxPkgManifest.txt"
        manifest_text = self._fetch_text(url)
        if manifest_text is None:
            return
        if self.cancel.is_set():
            return

        packages = parse_manifest(manifest_text)
        if not packages:
            self.signals.error.emit(
                "Empty Manifest",
                "Could not read the package list from CDN.\n"
                "Try again or check the version hash."
            )
            return

        zips = [p for p in packages if p["name"].endswith(".zip")]
        total_bytes = sum(p["compressed"] for p in zips)
        self.signals.log.emit(
            f"Found {len(zips)} packages  ({fmt_bytes(total_bytes)})",
            PALETTE["muted"]
        )

        self.install_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        downloaded = 0
        t_start    = time.time()

        for idx, pkg in enumerate(zips):
            if self.cancel.is_set():
                self.signals.log.emit("Cancelled.", PALETTE["muted"])
                return

            name       = pkg["name"]
            expected   = pkg["md5"]
            cache_path = self.cache_dir / f"{self.vh}-{name}"

            self.signals.log.emit(f"[{idx+1}/{len(zips)}]  {name}", PALETTE["warning"])

            if cache_path.exists():
                if md5_file(cache_path).upper() == expected.upper():
                    self.signals.log.emit("  Cache OK, skipping download.", PALETTE["muted"])
                else:
                    cache_path.unlink()
                    self.signals.log.emit("  Cache corrupted, re-downloading.", PALETTE["warning"])

            if not cache_path.exists():
                ok = self._download_pkg(name, expected, cache_path,
                                        downloaded, total_bytes, t_start)
                if not ok:
                    return

            downloaded += pkg["compressed"]
            pct = downloaded / total_bytes * 100 if total_bytes else 0
            self.signals.progress.emit(pct, name, 100.0, 0.0, 0.0)

            if self.cancel.is_set():
                return
            self.signals.log.emit(f"  Extracting {name}...", PALETTE["muted"])
            try:
                self._extract(cache_path, name)
            except Exception as e:
                self.signals.error.emit("Extraction Error", f"{name}\n\n{e}")
                return

        if self.cancel.is_set():
            return

        self._write_app_settings()
        self.signals.log.emit("AppSettings.xml written.", PALETTE["muted"])

        if self.register_protocol:
            self._register_protocol()

        if self.create_shortcut:
            exe = self.install_dir / "RobloxPlayerBeta.exe"
            if exe.exists():
                ok = create_desktop_shortcut(exe, self.vh)
                if ok:
                    self.signals.log.emit("Desktop shortcut created.", PALETTE["success"])
                else:
                    self.signals.log.emit("Could not create desktop shortcut.", PALETTE["warning"])

        self.signals.done.emit(self.install_dir)

    def _pick_cdn(self) -> str:
        all_cdns = [CDN_BASE] + CDN_FALLBACKS
        lock = threading.Lock()

        def probe(cdn):
            try:
                t0 = time.time()
                r  = requests.head(f"{cdn}/{self.vh}-rbxPkgManifest.txt", timeout=5)
                if r.status_code in (200, 403, 404):
                    return cdn, time.time() - t0
            except Exception:
                pass
            return cdn, 9999.0

        nonlocal_best = [CDN_BASE, 9999.0]
        with ThreadPoolExecutor(max_workers=len(all_cdns)) as ex:
            for cdn, dt in ex.map(probe, all_cdns):
                with lock:
                    if dt < nonlocal_best[1]:
                        nonlocal_best[0] = cdn
                        nonlocal_best[1] = dt
        return nonlocal_best[0]

    def _fetch_text(self, url: str):
        try:
            r = requests.get(url, timeout=(CONNECT_TO, READ_TO))
            if r.status_code == 404:
                self.signals.error.emit(
                    "Version Not Found",
                    f"Hash does not exist on CDN:\n{self.vh}\n\n"
                    "Please check the version hash again."
                )
                return None
            r.raise_for_status()
            return r.text
        except requests.exceptions.ConnectionError:
            self.signals.error.emit(
                "Connection Lost",
                "Check your Internet connection and try again."
            )
            return None
        except requests.exceptions.Timeout:
            self.signals.error.emit(
                "Timeout", "Server did not respond, please try again later."
            )
            return None
        except Exception as e:
            self.signals.error.emit("Network Error", str(e))
            return None

    def _download_pkg(self, name, expected_md5, dest: Path,
                      done_bytes, total_bytes, t_start) -> bool:
        url = f"{self._cdn}/{self.vh}-{name}"
        tmp = dest.with_suffix(".part")

        headers = {}
        resume_pos = 0
        if tmp.exists():
            resume_pos = tmp.stat().st_size
            headers["Range"] = f"bytes={resume_pos}-"
            self.signals.log.emit(
                f"  Resuming from {fmt_bytes(resume_pos)}", PALETTE["muted"]
            )

        try:
            r = requests.get(url, stream=True, headers=headers,
                             timeout=(CONNECT_TO, READ_TO))

            if r.status_code == 416:
                resume_pos = 0
                tmp.unlink(missing_ok=True)
                r = requests.get(url, stream=True,
                                 timeout=(CONNECT_TO, READ_TO))

            if r.status_code == 404:
                self.signals.error.emit("Package Not Found",
                                        f"CDN does not have:\n{name}")
                return False
            r.raise_for_status()

            pkg_size = int(r.headers.get("content-length", 0)) + resume_pos
            pkg_done = resume_pos
            last_t   = time.time()
            last_b   = done_bytes + resume_pos

            mode = "ab" if resume_pos > 0 else "wb"
            with open(tmp, mode) as f:
                for chunk in r.iter_content(chunk_size=CHUNK):
                    if self.cancel.is_set():
                        return False
                    f.write(chunk)
                    pkg_done  += len(chunk)
                    now_bytes  = done_bytes + pkg_done
                    now        = time.time()
                    dt         = now - last_t
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
                        self.signals.progress.emit(o_pct, name, p_pct, speed, eta)

        except requests.exceptions.ConnectionError:
            self.signals.error.emit(
                "Connection Lost",
                f"Connection dropped while downloading:\n{name}\n\n"
                "You can retry — download will resume from where it stopped."
            )
            return False
        except requests.exceptions.Timeout:
            self.signals.error.emit("Timeout", f"Timed out while downloading:\n{name}")
            return False
        except PermissionError:
            tmp.unlink(missing_ok=True)
            self.signals.error.emit(
                "Write Permission Error",
                f"Cannot write to:\n{dest.parent}\n\nTry running as Administrator."
            )
            return False
        except Exception as e:
            tmp.unlink(missing_ok=True)
            self.signals.error.emit("Download Error", str(e))
            return False

        actual = md5_file(tmp)
        if actual.upper() != expected_md5.upper():
            tmp.unlink(missing_ok=True)
            self.signals.error.emit(
                "Checksum Failed",
                f"Package corrupted during download:\n{name}\n\n"
                f"Expected: {expected_md5}\nReceived: {actual}\n\n"
                "It will be re-downloaded next time."
            )
            return False

        tmp.replace(dest)
        return True

    def _extract(self, zip_path: Path, pkg_name: str):
        sub = PACKAGE_MAP.get(pkg_name, "")

        if sub == "__webview2_installer__":
            if not self.install_webview2:
                return
            installer_dir = self.install_dir / "_webview2"
            installer_dir.mkdir(exist_ok=True)
            with zipfile.ZipFile(zip_path) as zf:
                for member in zf.namelist():
                    if member.lower().endswith(".exe"):
                        data = zf.read(member)
                        inst_exe = installer_dir / Path(member).name
                        inst_exe.write_bytes(data)
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

    def _write_app_settings(self):
        (self.install_dir / "AppSettings.xml").write_text(
            APP_SETTINGS_XML, encoding="utf-8"
        )

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
                winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
                cmd = winreg.CreateKey(key, r"shell\open\command")
                winreg.SetValueEx(cmd, "", 0, winreg.REG_SZ,
                                  f'"{exe}" %1')
                cmd.Close()
                key.Close()
            self.signals.log.emit(
                "Registered roblox-player:// protocol.", PALETTE["muted"]
            )
        except Exception:
            pass


STYLESHEET = f"""
QMainWindow, QWidget#root {{
    background-color: {PALETTE["bg"]};
}}
QWidget {{
    background-color: transparent;
    color: {PALETTE["fg"]};
    font-family: 'Segoe UI', sans-serif;
    font-size: 10pt;
}}
QScrollArea {{
    border: none;
    background-color: {PALETTE["bg"]};
}}
QScrollBar:vertical {{
    background: {PALETTE["panel"]};
    width: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {PALETTE["border"]};
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {PALETTE["accent2"]};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QLineEdit {{
    background-color: {PALETTE["input_bg"]};
    color: {PALETTE["fg"]};
    border: 1px solid {PALETTE["border"]};
    border-radius: 4px;
    padding: 8px 10px;
    font-family: Consolas, monospace;
    font-size: 12pt;
    selection-background-color: {PALETTE["accent2"]};
}}
QLineEdit:focus {{
    border: 1px solid {PALETTE["accent"]};
}}
QTextEdit {{
    background-color: {PALETTE["input_bg"]};
    color: {PALETTE["fg"]};
    border: 1px solid {PALETTE["border"]};
    border-radius: 4px;
    font-family: Consolas, monospace;
    font-size: 9pt;
    selection-background-color: {PALETTE["accent2"]};
}}
QPushButton {{
    background-color: {PALETTE["panel"]};
    color: {PALETTE["muted"]};
    border: 1px solid {PALETTE["border"]};
    border-radius: 4px;
    padding: 7px 14px;
    font-size: 10pt;
}}
QPushButton:hover {{
    background-color: {PALETTE["card"]};
    color: {PALETTE["fg"]};
    border-color: {PALETTE["accent2"]};
}}
QPushButton:pressed {{
    background-color: {PALETTE["accent2"]};
    color: white;
}}
QPushButton:disabled {{
    background-color: {PALETTE["input_bg"]};
    color: {PALETTE["border"]};
    border-color: {PALETTE["border"]};
}}
QPushButton#install_btn {{
    background-color: {PALETTE["accent"]};
    color: white;
    font-size: 13pt;
    font-weight: bold;
    border: none;
    border-radius: 5px;
    padding: 13px 20px;
}}
QPushButton#install_btn:hover {{
    background-color: #c2263d;
    color: white;
}}
QPushButton#install_btn:disabled {{
    background-color: #6a1525;
    color: #c07080;
    border: none;
}}
QPushButton#cancel_btn {{
    background-color: {PALETTE["panel"]};
    color: {PALETTE["muted"]};
    font-size: 10pt;
    border: 1px solid {PALETTE["border"]};
    padding: 13px 20px;
}}
QPushButton#cancel_btn:hover {{
    background-color: {PALETTE["error"]};
    color: white;
    border-color: {PALETTE["error"]};
}}
QPushButton#cancel_btn:disabled {{
    background-color: {PALETTE["input_bg"]};
    color: {PALETTE["border"]};
    border-color: {PALETTE["border"]};
}}
QProgressBar {{
    background-color: {PALETTE["input_bg"]};
    border: 1px solid {PALETTE["border"]};
    border-radius: 4px;
    height: 13px;
    text-align: center;
    color: transparent;
    font-size: 0pt;
}}
QProgressBar#overall_bar::chunk {{
    background-color: {PALETTE["accent"]};
    border-radius: 3px;
}}
QProgressBar#pkg_bar::chunk {{
    background-color: {PALETTE["accent2"]};
    border-radius: 3px;
}}
QCheckBox {{
    color: {PALETTE["fg"]};
    font-size: 10pt;
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {PALETTE["border"]};
    border-radius: 3px;
    background-color: {PALETTE["input_bg"]};
}}
QCheckBox::indicator:checked {{
    background-color: {PALETTE["accent2"]};
    border-color: {PALETTE["accent2"]};
}}
QCheckBox::indicator:hover {{
    border-color: {PALETTE["accent"]};
}}
QComboBox {{
    background-color: {PALETTE["input_bg"]};
    color: {PALETTE["fg"]};
    border: 1px solid {PALETTE["border"]};
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 10pt;
}}
QComboBox:focus {{
    border-color: {PALETTE["accent"]};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background-color: {PALETTE["card"]};
    color: {PALETTE["fg"]};
    selection-background-color: {PALETTE["accent2"]};
    border: 1px solid {PALETTE["border"]};
}}
QSlider::groove:horizontal {{
    background: {PALETTE["border"]};
    height: 4px;
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {PALETTE["accent2"]};
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}
QSlider::handle:horizontal:hover {{
    background: {PALETTE["accent"]};
}}
QSlider::sub-page:horizontal {{
    background: {PALETTE["accent2"]};
    border-radius: 2px;
}}
"""


def _color_label(text: str, color: str, bold: bool = False, font_size: int = 10,
                 mono: bool = False) -> QLabel:
    lbl = QLabel(text)
    family = "Consolas, monospace" if mono else "'Segoe UI', sans-serif"
    weight = "bold" if bold else "normal"
    lbl.setStyleSheet(
        f"color: {color}; font-size: {font_size}pt; "
        f"font-weight: {weight}; font-family: {family};"
    )
    return lbl


def _section_header(text: str) -> QWidget:
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 12, 0, 2)
    layout.setSpacing(8)

    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {PALETTE['accent2']}; font-family: Consolas, monospace; "
        f"font-size: 9pt; font-weight: bold;"
    )
    layout.addWidget(lbl)

    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setStyleSheet(f"background-color: {PALETTE['border']}; max-height: 1px;")
    line.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    layout.addWidget(line)

    return container


class HistoryRow(QWidget):
    reinstall_requested = Signal(str)
    delete_requested    = Signal(str)

    def __init__(self, entry: dict, parent=None):
        super().__init__(parent)
        self._entry = entry
        self._build()

    def _build(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)
        self.setStyleSheet(
            f"background-color: {PALETTE['panel']}; "
            f"border: 1px solid {PALETTE['border']}; border-radius: 4px;"
        )

        hash_lbl = QLabel(self._entry["hash"])
        hash_lbl.setStyleSheet(
            f"color: {PALETTE['fg']}; font-family: Consolas, monospace; "
            f"font-size: 9pt; border: none;"
        )
        hash_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(hash_lbl)

        time_lbl = QLabel(self._entry.get("time", ""))
        time_lbl.setStyleSheet(
            f"color: {PALETTE['accent2']}; font-family: Consolas, monospace; "
            f"font-size: 8pt; border: none;"
        )
        layout.addWidget(time_lbl)

        folder_btn = QPushButton("📂")
        folder_btn.setFixedSize(28, 28)
        folder_btn.setToolTip("Open folder")
        folder_btn.setCursor(QCursor(Qt.PointingHandCursor))
        folder_btn.setStyleSheet(
            f"background: transparent; color: {PALETTE['muted']}; "
            f"border: none; font-size: 12pt;"
        )
        folder_btn.clicked.connect(self._open_folder)
        layout.addWidget(folder_btn)

        reinstall_btn = QPushButton("↺")
        reinstall_btn.setFixedSize(28, 28)
        reinstall_btn.setToolTip("Load this hash")
        reinstall_btn.setCursor(QCursor(Qt.PointingHandCursor))
        reinstall_btn.setStyleSheet(
            f"background: transparent; color: {PALETTE['accent']}; "
            f"border: none; font-size: 14pt; font-weight: bold;"
        )
        reinstall_btn.clicked.connect(
            lambda: self.reinstall_requested.emit(self._entry["hash"])
        )
        layout.addWidget(reinstall_btn)

        del_btn = QPushButton("🗑")
        del_btn.setFixedSize(28, 28)
        del_btn.setToolTip("Delete this version from disk")
        del_btn.setCursor(QCursor(Qt.PointingHandCursor))
        del_btn.setStyleSheet(
            f"background: transparent; color: {PALETTE['error']}; "
            f"border: none; font-size: 11pt;"
        )
        del_btn.clicked.connect(
            lambda: self.delete_requested.emit(self._entry["hash"])
        )
        layout.addWidget(del_btn)

    def _open_folder(self):
        p = Path(self._entry.get("path", ""))
        if not p.exists():
            QMessageBox.warning(self, "Not Found",
                                f"Folder does not exist:\n{p}")
            return
        try:
            if sys.platform == "win32":
                os.startfile(str(p))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(p)])
            else:
                subprocess.Popen(["xdg-open", str(p)])
        except Exception:
            pass


class VersionFetchSignals(QObject):
    result  = Signal(list, str)
    log     = Signal(str, str)


class VersionFetchWorker(QThread):
    def __init__(self, mode: str):
        super().__init__()
        self.mode    = mode
        self.signals = VersionFetchSignals()

    def run(self):
        if self.mode == "latest":
            self._fetch_latest()
        elif self.mode == "previous":
            self._fetch_previous()

    def _fetch_latest(self):
        try:
            r = requests.get(WEAO_CURRENT_API, headers=WEAO_HEADERS, timeout=8)
            r.raise_for_status()
            data = r.json()
            vh = data.get("Windows") or data.get("clientVersionUpload")
            if vh:
                self.signals.result.emit([vh], "latest")
                return
        except Exception:
            pass

        vh = fetch_latest_version("player")
        if vh:
            self.signals.result.emit([vh], "latest")
        else:
            self.signals.result.emit([], "latest")

    def _fetch_previous(self):
        versions = []
        try:
            r = requests.get(WEAO_PAST_API, headers=WEAO_HEADERS, timeout=8)
            r.raise_for_status()
            data = r.json()
            win = data.get("Windows")
            mac = data.get("Mac")
            if win:
                versions.append(f"{win}  (Windows — prev)")
            if mac:
                versions.append(f"{mac}  (Mac — prev)")
        except Exception:
            pass

        if not versions:
            self.signals.log.emit(
                "WEAO past API unavailable, falling back to CDN history...",
                PALETTE["warning"]
            )
            try:
                r2 = requests.get(f"{CDN_BASE}/DeployHistory.txt", timeout=10)
                if r2.status_code == 200:
                    seen = set()
                    for line in r2.text.splitlines():
                        if "version-" in line:
                            for part in line.split():
                                vh = validate_hash(part)
                                if vh and vh not in seen:
                                    seen.add(vh)
                                    versions.append(vh)
                                    if len(versions) >= 30:
                                        break
                        if len(versions) >= 30:
                            break
            except Exception:
                pass

        self.signals.result.emit(versions, "previous")


class App(QMainWindow):
    _log_signal   = Signal(str, str)
    _prog_signal  = Signal(float, str, float, float, float)
    _done_signal  = Signal(object)
    _error_signal = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Roblox Version Downloader  v{APP_VERSION}")
        self.setMinimumWidth(740)
        self.resize(740, 880)
        self.setObjectName("root")

        icon_path = Path(__file__).parent / "icon.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self._history       = load_history()
        self._music         = MusicPlayer()
        self._worker        = None
        self._fetch_worker  = None
        self._cancel_evt    = threading.Event()

        _local = Path(os.environ.get("LOCALAPPDATA", Path.home()))
        self._base_dir  = _local / "Roblox" / "Versions"
        self._cache_dir = _local / "Roblox" / "Downloads"

        self._build_ui()
        self._refresh_history()

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("root")
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        header = self._build_header()
        root_layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body_widget = QWidget()
        body_widget.setObjectName("root")
        body_layout = QVBoxLayout(body_widget)
        body_layout.setContentsMargins(26, 18, 26, 24)
        body_layout.setSpacing(0)

        self._build_body(body_layout)
        scroll.setWidget(body_widget)
        root_layout.addWidget(scroll)

        footer = QWidget()
        footer.setStyleSheet(f"background-color: {PALETTE['panel']}; border-top: 1px solid {PALETTE['border']};")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(14, 4, 14, 5)

        watermark = QLabel("✦  By  HoangLong  ✦")
        watermark.setStyleSheet(
            f"color: {PALETTE['accent2']}; font-size: 9pt; font-weight: bold; "
            f"font-family: Consolas, monospace; letter-spacing: 1px; border: none;"
        )
        watermark.setAlignment(Qt.AlignRight)
        footer_layout.addStretch()
        footer_layout.addWidget(watermark)
        root_layout.addWidget(footer)

    def _build_header(self) -> QWidget:
        hdr = QWidget()
        hdr.setStyleSheet(f"background-color: {PALETTE['card']};")
        hdr.setFixedHeight(60)
        layout = QHBoxLayout(hdr)
        layout.setContentsMargins(20, 0, 12, 0)
        layout.setSpacing(10)

        title = QLabel("⬦  ROBLOX  VERSION  DOWNLOADER")
        title.setStyleSheet(
            f"color: {PALETTE['accent']}; font-family: Consolas, monospace; "
            f"font-size: 13pt; font-weight: bold; background: transparent;"
        )
        layout.addWidget(title)
        layout.addStretch()

        author = QLabel("By HoangLong ❤")
        author.setStyleSheet(
            f"color: {PALETTE['accent']}; font-size: 10pt; font-weight: bold; "
            f"font-family: Consolas, monospace; background: transparent; letter-spacing: 1px;"
        )
        layout.addWidget(author)

        layout.addSpacing(12)

        self._music_btn = QPushButton("🎵" if self._music.is_on else "🔇")
        self._music_btn.setFixedSize(34, 34)
        self._music_btn.setStyleSheet(
            f"background: {PALETTE['panel']}; border: 1px solid {PALETTE['border']}; "
            f"border-radius: 17px; color: {PALETTE['fg']}; font-size: 14pt;"
        )
        self._music_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._music_btn.clicked.connect(self._toggle_music)
        self._music_btn.setToolTip("Toggle background music")
        layout.addWidget(self._music_btn)

        self._vol_slider = QSlider(Qt.Horizontal)
        self._vol_slider.setRange(0, 100)
        self._vol_slider.setValue(int(self._music.volume * 100))
        self._vol_slider.setFixedWidth(80)
        self._vol_slider.setFixedHeight(20)
        self._vol_slider.setCursor(QCursor(Qt.PointingHandCursor))
        self._vol_slider.setToolTip("Music volume")
        self._vol_slider.valueChanged.connect(self._on_volume_change)
        layout.addWidget(self._vol_slider)

        ver_lbl = QLabel(f"v{APP_VERSION}")
        ver_lbl.setStyleSheet(
            f"color: {PALETTE['muted']}; font-family: Consolas, monospace; "
            f"font-size: 8pt; background: transparent;"
        )
        layout.addWidget(ver_lbl)

        return hdr

    def _build_body(self, layout: QVBoxLayout):
        layout.addWidget(_section_header("VERSION HASH"))

        hash_row = QWidget()
        hash_layout = QHBoxLayout(hash_row)
        hash_layout.setContentsMargins(0, 4, 0, 0)
        hash_layout.setSpacing(6)

        self._hash_input = QLineEdit()
        self._hash_input.setPlaceholderText("version-xxxxxxxxxxxxxxxx")
        self._hash_input.textChanged.connect(self._update_preview)
        hash_layout.addWidget(self._hash_input)

        self._latest_btn = QPushButton("Latest")
        self._latest_btn.setFixedHeight(38)
        self._latest_btn.setMinimumWidth(70)
        self._latest_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._latest_btn.clicked.connect(self._fetch_latest)
        hash_layout.addWidget(self._latest_btn)

        self._prev_btn = QPushButton("Previous")
        self._prev_btn.setFixedHeight(38)
        self._prev_btn.setMinimumWidth(80)
        self._prev_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._prev_btn.clicked.connect(self._fetch_previous)
        self._prev_btn.setToolTip("Browse previous Roblox versions via WEAO API")
        hash_layout.addWidget(self._prev_btn)

        clear_btn = QPushButton("✕")
        clear_btn.setFixedSize(38, 38)
        clear_btn.setCursor(QCursor(Qt.PointingHandCursor))
        clear_btn.setStyleSheet(
            f"background-color: {PALETTE['panel']}; color: {PALETTE['muted']}; "
            f"border: 1px solid {PALETTE['border']}; border-radius: 4px; font-size: 12pt;"
        )
        clear_btn.clicked.connect(lambda: self._hash_input.clear())
        hash_layout.addWidget(clear_btn)

        layout.addWidget(hash_row)

        self._preview_lbl = QLabel("")
        self._preview_lbl.setStyleSheet(
            f"color: {PALETTE['muted']}; font-family: Consolas, monospace; "
            f"font-size: 8pt; padding-top: 4px;"
        )
        self._preview_lbl.setWordWrap(True)
        layout.addWidget(self._preview_lbl)

        layout.addWidget(_section_header("INSTALL DIRECTORY  (Versions)"))

        dir_row = QWidget()
        dir_layout = QHBoxLayout(dir_row)
        dir_layout.setContentsMargins(0, 4, 0, 0)
        dir_layout.setSpacing(6)

        self._dir_lbl = QLabel(str(self._base_dir))
        self._dir_lbl.setStyleSheet(
            f"background-color: {PALETTE['input_bg']}; color: {PALETTE['fg']}; "
            f"font-family: Consolas, monospace; font-size: 9pt; "
            f"border: 1px solid {PALETTE['border']}; border-radius: 4px; padding: 8px 10px;"
        )
        self._dir_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        dir_layout.addWidget(self._dir_lbl)

        browse_btn = QPushButton("📁  Browse...")
        browse_btn.setFixedHeight(38)
        browse_btn.setMinimumWidth(110)
        browse_btn.setCursor(QCursor(Qt.PointingHandCursor))
        browse_btn.clicked.connect(self._choose_dir)
        dir_layout.addWidget(browse_btn)

        layout.addWidget(dir_row)

        layout.addWidget(_section_header("OPTIONS"))

        opts = QWidget()
        opts_layout = QVBoxLayout(opts)
        opts_layout.setContentsMargins(0, 4, 0, 0)
        opts_layout.setSpacing(6)

        self._chk_protocol = QCheckBox("Register roblox:// protocol in Registry")
        self._chk_protocol.setChecked(True)
        opts_layout.addWidget(self._chk_protocol)

        self._chk_webview2 = QCheckBox(
            "Install WebView2 Runtime  (opt-in — runs a silent installer)"
        )
        self._chk_webview2.setChecked(False)
        opts_layout.addWidget(self._chk_webview2)

        self._chk_shortcut = QCheckBox("Create Desktop Shortcut after install")
        self._chk_shortcut.setChecked(False)
        opts_layout.addWidget(self._chk_shortcut)

        layout.addWidget(opts)

        layout.addWidget(_section_header("INSTALLATION PROGRESS"))

        self._overall_bar = QProgressBar()
        self._overall_bar.setObjectName("overall_bar")
        self._overall_bar.setRange(0, 1000)
        self._overall_bar.setValue(0)
        self._overall_bar.setFixedHeight(13)
        layout.addWidget(self._overall_bar)

        self._pkg_bar = QProgressBar()
        self._pkg_bar.setObjectName("pkg_bar")
        self._pkg_bar.setRange(0, 1000)
        self._pkg_bar.setValue(0)
        self._pkg_bar.setFixedHeight(10)
        layout.addSpacing(3)
        layout.addWidget(self._pkg_bar)

        meta_row = QWidget()
        meta_layout = QHBoxLayout(meta_row)
        meta_layout.setContentsMargins(0, 4, 0, 0)
        meta_layout.setSpacing(0)

        self._pct_lbl = QLabel("0%")
        self._pct_lbl.setStyleSheet(
            f"color: {PALETTE['accent']}; font-family: Consolas, monospace; "
            f"font-size: 11pt; font-weight: bold;"
        )
        meta_layout.addWidget(self._pct_lbl)
        meta_layout.addStretch()

        self._eta_lbl = QLabel("")
        self._eta_lbl.setStyleSheet(
            f"color: {PALETTE['muted']}; font-family: Consolas, monospace; font-size: 9pt;"
        )
        meta_layout.addWidget(self._eta_lbl)
        meta_layout.addSpacing(20)

        self._speed_lbl = QLabel("")
        self._speed_lbl.setStyleSheet(
            f"color: {PALETTE['muted']}; font-family: Consolas, monospace; font-size: 9pt;"
        )
        meta_layout.addWidget(self._speed_lbl)

        layout.addWidget(meta_row)

        self._pkg_lbl = QLabel("")
        self._pkg_lbl.setStyleSheet(
            f"color: {PALETTE['muted']}; font-family: Consolas, monospace; font-size: 9pt;"
        )
        layout.addWidget(self._pkg_lbl)

        layout.addWidget(_section_header("LOG"))

        self._log_widget = QTextEdit()
        self._log_widget.setReadOnly(True)
        self._log_widget.setFixedHeight(160)
        layout.addWidget(self._log_widget)

        layout.addSpacing(14)

        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(8)

        self._install_btn = QPushButton("⬇  INSTALL ROBLOX PLAYER")
        self._install_btn.setObjectName("install_btn")
        self._install_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._install_btn.clicked.connect(self._start_install)
        btn_layout.addWidget(self._install_btn, stretch=1)

        self._cancel_btn = QPushButton("✕  Cancel")
        self._cancel_btn.setObjectName("cancel_btn")
        self._cancel_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.setMinimumWidth(120)
        self._cancel_btn.clicked.connect(self._cancel)
        btn_layout.addWidget(self._cancel_btn)

        layout.addWidget(btn_row)

        layout.addWidget(_section_header("INSTALLATION HISTORY"))

        self._hist_container = QWidget()
        hist_layout = QVBoxLayout(self._hist_container)
        hist_layout.setContentsMargins(0, 4, 0, 0)
        hist_layout.setSpacing(4)
        self._hist_layout = hist_layout
        layout.addWidget(self._hist_container)

        layout.addStretch()

    def _update_preview(self, *_):
        h = self._hash_input.text().strip()
        if h:
            self._preview_lbl.setText(
                f"→ {CDN_BASE}/{h}-rbxPkgManifest.txt  (+all .zip packages)"
            )
        else:
            self._preview_lbl.clear()

    def _choose_dir(self):
        d = QFileDialog.getExistingDirectory(
            self, "Select Versions folder", str(self._base_dir)
        )
        if not d:
            return
        chosen = Path(d)
        if is_unsafe_dir(chosen):
            QMessageBox.warning(
                self, "Unsafe Directory",
                f"The selected directory is a system folder:\n{chosen}\n\n"
                "Please choose a safe location such as:\n"
                r"C:\Users\<you>\AppData\Local\Roblox\Versions"
            )
            return
        self._base_dir = chosen
        self._dir_lbl.setText(str(self._base_dir))

    def _fetch_latest(self):
        self._log_append("Fetching latest version via WEAO...", PALETTE["warning"])
        self._latest_btn.setEnabled(False)
        worker = VersionFetchWorker("latest")
        worker.signals.result.connect(self._on_fetch_result)
        worker.signals.log.connect(self._log_append)
        worker.finished.connect(lambda: self._latest_btn.setEnabled(True))
        self._fetch_worker = worker
        worker.start()

    def _fetch_previous(self):
        self._log_append("Fetching previous versions via WEAO...", PALETTE["warning"])
        self._prev_btn.setEnabled(False)
        worker = VersionFetchWorker("previous")
        worker.signals.result.connect(self._on_fetch_result)
        worker.signals.log.connect(self._log_append)
        worker.finished.connect(lambda: self._prev_btn.setEnabled(True))
        self._fetch_worker = worker
        worker.start()

    def _on_fetch_result(self, versions: list, mode: str):
        if mode == "latest":
            if versions:
                self._hash_input.setText(versions[0].split()[0])
                self._log_append(f"Latest version: {versions[0].split()[0]}", PALETTE["success"])
            else:
                self._log_append("Could not retrieve version! Check your network.", PALETTE["error"])
            return

        if not versions:
            self._log_append("No previous versions found.", PALETTE["error"])
            return

        self._log_append(f"Found {len(versions)} previous version(s).", PALETTE["success"])

        dlg = QDialog(self)
        dlg.setWindowTitle("Previous Versions  —  WEAO")
        dlg.setMinimumWidth(440)
        dlg.setStyleSheet(
            f"background-color: {PALETTE['bg']}; color: {PALETTE['fg']};"
        )
        v_layout = QVBoxLayout(dlg)
        v_layout.setSpacing(10)

        lbl = QLabel("Select a version to load:")
        lbl.setStyleSheet(f"color: {PALETTE['muted']}; padding-bottom: 4px;")
        v_layout.addWidget(lbl)

        lst = QListWidget()
        lst.setStyleSheet(
            f"background-color: {PALETTE['input_bg']}; "
            f"color: {PALETTE['fg']}; "
            f"border: 1px solid {PALETTE['border']}; "
            f"font-family: Consolas, monospace; font-size: 10pt;"
        )
        for vh in versions:
            lst.addItem(QListWidgetItem(vh))
        v_layout.addWidget(lst)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.setStyleSheet(f"color: {PALETTE['fg']};")
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        v_layout.addWidget(btns)

        if dlg.exec() == QDialog.Accepted and lst.currentItem():
            raw = lst.currentItem().text().split()[0]
            vh  = validate_hash(raw)
            if vh:
                self._hash_input.setText(vh)

    def _on_volume_change(self, value: int):
        self._music.set_volume(value / 100.0)

    def _toggle_music(self):
        if not PYGAME_OK:
            QMessageBox.information(
                self, "Background Music",
                "pygame is not installed.\npip install pygame"
            )
            return
        if not SOUND_FILE.exists():
            QMessageBox.information(
                self, "Background Music",
                f"File not found:\n{SOUND_FILE}\n\n"
                "Place music.mp3 in the sound/ folder.\n"
                "Music button will remain disabled."
            )
            return
        ok = self._music.toggle()
        if ok:
            self._music_btn.setText("🎵" if self._music.is_on else "🔇")

    def _log_append(self, msg: str, color: str = PALETTE["muted"]):
        ts = time.strftime("%H:%M:%S")
        self._log_widget.setTextColor(QColor(color))
        self._log_widget.append(f"[{ts}]  {msg}")
        self._log_widget.ensureCursorVisible()

    def _start_install(self):
        raw = self._hash_input.text()
        vh  = validate_hash(raw)
        if vh is None:
            QMessageBox.critical(
                self, "Invalid Hash",
                "Version hash must be in the format:\n"
                "version-eb4648e9148d440c\n\n"
                "(16 hex characters after the dash)"
            )
            return
        if vh != raw.strip():
            self._hash_input.setText(vh)

        if is_unsafe_dir(self._base_dir):
            QMessageBox.warning(
                self, "Unsafe Install Directory",
                f"The install directory appears to be a system folder:\n{self._base_dir}\n\n"
                "Please change it to a safe location before installing."
            )
            return

        install_dir = self._base_dir / vh

        if install_dir.exists() and any(install_dir.iterdir()):
            reply = QMessageBox.question(
                self, "Already Exists",
                f"This version is already installed at:\n{install_dir}\n\n"
                "Reinstall (overwrite)?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

        self._cancel_evt.clear()
        self._set_busy(True)
        self._reset_progress()
        self._log_append(f"▶ Starting installation of {vh}", PALETTE["warning"])

        self._worker = InstallWorker(
            vh               = vh,
            install_dir      = install_dir,
            cache_dir        = self._cache_dir,
            cancel_evt       = self._cancel_evt,
            register_protocol = self._chk_protocol.isChecked(),
            install_webview2  = self._chk_webview2.isChecked(),
            create_shortcut   = self._chk_shortcut.isChecked(),
        )
        self._worker.signals.log.connect(self._log_append)
        self._worker.signals.progress.connect(self._on_progress)
        self._worker.signals.done.connect(self._on_done)
        self._worker.signals.error.connect(self._on_error)
        self._worker.start()

    def _cancel(self):
        self._cancel_evt.set()
        self._log_append("Cancelling...", PALETTE["warning"])

    def _on_progress(self, pct_total, pkg_name, pkg_pct, speed, eta):
        self._overall_bar.setValue(int(pct_total * 10))
        self._pkg_bar.setValue(int(pkg_pct * 10))
        self._pct_lbl.setText(f"{pct_total:.1f}%")
        self._pkg_lbl.setText(f"  {pkg_name}  ({pkg_pct:.0f}%)")
        if speed > 0:
            self._speed_lbl.setText(fmt_speed(speed))
        if eta > 0:
            m, s = divmod(int(eta), 60)
            self._eta_lbl.setText(f"ETA {m:02d}:{s:02d}")

    def _on_done(self, install_dir):
        self._overall_bar.setValue(1000)
        self._pkg_bar.setValue(1000)
        self._pct_lbl.setText("100%")
        self._log_append(f"✔  Done! → {install_dir}", PALETTE["success"])
        self._set_busy(False)

        vh = install_dir.name
        entry = {"hash": vh, "path": str(install_dir),
                 "time": time.strftime("%Y-%m-%d %H:%M")}
        self._history = [e for e in self._history if e["hash"] != vh]
        self._history.insert(0, entry)
        save_history(self._history)
        self._refresh_history()

        reply = QMessageBox.question(
            self, "Installation Complete!",
            f"Roblox Player is ready!\n\n"
            f"Version: {vh}\n"
            f"Folder:  {install_dir}\n\n"
            "Open the installation folder?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._open_folder(install_dir)

    def _on_error(self, title: str, msg: str):
        self._log_append(f"✘  {title}", PALETTE["error"])
        self._set_busy(False)
        QMessageBox.critical(self, title, msg)

    def _refresh_history(self):
        while self._hist_layout.count():
            item = self._hist_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._history:
            empty = QLabel("No history yet.")
            empty.setStyleSheet(
                f"color: {PALETTE['muted']}; font-size: 10pt; padding: 10px 0;"
            )
            self._hist_layout.addWidget(empty)
            return

        for entry in self._history:
            row = HistoryRow(entry)
            row.reinstall_requested.connect(self._hash_input.setText)
            row.delete_requested.connect(self._delete_history_entry)
            self._hist_layout.addWidget(row)

    def _delete_history_entry(self, version_hash: str):
        entry = next((e for e in self._history if e["hash"] == version_hash), None)
        if not entry:
            return

        path = Path(entry.get("path", ""))
        msg = f"Remove {version_hash} from history?"
        if path.exists():
            msg += f"\n\nAlso delete from disk?\n{path}"
            reply = QMessageBox.question(
                self, "Delete Version", msg,
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            if reply == QMessageBox.Cancel:
                return
            if reply == QMessageBox.Yes:
                try:
                    import shutil
                    shutil.rmtree(str(path), ignore_errors=True)
                    self._log_append(f"Deleted {path}", PALETTE["warning"])
                except Exception as e:
                    self._log_append(f"Delete failed: {e}", PALETTE["error"])
        else:
            reply = QMessageBox.question(
                self, "Remove from History", msg,
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

        self._history = [e for e in self._history if e["hash"] != version_hash]
        save_history(self._history)
        self._refresh_history()

    def _reset_progress(self):
        self._overall_bar.setValue(0)
        self._pkg_bar.setValue(0)
        self._pct_lbl.setText("0%")
        self._speed_lbl.clear()
        self._eta_lbl.clear()
        self._pkg_lbl.clear()

    def _set_busy(self, state: bool):
        if state:
            self._install_btn.setEnabled(False)
            self._install_btn.setText("⏳  Installing...")
            self._cancel_btn.setEnabled(True)
        else:
            self._install_btn.setEnabled(True)
            self._install_btn.setText("⬇  INSTALL ROBLOX PLAYER")
            self._cancel_btn.setEnabled(False)

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

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            reply = QMessageBox.question(
                self, "Installation In Progress",
                "Installation is not finished yet!\nExiting will cancel it. Exit anyway?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                event.ignore()
                return
            self._cancel_evt.set()
            self._worker.wait(3000)
        self._music.quit()
        event.accept()


def main():
    if not REQUESTS_OK:
        app = QApplication(sys.argv)
        QMessageBox.critical(
            None, "Missing Library",
            "The 'requests' library is required.\n\nRun:\n  pip install requests"
        )
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)

    window = App()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
