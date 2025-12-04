import unittest
from io import BytesIO
import pandas as pd

from modules.parsing import parse_uploaded_file


class TestParsing(unittest.TestCase):
    def test_parse_qa_csv(self):
        content = b"question,answer\nq1,a1\nq2,a2\n"
        buf = BytesIO(content)
        buf.name = "qa.csv"
        meta, df, warnings = parse_uploaded_file(buf, "问答对")
        self.assertEqual(meta["type"], "问答对")
        self.assertEqual(meta["total"], 2)
        self.assertListEqual(meta["columns"], ["question", "answer"])
        self.assertEqual(list(df[["question","answer"]].values.flatten()), ["q1","a1","q2","a2"])
        self.assertEqual(len(warnings), 0)

    def test_parse_exercises_csv(self):
        content = (
            "type,stem,options,answer,knowledge,analysis\n"
            "选择,题干示例,\"A: 选项A\\nB: 选项B\",A,知识点,解析\n"
        ).encode("utf-8")
        buf = BytesIO(content)
        buf.name = "ex.csv"
        meta, df, warnings = parse_uploaded_file(buf, "习题库")
        self.assertEqual(meta["type"], "习题库")
        self.assertEqual(meta["total"], 1)
        self.assertListEqual(
            meta["columns"],
            ["type", "stem", "options", "answer", "knowledge", "analysis"],
        )
        self.assertEqual(len(warnings), 0)

    def test_exercises_question_options_mapping(self):
        content = (
            "question,options,answer,knowledge_points,source_file\n"
            "题干示例,\"A: 选项A\\nB: 选项B\",A,知识点,src.docx\n"
        ).encode("utf-8")
        buf = BytesIO(content)
        buf.name = "ex_qopts.csv"
        meta, df, warnings = parse_uploaded_file(buf, None)
        self.assertEqual(meta["type"], "习题库")
        self.assertIn("stem", meta["columns"])
        self.assertIn("knowledge", meta["columns"])
        self.assertTrue((df["type"] == "选择").all())

    def test_detect_judgement(self):
        content = "stem,answer\n判断描述,True\n判断描述,False\n".encode("utf-8")
        buf = BytesIO(content)
        buf.name = "judge.csv"
        meta, df, warnings = parse_uploaded_file(buf, "习题库", None)
        self.assertEqual(meta["exercise_type"], "判断题")
        self.assertTrue((df["type"] == "判断题").all())

    def test_detect_fill_blank(self):
        content = "stem,answer\n填空描述,北京\n填空描述,上海\n".encode("utf-8")
        buf = BytesIO(content)
        buf.name = "blank.csv"
        meta, df, warnings = parse_uploaded_file(buf, "习题库", None)
        self.assertIn(meta["exercise_type"], ["填空题", "简答题"])  # 视长度自动判断

    def test_override_type(self):
        content = "stem,answer\n论述描述,这是答案\n".encode("utf-8")
        buf = BytesIO(content)
        buf.name = "essay.csv"
        meta, df, warnings = parse_uploaded_file(buf, "习题库", "论述题")
        self.assertEqual(meta["exercise_type"], "论述题")
        self.assertTrue((df["type"] == "论述题").all())

    def test_level_selection(self):
        content = "stem,answer\n题干,答案\n".encode("utf-8")
        buf = BytesIO(content)
        buf.name = "ex_level.csv"
        meta, df, warnings = parse_uploaded_file(buf, "习题库", None, "研究生")
        self.assertEqual(meta.get("level"), "研究生")

    def test_parse_qa_missing_column(self):
        content = b"question\nq1\nq2\n"
        buf = BytesIO(content)
        buf.name = "qa_missing.csv"
        meta, df, warnings = parse_uploaded_file(buf, "问答对")
        self.assertEqual(meta["type"], "问答对")
        # 仅有 question 列，应有缺少 answer 的警告（统一文案）
        self.assertTrue(any("缺少必填列" in w for w in warnings))
        # 缺少 answer 时，归一化后 answer 列为空，total 至少为 0 或仅保留非空 question
        self.assertIn("question", meta["columns"]) if meta["columns"] else None

    def test_parse_exercises_missing_required(self):
        content = "stem,answer\n題干,Ａ\n".encode("utf-8")
        buf = BytesIO(content)
        buf.name = "ex_missing.csv"
        meta, df, warnings = parse_uploaded_file(buf, "习题库")
        self.assertEqual(meta["type"], "习题库")
        self.assertTrue(any("缺少必填列：type" in w for w in warnings))

    def test_parse_csv_garbled_fallback(self):
        # 使用 gb18030 编码，触发 UTF-8 失败并回退
        text = "question,answer\n你好,世界\n".encode("gb18030")
        buf = BytesIO(text)
        buf.name = "qa_garbled.csv"
        meta, df, warnings = parse_uploaded_file(buf, "问答对")
        self.assertEqual(meta["type"], "问答对")
        self.assertEqual(meta["total"], 1)
        self.assertEqual(df.iloc[0]["question"], "你好")
        self.assertEqual(df.iloc[0]["answer"], "世界")

    def test_mixed_excel_sheets_auto_type(self):
        # 创建混合 Excel：一个问答 sheet，一个选择题 sheet
        xbuf = BytesIO()
        with pd.ExcelWriter(xbuf, engine="openpyxl") as writer:
            pd.DataFrame({"question": ["q"], "answer": ["a"]}).to_excel(writer, index=False, sheet_name="问答")
            pd.DataFrame({"type": ["选择"], "stem": ["题干"], "answer": ["A"]}).to_excel(writer, index=False, sheet_name="选择题")
        xbuf.seek(0)
        xbuf.name = "mixed.xlsx"
        # 不指定 upload_type，使用自动识别
        meta, df, warnings = parse_uploaded_file(xbuf, None)
        self.assertEqual(meta["type"], "问答对")
        self.assertEqual(meta["total"], 1)
        # 应存在对非 QA sheet 的警告（缺少必填列）
        self.assertTrue(any("选择题" in w for w in warnings))


if __name__ == "__main__":
    unittest.main()
