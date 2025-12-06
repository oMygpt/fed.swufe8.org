import re
import pandas as pd


def _flag(level: str, code: str, msg: str) -> str:
    return f"{level}:{code}:{msg}"


def assess_qa(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    scores = []
    flags = []
    for _, row in df.iterrows():
        s = 100
        f = []
        q = str(row.get("question", "") or "").strip()
        a = str(row.get("answer", "") or "").strip()
        if not q:
            s -= 50
            f.append(_flag("Error", "Q_EMPTY", "问题为空"))
        if not a:
            s -= 50
            f.append(_flag("Error", "A_EMPTY", "答案为空"))
        if len(q) < 3:
            s -= 15
            f.append(_flag("Warn", "Q_SHORT", "问题过短"))
        if len(a) < 1:
            s -= 15
            f.append(_flag("Warn", "A_SHORT", "答案过短"))
        if q and a and q == a:
            s -= 20
            f.append(_flag("Warn", "Q_EQ_A", "问题与答案相同"))
        # Garbled check disabled (User Req: Math symbols false positive)
        # if _is_garbled(q):
        #     s -= 20
        #     f.append(_flag("Error", "Q_GARBLED", "问题疑似乱码"))
        # if _is_garbled(a):
        #     s -= 20
        #     f.append(_flag("Error", "A_GARBLED", "答案疑似乱码"))
        scores.append(max(0, s))
        flags.append("|".join(f))
    df["quality_score"] = scores
    df["quality_flags"] = flags
    return df


def _parse_options_text(text: str) -> set:
    opts = set()
    s = str(text or "")
    
    # We look for: (Start of string OR Whitespace) + Letter + Separator
    # Note: We need to be careful not to match random words. Usually Option keys are uppercase A-Z.
    # Comprehensive Regex for Option Keys:
    # 1. Boundary: Start or Non-Alphanumeric (avoids matching inside words)
    # 2. Optional Prefix: ( [ （
    # Comprehensive Regex for Option Keys with Negative Lookbehind-ish Logic
    # 1. Boundary: Start OR Any char that is NOT Alphanumeric, Underscore, Slash, or Hyphen.
    #    (This excludes P/E, R_f, Pre-E, TextB, etc.)
    # 2. Main Body:
    #    a. Upper ([A-G]) followed by (Explicit Separator OR Space)
    #    b. Lower ([a-g]) followed by (Explicit Separator ONLY)
    
    regex = r"(?:^|[^a-zA-Z0-9_\-/])(?:([A-G])(?:\s*[\.\:：、\)\）\]\．]|\s+)|([a-g])\s*(?:[\.\:：、\)\）\]\．]))"
    
    matches = re.finditer(regex, s)
    for m in matches:
        # Group 1 is Upper, Group 2 is Lower
        key = m.group(1) or m.group(2)
        if key:
            opts.add(key.upper())
            
    return opts
        
    return opts
        
    return opts

def _normalize_type(t: str) -> str:
    s = str(t or "").strip()
    u = s.upper()
    if any(k in u for k in ["选择", "单选", "多选"]):
        return "选择题"
    if any(k in u for k in ["判断", "TRUE/FALSE", "TF"]):
        return "判断题"
    if "填空" in u:
        return "填空题"
    if "论述" in u:
        return "论述题"
    if "案例" in u:
        return "案例分析题"
    if any(k in u for k in ["简答", "计算", "名词"]):
        return "简答题"
    return s


def assess_exercises(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    scores = []
    flags = []
    for _, row in df.iterrows():
        s = 100
        f = []
        t = _normalize_type(row.get("type", ""))
        stem = str(row.get("stem", "") or "").strip()
        ans = str(row.get("answer", "") or "").strip()
        opts_text = row.get("options", None)
        if not stem:
            s -= 50
            f.append(_flag("Error", "STEM_EMPTY", "题干为空"))
        if not ans:
            s -= 50
            f.append(_flag("Error", "ANS_EMPTY", "答案为空"))
        # Garbled check disabled
        # if _is_garbled(stem):
        #     s -= 20
        #     f.append(_flag("Error", "STEM_GARBLED", "题干疑似乱码"))
        # if _is_garbled(ans):
        #     s -= 20
        #     f.append(_flag("Error", "ANS_GARBLED", "答案疑似乱码"))
        if t == "选择题":
            opts = _parse_options_text(opts_text)
            if not opts:
                s -= 40
                f.append(_flag("Error", "OPT_EMPTY", "选项缺失"))
            else:
                pass
                # if _is_garbled(str(opts_text)):
                #     s -= 20
                #     f.append(_flag("Error", "OPT_GARBLED", "选项疑似乱码"))
            if ans:
                ans_u = ans.upper()
                # Check exact match OR overlap (for multi-select like "ABC")
                # Remove non-alpha chars from answer for checking
                ans_clean = re.sub(r"[^A-Z]", "", ans_u)
                if not ans_clean:
                     pass # handled by empty check
                else:
                    # If all letters in answer are in parsed options, it's valid
                    if not set(ans_clean).issubset(opts):
                         s -= 30
                         f.append(_flag("Error", "ANS_NOT_IN_OPTS", "答案不在选项中"))
        elif t == "判断题":
            valid = {"TRUE", "FALSE", "T", "F", "是", "否", "对", "错", "正确", "错误", "√", "×"}
            if ans.upper() not in valid:
                s -= 30
                f.append(_flag("Error", "ANS_INVALID", "判断题答案不合法"))
        elif t == "填空题":
            if len(ans) < 1:
                s -= 20
                f.append(_flag("Error", "ANS_SHORT", "填空题答案过短"))
        else:
            # 简答/论述/案例
            analysis = str(row.get("analysis", "") or "")
            if analysis and analysis.strip() and analysis.strip() == ans:
                s -= 10
                f.append(_flag("Info", "AN_EQ_ANS", "解析与答案相同"))
        knowledge = str(row.get("knowledge", "") or "").strip()
        if not knowledge:
            s -= 20
            f.append(_flag("Error", "KN_EMPTY", "知识点缺失"))
        # elif _is_garbled(knowledge):
        #     s -= 10
        #     f.append(_flag("Error", "KN_GARBLED", "知识点疑似乱码"))
        scores.append(max(0, s))
        flags.append("|".join(f))
    df["quality_score"] = scores
    df["quality_flags"] = flags
    return df


def summarize_quality(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {"score_avg": 0, "error_count": 0, "warn_count": 0, "error_row_ratio": 0.0, "errors": {}, "warns": {}}
    avg = float(df["quality_score"].mean()) if "quality_score" in df.columns else 0.0
    flags = df.get("quality_flags", pd.Series([""]*len(df))).astype(str)
    error_row_mask = flags.apply(lambda x: any(p.startswith("Error:") for p in x.split("|") if p))
    error_count = int(error_row_mask.sum())
    warn_count = int(flags.apply(lambda x: any(p.startswith("Warn:") for p in x.split("|") if p)).sum())
    error_ratio = float(error_count) / max(1, len(df))
    # breakdown
    err_map = {}
    warn_map = {}
    for line in flags.tolist():
        for frag in line.split("|"):
            if not frag:
                continue
            parts = frag.split(":", 2)
            if len(parts) < 3:
                continue
            level, code = parts[0], parts[1]
            if level == "Error":
                err_map[code] = err_map.get(code, 0) + 1
            elif level == "Warn":
                warn_map[code] = warn_map.get(code, 0) + 1
    return {
        "score_avg": round(avg, 2),
        "error_count": error_count,
        "warn_count": warn_count,
        "error_row_ratio": round(error_ratio, 4),
        "errors": err_map,
        "warns": warn_map,
    }
def _is_garbled(text: str) -> bool:
    if not text:
        return False
    # Remove valid characters
    # Includes: Word chars, Chinese, Whitespace, Common Punctuation (En/Cn), Math/Latex symbols, Brackets
    s = str(text)
    # Added: $%+=<>|{}^~@#&` and 【】《》“”‘’ and \ (backslash)
    garbage = re.sub(r"[\w\u4e00-\u9fa5\s.,;，。；？！:：\-\(\)\[\]/\\$%+=<>|{}^~@#&`【】《》“”‘’'\"“”]", "", s)
    ratio = len(garbage) / max(1, len(s))
    return ratio > 0.3
