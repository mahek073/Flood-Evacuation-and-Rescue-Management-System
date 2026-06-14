# =====================================================
# FLOOD EVACUATION & RESCUE MANAGEMENT SYSTEM
# =====================================================

import sys
import os
import heapq
import random
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
from collections import deque

_PROJECT_GRID_LOADED = False
try:
    sys.path.insert(0, os.path.abspath("."))
    from Environment.grid import (
        ROWS, COLS, ROAD, BUILDING, FLOOD, BLOCKED, VICTIM, SHELTER,
        RISKY_THRESHOLD, FLOOD_THRESHOLD,
        cell_type as _ct, water_level as _wl,
        victims as _proj_victims, shelter as _proj_shelter,
        get_neighbors, get_cost, get_risk_cost,
        heuristic, heuristic_multi,
        spread_flood, reset_grid as _proj_reset,
        original_cell_type, original_water_level,
    )
    import Environment.grid as _grid_mod
    _PROJECT_GRID_LOADED = True
except Exception:
    pass

ROWS  = 20
COLS  = 20
ROAD     = 0
BUILDING = 1
FLOOD    = 2
BLOCKED  = 3
VICTIM   = 4
SHELTER_TYPE = 5

RISKY_THRESHOLD = 0.3
FLOOD_THRESHOLD = 0.7

_BUILDINGS = [
    (3,3),(3,4),(3,5),
    (7,12),(7,13),(7,14),(8,12),(8,13),
    (12,5),(12,6),(13,5),(13,6),
    (15,15),(15,16),(16,15),(16,16),(16,17),(17,15),(17,16),
]
_BLOCKED_CELLS  = [(5,8),(5,9),(6,9),(10,15),(11,15),(12,15),(13,15)]
_DEFAULT_VICTIMS = [(18,6),(17,8),(15,10)]
_SHELTER         = (18,18)
_FLOOD_ORIGINS   = [
    (9,9),(9,10),(10,9),(10,10),(11,9),(11,10),(12,9),(12,10),
    (15,8),(15,9),(16,8),(16,9),(17,8),(17,9),
]

def _make_grid():
    ct = [[ROAD]*COLS for _ in range(ROWS)]
    wl = [[0.0]*COLS  for _ in range(ROWS)]
    for r,c in _BUILDINGS:       ct[r][c] = BUILDING
    for r,c in _BLOCKED_CELLS:   ct[r][c] = BLOCKED
    for r,c in _DEFAULT_VICTIMS: ct[r][c] = VICTIM
    ct[_SHELTER[0]][_SHELTER[1]] = SHELTER_TYPE
    for r,c in _FLOOD_ORIGINS:
        ct[r][c] = FLOOD
        wl[r][c] = 1.0
    for r in range(4,19): wl[r][5]  = 0.65
    for r in range(8,18): wl[r][9]  = 0.55
    return ct, wl

cell_type   = [[ROAD]*COLS for _ in range(ROWS)]
water_level = [[0.0]*COLS  for _ in range(ROWS)]
orig_cell   = [[ROAD]*COLS for _ in range(ROWS)]
orig_water  = [[0.0]*COLS  for _ in range(ROWS)]
dynamic_victims = []
shelter_pos = _SHELTER

def _init_state():
    global cell_type, water_level, orig_cell, orig_water, dynamic_victims, shelter_pos
    if _PROJECT_GRID_LOADED:
        cell_type   = [list(r) for r in _grid_mod.cell_type]
        water_level = [list(r) for r in _grid_mod.water_level]
        orig_cell   = [list(r) for r in _grid_mod.original_cell_type]
        orig_water  = [list(r) for r in _grid_mod.original_water_level]
        shelter_pos = _proj_shelter
        dynamic_victims = list(_proj_victims)
    else:
        ct, wl = _make_grid()
        cell_type   = ct
        water_level = wl
        orig_cell   = [list(r) for r in ct]
        orig_water  = [list(r) for r in wl]
        shelter_pos = _SHELTER
        dynamic_victims = list(_DEFAULT_VICTIMS)

def _reset_state():
    global cell_type, water_level
    if _PROJECT_GRID_LOADED:
        _proj_reset()
        cell_type   = [list(r) for r in _grid_mod.cell_type]
        water_level = [list(r) for r in _grid_mod.water_level]
    else:
        cell_type   = [list(r) for r in orig_cell]
        water_level = [list(r) for r in orig_water]
    _sync_victims_to_grid()

def _sync_victims_to_grid():
    for r,c in dynamic_victims:
        if cell_type[r][c] not in (BUILDING, BLOCKED, FLOOD, SHELTER_TYPE):
            cell_type[r][c] = VICTIM

