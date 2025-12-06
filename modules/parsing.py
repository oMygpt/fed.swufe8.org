import pandas as pd
from io import BytesIO, StringIO
from typing import Tuple, List, Dict, Optional, Any
import re
from modules.quality import assess_qa, assess_exercises, summarize_quality, _parse_options_text, _normalize_type

KEYWORDS_SHEET = ["选择", "填空", "问答", "判断", "简答", "案例", "论述", "习题", "计算", "名词解释"]

# Semantic Mapping Configuration
COLUMN_MAPPINGS = {
    "stem": ["stem", "题干", "问题", "题目", "question", "description", "问题描述", "题面", "题目内容", "正面"],
    "answer": ["answer", "答案", "正确答案", "reference_answer", "ans", "标准答案", "背面"],
    "options": ["options", "选项", "choices", "备选答案", "选项内容"],
    "analysis": ["analysis", "解析", "答案解析", "explanation", "详解", "题目解析", "分析"],
    "knowledge": ["knowledge", "知识点", "point", "考点", "关联知识点", "相关知识点"],
    "type": ["type", "题型", "question_type", "category", "题目类型"],
    "level": ["level", "难度", "difficulty", "grade", "学历", "适用层次"],
    "serial_no": ["serial_no", "序号", "id", "number", "no"]
}

def _match_columns(df: pd.DataFrame) -> Dict[str, str]:
    """
    Map standard semantic fields to actual DataFrame columns.
    Returns a dictionary: { standard_field: actual_column_name }
    """
    matched = {}
    cols = list(df.columns)
    cols_lower = {str(c).strip().lower(): str(c) for c in cols}
    
    # 1. Exact match (case-insensitive) on aliases
    for field, aliases in COLUMN_MAPPINGS.items():
        for alias in aliases:
            if alias.lower() in cols_lower:
                matched[field] = cols_lower[alias.lower()]
                break
    
    # 2. Fuzzy match specifically for stem if not found
    # If "stem" is not found, look for columns containing "题目" or "问题" but not "类型"/"解析"
    if "stem" not in matched:
        for c in cols:
            c_str = str(c).strip()
            # Avoid matching "题目类型", "问题解析" etc.
            if ("题目" in c_str or "问题" in c_str) and ("类型" not in c_str and "解析" not in c_str and "选项" not in c_str):
                 matched["stem"] = c_str
                 break
    
    return matched

def _read_file(uploaded_file) -> Dict[str, pd.DataFrame]:
    name = uploaded_file.name.lower()
    if name.endswith((".xlsx", ".xls")):
        # Read all sheets as string to preserve data fidelity initially
        try:
            xls = pd.read_excel(uploaded_file, sheet_name=None, dtype=str)
            return xls
        except Exception as e:
            raise ValueError(f"Excel read error: {str(e)}")
    elif name.endswith(".csv"):
        try:
            data = uploaded_file.getvalue() if hasattr(uploaded_file, "getvalue") else uploaded_file.read()
            # Try to detect encoding
            encoding = "utf-8"
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                text = data.decode("gb18030", errors="replace")
                encoding = "gb18030"
            
            # Robust CSV reading
            # 1. Try standard read
            try:
                df = pd.read_csv(StringIO(text), dtype=str)
                # Heuristic: if all data is in one column, maybe delimiter issue
                if len(df.columns) == 1 and "," in text:
                     pass
            except:
                 # Fallback
                 df = pd.read_csv(StringIO(text), sep=None, engine='python', dtype=str)
            
            # Trim column names
            df.columns = df.columns.astype(str).str.strip()
            return {"CSV": df}
        except Exception as e:
            raise ValueError(f"CSV read error: {str(e)}")
    else:
        raise ValueError("不支持的文件类型 (仅支持 .xlsx, .xls, .csv)")


def _detect_type_from_sheet_name(sheet_name: str) -> str | None:
    """Detect specific exercise subtype from sheet name."""
    s = sheet_name.strip()
    if any(k in s for k in ["选择", "单选", "多选", "单项", "多项"]): return "选择题"
    if "填空" in s: return "填空题"
    if "判断" in s: return "判断题"
    if "简答" in s: return "简答题"
    if "论述" in s: return "论述题"
    if "案例" in s: return "案例分析题"
    if "计算" in s: return "简答题" # Map Calculation to Short Answer as it's not a standalone standard type
    if "名词" in s: return "简答题" # Map Definition to Short Answer
    if "问答" in s: return "问答对"
    return None

def _detect_exercise_level_from_sheet(sheet_names: List[str]) -> str:
    names = " ".join(sheet_names).lower()
    grad_keys = ["研究生", "硕士", "graduate", "postgraduate", "硕博"]
    ug_keys = ["本科", "undergraduate", "大专"]
    if any(k in names for k in grad_keys):
        return "研究生"
    if any(k in names for k in ug_keys):
        return "本科"
    return "本科"

