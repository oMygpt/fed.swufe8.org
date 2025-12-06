import pytest
import pandas as pd
from modules.parsing import _match_columns, _normalize_exercises, _clean_answer_string, _detect_type_from_sheet_name

# Test 1: Semantic Mapping
def test_semantic_mapping():
    df = pd.DataFrame(columns=["序号", "题目", "正确答案", "相关知识点", "出题人"])
    mapping = _match_columns(df)
    assert mapping.get("stem") == "题目"
    assert mapping.get("answer") == "正确答案"
    assert mapping.get("knowledge") == "相关知识点"

def test_semantic_mapping_variations():
    df = pd.DataFrame(columns=["Question", "Answer", "Explanation"])
    mapping = _match_columns(df)
    assert mapping.get("stem").lower() == "question"
    assert mapping.get("answer").lower() == "answer"
    assert mapping.get("analysis").lower() == "explanation"

# Test 2: Sheet Name Type Detection
def test_sheet_type_detection():
    assert _detect_type_from_sheet_name("计算题") == "简答题" # Mapped to Short Answer
    assert _detect_type_from_sheet_name("单选题") == "选择题"
    assert _detect_type_from_sheet_name("多选题") == "选择题"
    assert _detect_type_from_sheet_name("判断题 (True/False)") == "判断题"
    assert _detect_type_from_sheet_name("Random") is None

# Test 3: Normalization & Fallback
def test_normalize_exercises_fallback():
    # Mock DF without type column
    df = pd.DataFrame({
        "题目": ["What is 1+1?", "Is earth flat?"],
        "正确答案": ["2", "False"]
    })
    # Process as "简答题"
    result, warnings = _normalize_exercises(df, default_type_from_sheet="简答题")
    assert not result.empty
    assert "type" in result.columns
    assert result["type"].iloc[0] == "简答题"
    assert result["stem"].iloc[0] == "What is 1+1?"

# Test 4: Answer Cleaning
def test_answer_cleaning():
    # Note: _clean_answer_string might need to be exposed or we test via _normalize_exercises
    # We will assume we implement a helper we can test, or test via integration
    
    # Case A: Choice "A: Blah" -> "A"
    raw_ans = "A: Option A description"
    assert _clean_answer_string(raw_ans, "选择题") == "A"
    
    # Case B: Choice "A" -> "A"
    assert _clean_answer_string("A", "选择题") == "A"
    
    # Case C: Non-Choice (keep as is)
    assert _clean_answer_string("It is 5.", "简答题") == "It is 5."
    
    # Case D: Choice "A. Option" -> "A"
    assert _clean_answer_string("A. Option A", "选择题") == "A"
