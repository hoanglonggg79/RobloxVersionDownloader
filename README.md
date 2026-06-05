# 📦 Roblox Version Downloader v1.2.0

A comprehensive tool to download and install any version of Roblox Player directly from the official CDN — with smart caching, resumable downloads, version browsing, and a modern PySide6 interface.

---

## ✨ Key Features

- 🌐 **Multi-CDN**: Probes all 5 CDN endpoints **concurrently** and picks the fastest automatically.
- 📊 **Live Progress**: Dual progress bars with real-time download speed and ETA.
- 💾 **Smart Cache**: MD5 verification avoids re-downloading intact files.
- ⏸️ **Resumable Downloads**: Uses HTTP `Range` headers to continue interrupted downloads without starting over.
- 📜 **Version Browser**: "Previous" button fetches recent versions from the WEAO API; falls back to `DeployHistory.txt`.
- 🕐 **History Panel**: Keeps a log of the last 20 installs — reload, open folder, or delete from disk in one click.
- 🔗 **Protocol Integration**: Registers `roblox://` and `roblox-player://` URI schemes in the Windows Registry.
- 🖥️ **Desktop Shortcut**: Optionally creates a `.lnk` shortcut to `RobloxPlayerBeta.exe` after install.
- 🎵 **Background Music**: Optional MP3 playback with a live volume slider and toggle button.
- 🗑️ **Delete Installs**: Remove old versions from history and disk directly from the UI.

---

## 🚀 How to Use

### Running from source

```bash
# 1. Install required libraries
pip install PySide6 requests

# Optional extras
pip install pygame winshell

# 2. Run
python RobloxVersionDownloader.py
```

### Steps inside the app

1. Click **"Latest"** to auto-fill the current version hash, or **"Previous"** to browse older builds.
2. Confirm the **install directory** (default: `%LOCALAPPDATA%\Roblox\Versions\`).
3. Configure **Options** (protocol registration, WebView2, desktop shortcut).
4. Click **⬇ INSTALL ROBLOX PLAYER** and wait.

> [!TIP]
> If a download is interrupted, just click Install again — it will resume from where it left off.

---

## 📂 File Structure

```
RobloxVersionDownloader/
├── RobloxVersionDownloader.py
├── sound/
│    └── music.mp3          <- Optional background music
├── icon.ico                <- Optional window icon
└── download_history.json   <- Auto-generated; stores last 20 installs
```

Cache (downloaded `.zip` packages) is stored separately at:

```
%LOCALAPPDATA%\Roblox\Downloads\
```

---

## ⚙️ Options Panel

| Option | Default | Description |
|---|---|---|
| Register `roblox://` protocol | ✅ On | Writes `HKCU\Software\Classes\roblox` and `roblox-player` registry keys |
| Install WebView2 Runtime | ☐ Off | Silently runs the WebView2 installer extracted from the downloaded package |
| Create Desktop Shortcut | ☐ Off | Places a `.lnk` on the Desktop pointing to `RobloxPlayerBeta.exe` |

---

## 🧠 What is a Version Hash?

Each Roblox build has a unique hash used to locate its files on the CDN.

| | Example |
|---|---|
| ✅ Valid | `version-eb4648e9148d440c` |
| ✅ Also valid | `eb4648e9148d440c` (prefix added automatically) |
| ❌ Invalid | `version-abc123` (fewer than 16 hex characters) |
| ❌ Invalid | `1.2.3.4567` (version number format) |

**Ways to find a hash:**
- Click **"Latest"** in the app — fetches the current live hash automatically.
- Click **"Previous"** — browse recent builds from the WEAO API.
- Check `%LOCALAPPDATA%\Roblox\Versions\` — subdirectory names are existing hashes.
- API: `https://clientsettingscdn.roblox.com/v2/client-version/WindowsPlayer`

---

## 🛠 Troubleshooting

| Problem | Solution |
|---|---|
| `ModuleNotFoundError: No module named 'PySide6'` | Run `pip install PySide6` |
| `ModuleNotFoundError: No module named 'requests'` | Run `pip install requests` |
| **Version Not Found** (404) | The hash is wrong or no longer on the CDN. Use "Latest" or "Previous" to get a valid hash. |
| **Connection Lost** | Check your internet connection. Simply retry — downloads resume automatically. |
| **Checksum Failed** (MD5 mismatch) | File was corrupted; the bad cache is deleted automatically. Retry to re-download. |
| **Write Permission Error** | Run as Administrator or choose a directory where your user has write access. |
| Music won't play | Install `pip install pygame` and place `music.mp3` in the `sound/` folder. |
| Desktop shortcut not created | Install `pip install winshell` or ensure PowerShell scripts are not blocked by execution policy. |

---

## 📚 Libraries & APIs Used

### Python Libraries

| Library | Role | License |
|---|---|---|
| [PySide6](https://pypi.org/project/PySide6/) | GUI framework (Qt6 widgets, signals/slots, threading) | LGPL v3 |
| [requests](https://pypi.org/project/requests/) | HTTP downloads, CDN probing, API calls | Apache 2.0 |
| [pygame](https://pypi.org/project/pygame/) | Background music playback (optional) | LGPL |
| [winshell](https://pypi.org/project/winshell/) | Desktop shortcut creation on Windows (optional) | MIT |
| `hashlib` | MD5 checksum verification | Python stdlib |
| `zipfile` | Package extraction | Python stdlib |
| `winreg` | Windows Registry access for `roblox://` protocol | Python stdlib (Windows only) |
| `concurrent.futures` | Parallel CDN probing via `ThreadPoolExecutor` | Python stdlib |

### External APIs & CDNs

| Service | URL | Usage |
|---|---|---|
| Roblox CDN (primary) | `https://setup.rbxcdn.com` | Downloads manifests and all `.zip` packages |
| Roblox CDN (fallback × 4) | `setup-ak`, `setup-cf`, `roblox-setup.cachefly.net`, `s3.amazonaws.com/setup.roblox.com` | Automatic fallback if primary CDN is slow |
| Roblox Client Settings API | `https://clientsettingscdn.roblox.com/v2/client-version/WindowsPlayer` | Fallback for fetching the latest version hash |
| **WEAO API** (current) | `https://weao.xyz/api/versions/current` | Primary source for the "Latest" button |
| **WEAO API** (past) | `https://weao.xyz/api/versions/past` | Primary source for the "Previous" version browser |

> [!NOTE]
> WEAO ([weao.xyz](https://weao.xyz)) is a third-party Roblox version tracking service. The app uses it with the `User-Agent: WEAO-3PService` header as recommended. If WEAO is unavailable, the app falls back to the official Roblox API or `DeployHistory.txt`.

---

## ⚖️ License

This project is licensed under the **MIT License** — free to use, modify, and distribute. This software should not be sold for profit.

---

*By HoangLong · v1.2.0*
