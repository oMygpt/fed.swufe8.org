import pandas as pd
from io import BytesIO
from modules.parsing import parse_uploaded_file

# Create a dummy Excel file with mixed types
df = pd.DataFrame({
    "stem": ["Question 1", "Question 2", "Question 3"],
    "options": ["A. 1\nB. 2", None, "A. Yes\nB. No"],
    "answer": ["A", "Some text answer", "T"]
})

# Mock uploaded file
output = BytesIO()
with pd.ExcelWriter(output) as writer:
    df.to_excel(writer, index=False)
output.seek(0)
output.name = "test.xlsx"

# Parse
meta, result, warnings = parse_uploaded_file(output, "习题库", exercise_type=None)

print("Warnings:", warnings)
print("Result Types:", result["type"].tolist())
print("Mixed Types Meta:", meta.get("mixed_types"))
