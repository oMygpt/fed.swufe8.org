import unittest
from io import BytesIO
from pathlib import Path
import os

from modules.storage import archive_raw_file, save_parsed_dataset
import pandas as pd


class TestStorage(unittest.TestCase):
    def test_archive_and_save(self):
        buf = BytesIO(b"question,answer\nq1,a1\n")
        buf.name = "qa.csv"
        raw_path = archive_raw_file(buf, "economy")
        self.assertTrue(raw_path.exists())
        df = pd.DataFrame({"question": ["q1"], "answer": ["a1"]})
        meta = {"filename": buf.name}
        parsed_path = save_parsed_dataset(df, meta, "economy")
        self.assertTrue(parsed_path.exists())
        # cleanup
        try:
            os.remove(parsed_path)
            os.remove(raw_path)
            day_dir = raw_path.parent
            if day_dir.exists():
                for f in day_dir.iterdir():
                    try:
                        os.remove(f)
                    except Exception:
                        pass
                os.rmdir(day_dir)
        except Exception:
            pass


if __name__ == "__main__":
    unittest.main()

