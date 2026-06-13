# =====================================================================
# FLOOD EVACUATION & RESCUE MANAGEMENT SYSTEM
# UNIFIED ML-READY DATASET GENERATOR
# =====================================================================
#
# FEATURES PER CELL PER TIMESTEP:
#
#   IDENTIFIERS
#     simulation_id, flood_timestep, row, col
#
#   CELL STATE
#     cell_type, water_level, water_level_delta, time_since_flooded
#     is_passable, is_victim_cell, is_shelter_cell
#
#   COST FEATURES
#     movement_cost, risk_cost
#
#   NEIGHBOR FEATURES
#     flood_neighbor_count, safe_neighbor_count
#     passable_neighbor_count
#
#   CONNECTIVITY
#     road_connectivity, is_dead_end
#
#   DISTANCE FEATURES
#     dist_to_nearest_flood, dist_to_nearest_victim
#     dist_to_shelter, dist_to_nearest_flood_origin
#
#   RISK INTELLIGENCE
#     safety_margin, exposure_score, flood_risk_level
#
#   VICTIM ATTRIBUTES (of nearest victim)
#     nearest_victim_age_group   : 0=child, 1=adult, 2=elderly
#     nearest_victim_mobility    : 0=mobile, 1=limited, 2=immobile
#     nearest_victim_medical     : 0=none, 1=injured, 2=critical
#     nearest_victim_group_size  : number of people at that victim cell
#     nearest_victim_wait_time   : timesteps stranded (increases per step)
#
#   ML LABELS
#     zone_label      : 0=safe, 1=risky, 2=victim/critical
#     rescue_needed   : binary (1 if rescue required)
#     rescue_priority : 0=low, 1=medium, 2=high, 3=critical
#                       (derived from victim attrs + water + distance — NOT used as input feature)
#
# =====================================================================

import sys
import os
import copy
import random
import math
import pandas as pd

# ---- Load grid module ----
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Environment import grid as grid_module

# =====================================================================
# CONSTANTS FROM GRID
# =====================================================================

ROWS            = grid_module.ROWS
COLS            = grid_module.COLS

ROAD            = grid_module.ROAD
BUILDING        = grid_module.BUILDING
FLOOD           = grid_module.FLOOD
BLOCKED         = grid_module.BLOCKED
VICTIM          = grid_module.VICTIM
SHELTER         = grid_module.SHELTER

RISKY_THRESHOLD = grid_module.RISKY_THRESHOLD
FLOOD_THRESHOLD = grid_module.FLOOD_THRESHOLD

victims         = grid_module.victims       # list of (row, col)
shelter         = grid_module.shelter       # (row, col)
flood_origins   = grid_module.flood_origins # list of (row, col)


# =====================================================================
# VICTIM ATTRIBUTES
# =====================================================================
# Each victim gets realistic attributes assigned at simulation start.
# These stay fixed per simulation (a victim doesn't change age mid-flood).
# wait_time increases each timestep to simulate urgency.
#
# age_group  : 0 = Child (<15), 1 = Adult (15-60), 2 = Elderly (60+)
# mobility   : 0 = Mobile, 1 = Limited, 2 = Immobile (wheelchair/injury)
# medical    : 0 = None, 1 = Injured, 2 = Critical condition
# group_size : 1-5 people at that victim cell

VICTIM_AGE_GROUPS  = [0, 1, 2]      # child, adult, elderly
VICTIM_MOBILITIES  = [0, 1, 2]      # mobile, limited, immobile
VICTIM_MEDICALS    = [0, 1, 2]      # none, injured, critical

# Weights: elderly/children more likely, immobile/critical more realistic
AGE_WEIGHTS      = [0.25, 0.45, 0.30]
MOBILITY_WEIGHTS = [0.40, 0.35, 0.25]
MEDICAL_WEIGHTS  = [0.45, 0.35, 0.20]


def generate_victim_profiles(seed_offset=0):
    """
    Generate fixed victim attribute profiles for one simulation.
    Returns a dict: {(row, col): {age_group, mobility, medical, group_size}}
    """
    profiles = {}
    for i, pos in enumerate(victims):
        random.seed(seed_offset + i * 7)   # reproducible per victim per sim
        profiles[pos] = {
            "age_group"  : random.choices(VICTIM_AGE_GROUPS,  AGE_WEIGHTS)[0],
            "mobility"   : random.choices(VICTIM_MOBILITIES,  MOBILITY_WEIGHTS)[0],
            "medical"    : random.choices(VICTIM_MEDICALS,    MEDICAL_WEIGHTS)[0],
            "group_size" : random.randint(1, 5),
        }
    return profiles


