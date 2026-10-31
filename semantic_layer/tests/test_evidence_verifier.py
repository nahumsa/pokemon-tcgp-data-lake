"""Evidence checks must reject changed inputs and unequal row multiplicities."""

import gzip

import duckdb
import pytest

from transformations.analysis.verify_archetype_evidence import (
    difference_count,
    snapshot_counts,
)


def test_changed_snapshot_is_rejected_before_counts_are_trusted(tmp_path):
    snapshot = tmp_path / "changed.json.gz"
    snapshot.write_bytes(gzip.compress(b'{}'))
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        snapshot_counts(snapshot, "0" * 64)


@pytest.mark.parametrize("right_rows", ["(1), (1)", "(2)"])
def test_evidence_comparison_detects_duplicates_and_changed_values(right_rows):
    with duckdb.connect() as con:
        con.execute("create table before_rows as select 1 as value")
        con.execute(f"create table after_rows as select * from (values {right_rows}) t(value)")
        assert difference_count(con, "before_rows", "after_rows") > 0
        assert difference_count(con, "before_rows", "before_rows") == 0
