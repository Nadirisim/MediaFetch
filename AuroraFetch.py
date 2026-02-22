import multiprocessing
multiprocessing.freeze_support()

import os, sys, re, shutil, threading, time, json, zipfile, tempfile
import tkinter as tk
import urllib.request
from tkinter import ttk, messagebox, filedialog

# ── Constants ─────────────────────────────────────────────────────────────────
APP_NAME       = "AuroraFetch"
APP_VERSION    = "1.1.0"
APP_GITHUB     = "https://github.com/Nadirisim/AuroraFetch"
APP_ABOUT      = """AuroraFetch is a free, open-source video and audio downloader \
built on top of yt-dlp. It supports YouTube, YouTube Music, and hundreds of \
other websites — all wrapped in a clean, easy-to-use interface.

AuroraFetch is fully opensource and fully written in python.
We are planning to open a website for a free trial.
AuroraFetch does not collect data, in fact we dont even have servers LOL.
AuroraFetch doesnt rely on or really use any servers except for downloading yt-dlp and ffmpeg from their official github repo

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 FEATURES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ▸  Download videos in any available resolution as MP4
  ▸  Download audio as MP3 at up to 320 kbps
  ▸  Automatically embeds album art and metadata into MP3 files
  ▸  AAC audio encoding for full Windows Media Player compatibility
  ▸  Supports YouTube, YouTube Music, youtu.be short links,
     and hundreds of other sites via yt-dlp
  ▸  Auto-updates yt-dlp from GitHub on every launch
  ▸  Auto-downloads ffmpeg — no manual setup required
  ▸  Real-time download speed, ETA, and progress bar
  ▸  Abort any download mid-way with a single click
  ▸  Clean dark UI with no ads, no tracking, no nonsense

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 TECH STACK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Python  •  tkinter  •  yt-dlp  •  ffmpeg

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 LICENSE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  AuroraFetch is open source. Contributions and feedback
  are welcome on GitHub.
"""
FETCH_TIMEOUT  = 20   # seconds before fetch is considered hung

# ── Globals ───────────────────────────────────────────────────────────────────
IS_FROZEN      = getattr(sys, "frozen", False)
yt_dlp         = None
YT_DLP_VERSION = "checking…"
YT_DLP_UPDATED = False
FFMPEG_PATH    = None

if IS_FROZEN:
    APP_DIR = os.path.dirname(sys.executable)
else:
    try:
        APP_DIR = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        APP_DIR = os.getcwd()

