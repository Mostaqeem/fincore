import re
import uuid
import warnings
import pandas as pd
from django.db import connection

warnings.filterwarnings("ignore", category=UserWarning, module="pandas")


def sanitize_identifier(name):
    """Convert a column name to a safe Postgres identifier."""
    if not name:
        return "_col"
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name.strip())
    sanitized = re.sub(r'_+', '_', sanitized)
    sanitized = sanitized.strip('_')
    if not sanitized:
        return "_col"
    if not sanitized[0].isalpha() and sanitized[0] != '_':
        sanitized = '_' + sanitized
    return sanitized[:63]


def make_unique_names(names):
    """Deduplicate column names by adding numeric suffixes."""
    seen = {}
    unique_names = []
    for name in names:
        sanitized = sanitize_identifier(name)
        if sanitized in seen:
            seen[sanitized] += 1
            unique_names.append(f"{sanitized}_{seen[sanitized]}")
        else:
            seen[sanitized] = 0
            unique_names.append(sanitized)
    return unique_names


# Sample sizes: type inference only needs a representative slice, not the whole
# file. Parsing 1M rows (especially to_datetime on non-date columns) is orders of
# magnitude slower than a sample and is unnecessary for picking BIGINT/TIMESTAMP/TEXT.
INFERENCE_SAMPLE_SIZE = 50000
PREFILTER_SAMPLE_SIZE = 10000


def _sample(series, n=INFERENCE_SAMPLE_SIZE):
    if len(series) <= n:
        return series
    return series.sample(n=n, random_state=42)


def _looks_numeric(series):
    """Cheap pre-filter: is this column plausibly all-numeric?"""
    s = _sample(series, PREFILTER_SAMPLE_SIZE).astype(str).str.strip()
    return s.str.fullmatch(r'-?\d+(\.\d+)?([eE][+-]?\d+)?').mean() > 0.9


def _looks_datetime(series):
    """Cheap pre-filter: does this column plausibly contain dates/times?"""
    s = _sample(series, PREFILTER_SAMPLE_SIZE).astype(str).str.strip()
    # UUIDs (e.g. "92d96c14-52fa-4295-a9db-3575d82d4f67") look date-ish because of
    # dashes but are not dates; exclude them so they don't hit the slow parser.
    is_uuid = s.str.fullmatch(
        r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
        case=False,
    )
    has_digit = s.str.contains(r'\d', regex=True) & ~is_uuid
    has_sep = s.str.contains(
        r'[-/:,]|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec',
        case=False, regex=True,
    )
    return (has_digit & has_sep).mean() > 0.5


def infer_pg_type(series):
    """Infer Postgres data type from a pandas Series."""
    series = series.dropna()
    if len(series) == 0:
        return "TEXT"

    # 1. Numeric. The pre-filter keeps non-numeric text columns (1M-row IDs, names,
    #    etc.) from paying for a full to_numeric() parse attempt.
    if _looks_numeric(series):
        numeric_series = pd.to_numeric(series, errors='coerce')
        if numeric_series.notna().all():
            if pd.api.types.is_integer_dtype(numeric_series):
                return "BIGINT"
            return "NUMERIC"

    # 2. Boolean. Only pay for the full-series check when a sample already looks
    #    boolean-ish, otherwise text columns incur a full 1M-row string pass.
    bool_candidates = {'true', 'false', 'yes', 'no', '1', '0'}
    bool_sample = (
        _sample(series, PREFILTER_SAMPLE_SIZE)
        .astype(str)
        .str.lower()
        .isin(bool_candidates)
    )
    if bool_sample.mean() > 0.8:
        if series.astype(str).str.lower().isin(bool_candidates).all():
            return "BOOLEAN"

    # 3. Timestamp. Only attempt parsing when the column looks date-like; run on a
    #    sample first (full-series to_datetime on non-date columns is very slow) and
    #    validate on the full series only if the sample actually parsed.
    if _looks_datetime(series):
        sample_str = _sample(series, PREFILTER_SAMPLE_SIZE).astype(str).str.strip()
        pure_time = sample_str.str.fullmatch(r'\d{1,2}:\d{2}(:\d{2})?')
        # Bare time-of-day columns (e.g. "11:25:37") must not become TIMESTAMP: Postgres
        # cannot COPY a bare time into a timestamp column.
        if pure_time.mean() <= 0.5:
            try:
                sample_dates = pd.to_datetime(
                    _sample(series), errors='coerce', format='mixed'
                )
                if sample_dates.notna().all():
                    years = sample_dates.dt.year.dropna()
                    if years.between(1900, 2100).all():
                        full_dates = pd.to_datetime(
                            series, errors='coerce', format='mixed'
                        )
                        if full_dates.notna().all():
                            full_years = full_dates.dt.year.dropna()
                            if full_years.between(1900, 2100).all():
                                return "TIMESTAMP"
            except Exception:
                pass

    # 4. Text
    max_len = series.astype(str).str.len().max()
    if max_len <= 255:
        return f"VARCHAR({max_len})"
    return "TEXT"


