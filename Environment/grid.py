# =====================================================
# FLOOD EVACUATION & RESCUE ENVIRONMENT
# =====================================================

import random
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

# =====================================================
# GRID SIZE
# =====================================================

ROWS = 20
COLS = 20

# =====================================================
# CELL TYPES
# =====================================================

ROAD = 0
BUILDING = 1
FLOOD = 2
BLOCKED = 3
VICTIM = 4
SHELTER = 5

# =====================================================
# WATER THRESHOLDS
# =====================================================

# Water > 0.3 -> Risky Cell
RISKY_THRESHOLD = 0.3

# Water > 0.7 -> Flooded / Impassable
FLOOD_THRESHOLD = 0.7

# =====================================================
# CREATE GRIDS
# =====================================================

cell_type = [[ROAD for _ in range(COLS)] for _ in range(ROWS)]

water_level = [[0.0 for _ in range(COLS)] for _ in range(ROWS)]

# =====================================================
# BUILDINGS
# =====================================================

buildings = [
    (3,3),(3,4),(3,5),
    (7,12),(7,13),(7,14),
    (8,12),(8,13),
    (12,5),(12,6),
    (13,5), (13,6),
    (15,15), (15,16),
    (16,15),
    (16,16),(16,17),
    (17,15),
    (17,16)
]

for r, c in buildings:
    cell_type[r][c] = BUILDING

# =====================================================
# BLOCKED ROADS
# =====================================================

blocked = [
    (5,8),
    (5,9),
    (6,9),
    (10,15),
    (11,15),
    (12,15),
    (13,15)
]

for r, c in blocked:
    cell_type[r][c] = BLOCKED

# =====================================================
# VICTIM
# =====================================================

victims = [(1,1),(4,2),(2,9),(6,2)]

for r, c in victims:
    cell_type[r][c] = VICTIM

# =====================================================
# SHELTER
# =====================================================

shelter = (18,18)
cell_type[18][18] = SHELTER

# =====================================================
# FLOOD ORIGINS
# =====================================================

flood_origins = [
    (9,9),
    (9,10),
    (10,9),
    (10,10),
    (11,9),
    (11,10),
    (12,9),
    (12,10),
    (15,8),
    (15,9),
    (16,8),
    (16,9),
    (17,8),
    (17,9)
]

for r, c in flood_origins:

    cell_type[r][c] = FLOOD
    water_level[r][c] = 1.0

# =====================================================
# ADD SOME RISKY CELLS
# =====================================================

water_level[8][8] = 0.5
water_level[8][9] = 0.4
water_level[10][10] = 0.6
water_level[11][9] = 0.45
water_level[12][9] = 0.5
water_level[13][9] = 0.45
water_level[14][9] = 0.4

# =====================================================
# CHECK PASSABILITY
# =====================================================

def is_passable(row, col):

    if cell_type[row][col] == BUILDING:
        return False

    if cell_type[row][col] == BLOCKED:
        return False

    if water_level[row][col] > FLOOD_THRESHOLD:
        return False

    return True

# =====================================================
# GET CELL INFO
# =====================================================

def get_cell_info(row, col):

    return {
        "type": cell_type[row][col],
        "water_level": water_level[row][col],
        "passable": is_passable(row, col)
    }

# =====================================================
# GET VALID NEIGHBORS
# =====================================================

def get_neighbors(position):

    row, col = position

    directions = [
        (-1,0),   # UP
        (1,0),    # DOWN
        (0,-1),   # LEFT
        (0,1)     # RIGHT
    ]

    neighbors = []

    for dr, dc in directions:

        nr = row + dr
        nc = col + dc

        if (
            0 <= nr < ROWS
            and
            0 <= nc < COLS
            and
            is_passable(nr, nc)
        ):
            neighbors.append((nr, nc))

    return neighbors

# =====================================================
# MOVEMENT COST
# =====================================================

def get_cost(row, col):

    depth = water_level[row][col]

    return 1 + depth * 10

# =====================================================
# REFRESH FLOOD CELLS
# =====================================================

def refresh_flood_cells():

    for r in range(ROWS):
        for c in range(COLS):

            if water_level[r][c] > FLOOD_THRESHOLD:

                if cell_type[r][c] not in [
                    BUILDING,
                    VICTIM,
                    SHELTER
                ]:
                    cell_type[r][c] = FLOOD

# =====================================================
# FLOOD SPREAD SIMULATION
# =====================================================
def spread_flood():

    flooded_cells = []

    for r in range(ROWS):
        for c in range(COLS):

            if water_level[r][c] > FLOOD_THRESHOLD:
                flooded_cells.append((r, c))

    for row, col in flooded_cells:

        neighbors = get_neighbors((row, col))

        for nr, nc in neighbors:

            if random.random() < 0.65:

                water_level[nr][nc] += 0.2

                if water_level[nr][nc] > 1.0:
                    water_level[nr][nc] = 1.0

    refresh_flood_cells()

# =====================================================
# DISPLAY GRID
# =====================================================

def display_grid(save_image=True):

    colors = [
        "#f5f5f5",  # ROAD
        "#3d3d3d",  # BUILDING
        "#1f77b4",  # FLOOD
        "#ff7f0e",  # BLOCKED
        "#d62728",  # VICTIM
        "#2ca02c"   # SHELTER
    ]

    cmap = ListedColormap(colors)

    fig, ax = plt.subplots(figsize=(8,8))

    ax.imshow(
        cell_type,
        cmap=cmap,
        vmin=0,
        vmax=5
    )

    # ==========================================
    # RISKY CELL OVERLAY
    # ==========================================

    overlay = np.zeros((ROWS, COLS, 4))

    for r in range(ROWS):
        for c in range(COLS):

            if (
                RISKY_THRESHOLD
                <
                water_level[r][c]
                <=
                FLOOD_THRESHOLD
            ):

                overlay[r][c] = [
                    0.1,
                    0.4,
                    0.9,
                    0.35
                ]

    ax.imshow(overlay)

    # ==========================================
    # GRID LINES
    # ==========================================

    ax.set_xticks(range(COLS))
    ax.set_yticks(range(ROWS))

    ax.set_xticks(
        [x - 0.5 for x in range(1, COLS)],
        minor=True
    )

    ax.set_yticks(
        [y - 0.5 for y in range(1, ROWS)],
        minor=True
    )

    ax.grid(
        which="minor",
        color="black",
        linewidth=0.4
    )

    ax.set_title(
        "Flood Evacuation & Rescue Environment"
    )


    if save_image:

        plt.savefig(
            "../images/flood_environment.png",
            bbox_inches="tight"
        )

        print(
            "\nImage Saved: flood_environment.png"
        )

    plt.show()

# =====================================================
# TEST ENVIRONMENT
# =====================================================

print("\nVICTIM:")
print(victims)

print("\nSHELTER:")
print(shelter)

print("\nFLOOD ORIGINS:")
print(flood_origins)

print("\nNEIGHBORS OF VICTIM:")
for victim in victims:
    print(f"{victim}: {get_neighbors(victim)}")

print("\nCELL INFO (9,9):")
print(get_cell_info(9,9))

print("\nMOVEMENT COST OF (8,8):")
print(get_cost(8,8))

print("\nIS (3,3) PASSABLE?")
print(is_passable(3,3))

# =====================================================
# SHOW ENVIRONMENT
# =====================================================

if __name__ == "__main__":
    display_grid()
