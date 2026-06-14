# Flood Evacuation & Rescue Management System

An AI-powered flood simulation system that combines pathfinding algorithms with machine learning to support real-time emergency decision-making during flood disasters.

---

## Project Overview

This system simulates a dynamic flood environment on a grid and uses multiple AI techniques to:

- Navigate rescue teams through flooded terrain to reach victims
- Classify grid zones as **Safe**, **Risky**, or **Critical** in real time
- Detect which cells require **immediate rescue operations**
- Estimate **flood risk probability** for early warning
- Prioritize rescue operations based on victim vulnerability

---

## GUI — Live Simulation & ML Prediction

The desktop application (`gui.py`) provides a fully interactive simulation environment:

| Feature | Description |
|---|---|
| Live Grid | 20×20 dynamic flood grid with real-time flood spreading |
| 4 Algorithms | BFS, A*, Risk-Based A*, Hill Climbing — switchable mid-simulation |
| Place Victims | Left-click to add/remove victims anywhere on the grid |
| ML Prediction | Click any cell to get instant ML-powered zone, risk, and rescue predictions |
| Live Statistics | Steps, path cost, rescued count updated in real time |
| Dynamic Flood | Flood spreads every 5 steps during rescue simulation |

### Running the GUI

```bash
python gui.py
```

---

## 🤖 Algorithms

| Algorithm | Purpose | Key Property |
|---|---|---|
| **BFS** | Baseline pathfinding | Guarantees shortest path |
| **A\*** | Optimized pathfinding | Faster than BFS using heuristic |
| **Risk-Based A\*** | Flood-aware routing | Avoids high-risk flooded cells |
| **Hill Climbing** | Dynamic re-routing | Adapts in real time as flood spreads |

---

## Machine Learning Models

| Model | Task | Target | Accuracy |
|---|---|---|---|
| Decision Tree | Zone Classification | `zone_label` | ~95% |
| KNN + SMOTE | Rescue Detection | `rescue_needed` | F1: 0.93 |
| Naive Bayes | Flood Risk Probability | `zone_label` | ~40%* |
| ANN (MLP) | Zone Classification | `zone_label` | ~96% |

> *Naive Bayes accuracy drops without directly derived features — this intentionally demonstrates the model's limitation with correlated features, which is a key insight of this project.

### Dataset
- **60,000 rows × 33 columns** generated from flood simulation
- Features include: water level, neighbor counts, distances, victim attributes
- Labels: `zone_label`, `rescue_needed`, `rescue_priority`
- Class imbalance addressed using **SMOTE** for rescue detection

---

## Project Structure

```
Flood-Evacuation-and-Rescue-Management-System/
│
├── gui.py                          # Main desktop application
│
├── Environment/
│   └── grid.py                     # Grid setup, flood spread, helpers
│
├── Dataset/
│   ├── generate_dataset.py         # Dataset generator from simulation
│   └── flood_dataset.csv           # Generated dataset (60,000 rows)
│
├── Models/
│   ├── decision_tree.pkl           # Trained Decision Tree
│   ├── knn_model.pkl               # Trained KNN model
│   ├── knn_scaler.pkl              # KNN StandardScaler
│   ├── naive_bayes.pkl             # Trained Naive Bayes
│   ├── nb_scaler.pkl               # Naive Bayes StandardScaler
│   ├── ann_model.pkl               # Trained ANN (MLP)
│   ├── ann_scaler.pkl              # ANN StandardScaler
│   └── features.pkl                # Feature list used during training
│
├── notebook/
│   └── flood-evacuation-&-rescue-analysis.ipynb   # ML training notebook
│
├── Algorithms/
│   ├── bfs.ipynb                   # BFS implementation & visualization
│   ├── A-star.ipynb                # A* implementation & visualization
│   ├── RiskBased-A-star.ipynb      # Risk-Based A* notebook
│   └── Hill-Climbing.ipynb         # Hill Climbing notebook
│
└── requirements.txt
```

---

## Setup & Installation

### 1. Clone the repository
```bash
git clone https://github.com/RadhikaKapoor383/Flood-Evacuation-and-Rescue-Management-System.git
cd Flood-Evacuation-and-Rescue-Management-System
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the GUI
```bash
python gui.py
```

### 4. Run the ML Notebook (optional)
Open `notebook/flood-evacuation-&-rescue-analysis.ipynb` in Jupyter Notebook.

---

## Requirements

```
pandas
numpy
scikit-learn
imbalanced-learn
matplotlib
seaborn
```

---

## Key Design Decisions

- **Two-array grid architecture** — separate arrays for cell type and water level preserve nuance for ML feature extraction
- **Dataset from environment** — training data generated directly from simulation, with the simulator acting as the labeling oracle
- **SMOTE for class imbalance** — rescue cases are rare (~3%) so synthetic oversampling ensures the KNN model doesn't ignore them
- **Data leakage fix** — derived features (`movement_cost`, `risk_cost`, `exposure_score`, `safety_margin`, `flood_risk_level`) removed from training to ensure genuine learning

---


## Performance Metrics
| Model | Accuracy | Precision | Recall | F1-Score |
|---|---|---|---|---|
| Decision Tree (Zone Classification) | ~95% | 0.95 | 0.95 | 0.95 |
| KNN + SMOTE (Rescue Detection) | ~93% | 0.92 | 0.94 | 0.93 |
| Naive Bayes (Flood Risk Probability) | ~40% | 0.38 | 0.42 | 0.40 |
| ANN (MLP) (Zone Classification) | ~96% | 0.96 | 0.96 | 0.96 |
