"""Tk desktop editor. Rendering and transport are isolated from the UI thread."""
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import tempfile
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from app import tool, transport_args
from media import Edit, SOUND, VISUAL


SETTINGS = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".config") / "SoundStickerCreator" / "settings.json"
NUMBERS = [
    ("start", "Inicio visual (s)", "Visual start (s)", float),
    ("duration", "Duración (s)", "Duration (s)", float),
    ("audio_start", "Inicio audio (s)", "Audio start (s)", float),
    ("delay", "Desfase audio (s)", "Audio offset (s)", float),
    ("db", "Volumen (dB)", "Volume (dB)", float),
    ("fade_in", "Fundido entrada (s)", "Fade in (s)", float),
    ("fade_out", "Fundido salida (s)", "Fade out (s)", float),
    ("size", "Resolución (px)", "Resolution (px)", int),
    ("fps", "FPS", "FPS", int),
    ("quality", "Calidad", "Quality", int),
    ("budget", "Tamaño objetivo (bytes)", "Target size (bytes)", int),
    ("loop", "Repeticiones (0 = ∞)", "Loops (0 = ∞)", int),
    ("crop", "Recorte (ancho:alto:x:y)", "Crop (width:height:x:y)", str),
]


class Editor:
    def __init__(self, root, engine, dnd):
        self.root, self.engine, self.dnd = root, engine, dnd
        self.root.geometry("1080x760")
        self.root.minsize(800, 680)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        settings = {}
        try:
            settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
        self.lang = settings.get("lang", "es")
        self.dark = settings.get("dark", True)
        self.recent = settings.get("recent", [])
        self.engine.ffmpeg = settings.get("ffmpeg", self.engine.ffmpeg)
        self.engine.ffprobe = settings.get("ffprobe", self.engine.ffprobe)
        self.ffplay = settings.get("ffplay", tool("ffplay"))
        self.project = None
        self.report = {}
        self.wave = []
        self.visual = tk.StringVar()
        self.audio = tk.StringVar()
        self.status = tk.StringVar()
        self.connection = tk.StringVar()
        self.target = tk.StringVar(value="")
        self.test_account = tk.BooleanVar()
        self.normalize = tk.BooleanVar()
        self.static = tk.BooleanVar()
        self.values = {}
        default = Edit()
        for key, _, _, _ in NUMBERS:
            value = getattr(default, key)
            self.values[key] = tk.StringVar(value="" if value is None else str(value))
        for value in (self.visual, self.audio, self.normalize, self.static, *self.values.values()):
            value.trace_add("write", self.changed)
        self.scratch = tempfile.TemporaryDirectory(prefix="sound-sticker-editor-")
        self.render_number = 0
        self.events = queue.Queue()
        self.busy = False
        self.is_dirty = False
        self.transport = None
        self.audio_process = None
        self.preview = None
        self.preview_image = None
        self.preview_tick = None
        self.frame_times = []
        self.started = 0
        self.build()
        self.poll()

    def tr(self, spanish, english):
        return english if self.lang == "en" else spanish

    def changed(self, *_):
        self.is_dirty = True

    def build(self):
        for child in self.root.winfo_children():
            child.destroy()
        tr = self.tr
        self.root.title("Sound Sticker Creator")
        bg, fg, field, accent, well = (
            ("#141b25", "#e9f0fa", "#222d3c", "#70dfb2", "#0c121a") if self.dark
            else ("#f0f4f8", "#182633", "#ffffff", "#176b50", "#e1e8f0")
        )
        self.well, self.accent = well, accent
        self.root.configure(background=bg)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", background=bg, foreground=fg, font=("Segoe UI", 10))
        style.configure("TEntry", fieldbackground=field, foreground=fg, padding=4)
        style.configure("TButton", padding=(11, 6))
        style.configure("Accent.TButton", background=accent,
                        foreground="#101824" if self.dark else "#ffffff")
        style.configure("Title.TLabel", font=("Segoe UI", 24, "bold"))
        body = ttk.Frame(self.root, padding=22)
        body.pack(fill="both", expand=True)
        bar = ttk.Frame(body)
        bar.pack(fill="x", pady=(0, 12))
        ttk.Label(bar, text="Sound Sticker Creator", style="Title.TLabel").pack(side="left")
        ttk.Button(bar, text=tr("Configuración", "Settings"), command=self.settings).pack(side="right")
        ttk.Button(bar, text=tr("Recientes", "Recent"), command=self.recent_projects).pack(side="right", padx=6)
        inputs = ttk.Frame(body)
        inputs.pack(fill="x", pady=(0, 10))
        inputs.columnconfigure(1, weight=1)
        for row, (label, var, kind) in enumerate([
                (tr("Imagen o video", "Image or video"), self.visual, VISUAL),
                (tr("Audio opcional", "Optional audio"), self.audio, SOUND)]):
            ttk.Label(inputs, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=2)
            entry = ttk.Entry(inputs, textvariable=var)
            entry.grid(row=row, column=1, sticky="ew", pady=2)
            if self.dnd:
                entry.drop_target_register(self.dnd)
                entry.dnd_bind("<<Drop>>", lambda event, slot=var: self.drop(event, slot))
            ttk.Button(inputs, text=tr("Importar", "Import"), command=lambda v=var, k=kind: self.pick(v,k)
                       ).grid(row=row, column=2, padx=(8, 0), pady=2)
        split = ttk.Frame(body)
        split.pack(fill="both", expand=True)
        split.columnconfigure(0, weight=1)
        split.rowconfigure(0, weight=1)
        left = ttk.Frame(split)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 18))
        self.screen = tk.Canvas(left, bg=well, highlightthickness=0, height=230)
        self.screen.pack(fill="both", expand=True)
        self.screen.bind("<Configure>", lambda _: self.draw_frame(0) if self.preview and not self.preview_tick else None)
        if self.dnd:
            self.screen.drop_target_register(self.dnd)
            self.screen.dnd_bind("<<Drop>>", lambda event: self.drop(event))
        self.canvas = tk.Canvas(left, bg=well, highlightthickness=0, height=60)
        self.canvas.pack(fill="x", pady=(8,0))
        self.canvas.bind("<Configure>", lambda _: self.draw_wave())
        self.canvas.bind("<Button-1>", self.scrub)
        commands = ttk.Frame(left)
        commands.pack(fill="x", pady=7)
        ttk.Button(commands, text=tr("Reproducir", "Play"), command=self.play).pack(side="left")
        ttk.Button(commands, text=tr("Detener", "Stop"), command=self.stop).pack(side="left", padx=6)
        self.size_text = ttk.Label(commands)
        self.size_text.pack(side="right")
        right = ttk.Frame(split)
        right.grid(row=0, column=1, sticky="new")
        for row, (key, es, en, _) in enumerate(NUMBERS):
            ttk.Label(right, text=tr(es, en)).grid(row=row, column=0, sticky="w", pady=1)
            ttk.Entry(right, textvariable=self.values[key], width=18).grid(row=row, column=1, padx=(12,0), pady=1)
        ttk.Checkbutton(right, text=tr("Normalizar audio", "Normalize audio"), variable=self.normalize
                        ).grid(row=len(NUMBERS), columnspan=2, sticky="w")
        ttk.Checkbutton(right, text=tr("Sticker estático", "Static sticker"), variable=self.static
                        ).grid(row=len(NUMBERS)+1, columnspan=2, sticky="w")
        bottom = ttk.Frame(body)
        bottom.pack(fill="x", pady=(10,0))
        ttk.Button(bottom, text=tr("Generar", "Generate"), command=self.generate, style="Accent.TButton").pack(side="left")
        ttk.Button(bottom, text=tr("Exportar", "Export"), command=self.export).pack(side="left", padx=8)
        ttk.Button(bottom, text=tr("WhatsApp…", "WhatsApp…"), command=self.send_dialog).pack(side="left")
        ttk.Label(bottom, textvariable=self.connection).pack(side="right")
        self.status.set(tr("Importa medios para comenzar.", "Import media to get started."))
        self.connection.set(tr("WhatsApp desconectado", "WhatsApp disconnected"))
        self.progress = ttk.Progressbar(body, mode="indeterminate")
        self.progress.pack(fill="x", pady=(8,0))
        ttk.Label(body, textvariable=self.status).pack(anchor="w", pady=(5,0))
        self.render_labels()

    def pick(self, var, allowed):
        selected = filedialog.askopenfilename(filetypes=[("Media", " ".join("*"+x for x in allowed))])
        if selected:
            var.set(selected)

    def drop(self, event, slot=None):
        for item in self.root.tk.splitlist(event.data):
            extension = Path(item).suffix.lower()
            if slot is self.audio and extension in SOUND:
                self.audio.set(item)
            elif extension in VISUAL:
                self.visual.set(item)
            elif extension in SOUND:
                self.audio.set(item)

    def generate(self):
        if self.busy:
            return
        try:
            values = {}
            for key, _, _, cast in NUMBERS:
                value = self.values[key].get().strip()
                if key == "crop":
                    values[key] = tuple(map(int, value.split(":"))) if value else None
                elif key == "audio_start" and not value:
                    values[key] = None
                else:
                    values[key] = cast(value)
            edit = Edit(**values, normalize=self.normalize.get(), static=self.static.get())
            edit.validate()
            if not self.visual.get():
                raise ValueError(self.tr("Importa una imagen o video.", "Import an image or video."))
        except ValueError as error:
            self.status.set(str(error))
            return
        self.stop()
        self.render_number += 1
        path = Path(self.scratch.name) / ("render-" + str(self.render_number))
        visual, sound = self.visual.get(), self.audio.get()
        self.busy = True
        self.is_dirty = False
        self.progress.start(18)

        def render():
            try:
                report = self.engine.convert(visual, sound, path, edit, lambda step: self.events.put(("progress", step)))
                waveform = self.engine.waveform(path/"audio.ogg") if report["audioSeconds"] else []
                self.events.put(("rendered", (path, report, waveform)))
            except (ValueError, OSError) as error:
                shutil.rmtree(path, ignore_errors=True)
                self.events.put(("error", str(error)))

        threading.Thread(target=render, daemon=True).start()

    def poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "progress":
                    translations = {"Analizando medios": "Inspecting media", "Procesando imagen": "Processing image",
                                    "Procesando audio": "Processing audio"}
                    self.status.set(self.tr(value, translations.get(value, value)))
                elif kind == "rendered":
                    self.load_project(*value)
                    self.busy = False
                    self.progress.stop()
                elif kind == "error":
                    self.is_dirty = True
                    self.status.set(value)
                    self.busy = False
                    self.progress.stop()
                elif kind == "transport":
                    console, qr_canvas, line = value
                    if console.winfo_exists():
                        if line.startswith("QR:"):
                            self.draw_qr(qr_canvas, json.loads(line[3:]))
                            continue
                        if line.startswith("Escanea"):
                            console.delete("1.0", "end")
                        if line.startswith("Conectado"):
                            qr_canvas.pack_forget()
                            console.delete("1.0", "end")
                            self.connection.set(self.tr("WhatsApp conectado", "WhatsApp connected"))
                        console.insert("end", line)
                        console.see("end")
                elif kind == "transport_done":
                    if value.winfo_exists():
                        value.pack_forget()
                        value.delete("all")
                    self.transport = None
                    self.busy = False
                    self.progress.stop()
                    self.connection.set(self.tr("WhatsApp desconectado", "WhatsApp disconnected"))
        except queue.Empty:
            pass
        self.root.after(50, self.poll)

    def load_project(self, path, report, waveform):
        self.stop()
        previous = self.project
        if self.preview:
            self.preview.close()
        self.project, self.report, self.wave = path, report, waveform
        if previous and previous != path and previous.parent == Path(self.scratch.name):
            shutil.rmtree(previous, ignore_errors=True)
        self.preview = Image.open(path/"sticker.webp")
        elapsed = 0
        self.frame_times = []
        for frame in report["frames"]:
            self.frame_times.append(elapsed)
            elapsed += max(frame["ms"], 1)/1000
        self.render_labels()
        self.draw_frame(0)
        self.draw_wave()
        self.status.set(self.tr("Vista previa lista.", "Preview ready."))

    def render_labels(self):
        if self.report:
            self.size_text.config(text=f"{self.report['width']} × {self.report['height']}  ·  {self.report['bytes']/1024:.1f} KiB")
        else:
            self.screen.create_text(22, 24, anchor="nw", fill=self.accent,
                                    text=self.tr("Importa o suelta archivos aquí", "Import or drop files here"))

    def draw_frame(self, seconds):
        if not self.preview:
            return
        index = sum(t <= seconds for t in self.frame_times) - 1 if self.frame_times else 0
        self.preview.seek(max(index, 0))
        image = self.preview.convert("RGBA")
        image.thumbnail((max(1, self.screen.winfo_width()-8), max(1, self.screen.winfo_height()-8)))
        self.preview_image = ImageTk.PhotoImage(image)
        self.screen.delete("all")
        self.screen.create_image(self.screen.winfo_width()/2, self.screen.winfo_height()/2, image=self.preview_image)

    def total(self):
        return self.report.get("duration_ms", 0)/1000 or self.report.get("audioSeconds") or 0

    def draw_wave(self, timecode=0):
        self.canvas.delete("all")
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        middle = height/2
        self.canvas.create_line(0,middle,width,middle,fill="#607081")
        for i, peak in enumerate(self.wave):
            x = (i+.5)*width/len(self.wave)
            self.canvas.create_line(x,middle-peak*(middle-6),x,middle+peak*(middle-6),fill=self.accent,width=2)
        if self.total():
            x = timecode*width/self.total()
            self.canvas.create_line(x,0,x,height,fill="#f19e52", width=2)
            self.canvas.create_text(width-6, 3, anchor="ne", text=f"{timecode:.2f} / {self.total():.2f} s",
                                    fill=self.accent)

    def scrub(self, event):
        self.stop()
        tick = self.total()*event.x/max(1, self.canvas.winfo_width())
        self.draw_frame(tick)
        self.draw_wave(tick)

    def play(self):
        self.stop()
        if not self.preview:
            return
        if self.wave:
            try:
                self.audio_process = subprocess.Popen([self.ffplay, "-nodisp", "-loglevel", "error", "-autoexit",
                                                       "-protocol_whitelist", "file", str(self.project/"audio.ogg")],
                                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                                      creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            except FileNotFoundError:
                self.status.set(self.tr("Configura FFplay para escuchar audio.", "Set the FFplay path for sound."))
        self.started = time.monotonic()
        self.advance()

    def advance(self):
        elapsed = time.monotonic()-self.started
        self.draw_frame(min(elapsed,self.total()))
        self.draw_wave(min(elapsed,self.total()))
        self.preview_tick = self.root.after(16,self.advance) if elapsed < self.total() else None

    def stop(self):
        if self.preview_tick is not None:
            self.root.after_cancel(self.preview_tick)
            self.preview_tick = None
        if self.audio_process:
            if self.audio_process.poll() is None:
                self.audio_process.terminate()
            self.audio_process.wait()
            self.audio_process = None

    def current(self):
        return not self.busy and self.project is not None and not self.is_dirty

    def export(self):
        if not self.current():
            self.status.set(self.tr("Genera la versión actual primero.", "Generate the current edit first."))
            return
        folder = filedialog.askdirectory()
        if not folder:
            return
        target = Path(folder)/("SoundSticker-"+time.strftime("%Y%m%d-%H%M%S"))
        try:
            shutil.copytree(self.project, target)
            self.recent = [str(target), *[p for p in self.recent if p != str(target)]][:8]
            self.save_settings()
            self.status.set(self.tr("Componentes exportados.", "Components exported."))
        except OSError as error:
            self.status.set(str(error))

    def recent_projects(self):
        modal = tk.Toplevel(self.root)
        modal.title(self.tr("Recientes", "Recent"))
        if not self.recent:
            ttk.Label(modal, text=self.tr("Aún no hay exportaciones.", "No exports yet."), padding=16).pack()
        for path in self.recent:
            ttk.Button(modal, text=Path(path).name, command=lambda p=path: self.reopen(p, modal)).pack(fill="x", padx=8,pady=4)

    def reopen(self, path, modal):
        if self.busy:
            return
        from riff import read
        path = Path(path)
        try:
            report = read(path/"sticker.webp")
            sound = path/"audio.ogg"
            waveform = self.engine.waveform(sound) if sound.is_file() else []
            report["audioSeconds"] = self.engine.duration(self.engine.probe(sound, "ogg"), {}) if waveform else None
            self.load_project(path, report, waveform)
            self.is_dirty = False
            modal.destroy()
        except (ValueError, OSError) as error:
            self.status.set(str(error))

    def send_dialog(self):
        if self.busy:
            return
        tr = self.tr
        dialog = tk.Toplevel(self.root)
        dialog.title("WhatsApp")
        dialog.transient(self.root)
        dialog.grab_set()
        body = ttk.Frame(dialog, padding=16)
        body.pack(fill="both", expand=True)
        self.test_account.set(False)
        ttk.Checkbutton(body, variable=self.test_account, text=tr("Usaré una cuenta de pruebas", "I will use a test account")).pack(anchor="w")
        ttk.Label(body, text=tr("Número internacional del destinatario", "Destination in international format")).pack(anchor="w")
        ttk.Entry(body, textvariable=self.target, width=32).pack(anchor="w", pady=5)
        console = tk.Text(body, height=12, width=62, font=("Consolas", 10), wrap="none", background="#ffffff", foreground="#111111")
        qr_canvas = tk.Canvas(body, background="#ffffff", highlightthickness=0)
        buttons = ttk.Frame(body)
        buttons.pack(fill="x", pady=8)
        for text, action, dest in [(tr("Enviar", "Send"), "send", self.target.get),
                                   (tr("A mí", "To myself"), "send", lambda: "self"),
                                   (tr("Diagnóstico de recepción", "Receive diagnostics"), "receive", lambda: None)]:
            ttk.Button(buttons,text=text,command=lambda a=action,d=dest: self.start_transport(a,d(),console,qr_canvas)).pack(side="left",padx=(0,6))
        console.pack(fill="both", expand=True)

        def close():
            if self.transport and self.transport.poll() is None:
                self.transport.terminate()
            dialog.destroy()
        dialog.protocol("WM_DELETE_WINDOW", close)

    @staticmethod
    def draw_qr(canvas, rows):
        if not (21 <= len(rows) <= 177 and all(len(row) == len(rows) for row in rows)):
            return
        step = max(2, 280 // (len(rows) + 8))
        dimension = step * (len(rows) + 8)
        canvas.delete("all")
        canvas.config(width=dimension, height=dimension)
        for y, row in enumerate(rows, 4):
            for x, value in enumerate(row, 4):
                if value == "1":
                    canvas.create_rectangle(x*step, y*step, (x+1)*step, (y+1)*step,
                                            fill="#000000", width=0)
        canvas.pack(pady=4)

    def start_transport(self, action, dest, console, qr_canvas):
        if self.busy:
            return
        if not self.test_account.get():
            console.insert("end", self.tr("Confirma que usarás una cuenta de pruebas.\n", "Confirm use of a test account.\n"))
            return
        if action == "send" and (not self.current() or not self.report.get("audioSeconds") or not dest):
            console.insert("end", self.tr("Genera un sticker con audio e indica un destinatario.\n",
                                         "Generate a sticker with audio and enter a destination.\n"))
            return
        self.busy = True
        self.progress.start(18)
        self.connection.set(self.tr("Vinculando WhatsApp", "Linking WhatsApp"))
        console.delete("1.0","end")
        command = transport_args(action, self.project, dest) + ["--gui"]

        def relay():
            try:
                with tempfile.TemporaryDirectory(prefix="sound-sticker-transport-") as scratch:
                    env = {**os.environ, "TMPDIR": scratch, "TEMP": scratch, "TMP": scratch, "FORCE_COLOR": "0"}
                    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                            encoding="utf-8", errors="replace", env=env,
                                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    self.transport = proc
                    with proc.stdout:
                        for line in proc.stdout:
                            self.events.put(("transport", (console,qr_canvas,line)))
                    proc.wait()
            except OSError:
                self.events.put(("transport", (console,qr_canvas,self.tr("No se pudo iniciar Node.js.\n","Could not start Node.js.\n"))))
            finally:
                self.events.put(("transport_done",qr_canvas))

        threading.Thread(target=relay, daemon=True).start()

    def save_settings(self):
        SETTINGS.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS.write_text(json.dumps(dict(lang=self.lang, dark=self.dark,recent=self.recent,
                                            ffmpeg=self.engine.ffmpeg,ffprobe=self.engine.ffprobe,
                                            ffplay=self.ffplay)), encoding="utf-8")

    def settings(self):
        if self.busy:
            return
        tr = self.tr
        dialog = tk.Toplevel(self.root)
        dialog.title(tr("Configuración", "Settings"))
        pane = ttk.Frame(dialog,padding=16)
        pane.pack()
        dark, language = tk.BooleanVar(value=self.dark), tk.StringVar(value=self.lang)
        ttk.Checkbutton(pane,text=tr("Tema oscuro","Dark theme"),variable=dark).grid(row=0,columnspan=2,sticky="w")
        ttk.Label(pane,text=tr("Idioma","Language")).grid(row=1,column=0,sticky="w")
        ttk.Combobox(pane,textvariable=language,values=["es","en"],state="readonly").grid(row=1,column=1,sticky="ew")
        vars_ = []
        for row, (name, value) in enumerate([("FFmpeg",self.engine.ffmpeg),("FFprobe",self.engine.ffprobe),("FFplay",self.ffplay)],start=2):
            var = tk.StringVar(value=value)
            vars_.append(var)
            ttk.Label(pane,text=name).grid(row=row,column=0,sticky="w",padx=(0,10),pady=4)
            ttk.Entry(pane,textvariable=var,width=42).grid(row=row,column=1,sticky="ew")

        def save():
            self.lang, self.dark = language.get(), dark.get()
            self.engine.ffmpeg,self.engine.ffprobe,self.ffplay = [v.get() for v in vars_]
            self.save_settings()
            dialog.destroy()
            self.build()
            self.draw_frame(0)

        def reset():
            SETTINGS.unlink(missing_ok=True)
            self.recent.clear()
            dialog.destroy()
            self.status.set(tr("Preferencias y recientes eliminados.","Preferences and recents cleared."))

        ttk.Label(pane,text="Sound Sticker Creator 0.1.0 · MIT").grid(row=5,columnspan=2,sticky="w",pady=8)
        ttk.Button(pane,text=tr("Eliminar preferencias y recientes","Clear preferences and recents"),command=reset).grid(row=6,column=0,padx=(0,8))
        ttk.Button(pane,text=tr("Guardar","Save"),command=save).grid(row=6,column=1,sticky="e")

    def close(self):
        if self.busy:
            messagebox.showinfo("Sound Sticker Creator", self.tr("Espera a que termine la operación activa.",
                                                                  "Wait for the current operation to finish."))
            return
        self.stop()
        if self.preview:
            self.preview.close()
        self.scratch.cleanup()
        self.root.destroy()


def open_editor(engine):
    try:
        from tkinterdnd2 import DND_FILES, TkinterDnD
        root = TkinterDnD.Tk()
    except (ImportError, RuntimeError):
        root, DND_FILES = tk.Tk(), None
    Editor(root,engine,DND_FILES)
    root.mainloop()
