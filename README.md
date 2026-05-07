# AuroraFetch

A clean, open-source video and audio downloader built with Python and tkinter. Powered by [yt-dlp](https://github.com/yt-dlp/yt-dlp) and [FFmpeg](https://ffmpeg.org/).

AuroraFetch is intended for downloading content you have the legal right to access, including public domain media, Creative Commons content, and personal files. This project does **not** encourage piracy or copyright infringement.

## Features

- Download videos in any available resolution as MP4
- Download audio as MP3 at up to 320 kbps with embedded album art and metadata
- AAC audio encoding for full Windows Media Player compatibility
- Supports YouTube, YouTube Music, and hundreds of other sites via yt-dlp
- Auto-downloads yt-dlp and FFmpeg on first launch — no manual setup required
- Real-time download speed, ETA, and progress bar
- Abort any download mid-way
- English and Turkish language support
- Dark UI theme — no ads, no tracking, no data collection

## Installation

### Option 1 — Run from source

1. Install [Python 3.x](https://www.python.org/downloads/)
2. Install yt-dlp: `pip install yt-dlp`
3. Run:
   ```
   python AuroraFetch.py
   ```

### Option 2 — Windows executable

Download the latest build from [Releases](https://github.com/Nadirisim/AuroraFetch/releases).

You can also compile it yourself with PyInstaller:
```
pip install pyinstaller
pyinstaller --onefile --noconsole AuroraFetch.py
```

## Requirements

- Python 3.8+
- yt-dlp (auto-downloaded if missing)
- FFmpeg (auto-downloaded on Windows if missing)

## Credits

Built on top of [yt-dlp](https://github.com/yt-dlp/yt-dlp) and [FFmpeg](https://github.com/FFmpeg/FFmpeg).

## License

Open source. Contributions and feedback are welcome.
