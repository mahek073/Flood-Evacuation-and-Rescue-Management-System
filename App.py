# =====================================================
# FLOOD EVACUATION & RESCUE SYSTEM — STREAMLIT
# Exact port of gui.py visual & logic
# =====================================================
 
import streamlit as st
import time
import heapq
import pickle
import random
import os
from collections import deque
 
st.set_page_config(
    page_title="Flood Evacuation & Rescue — AI Simulator",
    layout="wide",
    initial_sidebar_state="collapsed",
)
 
# ── Custom CSS (mirror gui.py colour scheme) ──────
st.markdown("""
<style>
/* ── palette ── */
:root{
  --bg:#F8F7F4; --panel:#FFFFFF; --accent:#185FA5;
  --text:#2C2C2A; --muted:#888780; --border:#D3D1C7;
  --success:#3B6D11; --warn:#854F0B; --danger:#A32D2D;
  --flood:#1F77B4; --road:#F0EEEA; --building:#3D3D3D;
  --blocked:#FF7F0E; --victim:#D62728; --shelter:#2CA02C;
  --path:#FFD700; --agent:#00C864; --rescued:#A8E6CF;
  --risky:#85C1E9;
}
body, .stApp { background:var(--bg) !important; color:var(--text); font-family:Helvetica,Arial,sans-serif; }
 
/* top bar */
.topbar{background:var(--accent);color:#fff;padding:10px 16px;
        border-radius:6px;font-size:1.05rem;font-weight:bold;
        display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;}
.topbar .status{font-size:0.9rem;}
 
/* panel cards */
.panel{background:var(--panel);border:1px solid var(--border);
       border-radius:8px;padding:12px 14px;height:100%;}
.section-title{font-size:0.7rem;font-weight:bold;color:var(--muted);
               letter-spacing:.08em;text-transform:uppercase;
               border-bottom:1px solid var(--border);padding-bottom:4px;margin:10px 0 6px;}
 
/* algo buttons */
.algo-btn{display:block;width:100%;text-align:left;padding:7px 12px;
          margin:3px 0;border:1px solid var(--border);border-radius:5px;
          background:var(--panel);color:var(--text);font-size:0.95rem;cursor:pointer;}
.algo-btn.active{background:var(--accent);color:#fff;border-color:var(--accent);}
 
/* stat rows */
.stat-row{margin:5px 0;}
.stat-label{font-size:0.78rem;color:var(--muted);}
.stat-value{font-size:0.95rem;font-weight:bold;color:var(--text);}
 
/* ML badges */
.ml-zone   {background:#EEF4FF;color:var(--accent);  border-radius:4px;padding:5px 10px;margin:3px 0;font-weight:bold;}
.ml-risk   {background:#FFF8EE;color:var(--warn);    border-radius:4px;padding:5px 10px;margin:3px 0;font-weight:bold;}
.ml-rescue {background:#FFEEEE;color:var(--danger);  border-radius:4px;padding:5px 10px;margin:3px 0;font-weight:bold;}
.ml-priority{background:#EEFFEE;color:var(--success);border-radius:4px;padding:5px 10px;margin:3px 0;font-weight:bold;}
 
/* log box */
.log-box{background:#F8F7F4;border:1px solid var(--border);border-radius:5px;
         font-family:Courier,monospace;font-size:0.78rem;padding:8px;
         height:130px;overflow-y:auto;white-space:pre-wrap;}
.log-info   {color:var(--accent);}
.log-success{color:var(--success);}
.log-warn   {color:var(--warn);}
.log-error  {color:var(--danger);}
 
/* legend dots */
.legend-row{display:flex;align-items:center;gap:6px;margin:2px 0;font-size:0.8rem;color:var(--muted);}
.dot{width:14px;height:14px;border-radius:2px;border:1px solid var(--border);display:inline-block;flex-shrink:0;}
 
/* grid canvas area */
.grid-wrap{border:1px solid var(--border);border-radius:6px;overflow:hidden;background:var(--bg);display:inline-block;}
svg text{font-family:Helvetica,Arial,sans-serif;}
 
/* hide default streamlit padding */
.block-container{padding-top:0.5rem !important;}
div[data-testid="stVerticalBlock"]{gap:0.3rem;}
 
/* radio button text visibility fix */
div[data-testid="stRadio"] label,
div[data-testid="stRadio"] label p,
div[data-testid="stRadio"] label span{color:var(--text) !important;}
 
/* generic button styling to match algo-btn look */
.stButton button{
  border:1px solid var(--border) !important;
  border-radius:5px !important;
  color:var(--text) !important;
  background:var(--panel) !important;
}
.stButton button:hover{
  border-color:var(--accent) !important;
  color:var(--accent) !important;
}
</style>
""", unsafe_allow_html=True)
 
