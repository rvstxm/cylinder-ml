import json, re, shutil
from pathlib import Path
import numpy as np

PROJECT  = Path.home() / "cylinder-ml"
TEMPLATE = PROJECT / "cases" / "template_sf7"
SWEEP    = PROJECT / "cases" / "sweep_v1"

NU, D    = 1.5e-5, 1e-3
N_WRITES = 10

RE_TRAIN = [20, 30, 38, 44, 47, 50, 53, 57, 62, 70, 80, 90,
            100, 110, 120, 132, 145, 158, 170, 180]
RE_TEST  = [float(x) for x in np.round(np.random.default_rng(7).uniform(25, 175, 5), 1)]


def set_value(path, key, value, line_start=True):
    """Заменяет число после key в файле. Падает, если key не найден."""
    text = path.read_text()
    prefix = r"^" if line_start else r""
    pattern = rf"({prefix}{key}\s*=?\s*)[-+0-9.eE]+"
    new, n = re.subn(pattern, rf"\g<1>{value:.6g}", text, flags=re.M)
    if n == 0:
        raise ValueError(f"'{key}' не найден в {path}")
    path.write_text(new)


def make_case(Re, split):
    U = Re * NU / D
    t_conv = 600 if 40 <= Re <= 60 else 300          # около порога — вдвое дольше
    end = t_conv * D / U
    case = SWEEP / f"Re{Re:g}"
    if case.exists():
        print("уже есть, пропускаю:", case.name)
        return
    shutil.copytree(TEMPLATE, case)
    set_value(case / "0" / "U", "Uinlet", U)
    cd = case / "system" / "controlDict"
    set_value(cd, "endTime", end)
    set_value(cd, "deltaT", 1e-6 * 1.5 / U)
    set_value(cd, "writeInterval", end / N_WRITES)
    set_value(cd, "magUInf", U, line_start=False)
    (case / "params.json").write_text(json.dumps(
        {"Re": Re, "U": U, "endTime": end, "t_conv": t_conv, "split": split}, indent=2))
    print(f"создан {case.name}:  U = {U:.4f} м/с,  endTime = {end:.4f} с")


if __name__ == "__main__":
    SWEEP.mkdir(parents=True, exist_ok=True)
    for Re in RE_TRAIN:
        make_case(Re, "train")
    for Re in RE_TEST:
        make_case(Re, "test")