def is_passable(r,c):
    return cell_type[r][c] not in (BUILDING, BLOCKED)

def get_neighbors_local(pos):
    r,c = pos
    out = []
    for dr,dc in ((-1,0),(1,0),(0,-1),(0,1)):
        nr,nc = r+dr, c+dc
        if 0<=nr<ROWS and 0<=nc<COLS and is_passable(nr,nc):
            out.append((nr,nc))
    return out

def get_cost_local(r,c):
    return 1 + water_level[r][c]*10

def get_risk_cost_local(r,c):
    base = get_cost_local(r,c)
    flooded = sum(
        1 for dr,dc in ((-1,0),(1,0),(0,-1),(0,1))
        if 0<=r+dr<ROWS and 0<=c+dc<COLS
        and water_level[r+dr][c+dc] > FLOOD_THRESHOLD
    )
    return base + flooded*3

def heuristic_local(a,b):
    return abs(a[0]-b[0]) + abs(a[1]-b[1])

def heuristic_multi_local(pos, goals):
    return min(heuristic_local(pos,g) for g in goals) if goals else 0

def spread_flood_local():
    flooded = [(r,c) for r in range(ROWS) for c in range(COLS)
               if water_level[r][c] > FLOOD_THRESHOLD]
    for r,c in flooded:
        for nr,nc in get_neighbors_local((r,c)):
            if random.random() < 0.65:
                water_level[nr][nc] = min(1.0, water_level[nr][nc]+0.2)
    for r in range(ROWS):
        for c in range(COLS):
            if water_level[r][c] > FLOOD_THRESHOLD:
                if cell_type[r][c] not in (BUILDING, VICTIM, SHELTER_TYPE):
                    cell_type[r][c] = FLOOD

def _cost(r,c):   return get_cost_local(r,c)
def _rcost(r,c):  return get_risk_cost_local(r,c)
def _hm(pos,gs):  return heuristic_multi_local(pos,gs)
def _spread():    spread_flood_local()

# ── Algorithms ────────────────────────────────────

def algo_bfs(start, goals):
    goal_set = set(goals)
    q = deque([start]); visited = {start}; parent = {start:None}
    while q:
        cur = q.popleft()
        if cur in goal_set:
            path=[]; node=cur
            while node: path.append(node); node=parent[node]
            return path[::-1], cur
        for nb in get_neighbors_local(cur):
            if nb not in visited:
                visited.add(nb); parent[nb]=cur; q.append(nb)
    return None, None

def algo_astar(start, goals):
    goal_set=set(goals); open_list=[(0,start)]
    g={start:0}; parent={start:None}; vis=set()
    while open_list:
        _,cur=heapq.heappop(open_list)
        if cur in vis: continue
        vis.add(cur)
        if cur in goal_set:
            path=[]; node=cur
            while node is not None: path.append(node); node=parent[node]
            return path[::-1], cur
        for nb in get_neighbors_local(cur):
            tg=g[cur]+_cost(*nb)
            if nb not in g or tg<g[nb]:
                g[nb]=tg; parent[nb]=cur
                heapq.heappush(open_list,(tg+_hm(nb,list(goal_set)),nb))
    return None, None

def algo_risk_astar(start, goals):
    goal_set=set(goals); open_list=[(0,start)]
    g={start:0}; parent={start:None}; vis=set()
    while open_list:
        _,cur=heapq.heappop(open_list)
        if cur in goal_set:
            path=[]; node=cur
            while node is not None: path.append(node); node=parent[node]
            return path[::-1], cur
        if cur in vis: continue
        vis.add(cur)
        for nb in get_neighbors_local(cur):
            tg=g[cur]+_rcost(*nb)
            if nb not in g or tg<g[nb]:
                g[nb]=tg; parent[nb]=cur
                heapq.heappush(open_list,(tg+_hm(nb,list(goal_set)),nb))
    return None, None

def algo_hill_climb(start, goals, max_steps=400):
    goal_set=set(goals); cur=start; path=[cur]; vis={cur}
    for _ in range(max_steps):
        if cur in goal_set: break
        nbs=get_neighbors_local(cur)
        if not nbs: break
        best=None; best_score=_hm(cur,list(goal_set))
        for nb in nbs:
            if nb in vis: continue
            s=_hm(nb,list(goal_set))
            if s<best_score: best_score=s; best=nb
        if best is None: break
        cur=best; vis.add(cur); path.append(cur)
    return path, (cur if cur in goal_set else None)

ALGORITHMS = {
    "BFS": algo_bfs, "A*": algo_astar,
    "Risk-Based A*": algo_risk_astar, "Hill Climb": algo_hill_climb,
}