# =====================================================
# GRID CONSTANTS  (exact values from gui.py)
# =====================================================
ROWS = 20; COLS = 20
ROAD=0; BUILDING=1; FLOOD=2; BLOCKED=3; VICTIM=4; SHELTER_TYPE=5
RISKY_THRESHOLD = 0.3; FLOOD_THRESHOLD = 0.7
 
_BUILDINGS  = [(3,3),(3,4),(3,5),(7,12),(7,13),(7,14),(8,12),(8,13),
               (12,5),(12,6),(13,5),(13,6),(15,15),(15,16),(16,15),(16,16),(16,17),(17,15),(17,16)]
_BLOCKED    = [(5,8),(5,9),(6,9),(10,15),(11,15),(12,15),(13,15)]
_DEFAULT_VICTIMS = [(18,6),(17,8),(15,10)]
_SHELTER    = (18,18)
_FLOOD_ORIGINS = [(9,9),(9,10),(10,9),(10,10),(11,9),(11,10),(12,9),(12,10),
                  (15,8),(15,9),(16,8),(16,9),(17,8),(17,9)]
 
CELL_COLORS = {ROAD:"#F0EEEA", BUILDING:"#3D3D3D", FLOOD:"#1F77B4",
               BLOCKED:"#FF7F0E", VICTIM:"#D62728", SHELTER_TYPE:"#2CA02C"}
COLOR_RISKY  = "#85C1E9"
COLOR_PATH   = "#FFD700"
COLOR_AGENT  = "#00C864"
COLOR_RESCUED= "#A8E6CF"
COLOR_LINE   = "#CCCAC4"
 
# =====================================================
# GRID FACTORY
# =====================================================
def _make_grid():
    ct = [[ROAD]*COLS for _ in range(ROWS)]
    wl = [[0.0]*COLS  for _ in range(ROWS)]
    for r,c in _BUILDINGS:    ct[r][c] = BUILDING
    for r,c in _BLOCKED:      ct[r][c] = BLOCKED
    for r,c in _DEFAULT_VICTIMS: ct[r][c] = VICTIM
    ct[_SHELTER[0]][_SHELTER[1]] = SHELTER_TYPE
    for r,c in _FLOOD_ORIGINS:
        ct[r][c] = FLOOD; wl[r][c] = 1.0
    for r in range(4,19): wl[r][5]  = 0.65
    for r in range(8,18): wl[r][9]  = 0.55
    return ct, wl
 
# =====================================================
# SESSION STATE INIT
# =====================================================
def _init_ss():
    if "ct" not in st.session_state:
        ct, wl = _make_grid()
        st.session_state.ct = ct
        st.session_state.wl = wl
        st.session_state.orig_ct = [list(r) for r in ct]
        st.session_state.orig_wl = [list(r) for r in wl]
    defaults = dict(
        victims=list(_DEFAULT_VICTIMS),
        shelter=_SHELTER,
        rescued=set(),
        path_cells=set(),
        agent_pos=None,
        running=False,
        total_steps=0,
        total_cost=0.0,
        sim_status="Ready",
        algo="BFS",
        speed_ms=120,
        flood_spread=True,
        edit_mode="Place Victim",
        selected_cell=None,
        logs=[],
        ml_zone="—", ml_risk="—", ml_rescue="—", ml_priority="—",
        cell_info="Hover a cell",
        run_requested=False,
        stop_flag=False,
    )
    for k,v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
 
_init_ss()
S = st.session_state   # shorthand
 
# =====================================================
# HELPERS: grid access
# =====================================================
def ct(): return S.ct
def wl(): return S.wl
 
def is_passable(r,c):
    return ct()[r][c] not in (BUILDING, BLOCKED)
 
def neighbors(pos):
    r,c = pos
    out=[]
    for dr,dc in ((-1,0),(1,0),(0,-1),(0,1)):
        nr,nc=r+dr,c+dc
        if 0<=nr<ROWS and 0<=nc<COLS and is_passable(nr,nc):
            out.append((nr,nc))
    return out
 
def cost(r,c):      return 1 + wl()[r][c]*10
def risk_cost(r,c):
    base = cost(r,c)
    fl = sum(1 for dr,dc in ((-1,0),(1,0),(0,-1),(0,1))
             if 0<=r+dr<ROWS and 0<=c+dc<COLS and wl()[r+dr][c+dc]>FLOOD_THRESHOLD)
    return base + fl*3