DEPS_DIR   = os.path.join(APP_DIR, "ytdl_deps")
YTDLP_EXE  = os.path.join(DEPS_DIR, "yt-dlp.exe" if sys.platform == "win32" else "yt-dlp")
FFMPEG_EXE = os.path.join(DEPS_DIR, "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
YTDLP_VERF = os.path.join(DEPS_DIR, "yt-dlp.version")


# ── Network helpers ───────────────────────────────────────────────────────────

def _http_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "AuroraFetch/1.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())

def _download_file(url, dest, on_progress=None):
    req = urllib.request.Request(url, headers={"User-Agent": "AuroraFetch/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        total = int(r.headers.get("Content-Length", 0))
        done  = 0
        with open(dest, "wb") as f:
            while True:
                chunk = r.read(65536)
                if not chunk: break
                f.write(chunk)
                done += len(chunk)
                if on_progress and total:
                    on_progress(done, total)

def _github_latest(repo):
    return _http_json(f"https://api.github.com/repos/{repo}/releases/latest")["tag_name"]


# ── yt-dlp bootstrap ──────────────────────────────────────────────────────────

def ensure_yt_dlp(on_status=None):
    global yt_dlp, YT_DLP_VERSION, YT_DLP_UPDATED
    os.makedirs(DEPS_DIR, exist_ok=True)

    if on_status: on_status("Checking yt-dlp…")

    try:
        latest_tag = _github_latest("yt-dlp/yt-dlp")
    except Exception:
        latest_tag = None

    try:
        stored = open(YTDLP_VERF).read().strip()
    except Exception:
        stored = None

    need = not os.path.isfile(YTDLP_EXE) or (latest_tag and stored != latest_tag)

    if need:
        tag   = latest_tag or stored or "2025.01.26"
        fname = "yt-dlp.exe" if sys.platform == "win32" else (
                "yt-dlp_macos" if sys.platform == "darwin" else "yt-dlp")
        url   = f"https://github.com/yt-dlp/yt-dlp/releases/download/{tag}/{fname}"
        if on_status: on_status(f"Downloading yt-dlp {tag}…")
        try:
            _download_file(url, YTDLP_EXE)
            if sys.platform != "win32":
                os.chmod(YTDLP_EXE, 0o755)
            open(YTDLP_VERF, "w").write(tag)
            YT_DLP_UPDATED = True
            YT_DLP_VERSION = tag
        except Exception as e:
            if on_status: on_status(f"yt-dlp download failed: {e}")
    else:
        YT_DLP_VERSION = stored or "unknown"

    try:
        import yt_dlp as _ydl
        yt_dlp = _ydl
        YT_DLP_VERSION = _ydl.version.__version__
    except ImportError:
        yt_dlp = None

    if on_status: on_status(f"yt-dlp {YT_DLP_VERSION} ready.")


# ── ffmpeg bootstrap ──────────────────────────────────────────────────────────

def ensure_ffmpeg(on_status=None):
    global FFMPEG_PATH

    if os.path.isfile(FFMPEG_EXE):
        FFMPEG_PATH = FFMPEG_EXE; return

    ff = shutil.which("ffmpeg")
    if ff:
        FFMPEG_PATH = ff; return

    for p in [r"C:\ffmpeg\bin\ffmpeg.exe", r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"]:
        if os.path.isfile(p):
            FFMPEG_PATH = p; return

    if sys.platform != "win32":
        if on_status: on_status("⚠ ffmpeg not found. Install via package manager.")
        return

    if on_status: on_status("Downloading ffmpeg from GitHub…")
    zip_url  = ("https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
                "ffmpeg-master-latest-win64-gpl.zip")
    zip_path = os.path.join(tempfile.gettempdir(), "ffmpeg_dl.zip")
    try:
        _download_file(zip_url, zip_path)
        if on_status: on_status("Extracting ffmpeg…")
        with zipfile.ZipFile(zip_path, "r") as z:
            for member in z.namelist():
                if member.endswith("/bin/ffmpeg.exe"):
                    with z.open(member) as src, open(FFMPEG_EXE, "wb") as dst:
                        dst.write(src.read())
                    break
        try: os.remove(zip_path)
        except: pass
        if os.path.isfile(FFMPEG_EXE):
            FFMPEG_PATH = FFMPEG_EXE
            if on_status: on_status("ffmpeg ready.")
        else:
            if on_status: on_status("ffmpeg extraction failed.")
    except Exception as e:
        if on_status: on_status(f"ffmpeg download failed: {e}")


# ── URL cleaner ───────────────────────────────────────────────────────────────

def clean_url(url):
    url = url.strip().strip(".")
    vid = re.search(r'[?&]v=([a-zA-Z0-9_-]{11})', url)
    if vid: return f"https://www.youtube.com/watch?v={vid.group(1)}"
    ys = re.search(r'https?://youtu\.be/([a-zA-Z0-9_-]{11})', url)
    if ys: return f"https://www.youtube.com/watch?v={ys.group(1)}"
    return url


# ── Main App ──────────────────────────────────────────────────────────────────

class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.geometry("880x790")
        self.root.resizable(True, True)
        self.root.minsize(820, 720)
        self.root.configure(bg="#1e1e2e")
        self.root.eval("tk::PlaceWindow . center")

        self.abort_flag   = threading.Event()
        self.formats      = []
        self.selected_fmt = tk.StringVar()
        self.dl_mode      = tk.StringVar(value="video")
        self.output_dir   = tk.StringVar(value=os.path.expanduser("~/Downloads"))
        self._deps_ready  = False
        self._fetch_timer = None   # used for timeout

        self._apply_styles()
        self._build_ui()
        self._mode_changed()
        self.root.update()

        threading.Thread(target=self._bootstrap, daemon=True).start()
        self.root.mainloop()

    # ── Styles ────────────────────────────────────────────────────────────────

    def _apply_styles(self):
        s = ttk.Style()
        s.theme_use("clam")
        bg, fg, eb = "#1e1e2e", "#cdd6f4", "#313244"
        s.configure("TFrame",       background=bg)
        s.configure("TLabel",       background=bg, foreground=fg, font=("Segoe UI", 10))
        s.configure("TButton",      background=eb, foreground=fg,
                     font=("Segoe UI", 10), borderwidth=0, padding=4)
        s.map("TButton",            background=[("active", "#45475a")])
        s.configure("Accent.TButton", background="#89b4fa", foreground=bg,
                     font=("Segoe UI", 10, "bold"), padding=4)
        s.map("Accent.TButton",     background=[("active", "#74c7ec")])
        s.configure("Danger.TButton", background="#f38ba8", foreground=bg,
                     font=("Segoe UI", 10, "bold"), padding=4)
        s.map("Danger.TButton",     background=[("active", "#eba0ac")])
        s.configure("TEntry",       fieldbackground=eb, foreground=fg,
                     insertcolor=fg, borderwidth=0)
        s.configure("TCombobox",    fieldbackground=eb, foreground=fg,
                     selectbackground="#45475a", borderwidth=0)
        s.map("TCombobox",          fieldbackground=[("readonly", eb)],
              foreground=[("readonly", fg)])
        s.configure("TProgressbar", troughcolor=eb, background="#89b4fa", thickness=22)
        s.configure("TLabelframe",  background=bg, bordercolor="#45475a")
        s.configure("TLabelframe.Label", background=bg, foreground="#89b4fa",
                     font=("Segoe UI", 10, "bold"))
        s.configure("TRadiobutton", background=bg, foreground=fg,
                     font=("Segoe UI", 10), focuscolor=bg)
        s.map("TRadiobutton",       background=[("active", bg)])

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        P = 14

        # ── Menu bar ──────────────────────────────────────────────────────────
        menubar = tk.Menu(self.root, bg="#313244", fg="#cdd6f4",
                          activebackground="#45475a", activeforeground="#cdd6f4",
                          borderwidth=0, relief="flat")
        help_menu = tk.Menu(menubar, tearoff=0, bg="#313244", fg="#cdd6f4",
                             activebackground="#45475a", activeforeground="#cdd6f4")
        help_menu.add_command(label="About AuroraFetch", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)
        self.root.config(menu=menubar)

        # ── Dependency status ─────────────────────────────────────────────────
        dep = ttk.LabelFrame(self.root, text="  Dependency Status  ", padding=10)
        dep.pack(fill="x", padx=P, pady=(P, 6))
        self.lbl_ytdlp  = ttk.Label(dep, text="⏳ Checking yt-dlp…",
                                     foreground="#f9e2af", font=("Segoe UI", 9))
        self.lbl_ytdlp.pack(anchor="w")
        self.lbl_ffmpeg = ttk.Label(dep, text="⏳ Checking ffmpeg…",
                                     foreground="#f9e2af", font=("Segoe UI", 9))
        self.lbl_ffmpeg.pack(anchor="w")
        self.dep_pbar = ttk.Progressbar(dep, mode="indeterminate", length=300)
        self.dep_pbar.pack(anchor="w", pady=(6, 0))
        self.dep_pbar.start(10)

        # ── URL ───────────────────────────────────────────────────────────────
        uf = ttk.LabelFrame(self.root, text="  Video URL  ", padding=10)
        uf.pack(fill="x", padx=P, pady=6)
        ur = ttk.Frame(uf); ur.pack(fill="x")
        self.url_entry = ttk.Entry(ur, font=("Segoe UI", 10))
        self.url_entry.pack(side="left", fill="x", expand=True, ipady=5)
        self.url_entry.insert(0, "Paste URL here…")
        self.url_entry.config(foreground="#6c7086")
        self.url_entry.bind("<FocusIn>",  self._clr_ph)
        self.url_entry.bind("<FocusOut>", self._rst_ph)
        self.fetch_btn = ttk.Button(ur, text="  Fetch Info  ", style="Accent.TButton",
                                    command=self._fetch_thread)
        self.fetch_btn.pack(side="left", padx=(10, 0), ipady=3)

        # ── Mode ──────────────────────────────────────────────────────────────
        mf = ttk.LabelFrame(self.root, text="  Download Mode  ", padding=10)
        mf.pack(fill="x", padx=P, pady=6)
        mr = ttk.Frame(mf); mr.pack(anchor="w")
        ttk.Radiobutton(mr, text="Video (MP4)", variable=self.dl_mode,
                         value="video", command=self._mode_changed).pack(side="left", padx=(0, 24))
        ttk.Radiobutton(mr, text="MP3 (audio only)", variable=self.dl_mode,
                         value="mp3", command=self._mode_changed).pack(side="left")
        self.mode_note = ttk.Label(mf, foreground="#6c7086",
                                    font=("Segoe UI", 9), wraplength=820)
        self.mode_note.pack(anchor="w", pady=(6, 0))

        # ── Video Info ────────────────────────────────────────────────────────
        inf = ttk.LabelFrame(self.root, text="  Video Info  ", padding=10)
        inf.pack(fill="x", padx=P, pady=6)
        tr = ttk.Frame(inf); tr.pack(fill="x")
        ttk.Label(tr, text="Title:", width=10).pack(side="left")
        self.lbl_title = ttk.Label(tr, text="—", foreground="#a6e3a1",
                                    font=("Segoe UI", 10, "bold"),
                                    wraplength=720, justify="left")
        self.lbl_title.pack(side="left", fill="x", expand=True)
        dr = ttk.Frame(inf); dr.pack(fill="x", pady=(4, 0))
        ttk.Label(dr, text="Duration:", width=10).pack(side="left")
        self.lbl_dur = ttk.Label(dr, text="—")
        self.lbl_dur.pack(side="left")

        # ── Options ───────────────────────────────────────────────────────────
        of = ttk.LabelFrame(self.root, text="  Options  ", padding=10)
        of.pack(fill="x", padx=P, pady=6)
        rr = ttk.Frame(of); rr.pack(fill="x", pady=(0, 8))
        self.lbl_res = ttk.Label(rr, text="Resolution:", width=10)
        self.lbl_res.pack(side="left")
        self.res_combo = ttk.Combobox(rr, textvariable=self.selected_fmt,
                                       state="readonly", font=("Segoe UI", 10))
        self.res_combo.pack(side="left", fill="x", expand=True, ipady=4)
        xr = ttk.Frame(of); xr.pack(fill="x")
        ttk.Label(xr, text="Save to:", width=10).pack(side="left")
        ttk.Entry(xr, textvariable=self.output_dir,
                  font=("Segoe UI", 9)).pack(side="left", fill="x", expand=True, ipady=4)
        ttk.Button(xr, text="Browse",
                   command=self._browse).pack(side="left", padx=(8, 0), ipady=3)

        # ── Download / Abort ──────────────────────────────────────────────────
        bf = ttk.Frame(self.root); bf.pack(fill="x", padx=P, pady=8)
        self.dl_btn = ttk.Button(bf, text="⬇  Download", style="Accent.TButton",
                                  command=self._start_dl)
        self.dl_btn.pack(side="left", fill="x", expand=True, ipady=7, padx=(0, 8))
        self.abort_btn = ttk.Button(bf, text="✖  Abort", style="Danger.TButton",
                                     command=self._abort, state="disabled")
        self.abort_btn.pack(side="left", fill="x", expand=True, ipady=7)

        # ── Progress ──────────────────────────────────────────────────────────
        pf = ttk.LabelFrame(self.root, text="  Progress  ", padding=12)
        pf.pack(fill="x", padx=P, pady=(0, P))
        self.pbar = ttk.Progressbar(pf, orient="horizontal",
                                     mode="determinate", maximum=100)
        self.pbar.pack(fill="x", pady=(0, 8))
        sr = ttk.Frame(pf); sr.pack(fill="x")
        self.lbl_pct  = ttk.Label(sr, text="0%",       font=("Segoe UI", 11, "bold"),
                                    foreground="#89b4fa", width=7)
        self.lbl_spd  = ttk.Label(sr, text="Speed: —", foreground="#f9e2af",
                                    font=("Segoe UI", 10), width=20)
        self.lbl_eta  = ttk.Label(sr, text="ETA: —",   foreground="#a6e3a1",
                                    font=("Segoe UI", 10), width=14)
        self.lbl_size = ttk.Label(sr, text="Size: —",  foreground="#cba6f7",
                                    font=("Segoe UI", 10))
        for w in (self.lbl_pct, self.lbl_spd, self.lbl_eta, self.lbl_size):
            w.pack(side="left")
        self.lbl_status = ttk.Label(pf, text="Waiting for dependencies…",
                                     foreground="#6c7086", font=("Segoe UI", 9),
                                     wraplength=840, justify="left")
        self.lbl_status.pack(anchor="w", pady=(8, 0))

    # ── About dialog ─────────────────────────────────────────────────────────

    def _show_about(self):
        win = tk.Toplevel(self.root)
        win.title(f"About {APP_NAME}")
        win.geometry("560x560")
        win.resizable(False, False)
        win.configure(bg="#1e1e2e")
        win.transient(self.root)
        win.lift()
        win.focus_force()

        # Center manually
        win.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width()  // 2) - 280
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 280
        win.geometry(f"560x560+{x}+{y}")

        # Header
        tk.Label(win, text=APP_NAME, bg="#1e1e2e", fg="#89b4fa",
                 font=("Segoe UI", 18, "bold")).pack(pady=(20, 2))
        tk.Label(win, text=f"Version {APP_VERSION}",
                 bg="#1e1e2e", fg="#6c7086",
                 font=("Segoe UI", 10)).pack()

        tk.Frame(win, bg="#45475a", height=1).pack(fill="x", padx=20, pady=10)

        # Scrollable text area
        txt_frame = tk.Frame(win, bg="#313244")
        txt_frame.pack(fill="both", expand=True, padx=20)

        scrollbar = tk.Scrollbar(txt_frame)
        scrollbar.pack(side="right", fill="y")

        txt = tk.Text(
            txt_frame,
            bg="#313244", fg="#cdd6f4",
            font=("Segoe UI", 9),
            wrap="word", relief="flat", bd=0,
            padx=12, pady=10,
            cursor="arrow",
            yscrollcommand=scrollbar.set,
        )
        txt.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=txt.yview)

        # Must insert text AFTER the widget is packed and window is updated
        win.update()
        txt.insert("1.0", APP_ABOUT)
        txt.config(state="disabled")

        tk.Frame(win, bg="#45475a", height=1).pack(fill="x", padx=20, pady=(10, 6))

        # GitHub
        gh_row = tk.Frame(win, bg="#1e1e2e")
        gh_row.pack()
        tk.Label(gh_row, text="GitHub:", bg="#1e1e2e", fg="#6c7086",
                 font=("Segoe UI", 9)).pack(side="left")
        lnk = tk.Label(gh_row, text=APP_GITHUB, bg="#1e1e2e", fg="#89b4fa",
                       font=("Segoe UI", 9, "underline"), cursor="hand2")
        lnk.pack(side="left", padx=(4, 0))
        lnk.bind("<Button-1>", lambda _: self._open_url(APP_GITHUB))

        # Footer
        ff = "found" if FFMPEG_PATH else "not found"
        tk.Label(win,
                 text=f"yt-dlp {YT_DLP_VERSION}   •   ffmpeg: {ff}",
                 bg="#1e1e2e", fg="#585b70",
                 font=("Segoe UI", 8)).pack(pady=(6, 4))

        ttk.Button(win, text="Close", command=win.destroy).pack(pady=(0, 14))

    def _open_url(self, url):
        import webbrowser
        webbrowser.open(url)

    # ── Bootstrap ────────────────────────────────────────────────────────────

    def _bootstrap(self):
        ensure_yt_dlp(on_status=self._safe_status)
        ensure_ffmpeg(on_status=self._safe_status)
        self.root.after(0, self._bootstrap_done)

    def _safe_status(self, msg):
        self.root.after(0, lambda: self.lbl_status.config(text=msg, foreground="#f9e2af"))

    def _bootstrap_done(self):
        self._deps_ready = True
        self.dep_pbar.stop()
        self.dep_pbar.pack_forget()

        if yt_dlp is None:
            self.lbl_ytdlp.config(text="✘ yt-dlp not available — restart app",
                                   foreground="#f38ba8")
        else:
            c = "#f9e2af" if YT_DLP_UPDATED else "#a6e3a1"
            s = " (just updated!)" if YT_DLP_UPDATED else " (up to date)"
            self.lbl_ytdlp.config(text=f"✔ yt-dlp {YT_DLP_VERSION}{s}", foreground=c)

        if FFMPEG_PATH:
            self.lbl_ffmpeg.config(text=f"✔ ffmpeg: {FFMPEG_PATH}", foreground="#a6e3a1")
        else:
            self.lbl_ffmpeg.config(
                text="⚠ ffmpeg not available — MP3 and high-res merging disabled",
                foreground="#f38ba8")

        self.lbl_status.config(text="Ready.", foreground="#6c7086")

    # ── Placeholder ───────────────────────────────────────────────────────────

    def _clr_ph(self, _=None):
        if self.url_entry.get() == "Paste URL here…":
            self.url_entry.delete(0, "end")
            self.url_entry.config(foreground="#cdd6f4")

    def _rst_ph(self, _=None):
        if not self.url_entry.get().strip():
            self.url_entry.insert(0, "Paste URL here…")
            self.url_entry.config(foreground="#6c7086")

    # ── Mode ──────────────────────────────────────────────────────────────────

    def _mode_changed(self):
        if self.dl_mode.get() == "mp3":
            self.lbl_res.config(text="Quality:")
            self.mode_note.config(
                text="MP3 mode: extracts audio only, converts to MP3, "
                     "embeds thumbnail & metadata. Requires ffmpeg.")
            self.res_combo.config(values=[
                "320 kbps (best quality)", "256 kbps", "192 kbps",
                "128 kbps", "96 kbps (smallest file)"])
            self.res_combo.current(0)
        else:
            self.lbl_res.config(text="Resolution:")
            self.mode_note.config(
                text="Video mode: downloads video + audio merged into MP4 "
                     "with AAC audio (Windows Media Player compatible).")
            if self.formats:
                self.res_combo.config(values=[c[1] for c in self.formats])
                self.res_combo.current(0)
            else:
                self.res_combo.set("")
                self.res_combo.config(values=[])

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _browse(self):
        d = filedialog.askdirectory(initialdir=self.output_dir.get())
        if d: self.output_dir.set(d)

    def _setstatus(self, msg, color="#6c7086"):
        self.root.after(0, lambda: self.lbl_status.config(text=msg, foreground=color))

    # ── Fetch info with timeout ───────────────────────────────────────────────

    def _fetch_thread(self):
        if not self._deps_ready:
            messagebox.showinfo("Please wait", "Dependencies are still loading.")
            return
        if yt_dlp is None:
            messagebox.showerror("yt-dlp missing", "yt-dlp not available. Restart the app.")
            return
        url = self.url_entry.get().strip()
        if not url or url == "Paste URL here…":
            messagebox.showwarning("No URL", "Please paste a URL first.")
            return

        self.fetch_btn.config(state="disabled")
        self._setstatus("Fetching video info…", "#f9e2af")

        # Start timeout timer
        self._fetch_timed_out = False
        self._fetch_timer = self.root.after(
            FETCH_TIMEOUT * 1000, self._fetch_timeout
        )

        threading.Thread(target=self._fetch_worker, args=(url,), daemon=True).start()

    def _fetch_timeout(self):
        """Called if fetch takes longer than FETCH_TIMEOUT seconds."""
        self._fetch_timed_out = True
        self._setstatus(
            f"Fetch timed out after {FETCH_TIMEOUT}s — check your connection or URL.",
            "#f38ba8"
        )
        self.fetch_btn.config(state="normal")

    def _cancel_fetch_timer(self):
        if self._fetch_timer is not None:
            self.root.after_cancel(self._fetch_timer)
            self._fetch_timer = None

    def _fetch_worker(self, raw_url):
        url = clean_url(raw_url)
        try:
            opts = {"quiet": True, "no_warnings": True, "skip_download": True}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)

            # If timeout already fired, discard result silently
            if self._fetch_timed_out:
                return

            if not info:
                raise ValueError("No info returned — check the URL.")

            title  = info.get("title", "Unknown")
            dur_s  = info.get("duration") or 0
            dur_st = time.strftime("%H:%M:%S", time.gmtime(dur_s)) if dur_s else "—"

            seen, choices = set(), [("best", "Best (auto-selected)")]
            for f in sorted(info.get("formats", []),
                            key=lambda x: x.get("height") or 0, reverse=True):
                h   = f.get("height")
                vc  = f.get("vcodec", "none")
                ext = f.get("ext", "?")
                fid = f.get("format_id", "")
                fps = f.get("fps")
                fsz = f.get("filesize") or f.get("filesize_approx")
                if not h or vc in ("none", None): continue
                if (h, ext) in seen: continue
                seen.add((h, ext))
                fps_s = f" {int(fps)}fps" if fps else ""
                sz_s  = f"  ~{fsz/1_048_576:.0f} MB" if fsz else ""
                warn  = "  ⚠ needs ffmpeg" if not FFMPEG_PATH and h > 720 else ""
                choices.append((fid, f"{h}p{fps_s}  [{ext}]{sz_s}{warn}  (id:{fid})"))

            self.root.after(0, lambda: self._fetch_done(title, dur_st, choices))
        except Exception as e:
            if self._fetch_timed_out:
                return
            err = str(e)
            self.root.after(0, lambda: self._fetch_err(err))

    def _fetch_done(self, title, dur_st, choices):
        self._cancel_fetch_timer()
        self.formats = choices
        self.lbl_title.config(text=title)
        self.lbl_dur.config(text=dur_st)
        if self.dl_mode.get() == "video":
            self.res_combo.config(values=[c[1] for c in choices])
            self.res_combo.current(0)
        self._setstatus("Info fetched — select options and click Download.", "#a6e3a1")
        self.fetch_btn.config(state="normal")

    def _fetch_err(self, err):
        self._cancel_fetch_timer()
        self._setstatus(f"Error: {err}", "#f38ba8")
        messagebox.showerror("Fetch Error", f"Could not fetch video info:\n\n{err}")
        self.fetch_btn.config(state="normal")

    # ── Download ──────────────────────────────────────────────────────────────

    def _start_dl(self):
        if not self._deps_ready:
            messagebox.showinfo("Please wait", "Dependencies are still loading.")
            return
        if yt_dlp is None:
            messagebox.showerror("yt-dlp missing", "yt-dlp not available. Restart the app.")
            return
        url = self.url_entry.get().strip()
        if not url or url == "Paste URL here…":
            messagebox.showwarning("No URL", "Please paste a URL first.")
            return
        mode = self.dl_mode.get()
        if mode == "video" and not self.formats:
            messagebox.showwarning("No Format", "Please fetch video info first.")
            return
        if mode == "mp3" and not FFMPEG_PATH:
            messagebox.showerror("ffmpeg Required",
                "ffmpeg was not found or could not be downloaded.\n"
                "Check your internet connection and restart the app.")
            return

        idx = self.res_combo.current()
        out = self.output_dir.get()
        self.abort_flag.clear()
        self.dl_btn.config(state="disabled")
        self.abort_btn.config(state="normal")
        self.pbar["value"] = 0
        for lbl, txt in [(self.lbl_pct,"0%"), (self.lbl_spd,"Speed: —"),
                          (self.lbl_eta,"ETA: —"), (self.lbl_size,"Size: —")]:
            lbl.config(text=txt)

        if mode == "mp3":
            br = ["320","256","192","128","96"][max(idx, 0)]
            self._setstatus(f"Starting MP3 download at {br} kbps…", "#89b4fa")
            t = threading.Thread(target=self._dl_mp3,
                                  args=(clean_url(url), br, out), daemon=True)
        else:
            fid = self.formats[idx][0] if idx >= 0 and self.formats else "best"
            self._setstatus("Starting video download…", "#89b4fa")
            t = threading.Thread(target=self._dl_video,
                                  args=(clean_url(url), fid, out), daemon=True)
        t.start()

    # ── Progress hook ─────────────────────────────────────────────────────────

    def _hook(self):
        def h(d):
            if self.abort_flag.is_set():
                raise Exception("Download aborted by user.")
            if d["status"] == "downloading":
                dl  = d.get("downloaded_bytes", 0)
                tot = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                spd = d.get("speed") or 0
                eta = d.get("eta") or 0
                pct = (dl / tot * 100) if tot else 0
                sm  = spd / 1_048_576
                es  = time.strftime("%M:%S", time.gmtime(eta)) if eta else "—"
                ss  = f"{tot/1_048_576:.1f} MB" if tot else "—"
                def upd():
                    self.pbar["value"] = pct
                    self.lbl_pct.config(text=f"{pct:.1f}%")
                    self.lbl_spd.config(text=f"Speed: {sm:.2f} MB/s")
                    self.lbl_eta.config(text=f"ETA: {es}")
                    self.lbl_size.config(text=f"Size: {ss}")
                    self._setstatus(f"Downloading… {pct:.1f}%", "#89b4fa")
                self.root.after(0, upd)
            elif d["status"] == "finished":
                self.root.after(0, lambda: self._setstatus("Post-processing…", "#f9e2af"))
        return h

    # ── Video download ────────────────────────────────────────────────────────

    def _dl_video(self, url, fid, out):
        fmt = ("bestvideo+bestaudio/best" if FFMPEG_PATH else "best") if fid == "best" \
              else (f"{fid}+bestaudio/best" if FFMPEG_PATH else fid)
        opts = {
            "format": fmt,
            "outtmpl": os.path.join(out, "%(title)s.%(ext)s"),
            "progress_hooks": [self._hook()],
            "quiet": True, "no_warnings": True,
        }
        if FFMPEG_PATH:
            opts["ffmpeg_location"]     = os.path.dirname(FFMPEG_PATH)
            opts["merge_output_format"] = "mp4"
            opts["postprocessor_args"]  = {
                "merger": ["-c:v","copy","-c:a","aac","-b:a","192k"]}
        self._run(opts, url, "Video")

    # ── MP3 download ──────────────────────────────────────────────────────────

    def _dl_mp3(self, url, bitrate, out):
        opts = {
            "format": "bestaudio/best",
            "outtmpl": os.path.join(out, "%(title)s.%(ext)s"),
            "progress_hooks": [self._hook()],
            "quiet": True, "no_warnings": True,
            "ffmpeg_location": os.path.dirname(FFMPEG_PATH),
            "writethumbnail": True,
            "postprocessors": [
                {"key": "FFmpegExtractAudio",
                 "preferredcodec": "mp3", "preferredquality": bitrate},
                {"key": "FFmpegMetadata", "add_metadata": True},
                {"key": "EmbedThumbnail"},
            ],
        }
        self._run(opts, url, "MP3")

    # ── Shared runner ─────────────────────────────────────────────────────────

    def _run(self, opts, url, label):
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
            if not self.abort_flag.is_set():
                self.root.after(0, lambda: self._done(label))
        except Exception as e:
            err = str(e)
            if "aborted" in err.lower():
                self.root.after(0, lambda: self._setstatus("Download aborted.", "#f38ba8"))
            else:
                self.root.after(0, lambda: self._setstatus(f"Error: {err}", "#f38ba8"))
                self.root.after(0, lambda: messagebox.showerror("Download Error", err))
        finally:
            self.root.after(0, self._reset)

    def _done(self, label):
        self.pbar["value"] = 100
        self.lbl_pct.config(text="100%")
        self._setstatus(f"✔ {label} download complete!", "#a6e3a1")
        messagebox.showinfo("Done", f"{label} saved to:\n{self.output_dir.get()}")

    def _abort(self):
        self.abort_flag.set()
        self._setstatus("Aborting…", "#f38ba8")

    def _reset(self):
        self.dl_btn.config(state="normal")
        self.abort_btn.config(state="disabled")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    App()