def _clean_answer_string(val, type_context: str | None = None) -> str:
    """Clean the answer string. Handle 'A: Description' for choice questions."""
    s = str(val).strip()
    if s.lower() == "nan" or s == "": return ""
    
    # 1. Remove generic prefixes like "答案", "Answer:"
    # Use NON-GREEDY match for the prefix part
    s = re.sub(r"^(答案|Answer|Correct Answer)[:：\s\t]*", "", s, flags=re.IGNORECASE).strip()
    
    # 2. Logic for Choice Questions (Selection)
    # If type is Selection, we want to extract just the option letter if standard format
    is_selection = type_context == "选择题"
    
    if is_selection:
        # Patter: Starts with Single Letter (A-F), followed by dot/colon/space?
        # Check if it looks like "A: xxx" or "A. xxx" or "A xxx"
        match = re.match(r"^([A-F])\s*[:\.]\s*(.*)$", s, re.IGNORECASE)
        if match:
             # It matches "A: content". Return just "A" as standard answer for system?
             # OR should we keep it? 
             # PRD Requirement check: Usually answer for choice is just "A".
             # If the user put "A: Description", usually "A" is the key.
             return match.group(1).upper()
        
        # Also check pure letter
        if re.match(r"^[A-F]$", s, re.IGNORECASE):
            return s.upper()

    return s