def heuristic(a,b): return abs(a[0]-b[0])+abs(a[1]-b[1])
def hm(pos,goals):  return min(heuristic(pos,g) for g in goals) if goals else 0
 
# =====================================================
# ALGORITHMS (exact from gui.py)
# =====================================================
def algo_bfs(start, goals):
    goal_set=set(goals); q=deque([start]); visited={start}; parent={start:None}
    while q:
        cur=q.popleft()
        if cur in goal_set:
            path=[]; node=cur
            while node: path.append(node); node=parent[node]
            return path[::-1], cur
        for nb in neighbors(cur):
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
        for nb in neighbors(cur):
            tg=g[cur]+cost(*nb)
            if nb not in g or tg<g[nb]:
                g[nb]=tg; parent[nb]=cur
                heapq.heappush(open_list,(tg+hm(nb,list(goal_set)),nb))
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
        for nb in neighbors(cur):
            tg=g[cur]+risk_cost(*nb)
            if nb not in g or tg<g[nb]:
                g[nb]=tg; parent[nb]=cur
                heapq.heappush(open_list,(tg+hm(nb,list(goal_set)),nb))
    return None, None
 
def algo_hill_climb(start, goals, max_steps=2000):
    goal_set=set(goals); cur=start; path=[cur]; visited={cur}
    for _ in range(max_steps):
        if cur in goal_set: break
        nbs=neighbors(cur)
        if not nbs: break
        best=None; best_score=hm(cur,list(goal_set))
        for nb in nbs:
            s=hm(nb,list(goal_set))
            if s<best_score: best_score=s; best=nb
        if best is None:
            unvisited=[nb for nb in nbs if nb not in visited]
            if unvisited: best=min(unvisited,key=lambda nb:hm(nb,list(goal_set)))
            else: break
        visited.add(best); cur=best; path.append(cur)
    return path, (cur if cur in goal_set else None)
 
ALGORITHMS={"BFS":algo_bfs,"A*":algo_astar,"Risk-Based A*":algo_risk_astar,"Hill Climb":algo_hill_climb}
 
# =====================================================
# FLOOD SPREAD
# =====================================================
def spread_flood():
    flooded=[(r,c) for r in range(ROWS) for c in range(COLS) if wl()[r][c]>FLOOD_THRESHOLD]
    for r,c in flooded:
        for nr,nc in neighbors((r,c)):
            if random.random()<0.65:
                wl()[nr][nc]=min(1.0, wl()[nr][nc]+0.2)
    for r in range(ROWS):
        for c in range(COLS):
            if wl()[r][c]>FLOOD_THRESHOLD:
                if ct()[r][c] not in (BUILDING, VICTIM, SHELTER_TYPE):
                    ct()[r][c]=FLOOD
 
# =====================================================
# ML PREDICTION (optional models)
# =====================================================
_ML_READY=False; _dt_model=_nb_model=_scaler_nb=_features=None
try:
    _mp=os.path.join(os.path.dirname(os.path.abspath(__file__)),'Models')
    with open(os.path.join(_mp,'decision_tree.pkl'),'rb') as f: _dt_model=pickle.load(f)
    with open(os.path.join(_mp,'naive_bayes.pkl'),'rb') as f:   _nb_model=pickle.load(f)
    with open(os.path.join(_mp,'nb_scaler.pkl'),'rb') as f:     _scaler_nb=pickle.load(f)
    with open(os.path.join(_mp,'features.pkl'),'rb') as f:      _features=pickle.load(f)
    _ML_READY=True
except Exception: pass
 
