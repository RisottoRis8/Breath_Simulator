"""
Run:
    python C.py
"""

import flet as ft
import threading
import time
import math
import random
import json
from collections import deque
from datetime import datetime
import flet.canvas as cv
import asyncio
from bleak import BleakScanner, BleakClient

UART_RX_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"
UART_TX_CHAR_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"

# ─── Palette ──────────────────────────────────────────────────────
BG_DARK       = "#0D1117"
BG_PANEL      = "#161B22"
BG_CARD       = "#1C2333"
ACCENT_VIOLET = "#7C3AED"
ACCENT_CYAN   = "#06B6D4"
ACCENT_GREEN  = "#10B981"
ACCENT_RED    = "#EF4444"
ACCENT_AMBER  = "#F59E0B"
TEXT_PRIMARY  = "#F0F6FF"
TEXT_MUTED    = "#8B949E"
BORDER        = "#30363D"


class BLEDataSource:
    def __init__(self):
        self.client = None
        self.connected = False
        self.latest = None

    async def scan(self):
        devices = await BleakScanner.discover(timeout=5.0)
        return [(d.name, d.address) for d in devices if d.name]

    async def connect(self, address, callback):
        self.client = BleakClient(address)
        await self.client.connect()
        self.connected = True

        await self.client.start_notify(
            UART_RX_CHAR_UUID,
            lambda sender, data: asyncio.create_task(
                self._safe_callback(callback, data)
            )
        )

    async def disconnect(self):
        if self.client and self.client.is_connected:
            await self.client.disconnect()
        self.connected = False

    async def _safe_callback(self, callback, data):
        frame = self.parse(data)
        if callback and frame:
            callback(frame)

    def parse(self, data):
        try:
            msg = data.decode().strip()
            parts = msg.split(",")

            return {
                "flow_lpm": float(parts[0]),
                "press1_cmH2O": float(parts[1]),
                "press2_cmH2O": float(parts[2]),
                "motor_rpm": float(parts[3]),
                "encoder_cts": int(parts[4]),
                "volume_ml": float(parts[5]),
                "sw1": int(parts[6]),
                "sw2": int(parts[7]),
                "timestamp": time.time()
            }
        # except:
        #     return None
        except Exception as e:
            print("Parse error:", e)
            return None

    async def send(self, cmd):
        if self.client and self.client.is_connected:
            await self.client.write_gatt_char(
                UART_TX_CHAR_UUID,
                cmd.encode()
            )







class ScrollingChart:
    """Scrolling waveform chart backed by ft.Canvas."""

    def __init__(self, label: str, unit: str, color: str,
                 ymin: float, ymax: float, maxpts: int = 300):
        self.label  = label
        self.unit   = unit
        self.color  = color
        self.ymin   = ymin
        self.ymax   = ymax
        self.maxpts = maxpts
        self.data: deque = deque(maxlen=maxpts)
        self._W: float = 400.0
        self._H: float = 120.0

        self._canvas = cv.Canvas(
            width=400, height=120,
            on_resize=self._on_resize,
        )
        self.control = ft.Container(
            content=self._canvas,
            bgcolor=BG_CARD,
            border_radius=6,
            expand=True,
            height=130,
        )

    def _on_resize(self, e):
        self._W = max(float(e.width),  1.0)
        self._H = max(float(e.height), 1.0)
        self._redraw()

    def push(self, value: float):
        self.data.append(value)
        self._redraw()

    def _redraw(self):
        W, H  = self._W, self._H
        pts   = list(self.data)
        shapes: list = []

        # Grid
        grid_paint = ft.Paint(color=BORDER, stroke_width=1,
                              style=ft.PaintingStyle.STROKE)
        for i in range(1, 4):
            y = H * i / 4
            shapes.append(cv.Line(0, y, W, y, paint=grid_paint))
        for i in range(1, 8):
            x = W * i / 8
            shapes.append(cv.Line(x, 0, x, H, paint=grid_paint))

        # Waveform
        if len(pts) >= 2:
            path_elements = []
            for i, v in enumerate(pts):
                x = i / (self.maxpts - 1) * W
                norm = (v - self.ymin) / (self.ymax - self.ymin + 1e-9)
                y = H - max(0.0, min(1.0, norm)) * H
                if i == 0:
                    path_elements.append(cv.Path.MoveTo(x, y))
                else:
                    path_elements.append(cv.Path.LineTo(x, y))

            shapes.append(cv.Path(
                path_elements,
                paint=ft.Paint(
                    color=self.color,
                    stroke_width=2,
                    style=ft.PaintingStyle.STROKE,
                    stroke_join=ft.StrokeJoin.ROUND,
                    stroke_cap=ft.StrokeCap.ROUND,
                ),
            ))

        # Label top-left
        shapes.append(cv.Text(
            6, 6, self.label,
            style=ft.TextStyle(
                size=9, color=TEXT_MUTED,
                font_family="Courier New",
                weight=ft.FontWeight.BOLD,
            ),
        ))

        # Current value – manually right-aligned (approx 7 px/char)
        if pts:
            cur  = pts[-1]
            text = f"{cur:.2f} {self.unit}"
            approx_w = len(text) * 7
            shapes.append(cv.Text(
                W - approx_w - 4, 6, text,
                style=ft.TextStyle(
                    size=11, color=self.color,
                    font_family="Courier New",
                    weight=ft.FontWeight.BOLD,
                ),
            ))

        self._canvas.shapes = shapes
        try:
            self._canvas.update()
        except Exception:
            pass  # not yet mounted