# ── Colors ────────────────────────────────────────

CELL_COLORS = {
    ROAD: "#F0EEEA", BUILDING: "#3D3D3D", FLOOD: "#1F77B4",
    BLOCKED: "#FF7F0E", VICTIM: "#D62728", SHELTER_TYPE: "#2CA02C",
}
COLOR_RISKY_OVERLAY = "#85C1E9"
COLOR_PATH    = "#FFD700"
COLOR_AGENT   = "#00C864"
COLOR_RESCUED = "#A8E6CF"
COLOR_GRID_LINE = "#CCCAC4"
COLOR_BG      = "#F8F7F4"
COLOR_PANEL   = "#FFFFFF"
COLOR_ACCENT  = "#185FA5"
COLOR_TEXT    = "#2C2C2A"
COLOR_TEXT_MUTED = "#888780"
COLOR_BORDER  = "#D3D1C7"
COLOR_SUCCESS = "#3B6D11"
COLOR_WARN    = "#854F0B"
COLOR_DANGER  = "#A32D2D"

BTN_RUN_BG  = "#1A7F37"
BTN_RUN_FG  = "#FFFFFF"
BTN_STOP_BG = "#B91C1C"
BTN_STOP_FG = "#FFFFFF"


# =====================================================
# SCROLLABLE FRAME HELPER
# =====================================================