def ml_predict(r,c):
    if not _ML_READY: return "—","—","—","—"
    try:
        import pandas as pd
        wlv=wl()[r][c]
        fn=sum(1 for dr,dc in ((-1,0),(1,0),(0,-1),(0,1))
               if 0<=r+dr<ROWS and 0<=c+dc<COLS and wl()[r+dr][c+dc]>FLOOD_THRESHOLD)
        sn=4-fn; pn=len(neighbors((r,c))); conn=round(pn/4.0,4); dead=int(conn<=0.25)
        flood_cells=[(rr,cc) for rr in range(ROWS) for cc in range(COLS) if wl()[rr][cc]>FLOOD_THRESHOLD]
        d_flood =min((abs(r-rr)+abs(c-cc) for rr,cc in flood_cells),default=0)
        d_origin=min((abs(r-rr)+abs(c-cc) for rr,cc in _FLOOD_ORIGINS),default=0)
        d_victim=min((abs(r-rr)+abs(c-cc) for rr,cc in S.victims),default=0)
        d_shelt =abs(r-S.shelter[0])+abs(c-S.shelter[1])
        row_data={'water_level':round(wlv,4),'water_level_delta':0.0,'time_since_flooded':0,
                  'flood_neighbor_count':fn,'safe_neighbor_count':sn,'passable_neighbor_count':pn,
                  'road_connectivity':conn,'is_dead_end':dead,'dist_to_nearest_flood':d_flood,
                  'dist_to_flood_origin':d_origin,'dist_to_nearest_victim':d_victim,
                  'dist_to_shelter':d_shelt,'nearest_victim_age_group':1,
                  'nearest_victim_mobility':0,'nearest_victim_medical':0,
                  'nearest_victim_group_size':1,'nearest_victim_wait_time':0,
                  'is_passable':int(is_passable(r,c))}
        X=pd.DataFrame([row_data])[_features].values
        zone_names={0:"Safe",1:"Risky",2:"Critical"}
        zone=zone_names[_dt_model.predict(X)[0]]
        X_sc=_scaler_nb.transform(X)
        proba=_nb_model.predict_proba(X_sc)[0]
        flood_risk=f"{(proba[1]+proba[2])*100:.0f}%"
        score=(4 if ct()[r][c]==VICTIM else 0)+(3 if wlv>FLOOD_THRESHOLD else 1 if wlv>RISKY_THRESHOLD else 0)+fn+(1 if d_shelt>15 else 0)
        priority={3:"Critical",2:"High",1:"Medium",0:"Low"}[3 if score>=10 else 2 if score>=6 else 1 if score>=3 else 0]
        rescue_needed="Yes ⚠" if (ct()[r][c]==VICTIM or (is_passable(r,c) and wlv>RISKY_THRESHOLD and fn>=1)) else "No"
        return zone, flood_risk, rescue_needed, priority
    except Exception:
        return "—","—","—","—"
 
# =====================================================
# LOGGING
# =====================================================
def _log(msg, tag="info"):
    ts = time.strftime('%H:%M:%S')
    S.logs.append((ts, msg, tag))
    if len(S.logs)>200: S.logs=S.logs[-200:]
 
# =====================================================
# RESET
# =====================================================
def do_reset():
    ct2, wl2 = _make_grid()
    S.ct = ct2; S.wl = wl2
    S.orig_ct=[list(r) for r in ct2]; S.orig_wl=[list(r) for r in wl2]
    S.victims=list(_DEFAULT_VICTIMS); S.shelter=_SHELTER
    S.rescued=set(); S.path_cells=set(); S.agent_pos=None
    S.total_steps=0; S.total_cost=0.0; S.running=False
    S.sim_status="Ready"; S.stop_flag=False; S.run_requested=False
    S.ml_zone="—"; S.ml_risk="—"; S.ml_rescue="—"; S.ml_priority="—"
    S.cell_info="Hover a cell"; S.selected_cell=None; S.logs=[]
    _log(f"Grid reset. {len(S.victims)} victim(s) restored.")
 
# =====================================================
# SVG GRID  (replaces Tkinter canvas)
# =====================================================
PX = 24   # cell pixel size (fits 20x20 nicely)
 