# =====================================================================
# HELPERS
# =====================================================================

def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def dist_to_nearest(pos, point_list):
    """Manhattan distance to nearest point. Returns 0 if list is empty."""
    if not point_list:
        return 0
    return min(manhattan(pos, p) for p in point_list)


def is_passable(r, c, cell_type, water_level):
    if cell_type[r][c] in [BUILDING, BLOCKED]:
        return False
    if water_level[r][c] > FLOOD_THRESHOLD:
        return False
    return True


def neighbor_stats(r, c, cell_type, water_level):
    """Returns (flood_neighbor_count, safe_neighbor_count, passable_neighbor_count)."""
    dirs = [(-1,0),(1,0),(0,-1),(0,1)]
    flood_n = safe_n = passable_n = 0
    for dr, dc in dirs:
        nr, nc = r + dr, c + dc
        if 0 <= nr < ROWS and 0 <= nc < COLS:
            wl = water_level[nr][nc]
            ct = cell_type[nr][nc]
            if wl > FLOOD_THRESHOLD:
                flood_n += 1
            else:
                safe_n += 1
            if is_passable(nr, nc, cell_type, water_level):
                passable_n += 1
    return flood_n, safe_n, passable_n


def road_connectivity(r, c, cell_type, water_level):
    """Fraction of 4 neighbors that are passable (0.0 – 1.0)."""
    _, _, passable_n = neighbor_stats(r, c, cell_type, water_level)
    return round(passable_n / 4.0, 4)


def safety_margin(wl):
    return round(max(0.0, FLOOD_THRESHOLD - wl), 4)


def flood_risk_level(wl, flood_n):
    """
    0 = LOW, 1 = MEDIUM, 2 = HIGH
    Based on water level + surrounded flooded neighbors.
    """
    score = wl + flood_n * 0.2
    if score > 1.2:
        return 2
    elif score > 0.6:
        return 1
    return 0


def nearest_victim_attrs(pos, victim_profiles):
    """
    Returns attribute dict of the nearest victim by Manhattan distance.
    If no victims, returns all zeros.
    """
    if not victim_profiles:
        return {"age_group": 0, "mobility": 0, "medical": 0, "group_size": 0}
    nearest = min(victim_profiles.keys(), key=lambda v: manhattan(pos, v))
    return victim_profiles[nearest]


def compute_rescue_priority(cell_type_val, wl, flood_n, passable,
                             victim_attrs, dist_victim, dist_shelter):
    """
    Rescue priority label (NOT an input feature — this is the ML target).
    0 = Low, 1 = Medium, 2 = High, 3 = Critical

    Critical: victim cell + elderly/child + immobile/critical + surrounded by flood
    High    : victim cell OR (passable + very high water + surrounded)
    Medium  : passable + risky water or near flood
    Low     : everything else
    """
    if not passable and cell_type_val != VICTIM:
        return 0

    score = 0

    # Victim cell base
    if cell_type_val == VICTIM:
        score += 4
        # Vulnerability from attributes
        age   = victim_attrs.get("age_group", 1)
        mob   = victim_attrs.get("mobility", 0)
        med   = victim_attrs.get("medical", 0)
        grp   = victim_attrs.get("group_size", 1)

        if age in [0, 2]:   score += 2   # child or elderly
        if mob == 2:        score += 2   # immobile
        if med == 2:        score += 3   # critical condition
        if med == 1:        score += 1   # injured
        if grp >= 3:        score += 1   # larger group

    # Water danger
    if wl > FLOOD_THRESHOLD:
        score += 3
    elif wl > RISKY_THRESHOLD:
        score += 1

    # Surrounded by flood
    score += flood_n

    # Far from shelter = harder to evacuate
    if dist_shelter > 15:
        score += 1

    # Map to 4 priority tiers
    if score >= 10:
        return 3   # CRITICAL
    elif score >= 6:
        return 2   # HIGH
    elif score >= 3:
        return 1   # MEDIUM
    return 0       # LOW


# =====================================================================
# FLOOD SPREAD (local, doesn't mutate global grid)
# =====================================================================

