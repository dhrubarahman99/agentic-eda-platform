# Validates and parses uploaded CSV files; raises ValueError with a clear message on any issue.

import io
import chardet
import pandas as pd

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024   # 10 MB
MAX_ROWS = 100_000
ALLOWED_EXTENSIONS = {".csv"}
ALLOWED_CONTENT_TYPES = {
    "text/csv",
    "application/csv",
    "application/vnd.ms-excel",
    "text/plain",
    "application/octet-stream",   # some browsers send this for CSV
}

def validate_and_parse(
    filename: str,
    content_type: str,
    raw_bytes: bytes,
) -> pd.DataFrame:
    """
    Validate a raw file upload and return a parsed DataFrame.

    Parameters
    ----------
    filename     : original filename from the upload
    content_type : MIME type reported by the browser
    raw_bytes    : raw file bytes

    Returns
    -------
    pd.DataFrame — parsed, with no index reset needed

    Raises
    ------
    ValueError with a plain-language message on any validation failure.
    """

    # 1. Extension check
    ext = _get_extension(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Only CSV files are supported. "
            f"The file you uploaded has extension '{ext}'."
        )

    # 2. File size check
    size = len(raw_bytes)
    if size == 0:
        raise ValueError("The uploaded file is empty. Please upload a CSV with data.")
    if size > MAX_FILE_SIZE_BYTES:
        mb = size / (1024 * 1024)
        raise ValueError(
            f"File is too large ({mb:.1f} MB). "
            f"Maximum allowed size is 10 MB."
        )

    # 3. Encoding detection
    encoding = _detect_encoding(raw_bytes)

    # 4. Parse CSV
    try:
        df = pd.read_csv(
            io.BytesIO(raw_bytes),
            encoding=encoding,
            low_memory=False,
            on_bad_lines="skip",   # skip malformed rows rather than crash
        )
    except Exception as exc:
        raise ValueError(
            f"Could not read the CSV file. "
            f"Please ensure it is a valid, comma-separated file. "
            f"Technical detail: {exc}"
        )

    # 5. Shape validation
    if df.shape[0] == 0:
        raise ValueError(
            "The file has no data rows. "
            "Please upload a CSV that contains at least one data row."
        )
    if df.shape[1] < 2:
        raise ValueError(
            "The file has only one column. "
            "Please upload a CSV with at least two columns."
        )

    # 6. Row limit
    if df.shape[0] > MAX_ROWS:
        raise ValueError(
            f"The file has {df.shape[0]:,} rows, which exceeds the "
            f"limit of {MAX_ROWS:,} rows. "
            f"Please upload a smaller dataset."
        )

    # 7. Clean column names — strip whitespace
    df.columns = [str(c).strip() for c in df.columns]

    # 8. Drop columns that are entirely unnamed (e.g. trailing commas)
    df = df.loc[:, ~df.columns.str.match(r"^Unnamed")]

    return df.reset_index(drop=True)

# Helpers

def _get_extension(filename: str) -> str:
    """Return the lowercase file extension including the dot."""
    if "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[-1].lower()

def _detect_encoding(raw_bytes: bytes) -> str:
    """
    Detect character encoding. Falls back to utf-8 if detection fails
    or returns low confidence.
    """
    try:
        result = chardet.detect(raw_bytes[:10_000])   # sample first 10 KB
        encoding = result.get("encoding") or "utf-8"
        confidence = result.get("confidence") or 0.0
        if confidence < 0.5:
            encoding = "utf-8"
        return encoding
    except Exception:
        return "utf-8"
