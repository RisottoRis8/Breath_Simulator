"""
PROJECT VIOLET - Adult Breathing Simulator GUI
Design and development of an adult breathing simulator
Tutor: Matteo Mentasti - Politecnico di Milano
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import math
import random
from collections import deque
import json
import os
from datetime import datetime

# ─── Color Palette ───────────────────────────────────────────────
BG_DARK      = "#0D1117"
BG_PANEL     = "#161B22"
BG_CARD      = "#1C2333"
ACCENT_VIOLET= "#7C3AED"
ACCENT_CYAN  = "#06B6D4"
ACCENT_GREEN = "#10B981"
ACCENT_RED   = "#EF4444"
ACCENT_AMBER = "#F59E0B"
TEXT_PRIMARY = "#F0F6FF"
TEXT_MUTED   = "#8B949E"
BORDER       = "#30363D"

# ─── Simulated Serial / BLE data layer ───────────────────────────
class DataSource:
    """Simulates incoming data from µC via BLE/UART.
    Replace read_frame() with real serial/BLE calls."""
    def __init__(self):
        self.t = 0.0
        self.mode = "SINE"       # SINE | STEADY | INVIVO
        self.freq = 0.25         # Hz
        self.amp  = 500.0        # mL
        self.pressure_offset = 0.0
        self.connected = False
        self._motor_rpm = 0.0
        self._encoder_pos = 0.0

    def connect(self, port="BLE"):
        time.sleep(0.5)
        self.connected = True

    def disconnect(self):
        self.connected = False

    def read_frame(self):
        """Returns dict with all sensor values."""
        self.t += 0.05
        dt = self.t

        if self.mode == "SINE":
            flow = self.amp * math.sin(2 * math.pi * self.freq * dt)
        elif self.mode == "STEADY":
            flow = self.amp
        else:  # INVIVO
            # Asymmetric lung-like waveform
            phase = (dt * self.freq) % 1.0
            if phase < 0.4:
                flow = self.amp * math.sin(math.pi * phase / 0.4)
            else:
                flow = -self.amp * 0.6 * math.sin(math.pi * (phase - 0.4) / 0.6)

        # Syringe volume (integrate flow)
        volume = (self.amp / (2 * math.pi * self.freq + 1e-9)) * \
                  math.sin(2 * math.pi * self.freq * dt) * 0.05 + self.amp * 0.5

        press1 = 5.0 + flow / 100.0 + random.gauss(0, 0.05)
        press2 = 2.0 + flow / 150.0 + random.gauss(0, 0.03)
        rpm    = abs(flow) / self.amp * 3000 + random.gauss(0, 5)
        enc    = (self.t * rpm / 60 * 1000) % 65535

        self.t += 0              # already incremented above
        return {
            "timestamp": round(self.t, 3),
            "flow_lpm":  round(flow / 1000 * 60, 3),   # mL/s → L/min
            "volume_ml": round(abs(volume), 1),
            "press1_cmH2O": round(press1, 2),
            "press2_cmH2O": round(press2, 2),
            "motor_rpm":    round(rpm, 1),
            "encoder_cts":  int(enc),
            "sw1": int(abs(flow) > self.amp * 0.98),
            "sw2": int(abs(flow) > self.amp * 0.5),
        }


# ─── Scrolling Chart (pure tkinter Canvas) ───────────────────────
class ScrollingChart(tk.Canvas):
    def __init__(self, parent, label, unit, color, ymin, ymax,
                 width=500, height=130, maxpts=300, **kw):
        super().__init__(parent, width=width, height=height,
                         bg=BG_CARD, highlightthickness=0, **kw)
        self.label  = label
        self.unit   = unit
        self.color  = color
        self.ymin   = ymin
        self.ymax   = ymax
        self.maxpts = maxpts
        self.data   = deque(maxlen=maxpts)
        self.W      = width   # updated on <Configure>
        self.H      = height
        self.bind("<Configure>", self._on_resize)

    def _on_resize(self, event):
        self.W = event.width
        self.H = event.height
        self._draw_grid()
        self._redraw()

    def _draw_grid(self):
        self.delete("grid")
        for i in range(1, 4):
            y = int(self.H * i / 4)
            self.create_line(0, y, self.W, y, fill=BORDER, dash=(2, 4), tags="grid")
        for i in range(1, 8):
            x = int(self.W * i / 8)
            self.create_line(x, 0, x, self.H, fill=BORDER, dash=(2, 4), tags="grid")

    def push(self, value):
        self.data.append(value)
        self._redraw()

    def _redraw(self):
        self.delete("line", "label", "val")
        pts = list(self.data)
        if len(pts) < 2 or self.W < 2:
            return

        # Use actual number of stored points for x-spacing (fills from left)
        n = len(pts)
        coords = []
        for i, v in enumerate(pts):
            x = i / (self.maxpts - 1) * self.W
            norm = (v - self.ymin) / (self.ymax - self.ymin + 1e-9)
            y = self.H - max(0.0, min(1.0, norm)) * self.H
            coords.extend([x, y])

        # Poly fill
        poly = [coords[0], self.H] + coords + [coords[-2], self.H]
        r, g, b = self.winfo_rgb(self.color)
        fill_hex = "#{:02x}{:02x}{:02x}".format(r >> 8, g >> 8, b >> 8)
        self.create_polygon(poly, fill=fill_hex, stipple="gray25", outline="", tags="line")
        self.create_line(*coords, fill=self.color, width=2, tags="line", smooth=True)

        # Label
        self.create_text(6, 6, anchor="nw", text=self.label,
                         fill=TEXT_MUTED, font=("Courier", 9, "bold"), tags="label")
        # Current value
        cur = pts[-1]
        self.create_text(self.W - 4, 6, anchor="ne",
                         text=f"{cur:.2f} {self.unit}",
                         fill=self.color, font=("Courier", 11, "bold"), tags="val")


# ─── LED indicator ────────────────────────────────────────────────
class LED(tk.Canvas):
    def __init__(self, parent, label, color_on=ACCENT_GREEN, size=14, **kw):
        super().__init__(parent, width=size+60, height=size+4,
                         bg=BG_PANEL, highlightthickness=0, **kw)
        self.s  = size
        self.on_col  = color_on
        self.off_col = "#1A1A1A"
        self._oval = self.create_oval(2, 2, size+2, size+2, fill=self.off_col, outline=BORDER)
        self.create_text(size + 8, size // 2 + 2, anchor="w",
                         text=label, fill=TEXT_MUTED, font=("Courier", 9))

    def set(self, state: bool):
        self.itemconfig(self._oval, fill=self.on_col if state else self.off_col)


# ─── Gauge (semi-circle) ─────────────────────────────────────────
class Gauge(tk.Canvas):
    def __init__(self, parent, label, unit, color, vmin, vmax,
                 width=160, height=100, **kw):
        super().__init__(parent, width=width, height=height,
                         bg=BG_CARD, highlightthickness=0, **kw)
        self.label = label
        self.unit  = unit
        self.color = color
        self.vmin  = vmin
        self.vmax  = vmax
        self.W, self.H = width, height
        self.cx, self.cy = width // 2, height - 10
        self.R  = min(width, height) - 20
        self._draw_bg()

    def _draw_bg(self):
        x, y, r = self.cx, self.cy, self.R
        self.create_arc(x-r, y-r, x+r, y+r,
                        start=0, extent=180, style="arc",
                        outline=BORDER, width=8)
        self.create_text(x, y + 2, text=self.label,
                         fill=TEXT_MUTED, font=("Courier", 8, "bold"), anchor="n")

    def set(self, value):
        self.delete("needle", "val")
        x, y, r = self.cx, self.cy, self.R
        norm  = max(0, min(1, (value - self.vmin) / (self.vmax - self.vmin + 1e-9)))
        angle = math.pi - norm * math.pi       # 180° → 0°
        nx = x + (r - 5) * math.cos(angle)
        ny = y - (r - 5) * math.sin(angle)
        self.create_line(x, y, nx, ny, fill=self.color, width=3, tags="needle")
        self.create_oval(x-4, y-4, x+4, y+4, fill=self.color, tags="needle")
        self.create_text(x, y - 20, text=f"{value:.1f}",
                         fill=self.color, font=("Courier", 12, "bold"), tags="val", anchor="center")
        self.create_text(x, y - 6, text=self.unit,
                         fill=TEXT_MUTED, font=("Courier", 8), tags="val", anchor="center")


# ─── Main Application ─────────────────────────────────────────────
class VioletGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PROJECT VIOLET — Breathing Simulator Control")
        self.configure(bg=BG_DARK)
        self.minsize(1100, 720)

        self.ds   = DataSource()
        self._running  = False
        self._acq_thread = None
        self._log_data  = []
        self._log_active = False

        self._build_ui()
        self._update_connection_state()

    # ── UI Construction ──────────────────────────────────────────
    def _build_ui(self):
        # ── Header ──
        hdr = tk.Frame(self, bg=BG_DARK)
        hdr.pack(fill="x", padx=16, pady=(12, 4))

        tk.Label(hdr, text="◈ PROJECT VIOLET", bg=BG_DARK,
                 fg=ACCENT_VIOLET, font=("Courier", 18, "bold")).pack(side="left")
        tk.Label(hdr, text="  Adult Breathing Simulator", bg=BG_DARK,
                 fg=TEXT_MUTED, font=("Courier", 12)).pack(side="left")

        # Connection area (right side of header)
        conn_fr = tk.Frame(hdr, bg=BG_DARK)
        conn_fr.pack(side="right")

        tk.Label(conn_fr, text="Port/Device:", bg=BG_DARK,
                 fg=TEXT_MUTED, font=("Courier", 9)).pack(side="left", padx=(0, 4))
        self.port_var = tk.StringVar(value="BLE")
        port_entry = tk.Entry(conn_fr, textvariable=self.port_var,
                              bg=BG_CARD, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY,
                              font=("Courier", 10), width=12, relief="flat",
                              highlightbackground=BORDER, highlightthickness=1)
        port_entry.pack(side="left", padx=4)

        self.conn_btn = tk.Button(conn_fr, text="⬤ CONNECT",
                                  bg=ACCENT_GREEN, fg="#000000",
                                  activebackground=ACCENT_GREEN, activeforeground="#000000",
                                  font=("Courier", 9, "bold"),
                                  relief="flat", padx=10, cursor="hand2",
                                  command=self._toggle_connection)
        self.conn_btn.pack(side="left", padx=4)

        self.status_lbl = tk.Label(conn_fr, text="● DISCONNECTED",
                                   bg=BG_DARK, fg=ACCENT_RED, font=("Courier", 9, "bold"))
        self.status_lbl.pack(side="left", padx=8)

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=16, pady=4)

        # ── Main paned area ──
        main = tk.Frame(self, bg=BG_DARK)
        main.pack(fill="both", expand=True, padx=12, pady=4)

        # Left column: Parameters + controls
        left = tk.Frame(main, bg=BG_DARK, width=300)
        left.pack(side="left", fill="y", padx=(0, 8))
        left.pack_propagate(False)
        self._build_left(left)

        # Right column: Charts + gauges
        right = tk.Frame(main, bg=BG_DARK)
        right.pack(side="left", fill="both", expand=True)
        self._build_right(right)

        # ── Footer / status bar ──
        foot = tk.Frame(self, bg=BG_PANEL, height=24)
        foot.pack(fill="x", side="bottom")
        foot.pack_propagate(False)
        self.footer_lbl = tk.Label(foot, text="Ready.", bg=BG_PANEL,
                                   fg=TEXT_MUTED, font=("Courier", 8), anchor="w")
        self.footer_lbl.pack(side="left", padx=8, fill="y")
        self.time_lbl = tk.Label(foot, text="", bg=BG_PANEL,
                                 fg=TEXT_MUTED, font=("Courier", 8), anchor="e")
        self.time_lbl.pack(side="right", padx=8, fill="y")
        self._tick_clock()

    def _section(self, parent, title):
        fr = tk.LabelFrame(parent, text=f" {title} ", bg=BG_PANEL,
                           fg=ACCENT_CYAN, font=("Courier", 9, "bold"),
                           bd=1, relief="flat", labelanchor="nw",
                           highlightbackground=BORDER, highlightthickness=1)
        fr.pack(fill="x", padx=4, pady=4)
        return fr

    def _row(self, parent, label, widget_fn, **kw):
        row = tk.Frame(parent, bg=BG_PANEL)
        row.pack(fill="x", padx=6, pady=2)
        tk.Label(row, text=label, bg=BG_PANEL, fg=TEXT_MUTED,
                 font=("Courier", 9), width=18, anchor="w").pack(side="left")
        widget_fn(row, **kw)
        return row

    # ── Left panel ───────────────────────────────────────────────
    def _build_left(self, parent):
        # ── Waveform settings ──
        ws = self._section(parent, "WAVEFORM SETTINGS")
        self.mode_var = tk.StringVar(value="SINE")
        for m in ("SINE", "STEADY", "INVIVO"):
            tk.Radiobutton(ws, text=m, variable=self.mode_var, value=m,
                           bg=BG_PANEL, fg=TEXT_PRIMARY, selectcolor=BG_CARD,
                           activebackground=BG_PANEL, font=("Courier", 9),
                           command=self._apply_params).pack(anchor="w", padx=8)

        # Frequency — slider + entry in sync
        self.freq_var = tk.DoubleVar(value=0.25)
        self._row(ws, "Frequency (Hz):",
                  lambda p: self._slider_entry(p, self.freq_var, 0.05, 2.0, 0.05))

        # Amplitude — slider + entry in sync
        self.amp_var = tk.DoubleVar(value=500)
        self._row(ws, "Amplitude (mL):",
                  lambda p: self._slider_entry(p, self.amp_var, 50, 1500, 10))

        # ── Motor params ──
        mp = self._section(parent, "MOTOR / DRIVER")
        self.target_rpm_var = tk.StringVar(value="1500")
        self._row(mp, "Target RPM:",
                  lambda p: self._entry(p, self.target_rpm_var))
        self.accel_var = tk.StringVar(value="500")
        self._row(mp, "Accel (rpm/s):",
                  lambda p: self._entry(p, self.accel_var))
        self.pwm_var = tk.StringVar(value="80")
        self._row(mp, "PWM duty (%):",
                  lambda p: self._entry(p, self.pwm_var))

        # ── Limits / safety ──
        lp = self._section(parent, "SAFETY LIMITS")
        self.max_press_var = tk.StringVar(value="30.0")
        self._row(lp, "Max Press (cmH₂O):",
                  lambda p: self._entry(p, self.max_press_var))
        self.max_flow_var = tk.StringVar(value="120.0")
        self._row(lp, "Max Flow (L/min):",
                  lambda p: self._entry(p, self.max_flow_var))
        self.max_vol_var = tk.StringVar(value="1200")
        self._row(lp, "Max Vol (mL):",
                  lambda p: self._entry(p, self.max_vol_var))

        # ── Apply / Send ──
        btn_fr = tk.Frame(parent, bg=BG_DARK)
        btn_fr.pack(fill="x", padx=4, pady=6)
        self._btn(btn_fr, "▶  APPLY PARAMS", self._apply_params, ACCENT_VIOLET)
        self._btn(btn_fr, "⏹  STOP MOTOR",   self._stop_motor,  ACCENT_RED)
        # ── Acquisition control ──
        ac = self._section(parent, "DATA ACQUISITION")
        self.acq_btn = tk.Button(ac, text="⬤  START ACQUISITION",
                                 bg=ACCENT_CYAN, fg="#000000",
                                 activebackground=ACCENT_CYAN, activeforeground="#000000",
                                 font=("Courier", 9, "bold"), relief="flat",
                                 cursor="hand2", pady=4,
                                 command=self._toggle_acquisition)
        self.acq_btn.pack(fill="x", padx=6, pady=4)

        self.log_btn = tk.Button(ac, text="📁  START LOGGING",
                                 bg=BG_CARD, fg=TEXT_PRIMARY,
                                 activebackground=BG_CARD, activeforeground=TEXT_PRIMARY,
                                 font=("Courier", 9, "bold"), relief="flat",
                                 cursor="hand2", pady=4,
                                 command=self._toggle_logging)
        self.log_btn.pack(fill="x", padx=6, pady=(0, 4))
        # ── Switches / LEDs ──
        sw = self._section(parent, "DIGITAL INPUTS")
        self.led_sw1 = LED(sw, "Switch 1 (top)",    ACCENT_GREEN)
        self.led_sw1.pack(anchor="w", padx=8, pady=2)
        self.led_sw2 = LED(sw, "Switch 2 (bottom)", ACCENT_GREEN)
        self.led_sw2.pack(anchor="w", padx=8, pady=2)
        self.led_conn = LED(sw, "µC Connected",      ACCENT_CYAN)
        self.led_conn.pack(anchor="w", padx=8, pady=2)

    def _slider(self, parent, var, from_, to, resolution):
        sl = tk.Scale(parent, variable=var, from_=from_, to=to,
                      resolution=resolution, orient="horizontal",
                      bg=BG_PANEL, fg=TEXT_PRIMARY, troughcolor=BG_CARD,
                      highlightthickness=0, activebackground=ACCENT_VIOLET,
                      font=("Courier", 8), length=140, sliderlength=12)
        sl.pack(side="left")

    def _slider_entry(self, parent, var, from_, to, resolution):
        """Slider + numeric entry field kept in sync."""
        # Shortened slider to leave room for entry
        sl = tk.Scale(parent, variable=var, from_=from_, to=to,
                      resolution=resolution, orient="horizontal",
                      bg=BG_PANEL, fg=TEXT_PRIMARY, troughcolor=BG_CARD,
                      highlightthickness=0, activebackground=ACCENT_VIOLET,
                      font=("Courier", 8), length=100, sliderlength=12,
                      showvalue=False)   # value shown in entry instead
        sl.pack(side="left")

        # Entry field bound to the same DoubleVar
        ent = tk.Entry(parent, textvariable=var, bg=BG_CARD, fg=ACCENT_CYAN,
                       insertbackground=TEXT_PRIMARY, font=("Courier", 10),
                       width=6, relief="flat",
                       highlightbackground=ACCENT_VIOLET, highlightthickness=1,
                       justify="center")
        ent.pack(side="left", padx=(4, 0))

        def _on_entry(event=None):
            try:
                v = float(ent.get())
                v = max(from_, min(to, round(v / resolution) * resolution))
                var.set(round(v, 6))
            except ValueError:
                pass  # ignore bad input while typing

        ent.bind("<Return>",    _on_entry)
        ent.bind("<FocusOut>",  _on_entry)

    def _entry(self, parent, var):
        e = tk.Entry(parent, textvariable=var, bg=BG_CARD, fg=TEXT_PRIMARY,
                     insertbackground=TEXT_PRIMARY, font=("Courier", 10),
                     width=10, relief="flat",
                     highlightbackground=BORDER, highlightthickness=1)
        e.pack(side="left", padx=2)

    def _btn(self, parent, text, cmd, color):
        # bright colours (violet, cyan, green, amber) → black text; dark/red → white text
        dark_bg = color in (ACCENT_RED, BG_CARD, BG_PANEL, BG_DARK)
        fg = TEXT_PRIMARY if dark_bg else "#000000"
        tk.Button(parent, text=text, command=cmd,
                  bg=color, fg=fg,
                  activebackground=color, activeforeground=fg,
                  disabledforeground=TEXT_MUTED,
                  font=("Courier", 9, "bold"), relief="flat",
                  cursor="hand2", pady=5).pack(fill="x", padx=4, pady=2)

    # ── Right panel ──────────────────────────────────────────────
    def _build_right(self, parent):
        # Top: Gauges row
        gauge_row = tk.Frame(parent, bg=BG_DARK)
        gauge_row.pack(fill="x", pady=(0, 6))

        self.gauge_flow   = Gauge(gauge_row, "FLOW", "L/min",  ACCENT_CYAN,  -120, 120)
        self.gauge_press1 = Gauge(gauge_row, "PRESS 1", "cmH₂O", ACCENT_VIOLET, -5, 40)
        self.gauge_press2 = Gauge(gauge_row, "PRESS 2", "cmH₂O", ACCENT_AMBER,  -5, 30)
        self.gauge_rpm    = Gauge(gauge_row, "MOTOR", "RPM", ACCENT_GREEN,    0, 4000)
        self.gauge_vol    = Gauge(gauge_row, "VOLUME", "mL", "#F97316",       0, 1500)

        for g in (self.gauge_flow, self.gauge_press1, self.gauge_press2,
                  self.gauge_rpm, self.gauge_vol):
            tk.Frame(gauge_row, bg=BG_CARD, bd=1, relief="flat").pack(
                side="left", padx=3, pady=2, fill="y")
            g.pack(side="left", padx=3, pady=2)

        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=4)

        # Charts
        charts_fr = tk.Frame(parent, bg=BG_DARK)
        charts_fr.pack(fill="both", expand=True)

        col1 = tk.Frame(charts_fr, bg=BG_DARK)
        col1.pack(side="left", fill="both", expand=True, padx=(0, 4))
        col2 = tk.Frame(charts_fr, bg=BG_DARK)
        col2.pack(side="left", fill="both", expand=True)

        def chart(parent, label, unit, color, ymin, ymax):
            c = ScrollingChart(parent, label, unit, color, ymin, ymax,
                               width=400, height=120, maxpts=400)
            c.pack(fill="both", expand=True, pady=3)
            return c

        self.ch_flow   = chart(col1, "Flow", "L/min",    ACCENT_CYAN,   -120, 120)
        self.ch_press1 = chart(col1, "Pressure 1", "cmH₂O", ACCENT_VIOLET, -2,  40)
        self.ch_vol    = chart(col1, "Volume", "mL",     "#F97316",       0, 1500)

        self.ch_press2 = chart(col2, "Pressure 2", "cmH₂O", ACCENT_AMBER, -2, 30)
        self.ch_rpm    = chart(col2, "Motor RPM", "rpm", ACCENT_GREEN,    0, 4000)
        self.ch_enc    = chart(col2, "Encoder", "cts",   TEXT_MUTED,      0, 65535)

        # Encoder live display
        enc_fr = tk.Frame(parent, bg=BG_PANEL)
        enc_fr.pack(fill="x", pady=2)
        tk.Label(enc_fr, text="Encoder counts:", bg=BG_PANEL,
                 fg=TEXT_MUTED, font=("Courier", 9)).pack(side="left", padx=8)
        self.enc_var = tk.StringVar(value="–")
        tk.Label(enc_fr, textvariable=self.enc_var, bg=BG_PANEL,
                 fg=ACCENT_CYAN, font=("Courier", 12, "bold")).pack(side="left")

        tk.Label(enc_fr, text="   Motor RPM:", bg=BG_PANEL,
                 fg=TEXT_MUTED, font=("Courier", 9)).pack(side="left", padx=(20, 4))
        self.rpm_var = tk.StringVar(value="–")
        tk.Label(enc_fr, textvariable=self.rpm_var, bg=BG_PANEL,
                 fg=ACCENT_GREEN, font=("Courier", 12, "bold")).pack(side="left")

    # ── Actions ──────────────────────────────────────────────────
    def _toggle_connection(self):
        if not self.ds.connected:
            self.footer_lbl.config(text="Connecting…")
            def do():
                self.ds.connect(self.port_var.get())
                self.after(0, self._update_connection_state)
            threading.Thread(target=do, daemon=True).start()
        else:
            self._running = False
            self.ds.disconnect()
            self._update_connection_state()

    def _update_connection_state(self):
        if self.ds.connected:
            self.conn_btn.config(text="⬤ DISCONNECT", bg=ACCENT_RED, fg=TEXT_PRIMARY,
                                 activebackground=ACCENT_RED, activeforeground=TEXT_PRIMARY)
            self.status_lbl.config(text="● CONNECTED", fg=ACCENT_GREEN)
            self.led_conn.set(True)
            self.footer_lbl.config(text=f"Connected to {self.port_var.get()}")
        else:
            self.conn_btn.config(text="⬤ CONNECT", bg=ACCENT_GREEN, fg="#000000",
                                 activebackground=ACCENT_GREEN, activeforeground="#000000")
            self.status_lbl.config(text="● DISCONNECTED", fg=ACCENT_RED)
            self.led_conn.set(False)
            self._running = False
            self.acq_btn.config(text="⬤  START ACQUISITION", bg=ACCENT_CYAN, fg="#000000",
                                activebackground=ACCENT_CYAN, activeforeground="#000000")
            self.footer_lbl.config(text="Disconnected.")

    def _apply_params(self):
        self.ds.mode = self.mode_var.get()
        self.ds.freq  = self.freq_var.get()
        self.ds.amp   = self.amp_var.get()
        self.footer_lbl.config(
            text=f"Params applied: mode={self.ds.mode}  freq={self.ds.freq:.2f}Hz  amp={self.ds.amp:.0f}mL")

    def _stop_motor(self):
        self.ds.amp = 0
        self.amp_var.set(0)
        self.footer_lbl.config(text="Motor STOP commanded.")

    def _toggle_acquisition(self):
        if not self.ds.connected:
            messagebox.showwarning("Not connected", "Please connect first.")
            return
        if self._running:
            self._running = False
            self.acq_btn.config(text="⬤  START ACQUISITION", bg=ACCENT_CYAN, fg="#000000",
                                activebackground=ACCENT_CYAN, activeforeground="#000000")
        else:
            self._running = True
            self.acq_btn.config(text="⏹  STOP ACQUISITION", bg=ACCENT_RED, fg=TEXT_PRIMARY,
                                activebackground=ACCENT_RED, activeforeground=TEXT_PRIMARY)
            self._apply_params()
            self._acq_thread = threading.Thread(target=self._acq_loop, daemon=True)
            self._acq_thread.start()

    def _acq_loop(self):
        while self._running and self.ds.connected:
            frame = self.ds.read_frame()
            if self._log_active:
                self._log_data.append(frame)
            self.after(0, self._update_ui, frame)
            time.sleep(0.05)

    def _update_ui(self, f):
        self.ch_flow.push(f["flow_lpm"])
        self.ch_press1.push(f["press1_cmH2O"])
        self.ch_press2.push(f["press2_cmH2O"])
        self.ch_vol.push(f["volume_ml"])
        self.ch_rpm.push(f["motor_rpm"])
        self.ch_enc.push(f["encoder_cts"])

        self.gauge_flow.set(f["flow_lpm"])
        self.gauge_press1.set(f["press1_cmH2O"])
        self.gauge_press2.set(f["press2_cmH2O"])
        self.gauge_rpm.set(f["motor_rpm"])
        self.gauge_vol.set(f["volume_ml"])

        self.enc_var.set(str(f["encoder_cts"]))
        self.rpm_var.set(f"{f['motor_rpm']:.0f}")

        self.led_sw1.set(bool(f["sw1"]))
        self.led_sw2.set(bool(f["sw2"]))

    def _toggle_logging(self):
        if not self._log_active:
            self._log_data = []
            self._log_active = True
            self.log_btn.config(text="⏹  STOP & SAVE LOG", bg=ACCENT_AMBER, fg="#000000",
                                activebackground=ACCENT_AMBER, activeforeground="#000000")
            self.footer_lbl.config(text="Logging started…")
        else:
            self._log_active = False
            fname = f"violet_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(fname, "w") as fh:
                json.dump(self._log_data, fh, indent=2)
            self.log_btn.config(text="📁  START LOGGING", bg=BG_CARD, fg=TEXT_PRIMARY,
                                activebackground=BG_CARD, activeforeground=TEXT_PRIMARY)
            self.footer_lbl.config(text=f"Log saved → {fname}  ({len(self._log_data)} frames)")

    def _tick_clock(self):
        self.time_lbl.config(text=datetime.now().strftime("%Y-%m-%d  %H:%M:%S"))
        self.after(1000, self._tick_clock)


# ─── Entry point ─────────────────────────────────────────────────
if __name__ == "__main__":
    app = VioletGUI()
    # Dark title bar on Windows
    try:
        from ctypes import windll
        app.update()
        hwnd = windll.user32.GetParent(app.winfo_id())
        windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, byref(c_bool(True)), 4)
    except Exception:
        pass
    app.mainloop()