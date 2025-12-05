import pandas as pd
from io import BytesIO, StringIO
from typing import Tuple, List, Dict
from modules.quality import assess_qa, assess_exercises, summarize_quality, _parse_options_text, _normalize_type

KEYWORDS_SHEET = ["选择", "填空", "问答", "判断", "简答", "案例"]


def _read_file(uploaded_file):
    name = uploaded_file.name.lower()
    if name.endswith((".xlsx", ".xls")):
        xls = pd.read_excel(uploaded_file, sheet_name=None, dtype=str)
        return xls
    elif name.endswith(".csv"):
        # 尝试 UTF-8，失败则回退 GB18030
        try:
            data = uploaded_file.getvalue() if hasattr(uploaded_file, "getvalue") else uploaded_file.read()
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                text = data.decode("gb18030")
            df = pd.read_csv(StringIO(text))
            return {"CSV": df}
        except Exception as e:
            raise e
    else:
        raise ValueError("不支持的文件类型")


def _detect_type_from_sheet_names(sheets: Dict[str, pd.DataFrame]) -> str:
    for s in sheets.keys():
        for kw in KEYWORDS_SHEET:
            if kw in s:
                # 简单规则：含“问答”→QA，否则为习题库
                if "问答" in s:
                    return "问答对"
                return "习题库"
    # 默认：依赖列名判断
    for df in sheets.values():
        cols = set([c.strip() for c in df.columns.astype(str)])
        cols_lower = {c.lower() for c in cols}
        # 若存在选项相关列，优先判定为习题库
        option_cols = {"options", "选项", "a", "b", "c", "d", "e", "选项a", "选项b", "选项c", "选项d"}
        if cols_lower & option_cols:
            return "习题库"
        if "题型" in cols or "type" in cols:
            return "习题库"
        if {"question", "answer"}.issubset(cols_lower):
            return "问答对"
    return "习题库"

def _detect_exercise_subtype(sheet_names: List[str], df: pd.DataFrame) -> str:
    names = " ".join(sheet_names)
    if any(k in names for k in ["选择"]):
        return "选择题"
    if any(k in names for k in ["填空"]):
        return "填空题"
    if any(k in names for k in ["判断"]):
        return "判断题"
    if any(k in names for k in ["简答"]):
        return "简答题"
    if any(k in names for k in ["论述"]):
        return "论述题"
    if any(k in names for k in ["案例"]):
        return "案例分析题"
    cols_lower = {c.lower() for c in df.columns}
    if "options" in cols_lower or "选项" in cols_lower:
        colname = "options" if "options" in df.columns else ("选项" if "选项" in df.columns else None)
        if colname is not None:
            series = df[colname]
            series = series.fillna("").astype(str).str.strip()
            if series.str.len().gt(0).any():
                return "选择题"
    ans = df.get("answer") if "answer" in df.columns else (df.get("答案") if "答案" in df.columns else None)
    if ans is not None:
        vals = set(str(x).strip().lower() for x in ans.dropna().tolist())
        judge_set = {"true", "false", "t", "f", "是", "否", "对", "错"}
        if vals and vals.issubset(judge_set):
            return "判断题"
        if all(len(str(x)) <= 12 for x in ans.dropna().tolist()):
            return "填空题"
        return "简答题"
    return "简答题"

def _detect_exercise_level(sheet_names: List[str], df: pd.DataFrame) -> str:
    names = " ".join(sheet_names)
    grad_keys = ["研究生", "硕士", "graduate", "postgraduate"]
    ug_keys = ["本科", "undergraduate"]
    if any(k in names for k in grad_keys):
        return "研究生"
    if any(k in names for k in ug_keys):
        return "本科"
    return "本科"


