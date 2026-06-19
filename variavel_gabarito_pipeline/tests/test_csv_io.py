from pathlib import Path

import pandas as pd

from pipeline.io.csv_reader import read_csv
from pipeline.io.csv_writer import write_csv


def test_csv_io_uses_semicolon_and_utf8_sig(tmp_path: Path) -> None:
    output_path = tmp_path / "dados.csv"
    dataframe = pd.DataFrame({"Centro": ["CRBC"], "Rota": ["VA300"]})

    write_csv(dataframe, output_path)

    content = output_path.read_text(encoding="utf-8-sig")
    assert content.splitlines()[0] == "Centro;Rota"
    assert read_csv(output_path).equals(dataframe)