def _normalize_qa(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    warnings = []
    mapping = _match_columns(df)
    
    q_col = mapping.get("stem") # Re-use stem mapping as question
    if not q_col:
        # Fallback to pure question aliases if stem didn't catch it correctly or for clarity
         if "question" in df.columns.str.lower(): q_col = df.columns[list(df.columns.str.lower()).index("question")]
    
    # Specific QA check
    if not q_col:
        # Check specific Q aliases
        q_aliases = ["question", "问题", "问", "Q"]
        cols_lower = {str(c).lower(): c for c in df.columns}
        for a in q_aliases:
            if a.lower() in cols_lower:
                q_col = cols_lower[a.lower()]
                break
                
    a_col = mapping.get("answer")
    
    if not q_col or not a_col:
        warnings.append(f"缺少必填列：Question/Answer (Found: Q={q_col}, A={a_col})")
        return pd.DataFrame(), warnings

    out = pd.DataFrame({
        "question": df[q_col],
        "answer": df[a_col],
    })
    out = out.dropna(subset=["question", "answer"], how="any")
    return out, warnings

def _normalize_exercises(df: pd.DataFrame, default_type_from_sheet: Optional[str] = None) -> Tuple[pd.DataFrame, List[str]]:
    warnings = []
    mapping = _match_columns(df)
    
    # 1. Handle Options: Separate columns (A, B, C...) vs Single Column
    options_col_source = mapping.get("options")
    final_options_col = None
    
    # If no single options column mapped, look for spreading columns (A, B, C, D...)
    if not options_col_source:
        option_candidates = [c for c in df.columns if str(c).strip().lower() in ["a", "b", "c", "d", "e", "f"] or str(c).strip().startswith("选项")]
        if option_candidates:
            def join_options(row):
                parts = []
                for c in sorted(option_candidates): # sort to keep A,B,C order
                    val = str(row.get(c, "")).strip()
                    if val and val.lower() != "nan":
                        label = str(c).strip()
                        # Clean label "选项A" -> "A"
                        if label.startswith("选项") and len(label) > 2:
                            label = label.replace("选项", "").strip()
                        # If label is just A, B, C.. use it
                        parts.append(f"{label}: {val}")
                return "\n".join(parts)
            final_options_col = df.apply(join_options, axis=1)
    else:
        final_options_col = df[options_col_source]

    # 2. Build Result DataFrame
    out = pd.DataFrame()
    
    # Mapping helper
    def get_col(field):
        return df[mapping[field]] if field in mapping else pd.Series(dtype=str)

    out["type"] = get_col("type")
    # Preserve original serial number if exists
    if "serial_no" in mapping:
        out["serial_no"] = df[mapping["serial_no"]]
        
    out["stem"] = get_col("stem")
    out["options"] = final_options_col if final_options_col is not None else pd.Series(dtype=str)
    out["answer"] = get_col("answer")
    out["knowledge"] = get_col("knowledge")
    out["analysis"] = get_col("analysis")
    out["level"] = get_col("level") 
    
    # 3. Type Filling Strategy (Early)
    # Priority: 1. Row-level type column 2. Sheet-level deduction 3. Row-level inference
    
    # If type column is empty or missing, fill with detected sheet type
    if "type" not in mapping or out["type"].isna().all() or (out["type"].astype(str).str.strip() == "").all():
        if default_type_from_sheet:
            out["type"] = default_type_from_sheet

    # 4. Clean Answer
    if not out["answer"].empty:
        # Use vectorized apply with type context if possible, or straight map if type is uniform
        # Since type might vary per row (rarely if sheet-based), we do row-wise
        def clean_wrapper(row):
            t = str(row.get("type", "")).strip()
            return _clean_answer_string(row.get("answer", ""), type_context=t)
        
        out["answer"] = out.apply(clean_wrapper, axis=1)

    # 5. Mandatory Checks
    required = ["stem", "answer"]
    for c in required:
        if c not in mapping: # Check if source was found
             warnings.append(f"未找到列：{c}")
        elif out[c].isna().all() or (out[c].astype(str).str.strip() == "").all():
             warnings.append(f"列内容为空：{c}")
             
    # Remove empty rows
    # Only drop if stem is empty
    out = out[out["stem"].notna() & (out["stem"].astype(str).str.strip() != "")]
    
    return out, warnings

def parse_uploaded_file(uploaded_file, upload_type: str, exercise_type: str | None = None, exercise_level: str | None = None):
    sheets = _read_file(uploaded_file)
    
    # Global Level Detection (default for file)
    global_detected_level = _detect_exercise_level_from_sheet(list(sheets.keys())) if not exercise_level else exercise_level

    normalized_frames = []
    warnings_all: List[str] = []
    sheet_names = list(sheets.keys())
    
    is_qa_mode = (upload_type == "问答对")
    
    for name, df in sheets.items():
        if df.empty:
            continue
            
        sheet_detected_type = _detect_type_from_sheet_name(name)
        
        # If user explicitly selected "问答对" mode, treat all as QA
        if is_qa_mode:
            nf, w = _normalize_qa(df)
            if not nf.empty:
                normalized_frames.append(nf)
            warnings_all.extend([f"[{name}] {x}" for x in w])
            continue
            
        effective_sheet_type = exercise_type or sheet_detected_type
        
        nf, w = _normalize_exercises(df, default_type_from_sheet=effective_sheet_type)
        if not nf.empty:
            # Apply level if missing
            if "level" not in nf.columns or nf["level"].isna().all():
                nf["level"] = global_detected_level
            
            normalized_frames.append(nf)
        warnings_all.extend([f"[{name}] {x}" for x in w])

    if normalized_frames:
        result = pd.concat(normalized_frames, ignore_index=True)
    else:
        result = pd.DataFrame()

    # Final cleanup and type inference for rows that still lack type
    mixed_types = None
    if not result.empty and is_qa_mode is False:
        
        def infer_row_type(row):
            t = str(row.get("type", "")).strip()
            if t and t.lower() != "nan" and t != "": return _normalize_type(t)
            
            # Content-based inference
            opts = str(row.get("options", "")).strip()
            ans = str(row.get("answer", "")).strip().lower()
            
            if opts and opts.lower() != "nan" and opts != "": return "选择题"
            
            judge_keys = {"true", "false", "t", "f", "是", "否", "对", "错"}
            if ans in judge_keys: return "判断题"
            
            if len(ans) <= 12 and len(ans) > 0: return "填空题"
            return "简答题" 
            
        # Only apply inference where type is missing
        # NOTE: if we filled it from sheet, it is likely filled. 
        # But we run this to normalize the string (e.g. "Selection" -> "选择题")
        result["type"] = result.apply(infer_row_type, axis=1)
        
        # Stats for mixed types
        counts = result["type"].value_counts().to_dict()
        if len(counts) > 1:
            mixed_types = counts
            warnings_all.append("检测到混合题型/Multi-type detected: " + ", ".join([f"{k}:{v}" for k,v in counts.items()]))

    columns = list(result.columns) if not result.empty else []
    
    quality_summary = None
    if not result.empty:
        assessed = assess_qa(result) if is_qa_mode else assess_exercises(result)
        quality_summary = summarize_quality(assessed)
        result = assessed # Update result to include quality columns

    meta = {
        "filename": uploaded_file.name,
        "sheets": sheet_names,
        "columns": columns,
        "total": len(result),
        "type": "问答对" if is_qa_mode else "习题库",
        "detected_type": "问答对" if is_qa_mode else "习题库",
        "exercise_type": exercise_type,
        "level": global_detected_level,
        "detected_level": global_detected_level,
        "quality_summary": quality_summary,
        "mixed_types": mixed_types,
    }
    
    return meta, result, warnings_all

def split_dataset_by_type(df: pd.DataFrame, meta: dict) -> List[Tuple[dict, pd.DataFrame]]:
    """
    Split a parsed DataFrame into multiple DataFrames based on the 'type' column.
    Returns a list of (metadata, dataframe) tuples.
    """
    if df.empty or "type" not in df.columns:
        return [(meta, df)]
    
    unique_types = df["type"].unique()
    if len(unique_types) <= 1:
        return [(meta, df)]
        
    results = []
    base_filename = meta.get("filename", "upload")
    for t in unique_types:
        sub_df = df[df["type"] == t].copy()
        if sub_df.empty:
            continue
            
        # Create new metadata for this slice
        new_meta = meta.copy()
        # Append type to filename for clarity
        name_part = str(t).replace("题", "")
        if name_part not in base_filename:
             new_meta["filename"] = f"{base_filename.rsplit('.', 1)[0]}_{name_part}.csv" # Simplified naming
        else:
             new_meta["filename"] = base_filename
             
        new_meta["type"] = "习题库" # Default content type
        new_meta["detected_type"] = "习题库" 
        new_meta["total"] = len(sub_df)
        
        # Re-assess quality for this slice specifically
        if "quality_score" in sub_df.columns:
             # Just summarize existing scores
             new_meta["quality_summary"] = summarize_quality(sub_df)
        
        results.append((new_meta, sub_df))
        
    return results