def spread_flood_local(cell_type, water_level):
    """Spreads flood one timestep. Modifies cell_type and water_level in place."""
    flooded = [
        (r, c) for r in range(ROWS) for c in range(COLS)
        if water_level[r][c] > FLOOD_THRESHOLD
    ]
    for row, col in flooded:
        for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
            nr, nc = row + dr, col + dc
            if 0 <= nr < ROWS and 0 <= nc < COLS:
                ct = cell_type[nr][nc]
                if ct not in [BUILDING, BLOCKED, VICTIM, SHELTER]:
                    if random.random() < 0.65:
                        water_level[nr][nc] = min(1.0, water_level[nr][nc] + 0.2)

    # Refresh cell types to FLOOD where water is high
    for r in range(ROWS):
        for c in range(COLS):
            if water_level[r][c] > FLOOD_THRESHOLD:
                if cell_type[r][c] not in [BUILDING, VICTIM, SHELTER]:
                    cell_type[r][c] = FLOOD


# =====================================================================
# SNAPSHOT — ONE TIMESTEP → list of row dicts
# =====================================================================

def snapshot_timestep(cell_type, water_level, prev_water_level,
                       flood_age, timestep, victim_profiles):
    """
    Captures ML features for every cell at this timestep.

    Args:
        cell_type        : current cell type grid
        water_level      : current water level grid
        prev_water_level : water level from previous timestep (for delta)
        flood_age        : grid tracking how many steps each cell has been flooded
        timestep         : current timestep index
        victim_profiles  : dict {(r,c): {age_group, mobility, medical, group_size}}

    Returns:
        list of dicts (one per cell)
    """
    rows_data = []

    current_flood_cells = [
        (r, c) for r in range(ROWS) for c in range(COLS)
        if water_level[r][c] > FLOOD_THRESHOLD
    ]

    for r in range(ROWS):
        for c in range(COLS):

            ct  = cell_type[r][c]
            wl  = water_level[r][c]
            pwl = prev_water_level[r][c]

            passable   = is_passable(r, c, cell_type, water_level)
            is_victim  = int(ct == VICTIM)
            is_shelter = int(ct == SHELTER)

            flood_n, safe_n, passable_n = neighbor_stats(r, c, cell_type, water_level)

            conn     = road_connectivity(r, c, cell_type, water_level)
            dead_end = int(conn <= 0.25)

            # Distances
            d_flood        = dist_to_nearest((r,c), current_flood_cells)
            d_flood_origin = dist_to_nearest((r,c), flood_origins)
            d_victim       = dist_to_nearest((r,c), list(victim_profiles.keys())) if victim_profiles else 0
            d_shelter      = manhattan((r,c), shelter)

            # Cost features (only meaningful for passable cells; -1 otherwise for clarity)
            if passable:
                move_cost = round(1 + wl * 10, 4)
                risk_cost = round(move_cost + flood_n * 5, 4)
            else:
                move_cost = -1.0
                risk_cost = -1.0

            # Water change since last timestep
            wl_delta = round(wl - pwl, 4)

            # How many timesteps has this cell been flooded
            time_flooded = flood_age[r][c]

            # Risk indicators
            safety  = safety_margin(wl)
            exp_sc  = round(wl * 50 + flood_n * 10, 4)
            risk_lv = flood_risk_level(wl, flood_n)

            # Nearest victim attributes
            v_attrs = nearest_victim_attrs((r,c), victim_profiles)

            # ---- ML LABELS ----

            # zone_label: 0=safe, 1=risky, 2=critical/victim
            if ct == VICTIM:
                zone_label = 2
            elif passable and (wl > RISKY_THRESHOLD or flood_n >= 2):
                zone_label = 1
            else:
                zone_label = 0

            # rescue_needed: binary
            if ct == VICTIM:
                rescue_needed = 1
            elif passable and wl > RISKY_THRESHOLD and flood_n >= 1:
                rescue_needed = 1
            else:
                rescue_needed = 0

            # rescue_priority: 0–3 (the rich priority label)
            rescue_priority = compute_rescue_priority(
                ct, wl, flood_n, passable,
                v_attrs, d_victim, d_shelter
            )

            rows_data.append({

                # ---- IDENTIFIERS ----
                "row"                        : r,
                "col"                        : c,

                # ---- CELL STATE ----
                "cell_type"                  : ct,
                "water_level"                : round(wl, 4),
                "water_level_delta"          : wl_delta,
                "time_since_flooded"         : time_flooded,
                "is_passable"                : int(passable),
                "is_victim_cell"             : is_victim,
                "is_shelter_cell"            : is_shelter,

                # ---- COST FEATURES ----
                "movement_cost"              : move_cost,
                "risk_cost"                  : risk_cost,

                # ---- NEIGHBOR FEATURES ----
                "flood_neighbor_count"       : flood_n,
                "safe_neighbor_count"        : safe_n,
                "passable_neighbor_count"    : passable_n,

                # ---- CONNECTIVITY ----
                "road_connectivity"          : conn,
                "is_dead_end"                : dead_end,

                # ---- DISTANCES ----
                "dist_to_nearest_flood"      : d_flood,
                "dist_to_flood_origin"       : d_flood_origin,
                "dist_to_nearest_victim"     : d_victim,
                "dist_to_shelter"            : d_shelter,

                # ---- RISK INTELLIGENCE ----
                "safety_margin"              : safety,
                "exposure_score"             : exp_sc,
                "flood_risk_level"           : risk_lv,

                # ---- NEAREST VICTIM ATTRIBUTES ----
                "nearest_victim_age_group"   : v_attrs["age_group"],
                "nearest_victim_mobility"    : v_attrs["mobility"],
                "nearest_victim_medical"     : v_attrs["medical"],
                "nearest_victim_group_size"  : v_attrs["group_size"],

                # ---- ML LABELS ----
                "zone_label"                 : zone_label,
                "rescue_needed"              : rescue_needed,
                "rescue_priority"            : rescue_priority,
            })

    return rows_data