# ─── Gauge ─────────────────────────────────────────────────────────
class Gauge:
    """Semi-circle gauge backed by ft.Canvas."""

    def __init__(self, label: str, unit: str, color: str,
                 vmin: float, vmax: float):
        self.label = label
        self.unit  = unit
        self.color = color
        self.vmin  = vmin
        self.vmax  = vmax

        self._canvas = cv.Canvas(width=160, height=110)
        self.control = ft.Container(
            content=self._canvas,
            bgcolor=BG_CARD,
            border_radius=6,
            width=165,
            height=115,
            padding=4,
        )

    def set(self, value: float):
        W, H   = 160, 110
        cx, cy = W // 2, H - 12
        R      = min(W, H) - 22
        shapes: list = []

        # Background arc
        shapes.append(cv.Arc(
            cx - R, cy - R, R * 2, R * 2,
            start_angle=math.pi, sweep_angle=math.pi,
            paint=ft.Paint(color=BORDER, stroke_width=8,
                           style=ft.PaintingStyle.STROKE),
        ))

        # Coloured progress arc
        norm  = max(0.0, min(1.0,
                    (value - self.vmin) / (self.vmax - self.vmin + 1e-9)))
        sweep = norm * math.pi
        if sweep > 0.01:
            shapes.append(cv.Arc(
                cx - R, cy - R, R * 2, R * 2,
                start_angle=math.pi, sweep_angle=sweep,
                paint=ft.Paint(color=self.color, stroke_width=8,
                               style=ft.PaintingStyle.STROKE),
            ))

        # Needle
        angle = math.pi - norm * math.pi
        nx = cx + (R - 6) * math.cos(angle)
        ny = cy - (R - 6) * math.sin(angle)
        shapes.append(cv.Line(
            cx, cy, nx, ny,
            paint=ft.Paint(color=self.color, stroke_width=3,
                           stroke_cap=ft.StrokeCap.ROUND),
        ))
        shapes.append(cv.Circle(
            cx, cy, 5, paint=ft.Paint(color=self.color),
        ))

        # Texts (manually centred)
        val_text = f"{value:.1f}"
        shapes.append(cv.Text(
            cx - len(val_text) * 4, cy - 28, val_text,
            style=ft.TextStyle(size=13, color=self.color,
                               font_family="Courier New",
                               weight=ft.FontWeight.BOLD),
        ))
        shapes.append(cv.Text(
            cx - len(self.unit) * 3, cy - 13, self.unit,
            style=ft.TextStyle(size=8, color=TEXT_MUTED,
                               font_family="Courier New"),
        ))
        shapes.append(cv.Text(
            cx - len(self.label) * 3, cy + 2, self.label,
            style=ft.TextStyle(size=8, color=TEXT_MUTED,
                               font_family="Courier New",
                               weight=ft.FontWeight.BOLD),
        ))

        self._canvas.shapes = shapes
        try:
            self._canvas.update()
        except Exception:
            pass


# ─── LED ───────────────────────────────────────────────────────────
class LED:
    def __init__(self, label: str, color_on: str = ACCENT_GREEN):
        self.color_on  = color_on
        self._dot = ft.Container(
            width=12, height=12, border_radius=6,
            bgcolor="#1A1A1A",
            border=ft.Border.all(1, BORDER),
        )
        self.control = ft.Row(
            [self._dot,
             ft.Text(label, size=9, color=TEXT_MUTED, font_family="Courier New")],
            spacing=8,
        )

    def set(self, state: bool):
        self._dot.bgcolor = self.color_on if state else "#1A1A1A"
        try:
            self._dot.update()
        except Exception:
            pass


