import unittest
import pandas as pd
from modules.quality import assess_qa, assess_exercises, summarize_quality


class TestQuality(unittest.TestCase):
    def test_assess_qa(self):
        df = pd.DataFrame({"question": ["q1", ""], "answer": ["a1", ""]})
        out = assess_qa(df)
        self.assertIn("quality_score", out.columns)
        self.assertIn("quality_flags", out.columns)
        summary = summarize_quality(out)
        self.assertGreaterEqual(summary["error_count"], 1)

    def test_assess_exercises_choice(self):
        df = pd.DataFrame({
            "type": ["选择题"],
            "stem": ["题干"],
            "options": ["A: 选项A\nB: 选项B"],
            "answer": ["C"],
        })
        out = assess_exercises(df)
        flags = out["quality_flags"].iloc[0]
        self.assertIn("ANS_NOT_IN_OPTS", flags)


if __name__ == "__main__":
    unittest.main()

