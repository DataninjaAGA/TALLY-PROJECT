from pathlib import Path

from src.excel_reader import load_daily_check, parse_daily_check


def test_parse_sample_daily_check():
    # Coloca un archivo de prueba en tests/sample_daily_check.xlsx para ejecutar esta prueba localmente.
    sample = Path(__file__).parent / "sample_daily_check.xlsx"
    if not sample.exists():
        return

    wb = load_daily_check(str(sample))
    docs = parse_daily_check(wb, sheet_name="GDL")
    assert len(docs) > 0
    assert all(doc.register for doc in docs)
    assert all(len(doc.tasks) > 0 for doc in docs)