def _normalize_qa(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    warnings = []
    aliases_q = ["question", "问题", "问", "Q"]
    aliases_a = ["answer", "答案", "答", "A"]
    cols_lower = {c.lower(): c for c in df.columns}
    q_col = next((cols_lower.get(a.lower()) for a in aliases_q if a.lower() in cols_lower), None)
    a_col = next((cols_lower.get(a.lower()) for a in aliases_a if a.lower() in cols_lower), None)
    if not q_col or not a_col:
        warnings.append("缺少必填列：question/answer")
        return pd.DataFrame(), warnings
    out = pd.DataFrame({
        "question": df[q_col],
        "answer": df[a_col],
    })
    # 删除缺失任一必填列的行
    out = out.dropna(subset=["question", "answer"], how="any")
    return out, warnings


def _normalize_exercises(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    warnings = []
    def pick(*names):
        for n in names:
            if n in df.columns:
                return df[n]
        return pd.Series(dtype=str)
    # 处理分散选项列合并为标准 options
    option_candidates = [c for c in df.columns if c.strip().lower() in ["a", "b", "c", "d", "e"] or c.startswith("选项")]
    options_col = None
    if option_candidates and "options" not in df.columns and "选项" not in df.columns:
        def join_options(row):
            parts = []
            for c in option_candidates:
                val = str(row.get(c, "")).strip()
                if val:
                    label = c.strip().upper()
                    if label.startswith("选项") and len(label) > 2:
                        label = label[-1]
                    parts.append(f"{label}: {val}")
            return "\n".join(parts)
        options_col = df.apply(join_options, axis=1)

    out = pd.DataFrame({
        "type": pick("type", "题型"),
        "stem": pick("stem", "题干", "问题描述", "question", "问题"),
        "options": pick("options", "选项") if options_col is None else options_col,
        "answer": pick("answer", "答案"),
        "knowledge": pick("knowledge", "知识点", "knowledge_points"),
        "analysis": pick("analysis", "解析"),
    })
    required = ["stem", "answer"]
    for c in required:
        if c not in df.columns:
            warnings.append(f"缺少必填列：{c}")
        elif out[c].empty or (out[c].astype(str).str.len() == 0).all():
            warnings.append(f"缺少必填列：{c}")
    # 若缺失 type 但存在选项列，默认设置为 选择
    if ("type" not in df.columns or out["type"].astype(str).str.len().eq(0).all()) and (options_col is not None or "options" in df.columns or "选项" in df.columns):
        out["type"] = "选择"
    out = out.dropna(how="all")
    return out, warnings


def parse_uploaded_file(uploaded_file, upload_type: str, exercise_type: str | None = None, exercise_level: str | None = None):
    sheets = _read_file(uploaded_file)
    auto_type = _detect_type_from_sheet_names(sheets)
    final_type = upload_type or auto_type

    normalized_frames = []
    warnings_all: List[str] = []
    sheet_names = []
    had_type_col = False
    for name, df in sheets.items():
        sheet_names.append(name)
        if final_type == "问答对":
            nf, w = _normalize_qa(df)
        else:
            nf, w = _normalize_exercises(df)
        if "type" in df.columns:
            had_type_col = True
        warnings_all.extend([f"[{name}] {x}" for x in w])
        if not nf.empty:
            normalized_frames.append(nf)
    if normalized_frames:
        result = pd.concat(normalized_frames, ignore_index=True)
    else:
        result = pd.DataFrame()

    columns = list(result.columns) if not result.empty else []
    exercise_subtype = None
    mixed_types = None
    level = None
    detected_level = None
    if final_type == "习题库":
        exercise_subtype = exercise_type or _detect_exercise_subtype(sheet_names, result) if not result.empty else (exercise_type or "选择题")
        if exercise_type is not None:
            result["type"] = exercise_type
        elif "type" not in result.columns or result["type"].fillna("").astype(str).str.strip().str.len().eq(0).all():
            result["type"] = exercise_subtype
        # 级别识别
        # 若调用方指定了级别（如“研究生习题库”），则不进行自动识别，直接使用指定级别
        if exercise_level:
            detected_level = None
            level = exercise_level
        else:
            detected_level = _detect_exercise_level(sheet_names, result)
            level = detected_level or "本科"
        # 检测混合题型：当原始文件未提供题型列或类型疑似不可靠时，基于行级特征推断
        mixed_types = None
        if not result.empty:
            def infer_row_type(row):
                t = _normalize_type(row.get("type", ""))
                # 若原始文件没有题型列，则忽略自动填充，改用特征推断
                if not had_type_col or not t:
                    opts = _parse_options_text(row.get("options"))
                    ans = str(row.get("answer", "")).strip()
                    judge = {"true", "false", "t", "f", "是", "否", "对", "错"}
                    if opts:
                        return "选择题"
                    if ans and ans.strip().lower() in judge:
                        return "判断题"
                    if len(ans) <= 12:
                        return "填空题"
                    return "简答题"
                return t
            inferred = result.apply(infer_row_type, axis=1)
            counts = inferred.value_counts().to_dict()
            if len(counts) > 1:
                mixed_types = counts
                warnings_all.append("检测到混合题型：" + ", ".join([f"{k}{v}条" for k, v in counts.items()]))
            
            # 若原始文件未提供题型列，且用户选择了自动识别，则应用推断的混合题型
            if not had_type_col and exercise_type is None:
                result["type"] = inferred
    # 类型选择一致性提示
    if upload_type and auto_type and upload_type != auto_type:
        warnings_all.append(f"类型选择与系统识别不一致：你选择了{upload_type}，系统识别为{auto_type}")
    # 质量检测（仅用于页面展示，不写入 CSV）
    quality_summary = None
    if not result.empty:
        assessed = assess_qa(result) if final_type == "问答对" else assess_exercises(result)
        quality_summary = summarize_quality(assessed)
    meta = {
        "filename": uploaded_file.name,
        "sheets": sheet_names,
        "columns": columns,
        "total": len(result),
        "type": final_type,
        "detected_type": auto_type,
        "exercise_type": exercise_subtype,
        "level": level,
        "detected_level": detected_level,
        "quality_summary": quality_summary,
        "mixed_types": mixed_types,
    }
    return meta, result, warnings_all