# =====================================================================
# MAIN: GENERATE DATASET
# =====================================================================

def generate_dataset(num_simulations=10, timesteps_per_sim=15, seed=42):

    random.seed(seed)
    all_rows = []

    print(f"\n{'='*60}")
    print(f"  FLOOD EVACUATION — DATASET GENERATION")
    print(f"{'='*60}")
    print(f"  Simulations   : {num_simulations}")
    print(f"  Timesteps     : {timesteps_per_sim}")
    print(f"  Grid size     : {ROWS} x {COLS}")
    print(f"  Victims       : {len(victims)}")
    print(f"  Total rows    : ~{num_simulations * timesteps_per_sim * ROWS * COLS:,}")
    print(f"{'='*60}\n")

    for sim in range(num_simulations):

        print(f"  Simulation {sim+1:>3}/{num_simulations} ...", end=" ", flush=True)

        # Fresh grid copies for this simulation
        ct = copy.deepcopy(grid_module.original_cell_type)
        wl = copy.deepcopy(grid_module.original_water_level)

        # Victim profiles — randomised per simulation, fixed within it
        victim_profiles = generate_victim_profiles(seed_offset=seed + sim * 100)

        # Wait time increases each timestep (victims get more urgent)
        victim_wait = {pos: 0 for pos in victims}

        # Track how long each cell has been flooded
        flood_age = [[0] * COLS for _ in range(ROWS)]

        # Previous water level (needed for delta feature)
        prev_wl = copy.deepcopy(wl)

        for t in range(timesteps_per_sim):

            # Snapshot current state
            rows = snapshot_timestep(ct, wl, prev_wl, flood_age, t, victim_profiles)

            # Tag with simulation & timestep ids
            for row in rows:
                row["simulation_id"]  = sim
                row["flood_timestep"] = t
                # Add wait_time for victim cells specifically
                pos = (row["row"], row["col"])
                row["nearest_victim_wait_time"] = (
                    victim_wait.get(pos, 0) if row["is_victim_cell"]
                    else min(victim_wait.values(), default=0)
                )

            all_rows.extend(rows)

            # Update state for next timestep
            prev_wl = copy.deepcopy(wl)
            spread_flood_local(ct, wl)

            # Update flood age
            for r in range(ROWS):
                for c in range(COLS):
                    if wl[r][c] > FLOOD_THRESHOLD:
                        flood_age[r][c] += 1

            # Victims wait one more timestep
            for pos in victim_wait:
                victim_wait[pos] += 1

        print(f"done  ({timesteps_per_sim * ROWS * COLS:,} rows)")

    df = pd.DataFrame(all_rows)

    # ---- Column order ----
    col_order = [
        # Identifiers
        "simulation_id", "flood_timestep", "row", "col",
        # Cell state
        "cell_type", "water_level", "water_level_delta", "time_since_flooded",
        "is_passable", "is_victim_cell", "is_shelter_cell",
        # Cost
        "movement_cost", "risk_cost",
        # Neighbors
        "flood_neighbor_count", "safe_neighbor_count", "passable_neighbor_count",
        # Connectivity
        "road_connectivity", "is_dead_end",
        # Distances
        "dist_to_nearest_flood", "dist_to_flood_origin",
        "dist_to_nearest_victim", "dist_to_shelter",
        # Risk
        "safety_margin", "exposure_score", "flood_risk_level",
        # Victim attributes
        "nearest_victim_age_group", "nearest_victim_mobility",
        "nearest_victim_medical", "nearest_victim_group_size",
        "nearest_victim_wait_time",
        # Labels
        "zone_label", "rescue_needed", "rescue_priority",
    ]
    df = df[col_order]

    return df


