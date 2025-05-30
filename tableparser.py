import re
import pandas as pd
from collections import Counter
from io import StringIO

def stitch_multiline_rows(lines):
    stitched = []
    current = ""
    for line in lines:
        if line.strip().startswith('|'):
            if current:
                stitched.append(current)
            current = line.strip()
        else:
            current += ' ' + line.strip()
    if current:
        stitched.append(current)
    return stitched

def parse_markdown_to_csv(markdown_text, min_column_threshold=4):
    # Step 1: Extract candidate table lines
    lines = markdown_text.strip().split('\n')
    pipe_lines = [line for line in lines if '|' in line]
    stitched_lines = stitch_multiline_rows(pipe_lines)

    # Step 2: Clean and split rows
    rows = []
    for line in stitched_lines:
        if set(line).issubset({'|', '-', ' '}):
            continue  # skip divider lines
        segments = [col.strip() for col in line.split('|')[1:-1]]
        if len(segments) >= min_column_threshold:
            rows.append(segments)

    if not rows:
        return pd.DataFrame(), "No valid tables found."

    # Step 3: Find most common column count
    col_counts = [len(row) for row in rows]
    most_common_col_count = Counter(col_counts).most_common(1)[0][0]
    cleaned_rows = [row for row in rows if len(row) == most_common_col_count]

    # Step 4: Check for header (first row non-numeric is a decent guess)
    first_row = cleaned_rows[0]
    if all(not cell.replace('.', '', 1).isdigit() for cell in first_row):
        headers = first_row
        data_rows = cleaned_rows[1:]
    else:
        headers = [f"Column {i+1}" for i in range(most_common_col_count)]
        data_rows = cleaned_rows

    # Step 5: Create DataFrame
    df = pd.DataFrame(data_rows, columns=headers)
    return df, "Successfully parsed."


class TableParser:
    """
    TableParser class wrapper for the existing markdown parsing functions
    """
    
    def __init__(self):
        pass
    
    def markdown_to_csv(self, markdown_content: str) -> str:
        """
        Convert markdown content to CSV string
        
        Args:
            markdown_content: Markdown text containing tables
            
        Returns:
            CSV content as string
        """
        df, message = parse_markdown_to_csv(markdown_content)
        
        if df.empty:
            raise ValueError(f"Failed to parse markdown: {message}")
        
        # Convert DataFrame to CSV string
        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False)
        return csv_buffer.getvalue()


# Example usage:
# with open("example.md") as f:
#     content = f.read()
# df, message = parse_markdown_to_csv(content)
# df.to_csv("output.csv", index=False)
# print(message)
