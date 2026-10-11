import json, re
from pathlib import Path
import numpy as np
import pandas as pd
import duckdb
from scipy.signal import find_peaks

PROJECT = Path.home() / "cylinder-ml"
SWEEP   = PROJECT / "cases" / "sweep_v1"
DATA    = PROJECT / "data"
D = 1e-3
MESH_LEVEL, SCHEME = 7, "backward"


def read_forces(case):
    f = next((case / "postProcessing").glob("forceCoeffs*/0/forceCoeffs.dat"))
    d = np.loadtxt(f, comments="#")
    return d[:, 0], d[:, 2], d[:, 3]          # t, Cd, Cl


def read_clock_time(case):
    txt = (case / "log.foamRun").read_text(errors="ignore")
    m = re.findall(r"ClockTime = ([\d.]+)", txt)
    return float(m[-1]) if m else np.nan


def read_n_cells(case):
    with open(case / "constant" / "polyMesh" / "owner", "rb") as fh:
        head = fh.read(2000).decode(errors="ignore")
    m = re.search(r"nCells:\s*(\d+)", head)
    return int(m.group(1)) if m else None


def analyze(t, cd, cl, U):
    w = t > 0.5 * t[-1]                          # берём вторую половину расчёта
    t, cd, cl = t[w], cd[w], cl[w]
    half = t > t[0] + 0.5 * (t[-1] - t[0])       # и делим её ещё пополам
    amp1, amp2 = np.ptp(cl[~half]) / 2, np.ptp(cl[half]) / 2
    cd1, cd2 = cd[~half].mean(), cd[half].mean()

    shedding = amp2 > 1e-3
    out = {"cl_amp": amp2, "shedding": bool(shedding),
           "drift_cd": abs(cd2 - cd1) / cd2,
           "drift_amp": abs(amp2 - amp1) / amp2 if shedding else 0.0}

    if shedding:
        peaks, _ = find_peaks(cl, prominence=0.3 * np.ptp(cl))
        out["st"] = D / (np.mean(np.diff(t[peaks])) * U)
        out["n_peaks"] = len(peaks)
        out["cd"] = cd[peaks[0]:peaks[-1]].mean()   # целое число периодов
    else:
        out["st"], out["n_peaks"], out["cd"] = np.nan, 0, cd[half].mean()

    out["converged"] = bool(out["drift_cd"] < 0.005 and out["drift_amp"] < 0.02)
    return out


rows, series = [], []
for case in sorted(SWEEP.glob("Re*")):
    p = json.loads((case / "params.json").read_text())
    try:
        t, cd, cl = read_forces(case)
    except StopIteration:
        print(f"{case.name}: нет данных, пропускаю")
        continue
    res = analyze(t, cd, cl, p["U"])
    run_id = f"sweep_v1/{case.name}"
    rows.append({"run_id": run_id, "code": "OpenFOAM", "re": p["Re"], "u": p["U"],
                 "split": p["split"], "mesh_level": MESH_LEVEL, "scheme": SCHEME,
                 "n_cells": read_n_cells(case), "clock_time_s": read_clock_time(case),
                 "t_end": t[-1], **res})
    series.append(pd.DataFrame({"run_id": run_id, "t": t[::5], "cd": cd[::5], "cl": cl[::5]}))
    print(f"{case.name:9s} Cd={res['cd']:.4f}  St={res['st']:.4f}  Cl_amp={res['cl_amp']:.4f}  "
          f"срыв={res['shedding']!s:5s}  установился={res['converged']}")

df = pd.DataFrame(rows).sort_values("re")
ts = pd.concat(series)

DATA.mkdir(exist_ok=True)
df.to_csv(DATA / "dataset_v1.csv", index=False)

runs_cols    = ["run_id", "code", "re", "u", "split", "mesh_level", "scheme", "n_cells", "clock_time_s", "t_end"]
results_cols = ["run_id", "cd", "st", "cl_amp", "shedding", "converged", "drift_cd", "drift_amp", "n_peaks"]
runs, results = df[runs_cols], df[results_cols]

con = duckdb.connect(str(DATA / "experiments.duckdb"))
con.execute("CREATE OR REPLACE TABLE runs AS SELECT * FROM runs")
con.execute("CREATE OR REPLACE TABLE results AS SELECT * FROM results")
con.execute("CREATE OR REPLACE TABLE timeseries AS SELECT * FROM ts")
con.close()
print(f"\nготово: {len(df)} расчётов, {len(ts)} строк временных рядов")