def build_svg():
    W = COLS*PX; H = ROWS*PX
    parts = [f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">']
 
    for r in range(ROWS):
        for c in range(COLS):
            x0,y0=c*PX,r*PX
            cell=ct()[r][c]; w=wl()[r][c]
 
            # base fill
            if (r,c) in S.path_cells:
                fill=COLOR_PATH
            else:
                fill=CELL_COLORS.get(cell,"#F0EEEA")
 
            parts.append(f'<rect x="{x0}" y="{y0}" width="{PX}" height="{PX}" '
                         f'fill="{fill}" stroke="{COLOR_LINE}" stroke-width="0.4"/>')
 
            # risky water overlay
            if RISKY_THRESHOLD < w <= FLOOD_THRESHOLD:
                parts.append(f'<rect x="{x0}" y="{y0}" width="{PX}" height="{PX}" '
                             f'fill="{COLOR_RISKY}" fill-opacity="0.55" stroke="none"/>')
 
    # rescued victims
    for (r,c) in S.rescued:
        cx,cy=c*PX+PX//2, r*PX+PX//2; rad=PX//2-2
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="{rad}" fill="{COLOR_RESCUED}" stroke="#3B6D11" stroke-width="1.5"/>')
        parts.append(f'<text x="{cx}" y="{cy+4}" text-anchor="middle" fill="#3B6D11" font-size="9" font-weight="bold">✓</text>')
 
    # active victims
    for (r,c) in S.victims:
        if (r,c) not in S.rescued:
            cx,cy=c*PX+PX//2, r*PX+PX//2; rad=PX//2-1
            parts.append(f'<circle cx="{cx}" cy="{cy}" r="{rad}" fill="{CELL_COLORS[VICTIM]}" stroke="white" stroke-width="1.5"/>')
            parts.append(f'<text x="{cx}" y="{cy+4}" text-anchor="middle" fill="white" font-size="8" font-weight="bold">V</text>')
 
    # agent
    if S.agent_pos:
        r,c=S.agent_pos; cx,cy=c*PX+PX//2, r*PX+PX//2; rad=PX//2-2
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="{rad}" fill="{COLOR_AGENT}" stroke="white" stroke-width="1.5"/>')
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="3" fill="white"/>')
 
    # shelter label
    sr,sc=S.shelter; scx,scy=sc*PX+PX//2, sr*PX+PX//2
    parts.append(f'<text x="{scx}" y="{scy+3}" text-anchor="middle" fill="white" font-size="7" font-weight="bold">S</text>')
 
    parts.append('</svg>')
    return "".join(parts)
 
# =====================================================
# SIMULATION (runs step by step, redraws each step)
# =====================================================
def run_simulation():
    if not S.victims:
        _log("No victims on grid — place one first.", "warn")
        S.run_requested=False; return
 
    # reset positions
    S.path_cells=set(); S.rescued=set()
    S.agent_pos=(0,0); S.total_steps=0; S.total_cost=0.0
    # restore grid
    S.ct=[list(r) for r in S.orig_ct]; S.wl=[list(r) for r in S.orig_wl]
    for r2,c2 in S.victims:
        if ct()[r2][c2] not in (BUILDING,BLOCKED,FLOOD,SHELTER_TYPE):
            ct()[r2][c2]=VICTIM
 
    S.sim_status="Running"; S.running=True; S.stop_flag=False
    algo_fn=ALGORITHMS[S.algo]
    delay=S.speed_ms/1000.0
    rem=list(S.victims)
    cur_pos=(0,0)
    _log(f"Starting {S.algo} | {len(rem)} victim(s)","info")
 
    grid_slot = st.empty()   # placeholder updated each frame
 
    def redraw(status_txt, status_color):
        svg=build_svg()
        status_dot="🟢" if "Running" in status_txt else ("🔴" if "Stopped" in status_txt or "Stuck" in status_txt else "🏁")
        grid_slot.markdown(
            f'<div class="grid-wrap">{svg}</div>'
            f'<div style="margin-top:4px;font-size:0.8rem;color:{status_color}">'
            f'{status_dot} {status_txt} &nbsp;|&nbsp; Steps: {S.total_steps} &nbsp;|&nbsp; Cost: {S.total_cost:.1f}'
            f'</div>',
            unsafe_allow_html=True)
 
    while rem:
        if S.stop_flag: S.sim_status="Stopped"; break
        path, found = algo_fn(cur_pos, rem)
        if path is None or found is None:
            _log("⚠ Agent stuck — cannot reach victim.", "warn")
            S.sim_status="Stuck"; break
        _log(f"Routing to {found}: {len(path)-1} step(s)","info")
        for i, cell in enumerate(path):
            if S.stop_flag: S.sim_status="Stopped"; break
            S.agent_pos=cell
            if i>0:
                S.path_cells.add(cell); S.total_cost+=cost(*cell)
            S.total_steps+=1
            if S.flood_spread and S.total_steps%5==0: spread_flood()
            redraw("Running","#185FA5")
            time.sleep(delay)
        if S.stop_flag: break
        if found is None or found not in rem:
            _log("⚠ Victim unreachable.","warn"); S.sim_status="Stuck"; break
        S.rescued.add(found); rem.remove(found)
        if ct()[found[0]][found[1]]==VICTIM: ct()[found[0]][found[1]]=ROAD
        cur_pos=found
        _log(f"✓ Rescued {found}! ({len(S.rescued)}/{len(S.victims)})","success")
 
    if S.sim_status=="Running" and not S.stop_flag:
        _log("All victims rescued! Heading to shelter…","info")
        path_s,_=algo_fn(cur_pos,[S.shelter])
        if path_s:
            for i,cell in enumerate(path_s):
                if S.stop_flag: S.sim_status="Stopped"; break
                S.agent_pos=cell
                if i>0: S.path_cells.add(cell); S.total_cost+=cost(*cell)
                S.total_steps+=1
                if S.flood_spread and S.total_steps%5==0: spread_flood()
                redraw("Running","#185FA5")
                time.sleep(delay)
        if not S.stop_flag:
            _log(f"🏁 Complete! {S.total_steps} steps | cost {S.total_cost:.1f}","success")
            S.sim_status="Complete"
 
    S.running=False; S.run_requested=False
    redraw(S.sim_status, "#3B6D11" if S.sim_status=="Complete" else "#A32D2D")
 
# =====================================================
# TOP BAR
# =====================================================
status_colors={"Ready":"#A8E6CF","Running":"#A8E6CF","Complete":"#A8E6CF","Stopped":"#FAC775","Stuck":"#F7C1C1"}
sc=status_colors.get(S.sim_status,"white")
st.markdown(f'''
<div class="topbar">
  <span>⚡ Flood Evacuation &amp; Rescue — AI Simulator</span>
  <span class="status" style="color:{sc}">● {S.sim_status}</span>
</div>''', unsafe_allow_html=True)
 
# =====================================================
# 3-COLUMN LAYOUT
# =====================================================
left_col, center_col, right_col = st.columns([1.35, 2.4, 1.25])
 
# ─── LEFT PANEL ─────────────────────────────────────
with left_col:
    left_panel = st.container(key="left_panel")
    st.markdown(
        '<style>.st-key-left_panel{background:var(--panel);border:1px solid var(--border);'
        'border-radius:8px;padding:12px 14px;}</style>',
        unsafe_allow_html=True)
 
with left_panel:
    # Algorithm
    st.markdown('<div class="section-title">Algorithm</div>', unsafe_allow_html=True)
    for name in ALGORITHMS:
        label = f"{'► ' if S.algo==name else ''}{name}"
        if S.algo==name:
            st.markdown(
                f'<style>.st-key-algo_{name} button{{'
                f'background:var(--accent)!important;color:#fff!important;'
                f'border-color:var(--accent)!important;font-weight:bold!important;}}</style>',
                unsafe_allow_html=True)
        if st.button(label, key=f"algo_{name}", width='stretch'):
            S.algo=name; st.rerun()
 
    # Edit Grid
    st.markdown('<div class="section-title">Edit Grid</div>', unsafe_allow_html=True)
    st.caption("Left-click row,col to act on a cell:")
    S.edit_mode = st.radio("Mode", ["Place Victim","Erase Cell","Predict Cell"],
                            index=["Place Victim","Erase Cell","Predict Cell"].index(S.edit_mode),
                            label_visibility="collapsed")
    sel = S.selected_cell
    if sel:
        st.markdown(f'<div style="font-size:0.8rem;color:#185FA5">Selected: {sel}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="font-size:0.8rem;color:#888780">No cell selected</div>', unsafe_allow_html=True)
 
    # Cell coord input
    with st.expander("Click a cell (enter row,col)", expanded=False):
        inp_r = st.number_input("Row",0,ROWS-1,0,key="inp_r")
        inp_c = st.number_input("Col",0,COLS-1,0,key="inp_c")
        if st.button("Apply", key="apply_click"):
            r2,c2=int(inp_r),int(inp_c)
            S.selected_cell=(r2,c2)
            names={ROAD:"Road",BUILDING:"Building",FLOOD:"Flood",
                   BLOCKED:"Blocked",VICTIM:"Victim",SHELTER_TYPE:"Shelter"}
            S.cell_info=(f"({r2},{c2})\nType: {names.get(ct()[r2][c2],ct()[r2][c2])}\n"
                         f"Water: {wl()[r2][c2]:.2f}\n"
                         f"Pass: {'Yes' if is_passable(r2,c2) else 'No'}")
            if S.edit_mode=="Place Victim":
                if ct()[r2][c2] in (BUILDING,BLOCKED,FLOOD,SHELTER_TYPE):
                    _log(f"Cannot place victim at ({r2},{c2}).","warn")
                elif (r2,c2)==S.shelter:
                    _log("Cannot place victim on shelter.","warn")
                elif (r2,c2) in S.victims:
                    _log(f"Victim already at ({r2},{c2}).","warn")
                else:
                    S.victims.append((r2,c2)); ct()[r2][c2]=VICTIM
                    _log(f"Victim placed at ({r2},{c2}). Total: {len(S.victims)}","info")
            elif S.edit_mode=="Erase Cell":
                if (r2,c2) in S.victims: S.victims.remove((r2,c2))
                if ct()[r2][c2] not in (BUILDING,SHELTER_TYPE,FLOOD):
                    ct()[r2][c2]=ROAD
                _log(f"Cell ({r2},{c2}) erased.","warn")
            elif S.edit_mode=="Predict Cell":
                zone,risk,resc,pri=ml_predict(r2,c2)
                S.ml_zone=zone; S.ml_risk=risk; S.ml_rescue=resc; S.ml_priority=pri
                _log(f"Predicted ({r2},{c2}): zone={zone} risk={risk}","info")
            st.rerun()
 
    # Controls
    st.markdown('<div class="section-title">Controls</div>', unsafe_allow_html=True)
    S.speed_ms = st.slider("Speed (ms/step)", 20, 600, S.speed_ms, step=10, key="spd")
    S.flood_spread = st.checkbox("Dynamic flood spread", value=S.flood_spread, key="fs")
 
    # Actions
    st.markdown('<div class="section-title">Actions</div>', unsafe_allow_html=True)
 
    run_label = "■ Stop" if S.running else "▶ Run Rescue"
    run_color = "#B91C1C" if S.running else "#1A7F37"
    st.markdown(
        f'<style>.st-key-run_btn button{{'
        f'background:{run_color}!important;color:#fff!important;'
        f'border-color:{run_color}!important;font-weight:bold!important;font-size:1rem!important;}}</style>',
        unsafe_allow_html=True)
    if st.button(run_label, key="run_btn", width='stretch'):
        if S.running:
            S.stop_flag=True
        else:
            S.run_requested=True
        st.rerun()
 
    if st.button("↺  Reset Grid", width='stretch', key="reset_btn"):
        do_reset(); st.rerun()
 
    c1,c2=st.columns(2)
    with c1:
        if st.button("🗑 Clear Victims", width='stretch', key="clr_v"):
            for r2,c2v in list(S.victims):
                if ct()[r2][c2v]==VICTIM: ct()[r2][c2v]=ROAD
            S.victims.clear(); S.rescued.clear()
            _log("All victims cleared.","warn"); st.rerun()
    with c2:
        if st.button("〰 Spread Flood", width='stretch', key="spr_f"):
            spread_flood(); _log("Flood spread manually.","warn"); st.rerun()
 
    # Legend
    st.markdown('<div class="section-title">Legend</div>', unsafe_allow_html=True)
    legend=[
        ("#F0EEEA","Road"),("#3D3D3D","Building"),("#1F77B4","Flood"),
        ("#FF7F0E","Blocked"),("#D62728","Victim"),("#2CA02C","Shelter"),
        ("#85C1E9","Risky (water)"),("#FFD700","Agent path"),
        ("#00C864","Rescue agent"),("#A8E6CF","Rescued victim"),
    ]
    html=""
    for color,label in legend:
        html+=f'<div class="legend-row"><span class="dot" style="background:{color}"></span>{label}</div>'
    st.markdown(html, unsafe_allow_html=True)
 
 
# ─── CENTER PANEL ───────────────────────────────────
with center_col:
    st.markdown('<div class="section-title" style="font-size:0.9rem;margin-bottom:6px;">Simulation Grid  '
                f'<span style="font-size:0.75rem;color:#888780">20×20 · algorithm: {S.algo}</span></div>',
                unsafe_allow_html=True)
 
    grid_placeholder = st.empty()
 
    if S.run_requested:
        # run the full simulation (blocking, redraws inside)
        run_simulation()
        st.rerun()
    else:
        svg=build_svg()
        grid_placeholder.markdown(
            f'<div class="grid-wrap">{svg}</div>'
            f'<div style="margin-top:4px;font-size:0.8rem;color:#888780">'
            f'Steps: {S.total_steps} &nbsp;|&nbsp; Cost: {S.total_cost:.1f} &nbsp;|&nbsp; '
            f'Rescued: {len(S.rescued)}/{len(S.victims)}</div>',
            unsafe_allow_html=True)
 
    # Log box
    st.markdown('<div class="section-title" style="margin-top:10px;">Log</div>', unsafe_allow_html=True)
    tag_css={"info":"log-info","success":"log-success","warn":"log-warn","error":"log-error"}
    log_lines="".join(
        f'<span class="{tag_css.get(t,"")}">[{ts}] {msg}\n</span>'
        for ts,msg,t in S.logs[-40:]
    ) or '<span class="log-info">[--:--:--] System initialized\n</span>'
    st.markdown(f'<div class="log-box" id="logbox">{log_lines}</div>'
                '<script>var lb=document.getElementById("logbox");if(lb)lb.scrollTop=lb.scrollHeight;</script>',
                unsafe_allow_html=True)
 
# ─── RIGHT PANEL ────────────────────────────────────
with right_col:
    right_panel = st.container(key="right_panel")
    st.markdown(
        '<style>.st-key-right_panel{background:var(--panel);border:1px solid var(--border);'
        'border-radius:8px;padding:12px 14px;}</style>',
        unsafe_allow_html=True)
 
with right_panel:
    st.markdown('<div class="section-title">Statistics</div>', unsafe_allow_html=True)
 
    stats=[
        ("Algorithm",      S.algo),
        ("Victims remaining", len([v for v in S.victims if v not in S.rescued])),
        ("Rescued",        len(S.rescued)),
        ("Total steps",    S.total_steps if S.total_steps else "—"),
        ("Path cost",      f"{S.total_cost:.1f}" if S.total_cost else "—"),
        ("Status",         S.sim_status),
    ]
    stat_html=""
    sc_map={"Running":"#185FA5","Complete":"#3B6D11","Stuck":"#A32D2D","Stopped":"#854F0B","Ready":"#888780"}
    for lbl,val in stats:
        vc=sc_map.get(str(val),"#2C2C2A")
        stat_html+=f'<div class="stat-row"><div class="stat-label">{lbl}</div><div class="stat-value" style="color:{vc}">{val}</div></div>'
    st.markdown(stat_html, unsafe_allow_html=True)
 
    # Victims on grid
    st.markdown('<div class="section-title">Victims on grid</div>', unsafe_allow_html=True)
    vcount=len(S.victims)
    st.markdown(f'<div style="font-size:1rem;font-weight:bold;color:#A32D2D">{vcount} victim(s)</div>'
                '<div style="font-size:0.75rem;color:#888780">Use controls on left to place/remove</div>',
                unsafe_allow_html=True)
 
    # ML Prediction
    st.markdown('<div class="section-title">ML Prediction</div>', unsafe_allow_html=True)
    if not _ML_READY:
        st.markdown('<div style="font-size:0.75rem;color:#888780">Models not found — showing rule-based fallback</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="font-size:0.75rem;color:#888780">Select a cell → Apply to predict</div>', unsafe_allow_html=True)
 
    st.markdown(f'''
    <div class="ml-zone">Zone: {S.ml_zone}</div>
    <div class="ml-risk">Flood Risk: {S.ml_risk}</div>
    <div class="ml-rescue">Rescue Needed: {S.ml_rescue}</div>
    <div class="ml-priority">Priority: {S.ml_priority}</div>
    ''', unsafe_allow_html=True)
 
    # Cell info
    st.markdown('<div class="section-title">Cell Info</div>', unsafe_allow_html=True)
    st.markdown(f'<div style="font-family:Courier,monospace;font-size:0.8rem;'
                f'background:#F8F7F4;border:1px solid #D3D1C7;border-radius:4px;'
                f'padding:8px;white-space:pre-wrap">{S.cell_info}</div>',
                unsafe_allow_html=True)
 
 
# =====================================================
# BOTTOM — VICTIM TABLE
# =====================================================
st.divider()
st.markdown('<div style="font-size:1rem;font-weight:bold;color:#2C2C2A;margin-bottom:6px;">Victim Table</div>', unsafe_allow_html=True)
 
import pandas as pd
victim_rows=[]
for r2,c2 in S.victims:
    status="✓ Rescued" if (r2,c2) in S.rescued else "⚠ Active"
    wlv=wl()[r2][c2]
    zone,risk,resc,pri=ml_predict(r2,c2) if _ML_READY else ("—","—","—","—")
    victim_rows.append({"Row":r2,"Col":c2,"Status":status,"Water Level":f"{wlv:.2f}",
                        "Zone":zone,"Flood Risk":risk,"Rescue Needed":resc,"Priority":pri})
 
if victim_rows:
    st.dataframe(pd.DataFrame(victim_rows), width='stretch', hide_index=True)
else:
    st.caption("No victims on grid.")
 
# Footer
st.markdown(f'<div style="text-align:center;font-size:0.75rem;color:#888780;margin-top:8px;">'
            f'Algorithm: {S.algo} &nbsp;|&nbsp; Steps: {S.total_steps} &nbsp;|&nbsp; '
            f'Rescued: {len(S.rescued)} &nbsp;|&nbsp; Status: {S.sim_status}</div>',
            unsafe_allow_html=True)
 
 
