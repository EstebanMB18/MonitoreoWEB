# SPRINT_13_8_GENERAL_FINAL_ONLY_OK
from __future__ import annotations
import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from core.orchestrator import load_config, run_monitor, finalize, output_root

ORANGE = "#F45A0A"; BLUE = "#0D65D8"; GREEN = "#2E9F43"; BG = "#F4F7FA"; DARK = "#172334"
RED = "#E63946"; PURPLE = "#7757D6"; MUTED = "#657486"; BORDER = "#DCE5EE"
SOFT_ORANGE = "#FFF4EC"; SOFT_BLUE = "#EEF6FF"; SOFT_GREEN = "#EFF9EC"; SOFT_PURPLE = "#F4F0FF"

class ProgressRing(tk.Canvas):
    def __init__(self, master, size=78, accent=BLUE):
        super().__init__(master, width=size, height=size, bg="white", highlightthickness=0)
        self.size = size
        self.accent = accent
        pad = 8
        self.create_oval(pad, pad, size-pad, size-pad, outline="#E5EDF5", width=7)
        self.arc = self.create_arc(pad, pad, size-pad, size-pad, start=90, extent=0, style="arc", outline=accent, width=7)
        self.txt = self.create_text(size/2, size/2, text="0%", fill=accent, font=("Segoe UI", 11, "bold"))

    def set(self, p, done=False, error=False):
        p = max(0, min(100, int(p)))
        c = RED if error else self.accent
        self.itemconfigure(self.arc, extent=-(p/100)*360, outline=c)
        if error:
            label = "!"
        elif done:
            label = "100%"
        else:
            label = f"{p}%"
        self.itemconfigure(self.txt, text=label, fill=c, font=("Segoe UI", 11, "bold"))

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Centro de Monitoreo Compensar")
        self.geometry("1440x900")
        self.minsize(1180, 760)
        self.configure(bg=BG)
        self.q = queue.Queue()
        self.running = False
        self.last_selected = tuple()
        self.active_processes = []
        self.cancel_requested = False
        self.vars = {m: tk.BooleanVar(value=True) for m in ["PASARELAS", "AWS", "HERCULES"]}
        self.modo = tk.StringVar(value="actual")
        self.corte = tk.StringVar(value="09")
        self.fecha = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        self.historico_tipo = tk.StringVar(value="completo")
        self.hora_inicio = tk.StringVar(value="00:00")
        self.hora_fin = tk.StringVar(value="23:59")
        self.status = {m: tk.StringVar(value="Listo") for m in self.vars}
        self.progress = {m: 0 for m in self.vars}
        self.rings = {}
        self.final_labels = {}
        self.logo_img = None
        self._build()
        self.after(120, self._poll)

    def _build(self):
        self._build_header()

        main = tk.Frame(self, bg=BG)
        main.pack(fill="both", expand=True, padx=22, pady=18)

        top = tk.Frame(main, bg=BG)
        top.pack(fill="x")
        top.grid_columnconfigure(0, weight=3)
        top.grid_columnconfigure(1, weight=1)

        exec_card = tk.Frame(top, bg="white", highlightthickness=1, highlightbackground=BORDER)
        exec_card.grid(row=0, column=0, sticky="nsew", padx=(0, 9))
        cfg_card = tk.Frame(top, bg="white", highlightthickness=1, highlightbackground=BORDER)
        cfg_card.grid(row=0, column=1, sticky="nsew", padx=(9, 0))

        self._build_exec_panel(exec_card)
        self._build_cfg_panel(cfg_card)

        stat = tk.Frame(main, bg=BG)
        stat.pack(fill="x", pady=(16, 14))
        monitor_meta = {
            "PASARELAS": (BLUE, SOFT_BLUE, "▦"),
            "AWS": (ORANGE, SOFT_ORANGE, "●"),
            "HERCULES": (PURPLE, SOFT_PURPLE, "◆"),
        }
        for i, m in enumerate(self.vars):
            accent, soft, symbol = monitor_meta[m]
            card = tk.Frame(stat, bg="white", highlightthickness=1, highlightbackground=BORDER)
            card.pack(side="left", fill="both", expand=True, padx=(0 if i == 0 else 7, 0 if i == 2 else 7))

            inner = tk.Frame(card, bg="white")
            inner.pack(fill="both", expand=True, padx=16, pady=14)

            head = tk.Frame(inner, bg="white")
            head.pack(fill="x")
            icon = tk.Label(head, text=symbol, bg=accent, fg="white", font=("Segoe UI Symbol", 15, "bold"), width=3, height=1)
            icon.pack(side="left", padx=(0, 12))
            titlebox = tk.Frame(head, bg="white")
            titlebox.pack(side="left", fill="x", expand=True)
            tk.Label(titlebox, text=m, bg="white", fg=accent, font=("Segoe UI", 14, "bold")).pack(anchor="w")
            tk.Label(titlebox, textvariable=self.status[m], bg="white", fg=MUTED, font=("Segoe UI", 9), wraplength=220, justify="left").pack(anchor="w", pady=(4, 0))

            ring = ProgressRing(head, size=76, accent=accent)
            ring.pack(side="right")
            self.rings[m] = ring

            badge_row = tk.Frame(inner, bg="white")
            badge_row.pack(fill="x", pady=(7, 8))
            lab = tk.Label(badge_row, text="LISTO", bg="#EAF7E6", fg="#2B7A22", font=("Segoe UI", 8, "bold"), padx=10, pady=3)
            lab.pack(side="left")
            self.final_labels[m] = lab

            actions = tk.Frame(inner, bg="white")
            actions.pack(fill="x", pady=(4, 0))
            self._action_tile(actions, "▥", "Dashboard", "Abrir detalle", accent, soft, lambda mm=m: self.open_monitor_dashboard(mm), compact=True).pack(side="left", fill="x", expand=True, padx=(0, 5))
            self._action_tile(actions, "□", "Carpeta", "Archivos", BLUE, SOFT_BLUE, lambda mm=m: self.open_monitor_folder(mm), compact=True).pack(side="left", fill="x", expand=True, padx=(5, 0))

        activity = tk.Frame(main, bg="white", highlightthickness=1, highlightbackground=BORDER)
        activity.pack(fill="both", expand=True)
        activity_head = tk.Frame(activity, bg="white")
        activity_head.pack(fill="x", padx=16, pady=(11, 7))
        tk.Label(activity_head, text="▣  ACTIVIDAD", bg="white", fg=DARK, font=("Segoe UI", 11, "bold")).pack(side="left")
        tk.Label(activity_head, text="Eventos de la ejecución actual", bg="white", fg=MUTED, font=("Segoe UI", 9)).pack(side="right")

        log_wrap = tk.Frame(activity, bg="#0E1A27")
        log_wrap.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self.log = tk.Text(log_wrap, bg="#0E1A27", fg="#DCE8F4", insertbackground="white", font=("Consolas", 9), bd=0, relief="flat", padx=12, pady=10)
        self.log.pack(fill="both", expand=True)
        self.write("Listo. Los monitores son independientes y el consolidado se actualiza al final.")

    def _build_header(self):
        header = tk.Frame(self, bg=ORANGE, height=104)
        header.pack(fill="x")
        header.pack_propagate(False)

        wrap = tk.Frame(header, bg=ORANGE)
        wrap.pack(fill="both", expand=True, padx=28, pady=14)

        brand = tk.Frame(wrap, bg=ORANGE)
        brand.pack(side="left", anchor="w")

        logo = tk.Canvas(brand, width=62, height=62, bg=ORANGE, highlightthickness=0, bd=0)
        logo.pack(side="left", padx=(0, 12))
        r = 8
        centros = [(25,12),(43,12),(15,30),(31,30),(25,48),(43,48)]
        for cx, cy in centros:
            logo.create_oval(cx-r, cy-r, cx+r, cy+r, fill="white", outline="white")

        textos = tk.Frame(brand, bg=ORANGE)
        textos.pack(side="left", anchor="center")
        topbrand = tk.Frame(textos, bg=ORANGE)
        topbrand.pack(anchor="w")
        tk.Label(topbrand, text="compensar", bg=ORANGE, fg="white", font=("Segoe UI", 12, "bold")).pack(side="left")
        tk.Label(textos, text="CENTRO DE MONITOREO", bg=ORANGE, fg="white", font=("Segoe UI", 22, "bold")).pack(anchor="w", pady=(2,0))
        tk.Label(textos, text="Monitoreo inteligente, operación confiable", bg=ORANGE, fg="#FFF1E7", font=("Segoe UI", 10)).pack(anchor="w", pady=(2,0))

        right = tk.Frame(wrap, bg="#E94E08", padx=18, pady=9)
        right.pack(side="right", anchor="e", pady=5)
        tk.Label(right, text="HORARIO OPERATIVO", bg="#E94E08", fg="white", font=("Segoe UI", 9, "bold")).pack(anchor="center")
        tk.Label(right, text="◷  09:00  -  13:00  -  17:00", bg="#E94E08", fg="white", font=("Segoe UI", 9)).pack(anchor="center", pady=(5,0))

    def _build_exec_panel(self, execf):
        head = tk.Frame(execf, bg="white")
        head.pack(fill="x", padx=20, pady=(16, 8))
        tk.Label(head, text="●", bg="white", fg=ORANGE, font=("Segoe UI", 18, "bold")).pack(side="left", padx=(0, 8))
        tk.Label(head, text="EJECUTAR MONITOREO", bg="white", fg=DARK, font=("Segoe UI", 12, "bold")).pack(side="left")

        row = tk.Frame(execf, bg="white")
        row.pack(fill="x", padx=20, pady=(4, 10))
        for label, val in [("Corte programado", "actual"), ("Ahora (00:00 a hora actual)", "acumulado-hoy"), ("Día anterior", "dia-anterior"), ("Fecha específica", "fecha")]:
            tk.Radiobutton(row, text=label, variable=self.modo, value=val, bg="white", activebackground="white", fg=DARK, selectcolor="white", font=("Segoe UI", 9)).pack(side="left", padx=(0, 16))
        tk.Entry(row, textvariable=self.fecha, width=12, font=("Segoe UI", 10), relief="solid", bd=1, highlightthickness=1, highlightbackground=BORDER).pack(side="left", padx=(4, 12), ipady=4)
        tk.Label(row, text="Corte:", bg="white", fg=DARK, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 6))
        ttk.Combobox(row, textvariable=self.corte, values=["09", "13", "17"], width=5, state="readonly").pack(side="left")

        hist = tk.Frame(execf, bg=SOFT_ORANGE, highlightthickness=1, highlightbackground="#FFE1CF")
        hist.pack(fill="x", padx=20, pady=(2, 10))
        tk.Label(hist, text="▦", bg=SOFT_ORANGE, fg=ORANGE, font=("Segoe UI Symbol", 12, "bold")).pack(side="left", padx=(12, 8), pady=10)
        tk.Label(hist, text="Para día anterior / fecha específica:", bg=SOFT_ORANGE, fg=DARK, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 12))
        tk.Radiobutton(hist, text="Día completo (00:00 - 23:59)", variable=self.historico_tipo, value="completo", bg=SOFT_ORANGE, activebackground=SOFT_ORANGE, selectcolor=SOFT_ORANGE, font=("Segoe UI", 9)).pack(side="left")
        tk.Radiobutton(hist, text="Rango:", variable=self.historico_tipo, value="rango", bg=SOFT_ORANGE, activebackground=SOFT_ORANGE, selectcolor=SOFT_ORANGE, font=("Segoe UI", 9)).pack(side="left", padx=(12, 4))
        tk.Entry(hist, textvariable=self.hora_inicio, width=6, justify="center", relief="solid", bd=1).pack(side="left", ipady=3)
        tk.Label(hist, text="  ~  ", bg=SOFT_ORANGE, fg=MUTED).pack(side="left")
        tk.Entry(hist, textvariable=self.hora_fin, width=6, justify="center", relief="solid", bd=1).pack(side="left", ipady=3)

        mons = tk.Frame(execf, bg="white")
        mons.pack(fill="x", padx=20, pady=(2, 10))
        tk.Label(mons, text="Monitores a ejecutar:", bg="white", fg=DARK, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 12))
        for m in self.vars:
            tk.Checkbutton(mons, text=m, variable=self.vars[m], bg="white", activebackground="white", selectcolor="#FFF2E8", fg=DARK, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 18))

        buttons = tk.Frame(execf, bg="white")
        buttons.pack(fill="x", padx=20, pady=(2, 14))
        self.runbtn = tk.Button(buttons, text="▶  EJECUTAR", command=self.start, bg=ORANGE, fg="white", activebackground="#D94C05", activeforeground="white", font=("Segoe UI", 11, "bold"), bd=0, relief="flat", padx=28, pady=12, cursor="hand2")
        self.runbtn.pack(side="left")
        self.cancelbtn = tk.Button(buttons, text="■  CANCELAR TODO", command=self.cancel_all, bg="#FFF5F5", fg=RED, activebackground="#FFE9EA", activeforeground=RED, font=("Segoe UI", 10, "bold"), bd=1, relief="solid", padx=25, pady=11, state="disabled", cursor="hand2")
        self.cancelbtn.pack(side="left", padx=(12, 0))

        quick_title = tk.Frame(execf, bg="white")
        quick_title.pack(fill="x", padx=20, pady=(0, 8))
        tk.Label(quick_title, text="ϟ", bg="white", fg=BLUE, font=("Segoe UI Symbol", 13, "bold")).pack(side="left", padx=(0, 8))
        tk.Label(quick_title, text="Accesos rápidos", bg="white", fg=DARK, font=("Segoe UI", 10, "bold")).pack(side="left")

        quick = tk.Frame(execf, bg="white")
        quick.pack(fill="x", padx=20, pady=(0, 18))
        self.openbtn = self._action_tile(quick, "□", "Abrir carpeta", "según selección", BLUE, SOFT_BLUE, self.open_result_folder)
        self.openbtn.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.dashboard_btn = self._action_tile(quick, "▥", "Ver dashboard", "según selección", GREEN, SOFT_GREEN, self.refresh_dash)
        self.dashboard_btn.pack(side="left", fill="x", expand=True, padx=6)
        self._action_tile(quick, "◔", "Dashboard", "general", ORANGE, SOFT_ORANGE, self.open_general_dashboard).pack(side="left", fill="x", expand=True, padx=(6,0))

    def _build_cfg_panel(self, cfgf):
        cfg = load_config()
        self.pathvar = tk.StringVar(value=cfg["output_root"])

        head = tk.Frame(cfgf, bg="white")
        head.pack(fill="x", padx=18, pady=(16, 10))
        tk.Label(head, text="⚙", bg=PURPLE, fg="white", font=("Segoe UI Symbol", 12, "bold"), width=2, height=1).pack(side="left", padx=(0, 9))
        tk.Label(head, text="ACCESOS Y CONFIGURACIÓN", bg="white", fg=DARK, font=("Segoe UI", 11, "bold")).pack(side="left")

        tk.Label(cfgf, text="Carpeta raíz de salida", bg="white", fg=DARK, font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=18, pady=(4, 6))
        pathbox = tk.Frame(cfgf, bg="#FBFCFE", highlightthickness=1, highlightbackground=BORDER)
        pathbox.pack(fill="x", padx=18)
        tk.Label(pathbox, text="□", bg="#FBFCFE", fg=MUTED, font=("Segoe UI Symbol", 13)).pack(side="left", padx=(10, 8), pady=11)
        tk.Label(pathbox, textvariable=self.pathvar, bg="#FBFCFE", fg=DARK, justify="left", anchor="w", wraplength=285, font=("Segoe UI", 9)).pack(side="left", fill="x", expand=True, padx=(0,10), pady=9)

        quick = tk.Frame(cfgf, bg="white")
        quick.pack(fill="x", padx=18, pady=12)
        quick.grid_columnconfigure(0, weight=1)
        quick.grid_columnconfigure(1, weight=1)
        tk.Button(quick, text="Cambiar carpeta", command=self.change_path, bg=SOFT_PURPLE, fg=PURPLE, bd=0, relief="flat", pady=10, font=("Segoe UI", 9, "bold"), cursor="hand2").grid(row=0,column=0,sticky="ew",padx=(0,5),pady=(0,8))
        tk.Button(quick, text="Abrir salida raíz", command=self.open_output_root, bg="#F4F5F8", fg=DARK, bd=0, relief="flat", pady=10, font=("Segoe UI", 9), cursor="hand2").grid(row=0,column=1,sticky="ew",padx=(5,0),pady=(0,8))
        tk.Button(quick, text="Usuarios y sesiones", command=self.credentials_window, bg=SOFT_ORANGE, fg=ORANGE, bd=0, relief="flat", pady=10, font=("Segoe UI", 9, "bold"), cursor="hand2").grid(row=1,column=0,sticky="ew",padx=(0,5))
        tk.Button(quick, text="Dashboard general", command=self.open_general_dashboard, bg=SOFT_GREEN, fg="#277B31", bd=0, relief="flat", pady=10, font=("Segoe UI", 9, "bold"), cursor="hand2").grid(row=1,column=1,sticky="ew",padx=(5,0))

        info = tk.Frame(cfgf, bg=SOFT_BLUE, highlightthickness=1, highlightbackground="#D7E8FA")
        info.pack(fill="x", padx=18, pady=(2, 8))
        tk.Label(info, text="i", bg="#4A8FE7", fg="white", font=("Segoe UI", 9, "bold"), width=2).pack(side="left", padx=(8,9), pady=10)
        tk.Label(info, text="Tip: si ejecutas solo un monitor, los botones de su tarjeta abren directamente su dashboard y carpeta.", bg=SOFT_BLUE, fg="#40566D", wraplength=285, justify="left", font=("Segoe UI", 8)).pack(side="left", fill="x", expand=True, padx=(0,8), pady=8)

        info2 = tk.Frame(cfgf, bg="#F6F8FB", highlightthickness=1, highlightbackground="#E4E9EF")
        info2.pack(fill="x", padx=18, pady=(0,16))
        tk.Label(info2, text="</>", bg="#4A8FE7", fg="white", font=("Consolas", 8, "bold"), width=3).pack(side="left", padx=(8,9), pady=10)
        tk.Label(info2, text="41605 JAVA y 41610 RED se abren visibles en procesos separados para no bloquear el resto.", bg="#F6F8FB", fg="#5D6B79", wraplength=285, justify="left", font=("Segoe UI", 8)).pack(side="left", fill="x", expand=True, padx=(0,8), pady=8)

    def _action_tile(self, parent, symbol, title, subtitle, accent, soft, command, compact=False):
        tile = tk.Frame(parent, bg=soft, highlightthickness=1, highlightbackground=BORDER, cursor="hand2")
        icon = tk.Label(tile, text=symbol, bg=soft, fg=accent, font=("Segoe UI Symbol", 14, "bold"), cursor="hand2")
        icon.pack(side="left", padx=(10 if compact else 14, 8), pady=8 if compact else 11)
        txt = tk.Frame(tile, bg=soft, cursor="hand2")
        txt.pack(side="left", fill="both", expand=True, padx=(0,8), pady=6 if compact else 8)
        t = tk.Label(txt, text=title, bg=soft, fg=accent, font=("Segoe UI", 9, "bold"), cursor="hand2")
        t.pack(anchor="w")
        s = tk.Label(txt, text=subtitle, bg=soft, fg=MUTED, font=("Segoe UI", 8), cursor="hand2")
        s.pack(anchor="w", pady=(1,0))
        for w in (tile, icon, txt, t, s):
            w.bind("<Button-1>", lambda _e, cmd=command: cmd())
        return tile

    def write(self, msg):
        self.log.insert("end", f"[{datetime.now():%H:%M:%S}] {msg}\n")
        self.log.see("end")

    def _infer_progress(self, name, state, detail):
        t = (detail or "").lower()
        cur = self.progress.get(name, 0)

        if state == "ERROR":
            return 100, False, True
        if state == "OK":
            return 100, True, False
        if state == "CANCELADO":
            return cur, False, False

        if state == "PREPARANDO":
            if "sesiÃ³n ecollect preparada" in t or "sesion ecollect preparada" in t:
                return max(cur, 10), False, False
            if "sesiones de pasarelas listas" in t:
                return max(cur, 12), False, False
            return max(cur, 5), False, False

        if name == "PASARELAS":
            if "iniciando..." in t:
                cur = max(cur, 15)
            elif "payu: abriendo" in t or "payu: formulario" in t or "payu: sesiÃ³n" in t or "payu: sesion" in t:
                cur = max(cur, 20)
            elif "payu: fecha inicio" in t or "payu: fechas diligenciadas" in t:
                cur = max(cur, 24)
            elif "payu: iniciando descarga" in t or "botÃ³n download" in t or "boton download" in t:
                cur = max(cur, 28)
            elif "payu: descarga directa detectada" in t or "archivo guardado correctamente" in t:
                cur = max(cur, 34)
            elif "[fast]" in t and "consultas" in t:
                cur = max(cur, 30)
            elif "[41605_java]" in t or "[41610_red]" in t:
                cur = max(cur, 34)
            elif "csv descargado" in t:
                cur = min(82, max(cur + 3, 38))
            elif "sin_datos" in t or "sin datos" in t:
                cur = min(82, max(cur + 2, 38))
            elif "trabajos iniciados en paralelo" in t:
                cur = max(cur, 45)
            elif "finalizado con cÃ³digo 0" in t or "finalizado con codigo 0" in t:
                cur = min(90, max(cur + 4, 72))
            elif "html generado" in t:
                cur = max(cur, 94)
            elif "excel generado" in t:
                cur = max(cur, 97)
            elif "consolidado pasarelas" in t:
                cur = max(cur, 99)

        elif name == "AWS":
            if "iniciando" in t:
                cur = max(cur, 8)
            elif "monitoreando:" in t or "rango:" in t:
                cur = max(cur, 18)
            elif t.strip().startswith("-"):
                cur = min(88, max(cur + 2, 22))
            elif "excel:" in t:
                cur = max(cur, 94)
            elif "html:" in t:
                cur = max(cur, 97)

        elif name == "HERCULES":
            if "iniciando navegador" in t:
                cur = max(cur, 10)
            elif "entrando al reporte" in t:
                cur = max(cur, 18)
            elif "fechas configuradas" in t:
                cur = max(cur, 30)
            elif "torneos" in t:
                cur = max(cur, 38)
            elif "gimnasios" in t:
                cur = max(cur, 48)
            elif "turnos" in t:
                cur = max(cur, 58)
            elif "citas" in t:
                cur = max(cur, 68)
            elif "materiales" in t:
                cur = max(cur, 78)
            elif "generar reporte" in t:
                cur = max(cur, 84)
            elif "archivo descargado" in t:
                cur = max(cur, 90)
            elif "resumen excel generado" in t:
                cur = max(cur, 94)
            elif "dashboard" in t:
                cur = max(cur, 98)

        return cur, False, False

    def cb(self, name, state, detail):

        try:
            progreso = self._progress_from_message(
                monitor, estado, detalle
            )
            if progreso is not None:
                try:
                    self.progress_value[monitor] = progreso
                except Exception:
                    pass
        except Exception:
            pass
        self.q.put((name, state, detail))
    def _poll(self):
        try:
            while True:
                name, state, detail = self.q.get_nowait()
                if name in self.status:
                    self.status[name].set(f"{state}: {detail[:180]}")
                    pct,done,err=self._infer_progress(name,state,detail); self.progress[name]=pct
                    if name in self.rings: self.rings[name].set(pct,done,err)
                    if name in self.final_labels:
                        if done:
                            self.final_labels[name].config(text="FINALIZADO", fg="#2B7A22", bg="#EAF7E6")
                        elif err:
                            self.final_labels[name].config(text="ERROR", fg="#B5222A", bg="#FDEBEC")
                        elif state in ("EJECUTANDO", "PREPARANDO"):
                            self.final_labels[name].config(text="EN PROCESO", fg="#9A5A00", bg="#FFF3D6")
                self.write(f"{name} · {state} · {detail}")
        except queue.Empty:
            pass
        self.after(120, self._poll)

    def start(self):
        # -----------------------------------------------------
        # No permitir dos ejecuciones simultáneas desde la UI
        # -----------------------------------------------------
        if self.running:
            messagebox.showwarning(
                "Monitoreo en ejecución",
                "Ya existe un monitoreo ejecutándose.\n\n"
                "Espera a que finalice o utiliza CANCELAR TODO."
            )
            return

        # Captura INMUTABLE de la selección en este instante.
        selected = tuple(
            m
            for m, variable in self.vars.items()
            if variable.get() is True
        )

        # Recordar qué monitores fueron seleccionados en
        # la ejecución actual.
        self.last_selected = selected

        if not selected:
            messagebox.showwarning(
                "Monitoreo",
                "Selecciona al menos un monitor."
            )
            return

        # -----------------------------------------------------
        # Validar fecha/rango
        # -----------------------------------------------------
        if self.modo.get() == "fecha":
            try:
                datetime.strptime(
                    self.fecha.get(),
                    "%Y-%m-%d"
                )
            except ValueError:
                messagebox.showerror(
                    "Fecha",
                    "Usa formato YYYY-MM-DD."
                )
                return

        if (
            self.modo.get() in ("dia-anterior", "fecha")
            and self.historico_tipo.get() == "rango"
        ):
            try:
                hi = datetime.strptime(
                    self.hora_inicio.get().strip(),
                    "%H:%M"
                )

                hf = datetime.strptime(
                    self.hora_fin.get().strip(),
                    "%H:%M"
                )

                if hf <= hi:
                    raise ValueError

            except ValueError:
                messagebox.showerror(
                    "Rango horario",
                    "Usa horas HH:MM y asegúrate de que "
                    "la hora final sea mayor que la inicial."
                )
                return

        # -----------------------------------------------------
        # Reiniciar visualmente las tarjetas
        # -----------------------------------------------------
        for monitor in self.status:

            if monitor in selected:
                self.status[monitor].set(
                    "EN COLA · 0%"
                )
            else:
                self.status[monitor].set(
                    "NO SELECCIONADO"
                )

                # El indicador gráfico se limpia después en el
                # refresco visual; no debe conservar el ✓ anterior.
                try:
                    self.progress_value[monitor] = 0
                except Exception:
                    pass

        self.write(
            "SYSTEM · SELECCIÓN · "
            + ", ".join(selected)
        )

        self.last_selected = tuple(selected)

        # Limpiar el resultado visual de la ejecuciÃ³n anterior.
        for monitor in self.status:
            self.progress[monitor] = 0
            if monitor in self.rings:
                self.rings[monitor].set(0, False, False)
            if monitor in self.final_labels:
                self.final_labels[monitor].config(text="LISTO", fg="#2B7A22", bg="#EAF7E6")

        self._pasarelas_csv_count = 0

        # Marca temporal del inicio REAL de esta ejecución. El General solo
        # aceptará fuentes publicadas después de este instante.
        self.run_started_at = datetime.now()

        self.running = True
        self.cancel_requested = False

        self.runbtn.config(
            state="disabled"
        )

        self.cancelbtn.config(
            state="normal",
            text="■ CANCELAR TODO"
        )

        # La tupla selected ya no puede cambiar aunque el
        # usuario toque los checkboxes después.
        threading.Thread(
            target=self._run_all,
            args=(selected,),
            daemon=True
        ).start()



    def _progress_from_message(self, monitor, estado, detalle):
        """
        Calcula progreso aproximado usando hitos REALES del log.
        No es un temporizador.
        """
        m = (monitor or "").upper()
        e = (estado or "").upper()
        d = (detalle or "").lower()

        if e == "OK":
            return 100

        if e in ("ERROR", "CANCELADO"):
            return None

        if m == "PASARELAS":
            if "primera ejecución" in d or "preparando sesión" in d:
                return 5
            if "sesión ecollect preparada correctamente" in d:
                return 10
            if "iniciando" in d:
                return 15
            if "trabajos iniciados en paralelo" in d:
                return 25
            if "payu:" in d and "descarga directa detectada" in d:
                return 35
            if "payu:" in d and "archivo guardado correctamente" in d:
                return 40
            if "[fast]" in d:
                return 45
            if "csv descargado" in d:
                # Va progresando conforme aparecen archivos.
                actual = getattr(
                    self,
                    "_pasarelas_csv_count",
                    0
                ) + 1

                self._pasarelas_csv_count = actual

                return min(
                    45 + actual * 2,
                    82
                )

            if "41605_java" in d and "finalizado con código 0" in d:
                return 86

            if "41610_red" in d and "finalizado con código 0" in d:
                return 89

            if "ecollect_rapido" in d and "finalizado con código 0" in d:
                return 91

            if "payu" in d and "finalizado con código 0" in d:
                return 93

            if "html generado" in d:
                return 96

            if "excel generado" in d:
                return 98

            if "consolidado pasarelas" in d:
                return 99

        if m == "AWS":
            if "iniciando" in d:
                return 5
            if "monitoreando:" in d:
                return 20
            if "rango:" in d:
                return 30
            if "excel:" in d:
                return 85
            if "html:" in d:
                return 92
            if "alertas:" in d:
                return 97

        if m == "HERCULES":
            if "primera ejecución" in d:
                return 5
            if "sesión creada correctamente" in d:
                return 10
            if "iniciando navegador" in d:
                return 15
            if "configurando fechas" in d:
                return 25
            if "marcando cuadros principales" in d:
                return 35
            if "torneos" in d and "checkbox marcado" in d:
                return 45
            if "gimnasios" in d and "checkbox marcado" in d:
                return 55
            if "turnos" in d and "checkbox marcado" in d:
                return 65
            if "citas" in d and "checkbox marcado" in d:
                return 72
            if "materiales" in d and "checkbox marcado" in d:
                return 80
            if "generar reporte" in d:
                return 88
            if "archivo descargado" in d:
                return 94
            if "dashboard html generado" in d:
                return 98

        return None

    def _run_all(self, selected):
        try:
            threads = []

            def one(m):
                if self.cancel_requested:
                    return

                try:
                    run_monitor(
                        m,
                        self.modo.get(),
                        self.corte.get(),
                        self.fecha.get()
                        if self.modo.get() == "fecha"
                        else None,
                        "00:00"
                        if self.historico_tipo.get() == "completo"
                        else self.hora_inicio.get().strip(),
                        "23:59"
                        if self.historico_tipo.get() == "completo"
                        else self.hora_fin.get().strip(),
                        self.cb,
                    )
                except Exception as exc:
                    if not self.cancel_requested:
                        self.q.put(
                            (
                                m,
                                "ERROR",
                                str(exc)
                            )
                        )

            for m in selected:

                if self.cancel_requested:
                    break

                t = threading.Thread(
                    target=one,
                    args=(m,),
                    daemon=True
                )

                t.start()
                threads.append(t)

            # Espera controlada para poder reaccionar
            # correctamente a CANCELAR TODO.
            while any(t.is_alive() for t in threads):

                if self.cancel_requested:
                    break

                for t in threads:
                    t.join(timeout=0.25)

            # MUY IMPORTANTE:
            # después de una cancelación no se genera consolidado
            # ni se puede informar SYSTEM OK.
            if self.cancel_requested:

                self.q.put(
                    (
                        "SYSTEM",
                        "CANCELADO",
                        "Ejecución cancelada por el usuario."
                    )
                )

                return

            # Si no se canceló, terminamos de unir hilos.
            for t in threads:
                t.join()

            # Doble validación antes de consolidar.
            if self.cancel_requested:
                return

            # El consolidado GENERAL se genera UNA SOLA VEZ y únicamente
            # después de que todos los monitores seleccionados terminaron.
            # Además se rechazan archivos anteriores a esta ejecución.
            deleted, dash, excel = finalize(
                selected=selected,
                run_started_at=getattr(self, "run_started_at", None),
            )

            if self.cancel_requested:
                return

            self.q.put(
                (
                    "SYSTEM",
                    "OK",
                    (
                        f"Monitoreo finalizado. "
                        f"Limpieza: {deleted} archivos. "
                        f"Dashboard: {dash.name}. "
                        f"Excel: "
                        f"{excel.name if excel else 'pendiente'}"
                    )
                )
            )

        except Exception as exc:

            if not self.cancel_requested:

                self.q.put(
                    (
                        "SYSTEM",
                        "ERROR",
                        str(exc)
                    )
                )

        finally:

            self.running = False

            self.after(
                0,
                lambda: self.runbtn.config(
                    state="normal"
                )
            )

            self.after(
                0,
                lambda: self.cancelbtn.config(
                    state="disabled",
                    text="■ CANCELAR TODO"
                )
            )


    def cancel_all(self):
        """
        Cancela todos los procesos relacionados con esta
        ejecución de monitoreo.

        Esto incluye:
        - run.py / monitores principales
        - PayU worker
        - eCollect worker rápido
        - 41605 JAVA
        - 41610 RED
        - Hércules
        - AWS
        """

        if not self.running:
            return

        self.cancel_requested = True

        self.cancelbtn.config(
            state="disabled",
            text="CANCELANDO..."
        )

        self.write(
            "SYSTEM · CANCELANDO · "
            "Deteniendo todos los procesos activos..."
        )

        for m in self.status:
            actual = self.status[m].get()

            if (
                "OK" not in actual
                and "ERROR" not in actual
            ):
                self.status[m].set(
                    "CANCELANDO..."
                )

        def matar():
            try:
                if os.name == "nt":

                    # Buscar procesos Python/PowerShell/CMD
                    # relacionados exclusivamente con este proyecto.

                    proyecto = str(ROOT)

                    cmd = [
                        "powershell",
                        "-NoProfile",
                        "-Command",
                        (
                            "Get-CimInstance Win32_Process | "
                            "Where-Object { "
                            "$_.CommandLine -like "
                            f"'*{proyecto.replace(chr(92), chr(92)+chr(92))}*' "
                            "-and "
                            "$_.ProcessId -ne $PID "
                            "} | "
                            "ForEach-Object { "
                            "Stop-Process "
                            "-Id $_.ProcessId "
                            "-Force "
                            "-ErrorAction SilentlyContinue "
                            "}"
                        )
                    ]

                    subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=20
                    )

                self.after(
                    0,
                    self._cancel_finished
                )

            except Exception as exc:

                self.q.put(
                    (
                        "SYSTEM",
                        "ERROR",
                        f"No pude cancelar todo: {exc}"
                    )
                )

                self.after(
                    0,
                    self._cancel_finished
                )

        threading.Thread(
            target=matar,
            daemon=True
        ).start()


    def _cancel_finished(self):
        for m in self.status:
            actual = self.status[m].get()

            if (
                "OK" not in actual
                and "ERROR" not in actual
            ):
                self.status[m].set(
                    "CANCELADO"
                )

        self.write(
            "SYSTEM · CANCELADO · "
            "Todos los procesos del monitoreo fueron detenidos."
        )

        self.cancelbtn.config(
            text="■ CANCELAR TODO",
            state="disabled"
        )

        self.runbtn.config(
            state="normal"
        )

        self.running = False

    def _read_env(self, path):
        p = Path(path)
        return dict(dotenv_values(p)) if p.exists() else {}

    def _write_env(self, path, values):
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        old = self._read_env(p)
        old.update(values)
        lines = []
        for k, v in old.items():
            if v is None:
                v = ""
            lines.append(f"{k}={str(v).replace(chr(10), ' ').replace(chr(13), ' ')}")
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def credentials_window(self):
        w = tk.Toplevel(self)
        w.title("Credenciales y sesiones")
        w.geometry("900x650")
        w.minsize(820, 600)
        w.configure(bg=BG)
        w.transient(self)
        w.grab_set()

        # =========================================================
        # CABECERA
        # =========================================================

        header = tk.Frame(
            w,
            bg=ORANGE,
            height=64
        )
        header.pack(
            side="top",
            fill="x"
        )
        header.pack_propagate(False)

        tk.Label(
            header,
            text="USUARIOS, CLAVES Y SESIONES",
            bg=ORANGE,
            fg="white",
            font=("Segoe UI", 17, "bold")
        ).pack(
            expand=True
        )

        # =========================================================
        # FOOTER FIJO
        # =========================================================

        footer = tk.Frame(
            w,
            bg="white",
            height=70,
            highlightthickness=1,
            highlightbackground="#D9E5EF"
        )
        footer.pack(
            side="bottom",
            fill="x"
        )
        footer.pack_propagate(False)

        status_var = tk.StringVar(
            value="Sin cambios pendientes"
        )

        tk.Label(
            footer,
            textvariable=status_var,
            bg="white",
            fg="#53606C",
            font=("Segoe UI", 9)
        ).pack(
            side="left",
            padx=16
        )

        # =========================================================
        # CUERPO
        # =========================================================

        body = tk.Frame(
            w,
            bg=BG
        )
        body.pack(
            side="top",
            fill="both",
            expand=True,
            padx=16,
            pady=14
        )

        pe = self._read_env(
            ROOT / "monitores" / "pasarelas" / ".env"
        )

        he = self._read_env(
            ROOT / "monitores" / "hercules" / ".env"
        )

        vals = {}

        fields = [
            (
                "e_user",
                "eCollect · Usuario",
                pe.get("ECOLLECT_USER", ""),
                False
            ),
            (
                "e_pass",
                "eCollect · Clave",
                pe.get("ECOLLECT_PASSWORD", ""),
                True
            ),
            (
                "p_user",
                "PayU · Usuario",
                pe.get("PAYU_USER", ""),
                False
            ),
            (
                "p_pass",
                "PayU · Clave",
                pe.get("PAYU_PASSWORD", ""),
                True
            ),
            (
                "h_user",
                "Hércules · Usuario",
                he.get("HERCULES_USERNAME", ""),
                False
            ),
            (
                "h_pass",
                "Hércules · Clave",
                he.get("HERCULES_PASSWORD", ""),
                True
            ),
        ]

        form = tk.LabelFrame(
            body,
            text=" Credenciales locales ",
            bg="white",
            fg=DARK,
            font=("Segoe UI", 10, "bold"),
            bd=0,
            highlightthickness=1,
            highlightbackground="#D9E5EF"
        )

        form.pack(
            fill="x"
        )

        dirty = {
            "value": False
        }

        password_entries = []

        def mark_dirty(*_):
            dirty["value"] = True
            status_var.set(
                "Cambios sin guardar"
            )

        for i, (
            key,
            label,
            value,
            secret
        ) in enumerate(fields):

            tk.Label(
                form,
                text=label,
                bg="white",
                fg=DARK,
                font=("Segoe UI", 10, "bold")
            ).grid(
                row=i,
                column=0,
                sticky="w",
                padx=(16, 12),
                pady=10
            )

            variable = tk.StringVar(
                value=value
            )

            vals[key] = variable

            variable.trace_add(
                "write",
                mark_dirty
            )

            entry = tk.Entry(
                form,
                textvariable=variable,
                show="*" if secret else "",
                font=("Segoe UI", 10),
                relief="solid",
                bd=1
            )

            entry.grid(
                row=i,
                column=1,
                sticky="ew",
                padx=(0, 16),
                pady=10,
                ipady=4
            )

            if secret:
                password_entries.append(
                    entry
                )

        form.columnconfigure(
            1,
            weight=1
        )

        # =========================================================
        # MOSTRAR CLAVES
        # =========================================================

        show = tk.BooleanVar(
            value=False
        )

        def toggle_passwords():
            for entry in password_entries:
                entry.config(
                    show="" if show.get() else "*"
                )

        tk.Checkbutton(
            body,
            text="Mostrar claves",
            variable=show,
            command=toggle_passwords,
            bg=BG,
            activebackground=BG,
            font=("Segoe UI", 9)
        ).pack(
            anchor="w",
            pady=(10, 6)
        )

        # =========================================================
        # SESIONES
        # =========================================================

        sessions = tk.LabelFrame(
            body,
            text=" Sesiones del navegador ",
            bg="white",
            fg=DARK,
            font=("Segoe UI", 10, "bold"),
            bd=0,
            highlightthickness=1,
            highlightbackground="#D9E5EF"
        )

        sessions.pack(
            fill="x",
            pady=(6, 0)
        )

        tk.Label(
            sessions,
            text=(
                "Después de guardar las credenciales puedes "
                "crear o renovar la sesión de cada portal."
            ),
            bg="white",
            fg="#53606C",
            font=("Segoe UI", 9)
        ).pack(
            anchor="w",
            padx=14,
            pady=(10, 8)
        )

        session_buttons = tk.Frame(
            sessions,
            bg="white"
        )

        session_buttons.pack(
            fill="x",
            padx=14,
            pady=(0, 12)
        )

        # =========================================================
        # GUARDADO
        # =========================================================

        def save(show_message=True):

            self._write_env(
                ROOT
                / "monitores"
                / "pasarelas"
                / ".env",
                {
                    "ECOLLECT_URL":
                    "https://www.e-collect.com/app_express/admin/eCollectIndex.aspx",

                    "ECOLLECT_USER":
                    vals["e_user"].get().strip(),

                    "ECOLLECT_PASSWORD":
                    vals["e_pass"].get(),

                    "PAYU_URL":
                    "https://secure.payulatam.com/login.zul",

                    "PAYU_USER":
                    vals["p_user"].get().strip(),

                    "PAYU_PASSWORD":
                    vals["p_pass"].get(),

                    "HEADLESS":
                    "true",

                    "USAR_SESION":
                    "true",

                    "LOGIN_AUTOMATICO":
                    "true",

                    "TIMEOUT_CARGA_SEGUNDOS":
                    "480",

                    "REINTENTOS_CONSULTA":
                    "4",

                    "SHAREPOINT_SALIDA":
                    str(
                        output_root()
                        / "ECOLLECT"
                    )
                }
            )

            self._write_env(
                ROOT
                / "monitores"
                / "hercules"
                / ".env",
                {
                    "HERCULES_URL":
                    "https://sistemahercules.bienestarcompensar.com/",

                    "HERCULES_REPORT_URL":
                    "https://sistemahercules.bienestarcompensar.com/sistema.php/reportes/estadisticas#/",

                    "HERCULES_USERNAME":
                    vals["h_user"].get().strip(),

                    "HERCULES_PASSWORD":
                    vals["h_pass"].get(),

                    "AUTO_LOGIN":
                    "true",

                    "HEADLESS":
                    "true",

                    "SHAREPOINT_SYNC_DIR":
                    str(
                        output_root()
                        / "HERCULES"
                    )
                }
            )

            dirty["value"] = False

            status_var.set(
                "✓ Credenciales guardadas correctamente"
            )

            self.write(
                "Credenciales eCollect, PayU y Hércules "
                "guardadas localmente."
            )

            if show_message:
                messagebox.showinfo(
                    "Credenciales guardadas",
                    "Las credenciales quedaron guardadas "
                    "correctamente en este equipo.",
                    parent=w
                )

        # =========================================================
        # GUARDAR SESIONES
        # =========================================================

        def launch_session(which):

            save(
                show_message=False
            )

            py = (
                ROOT
                / ".venv"
                / "Scripts"
                / "python.exe"
            )

            pycmd = (
                str(py)
                if py.exists()
                else sys.executable
            )

            if which == "ECOLLECT":

                cmd = [
                    pycmd,
                    str(
                        ROOT
                        / "monitores"
                        / "pasarelas"
                        / "src"
                        / "main.py"
                    ),
                    "--modo",
                    "guardar-sesion-ecollect"
                ]

                cwd = (
                    ROOT
                    / "monitores"
                    / "pasarelas"
                )

            elif which == "PAYU":

                cmd = [
                    pycmd,
                    str(
                        ROOT
                        / "monitores"
                        / "pasarelas"
                        / "src"
                        / "main.py"
                    ),
                    "--modo",
                    "guardar-sesion-payu"
                ]

                cwd = (
                    ROOT
                    / "monitores"
                    / "pasarelas"
                )

            else:

                cmd = [
                    pycmd,
                    str(
                        ROOT
                        / "monitores"
                        / "hercules"
                        / "src"
                        / "guardar_sesion.py"
                    )
                ]

                cwd = (
                    ROOT
                    / "monitores"
                    / "hercules"
                )

            subprocess.Popen(
                cmd,
                cwd=str(cwd),
                creationflags=(
                    subprocess.CREATE_NEW_CONSOLE
                    if os.name == "nt"
                    else 0
                )
            )

            status_var.set(
                f"Capturando sesión {which}..."
            )

            self.write(
                f"Abierta ventana para guardar "
                f"sesión de {which}."
            )

        for name in [
            "ECOLLECT",
            "PAYU",
            "HERCULES"
        ]:

            tk.Button(
                session_buttons,
                text=f"Guardar sesión {name}",
                command=lambda n=name:
                    launch_session(n),
                bg="#EAF2FB",
                fg=BLUE,
                activebackground="#DCEAF8",
                bd=0,
                padx=14,
                pady=9,
                font=("Segoe UI", 9, "bold")
            ).pack(
                side="left",
                padx=(0, 8)
            )

        # =========================================================
        # BOTONES INFERIORES
        # =========================================================

        def save_close():
            save(
                show_message=False
            )
            w.destroy()

        def cancel():
            if dirty["value"]:
                if not messagebox.askyesno(
                    "Cambios sin guardar",
                    "Hay cambios sin guardar.\n\n"
                    "¿Quieres cerrar sin guardarlos?",
                    parent=w
                ):
                    return

            w.destroy()

        tk.Button(
            footer,
            text="CANCELAR",
            command=cancel,
            bg="#E8EDF2",
            fg=DARK,
            activebackground="#DCE3E9",
            bd=0,
            padx=18,
            pady=10,
            font=("Segoe UI", 9, "bold")
        ).pack(
            side="right",
            padx=(6, 16)
        )

        tk.Button(
            footer,
            text="GUARDAR Y CERRAR",
            command=save_close,
            bg=GREEN,
            fg="white",
            activebackground="#559927",
            activeforeground="white",
            bd=0,
            padx=18,
            pady=10,
            font=("Segoe UI", 10, "bold")
        ).pack(
            side="right",
            padx=6
        )

        tk.Button(
            footer,
            text="GUARDAR",
            command=lambda: save(True),
            bg=BLUE,
            fg="white",
            activebackground="#00468F",
            activeforeground="white",
            bd=0,
            padx=22,
            pady=10,
            font=("Segoe UI", 10, "bold")
        ).pack(
            side="right",
            padx=6
        )

        w.protocol(
            "WM_DELETE_WINDOW",
            cancel
        )

    def change_path(self):
        p = filedialog.askdirectory(title="Selecciona carpeta raíz de Monitoreo diario")
        if not p: return
        cfg = load_config(); cfg["output_root"] = p
        (ROOT / "config" / "app.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        self.pathvar.set(p); self.write("Carpeta de salida actualizada.")

    def open_output_root(self):
        p = output_root()
        p.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(str(p))

    def _monitor_folder(self, monitor):
        root = output_root()
        return {
            "PASARELAS": root / "ECOLLECT",
            "AWS": root / "AWS",
            "HERCULES": root / "HERCULES",
        }.get(str(monitor).upper(), root)

    def _monitor_dashboard_path(self, monitor):
        root = output_root()
        monitor = str(monitor).upper()
        candidates = {
            "PASARELAS": [
                root / "ECOLLECT" / "dashboard_verticales.html",
                ROOT / "monitores" / "pasarelas" / "data" / "salida" / "reporte_verticales_diario_ultimo.html",
            ],
            "AWS": [
                root / "AWS" / "Dashboard_AWS.html",
            ],
            "HERCULES": [
                root / "HERCULES" / "DASHBOARD_HERCULES.html",
                root / "HERCULES" / "dashboard_hercules.html",
                ROOT / "monitores" / "hercules" / "reports" / "dashboard_hercules.html",
            ],
        }.get(monitor, [])
        for p in candidates:
            if p.exists():
                return p
        return candidates[0] if candidates else None

    def open_monitor_folder(self, monitor):
        p = self._monitor_folder(monitor)
        p.mkdir(parents=True, exist_ok=True)
        self.write(f"Abriendo carpeta de {monitor}: {p}")
        if os.name == "nt":
            os.startfile(str(p))

    def open_monitor_dashboard(self, monitor):
        p = self._monitor_dashboard_path(monitor)
        if p and p.exists():
            self.write(f"Abriendo dashboard {monitor}: {p}")
            if os.name == "nt":
                os.startfile(str(p))
            return
        carpeta = self._monitor_folder(monitor)
        messagebox.showwarning(
            "Dashboard",
            f"Todavía no encuentro el dashboard de {monitor}.\n\nRevisa la carpeta:\n{carpeta}"
        )
        self.open_monitor_folder(monitor)

    def open_general_dashboard(self):
        """Abre el General ya consolidado; nunca lo genera durante una ejecución."""
        if getattr(self, "running", False):
            messagebox.showwarning(
                "Dashboard general",
                "El monitoreo todavía está en ejecución.\n\n"
                "El Dashboard General se genera automáticamente al final, "
                "después de terminar todos los monitores seleccionados."
            )
            return

        p = output_root() / "GENERAL" / "Dashboard_General.html"
        if not p.exists():
            messagebox.showwarning(
                "Dashboard general",
                "Todavía no existe un Dashboard General finalizado.\n\n"
                "Ejecuta el monitoreo y espera el mensaje SYSTEM · OK."
            )
            return

        self.write(f"Abriendo Dashboard General finalizado: {p}")
        if os.name == "nt":
            os.startfile(str(p))


    def _selection_for_results(self):
        if getattr(self, "last_selected", None):
            return tuple(self.last_selected)
        return tuple(m for m, v in self.vars.items() if v.get())

    def _result_folder(self):
        selected = self._selection_for_results()
        root = output_root()
        if len(selected) == 1:
            monitor = selected[0]
            return {
                "PASARELAS": root / "ECOLLECT",
                "AWS": root / "AWS",
                "HERCULES": root / "HERCULES",
            }.get(monitor, root)
        if len(selected) > 1:
            return root / "GENERAL"
        return root

    def open_result_folder(self):
        p = self._result_folder()
        p.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(str(p))

    def _dashboard_path(self):
        selected = self._selection_for_results()
        root = output_root()
        if len(selected) == 1:
            monitor = selected[0]
            candidates = {
                "PASARELAS": [
                    root / "ECOLLECT" / "dashboard_verticales.html",
                    ROOT / "monitores" / "pasarelas" / "data" / "salida" / "reporte_verticales_diario_ultimo.html",
                ],
                "AWS": [
                    root / "AWS" / "Dashboard_AWS.html",
                ],
                "HERCULES": [
                    root / "HERCULES" / "DASHBOARD_HERCULES.html",
                    root / "HERCULES" / "dashboard_hercules.html",
                    ROOT / "monitores" / "hercules" / "reports" / "dashboard_hercules.html",
                ],
            }.get(monitor, [])
            for p in candidates:
                if p.exists():
                    return p
            return candidates[0] if candidates else None
        return root / "GENERAL" / "Dashboard_General.html"

    def _selection_for_results(self):
        if getattr(self, "last_selected", None):
            return tuple(self.last_selected)
        return tuple(m for m, v in self.vars.items() if v.get())

    def _result_folder(self):
        selected = self._selection_for_results()
        root = output_root()
        if len(selected) == 1:
            monitor = selected[0]
            return {
                "PASARELAS": root / "ECOLLECT",
                "AWS": root / "AWS",
                "HERCULES": root / "HERCULES",
            }.get(monitor, root)
        if len(selected) > 1:
            return root / "GENERAL"
        return root

    def open_result_folder(self):
        p = self._result_folder()
        p.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(str(p))

    def _dashboard_path(self):
        selected = self._selection_for_results()
        root = output_root()
        if len(selected) == 1:
            monitor = selected[0]
            candidates = {
                "PASARELAS": [
                    root / "ECOLLECT" / "dashboard_verticales.html",
                    ROOT / "monitores" / "pasarelas" / "data" / "salida" / "reporte_verticales_diario_ultimo.html",
                ],
                "AWS": [
                    root / "AWS" / "Dashboard_AWS.html",
                ],
                "HERCULES": [
                    root / "HERCULES" / "DASHBOARD_HERCULES.html",
                    root / "HERCULES" / "dashboard_hercules.html",
                    ROOT / "monitores" / "hercules" / "reports" / "dashboard_hercules.html",
                ],
            }.get(monitor, [])
            for p in candidates:
                if p.exists():
                    return p
            return candidates[0] if candidates else None
        return root / "GENERAL" / "Dashboard_General.html"

    def open_general(self):
        # Compatibilidad con instalaciones anteriores.
        self.open_result_folder()

    def refresh_dash(self):
        selected = self._selection_for_results()

        # Si se ejecutÃ³ un solo monitor, abre SOLO su HTML.
        if len(selected) == 1:
            p = self._dashboard_path()
            if p and p.exists():
                self.write(f"Abriendo dashboard {selected[0]}: {p}")
                if os.name == "nt":
                    os.startfile(str(p))
                return

            carpeta = self._result_folder()
            messagebox.showwarning(
                "Dashboard",
                f"TodavÃ­a no encuentro el HTML de {selected[0]}.\n\n"
                f"Revisa la carpeta:\n{carpeta}"
            )
            self.open_result_folder()
            return

        # Si fueron varios monitores, usa el consolidado GENERAL.
        self.open_general_dashboard()

if __name__ == "__main__":
    App().mainloop()