# =====================================================================
# METRICS SUMMARY
# =====================================================================

def print_metrics(df):

    print(f"\n{'='*60}")
    print(f"  DATASET METRICS")
    print(f"{'='*60}")
    print(f"  Total rows         : {len(df):,}")
    print(f"  Total columns      : {len(df.columns)}")
    print(f"  Simulations        : {df['simulation_id'].nunique()}")
    print(f"  Timesteps          : {df['flood_timestep'].nunique()}")

    type_names = {0:"ROAD", 1:"BUILDING", 2:"FLOOD", 3:"BLOCKED", 4:"VICTIM", 5:"SHELTER"}
    print(f"\n  --- Cell Type Distribution ---")
    for k, v in df['cell_type'].value_counts().sort_index().items():
        print(f"    {type_names.get(k,k):<12}: {v:>9,}  ({v/len(df)*100:.1f}%)")

    print(f"\n  --- Water Level ---")
    print(f"    Mean  : {df['water_level'].mean():.4f}")
    print(f"    Max   : {df['water_level'].max():.4f}")
    print(f"    Std   : {df['water_level'].std():.4f}")

    print(f"\n  --- Passability ---")
    p = df['is_passable'].mean() * 100
    print(f"    Passable   : {p:.1f}%")
    print(f"    Impassable : {100-p:.1f}%")

    print(f"\n  --- zone_label (3-class) ---")
    label_names = {0:"Safe", 1:"Risky", 2:"Critical/Victim"}
    for k, v in df['zone_label'].value_counts().sort_index().items():
        print(f"    {label_names.get(k,k):<20}: {v:>9,}  ({v/len(df)*100:.1f}%)")

    print(f"\n  --- rescue_needed (binary) ---")
    for k, v in df['rescue_needed'].value_counts().sort_index().items():
        lbl = "Rescue Needed" if k else "Safe"
        print(f"    {lbl:<20}: {v:>9,}  ({v/len(df)*100:.1f}%)")

    print(f"\n  --- rescue_priority (0–3) ---")
    pnames = {0:"Low", 1:"Medium", 2:"High", 3:"Critical"}
    for k, v in df['rescue_priority'].value_counts().sort_index().items():
        print(f"    {pnames.get(k,k):<12}: {v:>9,}  ({v/len(df)*100:.1f}%)")

    print(f"\n  --- Victim Attributes (victim cells only) ---")
    vcells = df[df['is_victim_cell'] == 1]
    if len(vcells):
        ag_map = {0:"Child", 1:"Adult", 2:"Elderly"}
        mb_map = {0:"Mobile", 1:"Limited", 2:"Immobile"}
        md_map = {0:"None", 1:"Injured", 2:"Critical"}
        print(f"    Age Group  : { {ag_map[k]:v for k,v in vcells['nearest_victim_age_group'].value_counts().items()} }")
        print(f"    Mobility   : { {mb_map[k]:v for k,v in vcells['nearest_victim_mobility'].value_counts().items()} }")
        print(f"    Medical    : { {md_map[k]:v for k,v in vcells['nearest_victim_medical'].value_counts().items()} }")
        print(f"    Avg Group  : {vcells['nearest_victim_group_size'].mean():.2f}")
        print(f"    Max Wait   : {vcells['nearest_victim_wait_time'].max()} timesteps")

    print(f"\n{'='*60}\n")


# =====================================================================
# RUN
# =====================================================================

if __name__ == "__main__":

    df = generate_dataset(
        num_simulations=10,
        timesteps_per_sim=15,
        seed=42
    )

    print_metrics(df)

    out_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "flood_dataset.csv"
    )
    df.to_csv(out_path, index=False)

    print(f"  Dataset saved → {out_path}")
    print(f"  Shape         : {df.shape}\n")