class ScrollableFrame(tk.Frame):
    """A frame with a vertical scrollbar that works via mouse-wheel too."""
    def __init__(self, parent, bg=COLOR_PANEL, **kw):
        super().__init__(parent, bg=bg, **kw)
        self._canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self._sb     = tk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._sb.set)
        self._sb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self._canvas, bg=bg)
        self._win  = self._canvas.create_window((0,0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._on_inner_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._canvas.bind_all("<MouseWheel>",     self._on_mousewheel)
        self._canvas.bind_all("<Button-4>",       self._on_mousewheel)
        self._canvas.bind_all("<Button-5>",       self._on_mousewheel)

    def _on_inner_configure(self, _e):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, e):
        self._canvas.itemconfig(self._win, width=e.width)

    def _on_mousewheel(self, e):
        if e.num == 4 or e.delta > 0:
            self._canvas.yview_scroll(-1, "units")
        else:
            self._canvas.yview_scroll(1, "units")


# =====================================================
# MAIN GUI
# =====================================================

class FloodGUI:
    CELL_PX = 22

    def __init__(self, root):
        self.root = root
        root.title("Flood Evacuation & Rescue — AI Simulator")
        root.configure(bg=COLOR_BG)
        root.resizable(True, True)

        _init_state()

        self.agent_pos   = None
        self.path_cells  = set()
        self.rescued     = set()
        self.running     = False
        self._stop_flag  = False
        self.total_steps = 0
        self.total_cost  = 0.0
        self.hover_cell  = None
        self._stats      = {}
        self._algo_btns  = {}
        self._edit_mode  = tk.StringVar(value="victim")

        self._build_ui()
        self._draw_grid()

    # ─────────────────────────────────────────────
    # UI
    # ─────────────────────────────────────────────

    def _build_ui(self):
        root = self.root
        W = self.CELL_PX * COLS

        # top bar
        topbar = tk.Frame(root, bg=COLOR_ACCENT, height=44)
        topbar.pack(fill="x", side="top")
        topbar.pack_propagate(False)
        tk.Label(topbar, text="⚡  Flood Evacuation & Rescue System",
                 bg=COLOR_ACCENT, fg="white",
                 font=("Helvetica",13,"bold")).pack(side="left", padx=14, pady=10)
        self.status_lbl = tk.Label(topbar, text="● Ready",
                                   bg=COLOR_ACCENT, fg="#A8E6CF",
                                   font=("Helvetica",11))
        self.status_lbl.pack(side="right", padx=14)

        body = tk.Frame(root, bg=COLOR_BG)
        body.pack(fill="both", expand=True)

        # ── LEFT PANEL with scroll ──────────────────
        left_outer = tk.Frame(body, bg=COLOR_PANEL, width=270,
                              highlightthickness=1,
                              highlightbackground=COLOR_BORDER)
        left_outer.pack(side="left", fill="y", padx=(10,0), pady=10)
        left_outer.pack_propagate(False)

        self._scroll_frame = ScrollableFrame(left_outer, bg=COLOR_PANEL)
        self._scroll_frame.pack(fill="both", expand=True)
        left = self._scroll_frame.inner   # put widgets here
        self._build_left_panel(left)

        # grid canvas
        grid_frame = tk.Frame(body, bg=COLOR_BG)
        grid_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        self.canvas = tk.Canvas(grid_frame, width=W, height=W,
                                bg=COLOR_BG, highlightthickness=1,
                                highlightbackground=COLOR_BORDER,
                                cursor="crosshair")
        self.canvas.pack(side="top")
        self.canvas.bind("<Motion>",   self._on_hover)
        self.canvas.bind("<Leave>",    self._on_leave)
        self.canvas.bind("<Button-1>", self._on_left_click)
        self.canvas.bind("<Button-3>", self._on_right_click)

        # right panel
        right = tk.Frame(body, bg=COLOR_PANEL, width=185,
                         highlightthickness=1,
                         highlightbackground=COLOR_BORDER)
        right.pack(side="right", fill="y", padx=(0,10), pady=10)
        right.pack_propagate(False)
        self._build_right_panel(right)

        # log
        log_frame = tk.Frame(root, bg=COLOR_PANEL,
                             highlightthickness=1, highlightbackground=COLOR_BORDER)
        log_frame.pack(fill="x", padx=10, pady=(0,8))
        tk.Label(log_frame, text="  Log", bg=COLOR_PANEL, fg=COLOR_TEXT_MUTED,
                 font=("Helvetica",9,"bold")).pack(anchor="w")
        self.log_text = tk.Text(log_frame, height=5, state="disabled",
                                bg="#F8F7F4", fg=COLOR_TEXT, font=("Courier",9),
                                relief="flat", bd=0, highlightthickness=0)
        self.log_text.pack(fill="x", padx=4, pady=(0,4))
        self.log_text.tag_config("info",    foreground=COLOR_ACCENT)
        self.log_text.tag_config("success", foreground=COLOR_SUCCESS)
        self.log_text.tag_config("warn",    foreground=COLOR_WARN)
        self.log_text.tag_config("error",   foreground=COLOR_DANGER)

    def _section(self, parent, title):
        tk.Label(parent, text=title.upper(), bg=COLOR_PANEL,
                 fg=COLOR_TEXT_MUTED, font=("Helvetica",8,"bold")).pack(
                     anchor="w", padx=10, pady=(12,3))
        tk.Frame(parent, bg=COLOR_BORDER, height=1).pack(fill="x", padx=8, pady=(0,6))

    def _build_left_panel(self, p):
        tk.Label(p, text="Algorithm", bg=COLOR_PANEL, fg=COLOR_TEXT,
                 font=("Helvetica",11,"bold")).pack(anchor="w", padx=10, pady=(14,8))

        self.algo_var = tk.StringVar(value="BFS")
        for name in ALGORITHMS:
            btn = tk.Button(p, text=name, bg=COLOR_PANEL, fg=COLOR_TEXT,
                            font=("Helvetica",10), relief="flat", bd=0,
                            cursor="hand2", highlightthickness=1,
                            highlightbackground=COLOR_BORDER,
                            anchor="w", padx=10,
                            command=lambda n=name: self._select_algo(n))
            btn.pack(fill="x", padx=8, pady=2, ipady=5)
            self._algo_btns[name] = btn
        self._select_algo("BFS")

        self._section(p, "Edit Grid")
        tk.Label(p, text="Left-click on grid to:", bg=COLOR_PANEL,
                 fg=COLOR_TEXT_MUTED, font=("Helvetica",8)).pack(anchor="w", padx=10)
        for label, val in [("Place Victim","victim"),("Erase Cell","erase")]:
            tk.Radiobutton(p, text=label, variable=self._edit_mode, value=val,
                           bg=COLOR_PANEL, fg=COLOR_TEXT, font=("Helvetica",9),
                           activebackground=COLOR_PANEL,
                           selectcolor=COLOR_PANEL).pack(anchor="w", padx=12, pady=1)
        tk.Label(p, text="Right-click → remove victim", bg=COLOR_PANEL,
                 fg=COLOR_TEXT_MUTED, font=("Helvetica",8)).pack(anchor="w", padx=10, pady=(2,0))

        self._section(p, "Controls")
        tk.Label(p, text="Animation speed", bg=COLOR_PANEL,
                 fg=COLOR_TEXT_MUTED, font=("Helvetica",9)).pack(anchor="w", padx=10)
        speed_row = tk.Frame(p, bg=COLOR_PANEL)
        speed_row.pack(fill="x", padx=8, pady=(2,6))
        self.speed_var = tk.IntVar(value=120)
        ttk.Scale(speed_row, from_=20, to=600,
                  variable=self.speed_var, orient="horizontal").pack(
                      side="left", fill="x", expand=True)
        self.speed_lbl = tk.Label(speed_row, text="120ms", bg=COLOR_PANEL,
                                  fg=COLOR_TEXT_MUTED, font=("Helvetica",9), width=5)
        self.speed_lbl.pack(side="right")
        self.speed_var.trace_add("write", lambda *_: self.speed_lbl.config(
            text=f"{self.speed_var.get()}ms"))

        self.flood_var = tk.BooleanVar(value=True)
        tk.Checkbutton(p, text="Dynamic flood spread", variable=self.flood_var,
                       bg=COLOR_PANEL, fg=COLOR_TEXT, font=("Helvetica",9),
                       activebackground=COLOR_PANEL,
                       selectcolor=COLOR_PANEL).pack(anchor="w", padx=10, pady=2)

        # ── ACTIONS ──────────────────────────────
        self._section(p, "Actions")

        self.run_btn = tk.Button(
            p, text="▶  Run rescue",
            bg=BTN_RUN_BG, fg=BTN_RUN_FG,
            activebackground="#145C28", activeforeground="white",
            font=("Helvetica",11,"bold"),
            relief="raised", bd=2, cursor="hand2",
            command=self._run_or_stop,
        )
        self.run_btn.pack(fill="x", padx=8, pady=(4,6), ipady=8)

        tk.Button(p, text="↺  Reset grid",
                  bg=COLOR_PANEL, fg=COLOR_TEXT,
                  activebackground="#E0E0E0",
                  font=("Helvetica",10), relief="groove", bd=1,
                  cursor="hand2",
                  command=self._reset).pack(fill="x", padx=8, pady=2, ipady=5)

        tk.Button(p, text="🗑  Clear victims",
                  bg=COLOR_PANEL, fg=COLOR_DANGER,
                  activebackground="#FFE8E8",
                  font=("Helvetica",10), relief="groove", bd=1,
                  cursor="hand2",
                  command=self._clear_all_victims).pack(fill="x", padx=8, pady=2, ipady=5)

        tk.Button(p, text="〰  Spread flood",
                  bg=COLOR_PANEL, fg="#1F77B4",
                  activebackground="#E0F0FF",
                  font=("Helvetica",10), relief="groove", bd=1,
                  cursor="hand2",
                  command=self._manual_flood).pack(fill="x", padx=8, pady=2, ipady=5)

        # ── LEGEND ───────────────────────────────
        self._section(p, "Legend")
        legend = [
            (CELL_COLORS[ROAD],         "Road"),
            (CELL_COLORS[BUILDING],     "Building"),
            (CELL_COLORS[FLOOD],        "Flood"),
            (CELL_COLORS[BLOCKED],      "Blocked"),
            (CELL_COLORS[VICTIM],       "Victim"),
            (CELL_COLORS[SHELTER_TYPE], "Shelter"),
            (COLOR_RISKY_OVERLAY,       "Risky (water)"),
            (COLOR_PATH,                "Agent path"),
            (COLOR_AGENT,               "Rescue agent"),
            (COLOR_RESCUED,             "Rescued victim"),
        ]
        for color, label in legend:
            row = tk.Frame(p, bg=COLOR_PANEL)
            row.pack(anchor="w", padx=10, pady=1)
            dot = tk.Canvas(row, width=14, height=14,
                            bg=COLOR_PANEL, highlightthickness=0)
            dot.pack(side="left")
            dot.create_rectangle(1,1,13,13, fill=color, outline=COLOR_BORDER)
            tk.Label(row, text=label, bg=COLOR_PANEL,
                     fg=COLOR_TEXT_MUTED, font=("Helvetica",8)).pack(side="left", padx=4)

        tk.Label(p, text="", bg=COLOR_PANEL).pack(pady=6)  # bottom padding

    def _build_right_panel(self, parent):
        tk.Label(parent, text="Statistics", bg=COLOR_PANEL, fg=COLOR_TEXT,
                 font=("Helvetica",11,"bold")).pack(anchor="w", padx=10, pady=(14,8))
        self._stats = {}
        for key, label in [
            ("algo","Algorithm"), ("victims","Victims remaining"),
            ("rescued_ct","Rescued"), ("steps","Total steps"),
            ("cost","Path cost"), ("status","Status"),
        ]:
            row = tk.Frame(parent, bg=COLOR_PANEL)
            row.pack(fill="x", padx=8, pady=3)
            tk.Label(row, text=label, bg=COLOR_PANEL,
                     fg=COLOR_TEXT_MUTED, font=("Helvetica",9)).pack(anchor="w")
            val = tk.Label(row, text="—", bg=COLOR_PANEL,
                           fg=COLOR_TEXT, font=("Helvetica",10,"bold"))
            val.pack(anchor="w")
            self._stats[key] = val
        self._stats["algo"].config(text="BFS")

        self._section(parent, "Victims on grid")
        self.victim_count_lbl = tk.Label(parent,
                                         text=f"{len(dynamic_victims)} victim(s)",
                                         bg=COLOR_PANEL, fg=COLOR_DANGER,
                                         font=("Helvetica",11,"bold"))
        self.victim_count_lbl.pack(anchor="w", padx=12)
        tk.Label(parent, text="Left-click road cell\nto place a victim",
                 bg=COLOR_PANEL, fg=COLOR_TEXT_MUTED,
                 font=("Helvetica",8), justify="left").pack(anchor="w", padx=12, pady=(2,0))

        self._section(parent, "Cell info")
        self.cell_info_lbl = tk.Label(parent, text="Hover a cell",
                                      bg="#F8F7F4", fg=COLOR_TEXT_MUTED,
                                      font=("Courier",9),
                                      justify="left", anchor="nw",
                                      wraplength=160, padx=8, pady=6)
        self.cell_info_lbl.pack(fill="x", padx=8, pady=2)

    # ─────────────────────────────────────────────
    # DRAWING
    # ─────────────────────────────────────────────

    def _draw_grid(self):
        cv = self.canvas
        cv.delete("all")
        px = self.CELL_PX
        for r in range(ROWS):
            for c in range(COLS):
                x0,y0 = c*px, r*px
                ct = cell_type[r][c]
                cv.create_rectangle(x0,y0,x0+px,y0+px,
                                    fill=CELL_COLORS.get(ct,COLOR_BG),
                                    outline=COLOR_GRID_LINE, width=0.5)
                wl = water_level[r][c]
                if RISKY_THRESHOLD < wl <= FLOOD_THRESHOLD:
                    cv.create_rectangle(x0,y0,x0+px,y0+px,
                                        fill=COLOR_RISKY_OVERLAY,
                                        stipple="gray25", outline="")
                if (r,c) in self.path_cells:
                    cv.create_rectangle(x0+1,y0+1,x0+px-1,y0+px-1,
                                        fill=COLOR_PATH, outline="")

        for (r,c) in dynamic_victims:
            if (r,c) not in self.rescued:
                x0,y0 = c*px,r*px
                cx,cy = x0+px//2, y0+px//2
                rad = px//2-1
                cv.create_oval(cx-rad,cy-rad,cx+rad,cy+rad,
                               fill=CELL_COLORS[VICTIM], outline="white", width=2)
                cv.create_text(cx,cy, text="V", fill="white",
                               font=("Helvetica",7,"bold"))

        for (r,c) in self.rescued:
            x0,y0 = c*px,r*px
            cx,cy = x0+px//2, y0+px//2
            rad = px//2-2
            cv.create_oval(cx-rad,cy-rad,cx+rad,cy+rad,
                           fill=COLOR_RESCUED, outline=COLOR_SUCCESS, width=1.5)
            cv.create_text(cx,cy, text="✓", fill=COLOR_SUCCESS,
                           font=("Helvetica",8,"bold"))

        if self.agent_pos:
            r,c = self.agent_pos
            x0,y0 = c*px,r*px
            cx,cy = x0+px//2, y0+px//2
            rad = px//2-2
            cv.create_oval(cx-rad,cy-rad,cx+rad,cy+rad,
                           fill=COLOR_AGENT, outline="white", width=1.5)
            cv.create_oval(cx-3,cy-3,cx+3,cy+3, fill="white", outline="")

        if self.hover_cell:
            r,c = self.hover_cell
            x0,y0 = c*px,r*px
            cv.create_rectangle(x0,y0,x0+px,y0+px,
                                outline=COLOR_ACCENT, width=2)

        self.victim_count_lbl.config(text=f"{len(dynamic_victims)} victim(s)")

    # ─────────────────────────────────────────────
    # INTERACTION
    # ─────────────────────────────────────────────

    def _cell_from_event(self, e):
        px = self.CELL_PX
        c,r = e.x//px, e.y//px
        return (r,c) if 0<=r<ROWS and 0<=c<COLS else None

    def _on_left_click(self, e):
        if self.running: return
        pos = self._cell_from_event(e)
        if pos is None: return
        r,c = pos
        if self._edit_mode.get()=="victim": self._place_victim(r,c)
        else: self._erase_cell(r,c)

    def _on_right_click(self, e):
        if self.running: return
        pos = self._cell_from_event(e)
        if pos: self._remove_victim(*pos)

    def _place_victim(self, r, c):
        if cell_type[r][c] in (BUILDING,BLOCKED,FLOOD,SHELTER_TYPE):
            self._log(f"Cannot place victim at ({r},{c}).", "warn"); return
        if (r,c)==shelter_pos:
            self._log("Cannot place victim on shelter.", "warn"); return
        if (r,c) in dynamic_victims:
            self._log(f"Victim already at ({r},{c}).", "warn"); return
        dynamic_victims.append((r,c))
        cell_type[r][c] = VICTIM
        self._log(f"Victim placed at ({r},{c}). Total: {len(dynamic_victims)}", "info")
        self._draw_grid()

    def _remove_victim(self, r, c):
        if (r,c) in dynamic_victims:
            dynamic_victims.remove((r,c))
            cell_type[r][c] = ROAD
            self._log(f"Victim removed from ({r},{c}).", "warn")
            self._draw_grid()

    def _erase_cell(self, r, c):
        if (r,c) in dynamic_victims: dynamic_victims.remove((r,c))
        if cell_type[r][c] not in (BUILDING,SHELTER_TYPE,FLOOD):
            cell_type[r][c] = ROAD
            self._draw_grid()

    def _clear_all_victims(self):
        if self.running: return
        for r,c in list(dynamic_victims):
            if cell_type[r][c]==VICTIM: cell_type[r][c]=ROAD
        dynamic_victims.clear(); self.rescued.clear()
        self._log("All victims cleared.", "warn"); self._draw_grid()

    def _on_hover(self, e):
        px=self.CELL_PX; c,r = e.x//px, e.y//px
        if 0<=r<ROWS and 0<=c<COLS:
            self.hover_cell=(r,c)
            ct=cell_type[r][c]; wl=water_level[r][c]
            names={ROAD:"Road",BUILDING:"Building",FLOOD:"Flood",
                   BLOCKED:"Blocked",VICTIM:"Victim",SHELTER_TYPE:"Shelter"}
            info=(f"({r},{c})\nType: {names.get(ct,ct)}\n"
                  f"Water: {wl:.2f}\nCost: {1+wl*10:.1f}\n"
                  f"Risk: {get_risk_cost_local(r,c):.1f}\n"
                  f"Pass: {'Yes' if is_passable(r,c) else 'No'}")
            self.cell_info_lbl.config(text=info, fg=COLOR_TEXT)
            self._draw_grid()
        else:
            self.hover_cell=None

    def _on_leave(self, e):
        self.hover_cell=None
        self.cell_info_lbl.config(text="Hover a cell", fg=COLOR_TEXT_MUTED)
        self._draw_grid()

    def _select_algo(self, name):
        self.algo_var.set(name)
        for n,btn in self._algo_btns.items():
            if n==name: btn.config(bg=COLOR_ACCENT, fg="white",
                                   highlightbackground=COLOR_ACCENT)
            else:       btn.config(bg=COLOR_PANEL,  fg=COLOR_TEXT,
                                   highlightbackground=COLOR_BORDER)
        if "algo" in self._stats: self._stats["algo"].config(text=name)

    def _log(self, msg, tag=""):
        self.log_text.config(state="normal")
        self.log_text.insert("end", f"[{time.strftime('%H:%M:%S')}] {msg}\n",
                             tag if tag else ())
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _set_status(self, text, color):
        self.status_lbl.config(text=f"● {text}", fg=color)

    def _update_stats(self, **kw):
        cm={"Running":COLOR_ACCENT,"Complete":COLOR_SUCCESS,
            "Stuck":COLOR_DANGER,"Stopped":COLOR_WARN,"Ready":COLOR_TEXT_MUTED}
        for k,v in kw.items():
            lbl=self._stats.get(k)
            if lbl: lbl.config(text=str(v) if v is not None else "—",
                                fg=cm.get(v, COLOR_TEXT))

    # ─────────────────────────────────────────────
    # RUN BUTTON STATE (thread-safe)
    # ─────────────────────────────────────────────

    def _set_run_btn(self, mode):
        def _apply():
            if mode=="stop":
                self.run_btn.config(text="■  Stop",
                                    bg=BTN_STOP_BG, fg=BTN_STOP_FG,
                                    activebackground="#8B0000",
                                    activeforeground="white")
            else:
                self.run_btn.config(text="▶  Run rescue",
                                    bg=BTN_RUN_BG, fg=BTN_RUN_FG,
                                    activebackground="#145C28",
                                    activeforeground="white")
        self.root.after(0, _apply)

    def _run_or_stop(self):
        if self.running:
            self._stop_flag = True; return
        if not dynamic_victims:
            messagebox.showwarning("No Victims",
                "No victims on the grid.\nLeft-click a road cell to place one."); return
        threading.Thread(target=self._run_simulation, daemon=True).start()

    def _run_simulation(self):
        self.running=True; self._stop_flag=False
        self.path_cells.clear(); self.rescued.clear()
        self.agent_pos=(0,0); self.total_steps=0; self.total_cost=0.0
        _reset_state()
        self._set_run_btn("stop")
        self._set_status("Running","#A8E6CF")
        algo_name=self.algo_var.get()
        self._update_stats(status="Running",steps=0,cost="0.0",
                           victims=len(dynamic_victims),rescued_ct=0)
        self._log(f"Starting {algo_name} | {len(dynamic_victims)} victim(s)","info")

        algo_fn=ALGORITHMS[algo_name]; delay=lambda: self.speed_var.get()/1000.0
        cur_pos=(0,0); rem=list(dynamic_victims)

        while rem:
            if self._stop_flag: self._finish_run("Stopped"); return
            self._update_stats(victims=len(rem), rescued_ct=len(self.rescued))
            path,found=algo_fn(cur_pos,rem)
            if path is None:
                self._log("No path to any victim!","error")
                self._finish_run("Stuck"); return
            self._log(f"Routing to {found}: {len(path)-1} step(s)","info")
            for i,cell in enumerate(path):
                if self._stop_flag: self._finish_run("Stopped"); return
                self.agent_pos=cell
                if i>0: self.path_cells.add(cell); self.total_cost+=_cost(*cell)
                self.total_steps+=1
                if self.flood_var.get() and self.total_steps%5==0: _spread()
                self.root.after(0,self._draw_grid)
                self._update_stats(steps=self.total_steps,cost=f"{self.total_cost:.1f}")
                time.sleep(delay())
            self.rescued.add(found); rem.remove(found)
            if cell_type[found[0]][found[1]]==VICTIM: cell_type[found[0]][found[1]]=ROAD
            cur_pos=found
            self._log(f"✓ Rescued {found}! ({len(self.rescued)}/{len(dynamic_victims)})","success")
            self._update_stats(rescued_ct=len(self.rescued),victims=len(rem))
            self.root.after(0,self._draw_grid)

        if self._stop_flag: self._finish_run("Stopped"); return
        self._log("All victims rescued! Heading to shelter…","info")
        path_s,_=algo_fn(cur_pos,[shelter_pos])
        if path_s is None:
            self._log("No path to shelter!","warn"); self._finish_run("Stuck"); return
        for i,cell in enumerate(path_s):
            if self._stop_flag: self._finish_run("Stopped"); return
            self.agent_pos=cell
            if i>0: self.path_cells.add(cell); self.total_cost+=_cost(*cell)
            self.total_steps+=1
            if self.flood_var.get() and self.total_steps%5==0: _spread()
            self.root.after(0,self._draw_grid)
            self._update_stats(steps=self.total_steps,cost=f"{self.total_cost:.1f}")
            time.sleep(delay())
        self._log(f"🏁 Complete! {self.total_steps} steps | cost {self.total_cost:.1f}","success")
        self._finish_run("Complete")

    def _finish_run(self, status):
        self.running=False
        cm={"Complete":"#A8E6CF","Stopped":"#FAC775","Stuck":"#F7C1C1"}
        self._set_status(status, cm.get(status,"white"))
        self._update_stats(status=status)
        self._set_run_btn("run")
        self.root.after(0,self._draw_grid)

    def _reset(self):
        if self.running: self._stop_flag=True; time.sleep(0.15)
        dynamic_victims.clear()
        dynamic_victims.extend(_proj_victims if _PROJECT_GRID_LOADED else list(_DEFAULT_VICTIMS))
        _reset_state()
        self.path_cells.clear(); self.rescued.clear()
        self.agent_pos=None; self.total_steps=0; self.total_cost=0.0
        self._update_stats(steps="—",cost="—",victims=len(dynamic_victims),
                           rescued_ct=0,status="Ready")
        self._set_status("Ready","#A8E6CF")
        self._set_run_btn("run")
        self.log_text.config(state="normal")
        self.log_text.delete("1.0","end")
        self.log_text.config(state="disabled")
        self._log(f"Grid reset. {len(dynamic_victims)} victim(s) restored.","info")
        self._draw_grid()

    def _manual_flood(self):
        _spread(); self._log("Flood spread manually.","warn"); self._draw_grid()


def main():
    root = tk.Tk()
    root.minsize(900,700)
    style = ttk.Style()
    try: style.theme_use("clam")
    except: pass
    style.configure("TScale", troughcolor=COLOR_BORDER, sliderthickness=14)
    FloodGUI(root)
    root.mainloop()

if __name__=="__main__":
    main()