def read_uploaded_file(file_obj):
    """Read an uploaded CSV or Excel file into a pandas DataFrame."""
    file_obj.seek(0)
    filename = file_obj.name.lower()

    if filename.endswith('.csv'):
        return pd.read_csv(file_obj)
    elif filename.endswith(('.xls', '.xlsx')):
        return pd.read_excel(file_obj)
    else:
        raise ValueError(f"Unsupported file format: {filename}")


def build_schema(df):
    """Build column schema from DataFrame."""
    column_names = make_unique_names(df.columns.tolist())
    df.columns = column_names

    schema = []
    for i, col in enumerate(df.columns):
        pg_type = infer_pg_type(df[col])
        schema.append({
            'column_name': col,
            'data_type': pg_type,
            'ordinal_position': i
        })

    return schema, df


def generate_table_name(section='finance'):
    """Generate a unique table name."""
    suffix = uuid.uuid4().hex[:8]
    return f"ds_{section}_{suffix}"


def create_table_and_insert(table_name, schema, df, task=None):
    """Create a Postgres table and bulk insert data using COPY command."""
    import io

    with connection.cursor() as cursor:
        columns_def = ['id SERIAL PRIMARY KEY']
        for col in schema:
            columns_def.append(f'"{col["column_name"]}" {col["data_type"]}')

        create_sql = f'CREATE TABLE "{table_name}" ({", ".join(columns_def)})'
        cursor.execute(create_sql)

        columns = [col['column_name'] for col in schema]
        copy_sql = (
            f'COPY "{table_name}" ({", ".join([f"\"{c}\"" for c in columns])}) '
            "FROM STDIN WITH (FORMAT CSV, DELIMITER E'\\t', HEADER false)"
        )

        total_rows = len(df)
        block_size = 100000

        # Serialize via C-optimized to_csv (not Python-level iterrows) in bounded
        # chunks so memory stays low and progress can be reported per chunk.
        for start in range(0, total_rows, block_size):
            block = df.iloc[start:start + block_size]
            buffer = io.StringIO()
            block.to_csv(buffer, sep='\t', index=False, header=False, na_rep='')
            buffer.seek(0)
            cursor.copy_expert(copy_sql, buffer)

            if task:
                task.update_state(
                    state='PROGRESS',
                    meta={
                        'current': min(start + block_size, total_rows),
                        'total': total_rows,
                        'phase': 'inserting',
                    }
                )

    return total_rows


def cast_value(value, pg_type):
    """Cast a string value to the appropriate Python type based on Postgres type."""
    if value is None or value == '':
        return None

    pg_type_upper = pg_type.upper()

    if 'BIGINT' in pg_type_upper or 'INT' in pg_type_upper:
        return int(value)
    elif 'NUMERIC' in pg_type_upper or 'DECIMAL' in pg_type_upper or 'REAL' in pg_type_upper or 'FLOAT' in pg_type_upper or 'DOUBLE' in pg_type_upper:
        return float(value)
    elif pg_type_upper == 'BOOLEAN' or 'BOOL' in pg_type_upper:
        val_lower = str(value).lower()
        if val_lower in ('true', 'yes', '1'):
            return True
        elif val_lower in ('false', 'no', '0'):
            return False
        raise ValueError(f"Cannot cast '{value}' to BOOLEAN")
    elif 'TIMESTAMP' in pg_type_upper or 'DATE' in pg_type_upper:
        return pd.to_datetime(value)
    elif 'CHARACTER' in pg_type_upper or 'VARCHAR' in pg_type_upper or 'TEXT' in pg_type_upper:
        return str(value)
    else:
        return str(value)
