#  Roblox Version Downloader

A comprehensive tool to download and install Roblox Player directly from the official CDN — supporting custom version selection, smart caching, and an intuitive interface.

---

## ✨ Key Features

- 🌐 **Multi-CDN**: Automatically selects the fastest official server.  
- 📊 **Live Progress**: Displays download speed and Estimated Time of Arrival (ETA).  
- 💾 **Smart Cache**: Uses MD5 hashing to avoid re-downloading existing files.  
- 🕐 **History**: Keeps a log of the last 20 installed versions.  
- 🔗 **Protocol Integration**: Automatically registers `roblox://` protocols.  
- 🎵 **Background Music**: Optional audio feedback while you wait.  
- 📦 **Standalone**: No Python installation required; pre-built as a `.exe`.

---

## 🚀 How to Use

1. Run `RobloxVersionDownloader.exe` with Administrator privileges.  
2. Enter the specific **Version Hash** you need or click **"Latest"**.  
3. Click **⬇ INSTALL ROBLOX PLAYER**.  
4. Wait for completion (approximately 1–2 minutes).  

> [!WARNING]  
> Do not delete or move the `_internal/` folder as it contains the required runtime for the application.

---
 
## 🛠 Troubleshooting
- ❌ App won't start: Check if the _internal folder is missing or if your antivirus is blocking the execution.
- 🌐 Network Errors: Check your internet connection or disable VPN.
- 🔐 Permission Denied: Right-click the app and select "Run as Administrator".
- 🚫 Error 403 Forbidden: The Version Hash is invalid, or the version has been removed from the Roblox CDN.

---

## 🧠 What is a Version Hash?

### It is the unique ID for each Roblox build.

- ✔️ Correct: version-eb4648e9148d440c
- ❌ Incorrect: version-abc123 or 1.2.3

---

## ⚖️ License

- This project is licensed under the MIT License.
- This software is free and should not be sold for profit.
