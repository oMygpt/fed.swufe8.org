import unittest
from io import BytesIO
import os
from pathlib import Path

import pandas as pd
from modules.storage import archive_raw_file, save_parsed_dataset, merge_all_parsed


class TestAdminTestUploadIsolation(unittest.TestCase):
    def test_admin_test_separation(self):
        merged_before = merge_all_parsed()
        rows_before = 0 if merged_before is None else len(merged_before)
        buf = BytesIO(b"question,answer\nq1,a1\n")
        buf.name = "qa.csv"
        raw_test = archive_raw_file(buf, "admin", is_test=True)
        df = pd.DataFrame({"question": ["q1"], "answer": ["a1"]})
        meta = {"filename": buf.name}
        parsed_test = save_parsed_dataset(df, meta, "admin", is_test=True)
        merged_after = merge_all_parsed()
        rows_after = 0 if merged_after is None else len(merged_after)
        self.assertEqual(rows_before, rows_after)
        try:
            os.remove(parsed_test)
            os.remove(raw_test)
            day_dir = raw_test.parent
            for f in day_dir.iterdir():
                try:
                    os.remove(f)
                except Exception:
                    pass
            os.rmdir(day_dir)
            root = Path("storage_tests") / "admin"
            if root.exists():
                for dd in root.iterdir():
                    try:
                        os.rmdir(dd)
                    except Exception:
                        pass
        except Exception:
            pass


if __name__ == "__main__":
    unittest.main()