# ─── Layout helpers ────────────────────────────────────────────────
def section(title: str, content: ft.Control) -> ft.Container:
    return ft.Container(
        content=ft.Column(
            [ft.Text(title, size=9, color=ACCENT_CYAN,
                     font_family="Courier New", weight=ft.FontWeight.BOLD),
             content],
            spacing=6,
        ),
        bgcolor=BG_PANEL,
        border=ft.Border.all(1, BORDER),
        border_radius=6,
        padding=10,
        margin=ft.Margin.only(bottom=6),
    )

def label_row(lbl: str, ctrl: ft.Control) -> ft.Row:
    return ft.Row([
        ft.Text(lbl, size=9, color=TEXT_MUTED,
                font_family="Courier New", width=140),
        ctrl,
    ])

def mk_entry(val: str) -> ft.TextField:
    return ft.TextField(
        value=val, width=100,
        text_style=ft.TextStyle(color=TEXT_PRIMARY,
                                font_family="Courier New", size=11),
        bgcolor=BG_CARD, border_color=BORDER,
        content_padding=ft.padding.symmetric(horizontal=4, vertical=6)
    )


# ─── Main ──────────────────────────────────────────────────────────
def main(page: ft.Page):
    page.title   = "PROJECT VIOLET — Breathing Simulator"
    page.bgcolor = BG_DARK
    page.padding = 0

    #ds           = DataSource()
    ds = BLEDataSource()

    # UI BLE EXTRA — actual widgets defined after gui_log (see below)

    def gui_log(page, msg, color=TEXT_MUTED):
        def _add():
            try:
                ble_log_list.controls.append(
                    ft.Text(msg, color=color, size=10, font_family="Courier New")
                )
                page.update()
            except Exception:
                pass
        page.run_thread(_add)




    # ── BLE helpers (closures over ds, device_dropdown, gui_log) ──────
    async def send_ble_cmd(cmd: str):
        if ds.client and ds.client.is_connected:
            try:
                await ds.send(cmd)
                gui_log(page, f"🔵 [TX]: {cmd.strip()}", ACCENT_CYAN)
            except Exception as ex:
                gui_log(page, f"❌ Send error: {ex}", ACCENT_RED)
        else:
            gui_log(page, "⚠️ Not connected!", ACCENT_AMBER)

    async def scan_devices(e):
        scan_ble_btn.disabled = True
        try: scan_ble_btn.update()
        except Exception: pass
        gui_log(page, "🔎 Scanning BLE (5s)...", ACCENT_CYAN)
        try:
            found = await ds.scan()
            device_dropdown.options.clear()
            for name, addr in found:
                device_dropdown.options.append(
                    ft.dropdown.Option(text=f"{name} ({addr})", key=addr)
                )
            if device_dropdown.options:
                device_dropdown.value = device_dropdown.options[0].key
            gui_log(page, f"✅ Found {len(device_dropdown.options)} device(s)", ACCENT_GREEN)
        except Exception as ex:
            gui_log(page, f"❌ Scan error: {ex}", ACCENT_RED)
        scan_ble_btn.disabled = False
        try:
            scan_ble_btn.update()
            device_dropdown.update()
        except Exception: pass

    # async def connect_ble(e):
    #     if not device_dropdown.value:
    #         gui_log(page, "⚠️ Select a device first", ACCENT_AMBER)
    #         return
    #     gui_log(page, f"🔌 Connecting to {device_dropdown.value}...", ACCENT_CYAN)
    #     try:
    #         await ds.connect(device_dropdown.value, on_ble_frame)
    #         gui_log(page, "✅ BLE connected!", ACCENT_GREEN)
    #         page.run_thread(update_conn_state)
    #     except Exception as ex:
    #         gui_log(page, f"❌ Connection error: {ex}", ACCENT_RED)

    async def connect_ble(e):
        if not device_dropdown.value:
            gui_log(page, "⚠️ Select a device first", ACCENT_AMBER)
            return

        gui_log(page, f"🔌 Connecting to {device_dropdown.value}...", ACCENT_CYAN)

        try:
            await ds.connect(device_dropdown.value, on_ble_frame)
            gui_log(page, "✅ BLE connected!", ACCENT_GREEN)

            ds.connected = True
            page.run_thread(update_conn_state)

        except Exception as ex:
            gui_log(page, f"❌ Connection error: {ex}", ACCENT_RED)


    async def disconnect_ble(e):
            await ds.disconnect()
            ds.connected = False
            gui_log(page, "🛑 Disconnected", ACCENT_AMBER)
            page.run_thread(update_conn_state)
        # await ds.disconnect()
        # gui_log(page, "🛑 Disconnected", ACCENT_AMBER)
        # page.run_thread(update_conn_state)

    async def _btn_led_on(e):  await send_ble_cmd("LED_ON\n")
    async def _btn_led_off(e): await send_ble_cmd("LED_OFF\n")
    async def _btn_ping(e):    await send_ble_cmd("PING\n")
    async def _btn_read(e):    await send_ble_cmd("READ\n")

    scan_ble_btn = ft.ElevatedButton(
        "SCAN", icon=ft.Icons.SEARCH,
        bgcolor=BG_CARD, color=ACCENT_CYAN,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=4)),
        on_click=scan_devices,
    )
    connect_ble_btn = ft.ElevatedButton(
        "CONNECT", icon=ft.Icons.BLUETOOTH,
        bgcolor=ACCENT_GREEN, color="#000000",
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=4)),
        on_click=connect_ble,
    )
    disconnect_ble_btn = ft.ElevatedButton(
        "DISCONNECT", icon=ft.Icons.BLUETOOTH_DISABLED,
        bgcolor=ACCENT_RED, color=TEXT_PRIMARY,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=4)),
        on_click=disconnect_ble,
    )
    custom_input = ft.TextField(
        label="Custom command...", expand=True,
        text_style=ft.TextStyle(color=TEXT_PRIMARY, font_family="Courier New", size=11),
        bgcolor=BG_CARD, border_color=BORDER,
        content_padding=ft.padding.symmetric(horizontal=6, vertical=6),
    )
    async def _send_custom(e):
        if custom_input.value:
            await send_ble_cmd(custom_input.value + "\n")
            custom_input.value = ""
            try: custom_input.update()
            except Exception: pass
    custom_input.on_submit = _send_custom

    ble_log_list = ft.ListView(expand=True, spacing=2, auto_scroll=True)
    ble_log_container = ft.Container(
        content=ble_log_list,
        bgcolor=BG_CARD,
        border=ft.Border.all(1, BORDER),
        border_radius=6,
        padding=8,
        height=140,
    )

    # redefine device_dropdown with styling
    device_dropdown = ft.Dropdown(
        expand=True,
        label="BLE Devices",
        text_style=ft.TextStyle(color=TEXT_PRIMARY, font_family="Courier New", size=10),
        bgcolor=BG_CARD,
        border_color=BORDER,
    )

    running_flag = {"v": False}
    log_active   = {"v": False}
    log_data     = {"frames": []}

    # Widgets
    ch_flow   = ScrollingChart("Flow",       "L/min",  ACCENT_CYAN,   -120, 120)
    ch_press1 = ScrollingChart("Pressure 1", "cmH2O",  ACCENT_VIOLET,  -2,   40)
    ch_vol    = ScrollingChart("Volume",     "mL",     "#F97316",       0, 1500)
    ch_press2 = ScrollingChart("Pressure 2", "cmH2O",  ACCENT_AMBER,   -2,   30)
    ch_rpm    = ScrollingChart("Motor RPM",  "rpm",    ACCENT_GREEN,    0, 4000)
    ch_enc    = ScrollingChart("Encoder",    "cts",    TEXT_MUTED,      0, 65535)

    g_flow   = Gauge("FLOW",    "L/min", ACCENT_CYAN,   -120, 120)
    g_press1 = Gauge("PRESS1",  "cmH2O", ACCENT_VIOLET, -5,   40)
    g_press2 = Gauge("PRESS2",  "cmH2O", ACCENT_AMBER,  -5,   30)
    g_rpm    = Gauge("MOTOR",   "RPM",   ACCENT_GREEN,   0, 4000)
    g_vol    = Gauge("VOLUME",  "mL",    "#F97316",      0, 1500)

    led_sw1  = LED("Switch 1 (top)",    ACCENT_GREEN)
    led_sw2  = LED("Switch 2 (bottom)", ACCENT_GREEN)
    led_conn = LED("uC Connected",       ACCENT_CYAN)

    status_text = ft.Text("● DISCONNECTED", size=10, color=ACCENT_RED,
                           font_family="Courier New", weight=ft.FontWeight.BOLD)
    footer_text = ft.Text("Ready.", size=9, color=TEXT_MUTED, font_family="Courier New")
    clock_text  = ft.Text("", size=9, color=TEXT_MUTED, font_family="Courier New")
    enc_value   = ft.Text("–", size=13, color=ACCENT_CYAN,
                           font_family="Courier New", weight=ft.FontWeight.BOLD)
    rpm_value   = ft.Text("–", size=13, color=ACCENT_GREEN,
                           font_family="Courier New", weight=ft.FontWeight.BOLD)

    mode_radio = ft.RadioGroup(
        value="SINE",
        content=ft.Row([
            ft.Radio(value="SINE",   label="SINE",   fill_color=ACCENT_VIOLET),
            ft.Radio(value="STEADY", label="STEADY", fill_color=ACCENT_VIOLET),
            ft.Radio(value="INVIVO", label="INVIVO", fill_color=ACCENT_VIOLET),
        ]),
    )

    freq_slider = ft.Slider(min=0.05, max=2.0, divisions=39, value=0.25,
                             active_color=ACCENT_VIOLET, thumb_color=ACCENT_VIOLET,
                             expand=True)
    freq_field  = ft.TextField(value="0.25", width=70,
                                text_style=ft.TextStyle(color=ACCENT_CYAN,
                                    font_family="Courier New", size=11),
                                bgcolor=BG_CARD, border_color=ACCENT_VIOLET,
                                content_padding=ft.padding.symmetric(horizontal=4, vertical=6),
                                text_align=ft.TextAlign.CENTER)
    amp_slider  = ft.Slider(min=50, max=1500, divisions=145, value=500,
                             active_color=ACCENT_VIOLET, thumb_color=ACCENT_VIOLET,
                             expand=True)
    amp_field   = ft.TextField(value="500", width=70,
                                text_style=ft.TextStyle(color=ACCENT_CYAN,
                                    font_family="Courier New", size=11),
                                bgcolor=BG_CARD, border_color=ACCENT_VIOLET,
                                content_padding=ft.padding.symmetric(horizontal=4, vertical=6),
                                text_align=ft.TextAlign.CENTER)

    def on_freq_slider(e):
        freq_field.value = str(round(freq_slider.value, 2))
        freq_field.update()

    def on_freq_field(e):
        try:
            v = max(0.05, min(2.0, float(freq_field.value)))
            freq_slider.value = v; freq_slider.update()
        except ValueError:
            pass

    def on_amp_slider(e):
        amp_field.value = str(round(amp_slider.value))
        amp_field.update()

    def on_amp_field(e):
        try:
            v = max(50.0, min(1500.0, float(amp_field.value)))
            amp_slider.value = v; amp_slider.update()
        except ValueError:
            pass

    freq_slider.on_change = on_freq_slider
    freq_field.on_submit  = on_freq_field
    freq_field.on_blur    = on_freq_field
    amp_slider.on_change  = on_amp_slider
    amp_field.on_submit   = on_amp_field
    amp_field.on_blur     = on_amp_field

    port_field       = ft.TextField(value="BLE", width=110,
                                    text_style=ft.TextStyle(color=TEXT_PRIMARY,
                                        font_family="Courier New", size=10),
                                    bgcolor=BG_CARD, border_color=BORDER,
                                    content_padding=ft.padding.symmetric(horizontal=4, vertical=6))
    target_rpm_field = mk_entry("1500")
    accel_field      = mk_entry("500")
    pwm_field        = mk_entry("80")
    max_press_field  = mk_entry("30.0")
    max_flow_field   = mk_entry("120.0")
    max_vol_field    = mk_entry("1200")

    # conn_btn = ft.ElevatedButton("⬤  CONNECT",
    #                               bgcolor=ACCENT_GREEN, color="#000000",
    #                               style=ft.ButtonStyle(
    #                                   shape=ft.RoundedRectangleBorder(radius=4)))
    acq_btn  = ft.ElevatedButton("⬤  START ACQUISITION",
                                  bgcolor=ACCENT_CYAN, color="#000000",
                                  style=ft.ButtonStyle(
                                      shape=ft.RoundedRectangleBorder(radius=4)))
    log_btn  = ft.ElevatedButton("📁  START LOGGING",
                                  bgcolor=BG_CARD, color=TEXT_PRIMARY,
                                  style=ft.ButtonStyle(
                                      shape=ft.RoundedRectangleBorder(radius=4)))
    apply_btn = ft.ElevatedButton("▶  APPLY PARAMS",
                                   bgcolor=ACCENT_VIOLET, color="#000000",
                                   width=260,
                                   style=ft.ButtonStyle(
                                       shape=ft.RoundedRectangleBorder(radius=4)))
    stop_btn  = ft.ElevatedButton("⏹  STOP MOTOR",
                                   bgcolor=ACCENT_RED, color=TEXT_PRIMARY,
                                   width=260,
                                   style=ft.ButtonStyle(
                                       shape=ft.RoundedRectangleBorder(radius=4)))

    # ── Callbacks ──────────────────────────────────────────────────
    def update_conn_state():
        if ds.connected:
            status_text.value = "● CONNECTED"
            status_text.color = ACCENT_GREEN
            led_conn.set(True)
            footer_text.value = f"Connected to {device_dropdown.value or 'BLE device'}"
        else:
            status_text.value = "● DISCONNECTED"
            status_text.color = ACCENT_RED
            led_conn.set(False)
            running_flag["v"]  = False
            acq_btn.text     = "⬤  START ACQUISITION"
            acq_btn.bgcolor  = ACCENT_CYAN
            acq_btn.color    = "#000000"
            footer_text.value = "Disconnected."
        for w in ( status_text, footer_text, acq_btn):
            try: w.update()
            except Exception: pass

    # def toggle_connection(e):
    #     async def runner():
    #         if ds.connected:
    #             #await ds.client.disconnect()
    #             await ds.disconnect()
    #             ds.connected = False
    #             page.run_thread(update_conn_state)
    #             return

    #         footer_text.value = "Scanning..."
    #         footer_text.update()

    #         devices = await ds.scan()

    #         if not devices:
    #             footer_text.value = "No devices found"
    #             footer_text.update()
    #             return

    #         name, address = devices[0]

    #         footer_text.value = f"Connecting to {name}"
    #         footer_text.update()

    #         await ds.connect(address, on_ble_frame)

    #         page.run_thread(update_conn_state)

    #     asyncio.create_task(runner())


    def send_cmd(cmd):
        async def runner():
            await ds.send(cmd)

        asyncio.create_task(runner())

    #conn_btn.on_click = toggle_connection

    # def apply_params(e=None):
    #     ds.mode = mode_radio.value
    #     try:
    #         ds.freq = float(freq_field.value)
    #         ds.amp  = float(amp_field.value)
    #     except ValueError:
    #         pass
    #     footer_text.value = (
    #         f"Params: mode={ds.mode}  "
    #         f"freq={ds.freq:.2f} Hz  amp={ds.amp:.0f} mL")
    #     try: footer_text.update()
    #     except Exception: pass





    async def apply_params(e=None):
        if not ds.connected:
            gui_log(page, "⚠️ Not connected — cannot send params", ACCENT_AMBER)
            footer_text.value = "⚠️ Not connected."
            try: footer_text.update()
            except Exception: pass
            return
        try:
            freq      = float(freq_field.value)
            amp       = float(amp_field.value)
            rpm       = float(target_rpm_field.value)
            accel     = float(accel_field.value)
            pwm       = float(pwm_field.value)
            max_press = float(max_press_field.value)
            max_flow  = float(max_flow_field.value)
            max_vol   = float(max_vol_field.value)

            # waveform command
            wf_cmd = f"SET,{freq},{amp}\n"
            await send_ble_cmd(wf_cmd)

            # motor/driver command
            mot_cmd = f"MOT,{rpm},{accel},{pwm}\n"
            await send_ble_cmd(mot_cmd)

            # safety limits command
            lim_cmd = f"LIM,{max_press},{max_flow},{max_vol}\n"
            await send_ble_cmd(lim_cmd)

            footer_text.value = f"Params sent: WF={freq}Hz/{amp}mL  MOT={rpm}rpm  LIM={max_press}/{max_flow}/{max_vol}"
            footer_text.update()

        except ValueError:
            gui_log(page, "❌ Invalid parameters", ACCENT_RED)

    #apply_btn.on_click = apply_params
    apply_btn.on_click = apply_params

    async def stop_motor(e):
        if not ds.connected:
            gui_log(page, "⚠️ Not connected — cannot stop motor", ACCENT_AMBER)
            footer_text.value = "⚠️ Not connected."
            try: footer_text.update()
            except Exception: pass
            return
        ds.amp = 0.0

        running_flag["v"] = False
        acq_btn.text = "⬤  START ACQUISITION"
        acq_btn.bgcolor = ACCENT_CYAN
        acq_btn.color = "#000000"

        amp_slider.value = amp_slider.min
        amp_field.value = str(amp_slider.min)
        amp_slider.update()
        amp_field.update()
        footer_text.value = "Motor STOP commanded."
        footer_text.update()
        acq_btn.update()

        # invia comando STOP via BLE
        await send_ble_cmd("STOP\n")

    stop_btn.on_click = stop_motor

    def update_ui(f: dict):
        ch_flow.push(f["flow_lpm"])
        ch_press1.push(f["press1_cmH2O"])
        ch_press2.push(f["press2_cmH2O"])
        ch_vol.push(f["volume_ml"])
        ch_rpm.push(f["motor_rpm"])
        ch_enc.push(f["encoder_cts"])

        g_flow.set(f["flow_lpm"])
        g_press1.set(f["press1_cmH2O"])
        g_press2.set(f["press2_cmH2O"])
        g_rpm.set(f["motor_rpm"])
        g_vol.set(f["volume_ml"])

        enc_value.value = str(f["encoder_cts"])
        rpm_value.value = f"{f['motor_rpm']:.0f}"
        for w in (enc_value, rpm_value):
            try: w.update()
            except Exception: pass

        led_sw1.set(bool(f["sw1"]))
        led_sw2.set(bool(f["sw2"]))

    def on_ble_frame(frame):
        if frame is None:
            return

        # logging
        if log_active["v"]:
            log_data["frames"].append(frame)

        # aggiornamento UI thread-safe
        page.run_thread(lambda: update_ui(frame))


    # def toggle_acquisition(e):
    #     if not ds.connected:
    #         dlg = ft.AlertDialog(
    #             title=ft.Text("Not connected"),
    #             content=ft.Text("Please connect first."),
    #         )
    #         #page.overlay.append(dlg)
    #         page.dialog = dlg
    #         dlg.open = True
    #         page.update()
    #         #page.run_thread(lambda: gui_log(page, "..."))
            
    #         return
    #     if running_flag["v"]:
    #         running_flag["v"]  = False
    #         acq_btn.text     = "⬤  START ACQUISITION"
    #         acq_btn.bgcolor  = ACCENT_CYAN
    #         acq_btn.color    = "#000000"
    #     else:
    #         running_flag["v"]  = True
    #         acq_btn.text     = "⏹  STOP ACQUISITION"
    #         acq_btn.bgcolor  = ACCENT_RED
    #         acq_btn.color    = TEXT_PRIMARY
    #         apply_params()
    #         #threading.Thread(target=acq_loop, daemon=True).start()
    #         #on_ble_frame(frame)
    #     acq_btn.update()


    async def toggle_acquisition(e):
        if not ds.connected:
            gui_log(page, "⚠️ Not connected — connect first!", ACCENT_AMBER)
            footer_text.value = "⚠️ Not connected."
            try: footer_text.update()
            except Exception: pass
            return

        if running_flag["v"]:
            running_flag["v"]  = False
            acq_btn.text     = "⬤  START ACQUISITION"
            acq_btn.bgcolor  = ACCENT_CYAN
            acq_btn.color    = "#000000"
        else:
            running_flag["v"]  = True
            acq_btn.text     = "⏹  STOP ACQUISITION"
            acq_btn.bgcolor  = ACCENT_RED
            acq_btn.color    = TEXT_PRIMARY
            await apply_params()

        acq_btn.update()

    #acq_btn.on_click = toggle_acquisition
    acq_btn.on_click = toggle_acquisition

    def toggle_logging(e):
        if not ds.connected and not log_active["v"]:
            gui_log(page, "⚠️ Not connected — connect first to start logging", ACCENT_AMBER)
            footer_text.value = "⚠️ Not connected."
            try: footer_text.update()
            except Exception: pass
            return
        if not log_active["v"]:
            log_data["frames"] = []
            log_active["v"]    = True
            log_btn.text     = "⏹  STOP & SAVE LOG"
            log_btn.bgcolor  = ACCENT_AMBER
            log_btn.color    = "#000000"
            footer_text.value = "Logging started…"
        else:
            log_active["v"] = False
            fname = f"violet_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(fname, "w") as fh:
                json.dump(log_data["frames"], fh, indent=2)
            log_btn.text     = "📁  START LOGGING"
            log_btn.bgcolor  = BG_CARD
            log_btn.color    = TEXT_PRIMARY
            footer_text.value = (
                f"Log saved → {fname}  ({len(log_data['frames'])} frames)")
        log_btn.update()
        try: footer_text.update()
        except Exception: pass

    log_btn.on_click = toggle_logging

    def tick():
        while True:
            try:
                clock_text.value = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
                clock_text.update()
            except Exception:
                pass
            time.sleep(1)

    # ─── Layout ────────────────────────────────────────────────────
    header = ft.Container(
        content=ft.Row([
            ft.Row([
                ft.Text("◈ PROJECT VIOLET", size=18, color=ACCENT_VIOLET,
                        font_family="Courier New", weight=ft.FontWeight.BOLD),
                ft.Text("  Adult Breathing Simulator", size=12,
                        color=TEXT_MUTED, font_family="Courier New"),
            ]),
            status_text,
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        padding=ft.padding.symmetric(12, 16),
        bgcolor=BG_DARK,
    )

    left_panel = ft.Column([
        section("BLE CONNECTION", ft.Column([
            ft.Row([scan_ble_btn, connect_ble_btn, disconnect_ble_btn], spacing=4),
            device_dropdown,
        ], spacing=6)),
        section("QUICK COMMANDS", ft.Column([
            ft.Row([
                ft.ElevatedButton("LED ON",  bgcolor=ACCENT_GREEN, color="#000000",
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=4)),
                    on_click=_btn_led_on),
                ft.ElevatedButton("LED OFF", bgcolor=ACCENT_RED, color=TEXT_PRIMARY,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=4)),
                    on_click=_btn_led_off),
                ft.ElevatedButton("PING", icon=ft.Icons.NETWORK_PING, bgcolor=BG_CARD,
                    color=ACCENT_CYAN,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=4)),
                    on_click=_btn_ping),
                ft.ElevatedButton("READ", icon=ft.Icons.DOWNLOAD, bgcolor=BG_CARD,
                    color=ACCENT_VIOLET,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=4)),
                    on_click=_btn_read),
            ], spacing=4, wrap=True),
            ft.Row([
                custom_input,
                ft.ElevatedButton("SEND", icon=ft.Icons.SEND, bgcolor=ACCENT_VIOLET,
                    color="#000000",
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=4)),
                    on_click=_send_custom),
            ], spacing=4),
        ], spacing=6)),
        section("SERIAL LOG", ble_log_container),
        section("WAVEFORM SETTINGS", ft.Column([
            label_row("Frequency (Hz):", ft.Row([freq_slider, freq_field])),
            label_row("Amplitude (mL):",  ft.Row([amp_slider,  amp_field])),
        ], spacing=6)),
        section("MOTOR / DRIVER", ft.Column([
            label_row("Target RPM:",    target_rpm_field),
            label_row("Accel (rpm/s):", accel_field),
            label_row("PWM duty (%):",  pwm_field),
        ], spacing=6)),
        section("SAFETY LIMITS", ft.Column([
            label_row("Max Press (cmH2O):", max_press_field),
            label_row("Max Flow (L/min):",  max_flow_field),
            label_row("Max Vol (mL):",       max_vol_field),
        ], spacing=6)),
        ft.Column([apply_btn, stop_btn], spacing=4),
        section("DATA ACQUISITION", ft.Column([acq_btn, log_btn], spacing=6)),
        section("DIGITAL INPUTS", ft.Column(
            [led_sw1.control, led_sw2.control, led_conn.control], spacing=6)),
    ], scroll=ft.ScrollMode.AUTO, spacing=0, width=450)

    gauge_row = ft.Row(
        [g_flow.control, g_press1.control, g_press2.control,
         g_rpm.control,  g_vol.control],
        spacing=8, scroll=ft.ScrollMode.AUTO,
    )

    charts = ft.Row([
        ft.Column([ch_flow.control, ch_press1.control, ch_vol.control],
                  expand=True, spacing=4),
        ft.Column([ch_press2.control, ch_rpm.control,  ch_enc.control],
                  expand=True, spacing=4),
    ], expand=True, spacing=8)

    enc_bar = ft.Container(
        content=ft.Row([
            ft.Text("Encoder counts:", size=9, color=TEXT_MUTED,
                    font_family="Courier New"),
            enc_value,
            ft.Container(width=20),
            ft.Text("Motor RPM:", size=9, color=TEXT_MUTED,
                    font_family="Courier New"),
            rpm_value,
        ], spacing=6),
        bgcolor=BG_PANEL,
        padding=ft.padding.symmetric(6, 10),
        border_radius=4,
    )

    right_panel = ft.Column([
        gauge_row,
        ft.Divider(color=BORDER, height=1),
        charts,
        enc_bar,
    ], expand=True, spacing=6)

    footer = ft.Container(
        content=ft.Row(
            [footer_text, clock_text],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        bgcolor=BG_PANEL,
        padding=ft.padding.symmetric(4, 12),
        height=28,
    )

    body = ft.Row([
        ft.Container(content=left_panel,
                     padding=ft.padding.only(left=12, top=8, right=8, bottom=8)),
        ft.VerticalDivider(color=BORDER, width=1),
        ft.Container(content=right_panel, expand=True,
                     padding=ft.padding.symmetric(8, 12)),
    ], expand=True, spacing=0)

    page.add(
        header,
        ft.Divider(color=BORDER, height=1),
        ft.Container(content=body, expand=True),
        footer,
    )
    #page.update()
    page.run_thread(lambda: gui_log(page, "..."))


if __name__ == "__main__":
    ft.app(target=main, view=ft.AppView.FLET_APP)
    #ft.run(target=main)
