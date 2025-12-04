from pathlib import Path
import pandas as pd
import datetime as dt
import yaml

BASE = Path("storage")
BASE_TEST = Path("storage_tests")
TARGETS_PATH = Path("config/targets.yaml")
BASE_LOGINS = Path("storage_logins")
KNOWN_COLLEGES = ["economy", "finance", "intl", "west", "tax", "mgmt"]


def _today():
    return dt.date.today().isoformat()


def _safe_filename(name: str) -> str:
    return name.replace(" ", "_")

def _safe_dir(name: str) -> str:
    return name.replace("/", "_").replace(" ", "_")


def _dirnames_for_college(college: str) -> list[Path]:
    disp = get_college_display(college)
    names = [college]
    if disp and disp != college:
        names.append(_safe_dir(disp))
    return [BASE / n for n in names]

def _dirnames_for_college_test(college: str) -> list[Path]:
    disp = get_college_display(college)
    names = [college]
    if disp and disp != college:
        names.append(_safe_dir(disp))
    return [BASE_TEST / n for n in names]

def _primary_dir_for_college(college: str, is_test: bool = False) -> Path:
    disp = get_college_display(college)
    name = _safe_dir(disp) if disp else college
    return (BASE_TEST if is_test else BASE) / name

def archive_raw_file(uploaded_file, college: str, is_test: bool = False) -> Path:
    root = _primary_dir_for_college(college, is_test)
    d = root / _today()
    d.mkdir(parents=True, exist_ok=True)
    raw_path = d / _safe_filename(uploaded_file.name)
    with open(raw_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return raw_path


def save_parsed_dataset(df: pd.DataFrame, meta: dict, college: str, is_test: bool = False) -> Path:
    if df is None or df.empty:
        return None
    root = _primary_dir_for_college(college, is_test)
    d = root / _today()
    d.mkdir(parents=True, exist_ok=True)
    t = meta.get("type", "")
    tkey = "qa" if t == "问答对" else "ex"
    level = meta.get("level") if tkey == "ex" else None
    lvlkey = "ug" if level == "本科" else ("grad" if level == "研究生" else "ug")
    fname = f"{Path(meta['filename']).stem}_parsed_{tkey}{('_' + lvlkey) if tkey=='ex' else ''}.csv"
    out = d / fname
    df_out = df.copy()
    if level:
        df_out["level"] = level
    df_out.to_csv(out, index=False)
    return out


def list_history(college: str):
    records = []
    for d in _dirnames_for_college(college):
        if not d.exists():
            continue
        for day in sorted([p for p in d.iterdir() if p.is_dir()]):
            for f in day.iterdir():
                records.append({
                    "date": day.name,
                    "file": f.name,
                    "path": str(f),
                })
    return records

def list_history_tests(college: str):
    records = []
    for d in _dirnames_for_college_test(college):
        if not d.exists():
            continue
        for day in sorted([p for p in d.iterdir() if p.is_dir()]):
            for f in day.iterdir():
                records.append({
                    "date": day.name,
                    "file": f.name,
                    "path": str(f),
                })
    return records


def merge_all_parsed() -> pd.DataFrame | None:
    if not BASE.exists():
        return None
    frames = []
    for college_dir in BASE.iterdir():
        if not college_dir.is_dir():
            continue
        for day in college_dir.iterdir():
            if not day.is_dir():
                continue
            for f in day.glob("*_parsed_*.csv"):
                try:
                    df = pd.read_csv(f)
                    # 显示学院中文名（若不可映射则使用目录名）
                    df["college"] = get_college_display(college_dir.name)
                    df["date"] = day.name
                    # 从文件名推断级别（若列中不存在）
                    name = f.name
                    if "_parsed_ex_grad" in name and "level" not in df.columns:
                        df["level"] = "研究生"
                    elif "_parsed_ex_ug" in name and "level" not in df.columns:
                        df["level"] = "本科"
                    frames.append(df)
                except Exception:
                    continue
    if frames:
        return pd.concat(frames, ignore_index=True)
    return None

def list_parsed_datasets(college: str, is_test: bool = False):
    items = []
    dirs = _dirnames_for_college_test(college) if is_test else _dirnames_for_college(college)
    for d in dirs:
        if not d.exists():
            continue
        for day in sorted([p for p in d.iterdir() if p.is_dir()]):
            for f in day.glob("*_parsed_*.csv"):
                tkey = "qa" if "_parsed_qa" in f.name else "ex"
                level = None
                if tkey == "ex":
                    if "_parsed_ex_grad" in f.name:
                        level = "研究生"
                    elif "_parsed_ex_ug" in f.name:
                        level = "本科"
                items.append({
                    "date": day.name,
                    "file": f.name,
                    "path": str(f),
                    "type": tkey,
                    "level": level,
                })
    return items

def load_csv(path: str) -> pd.DataFrame:
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix in [".xlsx", ".xls"]:
        try:
            return pd.read_excel(p, sheet_name=0, dtype=str)
        except Exception:
            return pd.DataFrame()
    if suffix == ".csv":
        # Try UTF-8 first, then fallback to GB18030
        try:
            return pd.read_csv(p, encoding="utf-8")
        except UnicodeDecodeError:
            try:
                return pd.read_csv(p, encoding="gb18030")
            except Exception:
                return pd.DataFrame()
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()

def delete_path(path: str) -> bool:
    p = Path(path)
    try:
        if p.exists():
            p.unlink()
            return True
        return False
    except Exception:
        return False

def get_colleges(include_admin: bool = False):
    mapping = load_college_mapping()
    codes = list(mapping.keys())
    if not include_admin:
        codes = [c for c in codes if c != "admin"]
    return sorted(codes)

def get_targets(college: str) -> dict:
    if TARGETS_PATH.exists():
        with open(TARGETS_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}
    tgt = data.get(college, {"qa": 0, "ex": 0, "types": {}, "levels": {"ug": {"ex": 0}, "grad": {"ex": 0}}})
    # 兼容旧结构：若 levels 缺失，则从 ex 衍生
    levels = tgt.get("levels") or {"ug": {"ex": int(tgt.get("ex", 0))}, "grad": {"ex": 0}}
    tgt["levels"] = {
        "ug": {"ex": int(levels.get("ug", {}).get("ex", 0))},
        "grad": {"ex": int(levels.get("grad", {}).get("ex", 0))},
    }
    if "types" not in tgt:
        tgt["types"] = {}
    return tgt

def save_targets(college: str, qa: int, ex_ug: int, ex_grad: int, types: dict | None = None) -> None:
    if TARGETS_PATH.exists():
        with open(TARGETS_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}
    entry = {
        "qa": int(qa),
        "ex": int(ex_ug) + int(ex_grad),
        "types": types or data.get(college, {}).get("types", {}),
        "levels": {"ug": {"ex": int(ex_ug)}, "grad": {"ex": int(ex_grad)}},
    }
    data[college] = entry
    TARGETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(TARGETS_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True)

def log_login(username: str, college: str) -> None:
    d = BASE_LOGINS / college
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{_today()}.log"
    try:
        with open(p, "a", encoding="utf-8") as f:
            f.write(f"{dt.datetime.now().isoformat()}\t{username}\n")
    except Exception:
        pass

def list_logins(college: str):
    d = BASE_LOGINS / college
    items = []
    if not d.exists():
        return items
    for f in sorted([p for p in d.iterdir() if p.is_file()]):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                lines = [ln.strip() for ln in fh.readlines()]
        except Exception:
            lines = []
        items.append({"date": f.stem, "events": lines})
    return items

def load_college_mapping() -> dict:
    p = Path("config/users.yaml")
    mapping = {}
    if p.exists():
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            users = data.get("credentials", {}).get("usernames", {})
            for uname, info in users.items():
                code = info.get("college_code")
                if not code and uname.startswith("user_"):
                    code = uname.split("_", 1)[1]
                if code:
                    mapping[code] = info.get("name", code)
        except Exception:
            pass
    return mapping

def get_college_display(code: str) -> str:
    m = load_college_mapping()
    return m.get(code, code)
