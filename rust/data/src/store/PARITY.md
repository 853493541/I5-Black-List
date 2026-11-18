# Store parity with storage.py: what is proven and what is not

Proven by tests (rust/data/tests/store_*.rs) on golden data from tools/rust_golden_store.py:
- The same steps from the same files with a frozen clock leave the same bytes, from an old (v0.9.13 to v0.9.15) data
  folder and from none: the four JSON files and the dated backups.
- Every file the Python app wrote opens to the same values and saves back to the same bytes.
- Backups: one a day, the first change's, seven kept; a backup opens as the list it was.
- A broken file is set aside under the Python app's name, with the same warning.

Not ported, on purpose:
- Logging (storage.py's `_log` lines): the Rust app's log is another package's.
- File locking and encryption: storage.py has neither.

Known gaps, where Python is followed only for what its own files hold (no player file reaches them):
- `NaN`, `Infinity` and numbers past 1e308 or 2^64: Python reads them, serde_json refuses, so the file is set aside.
- `int()` on non-ASCII digits (Arabic-Indic etc.) and `sorted()` of a list of lists in column_order.
- `datetime.fromisoformat` takes a few forms `scans::parse_at` does not (week dates, `Z` with no seconds).
- `str.splitlines` splits on more than `\n` (`\x0b`, `\x1c`, U+2028) in tags_and_reason and 分享 text.
- Unicode tables: Python 3.13 is Unicode 15.1; the crates' tables may be newer for a few new characters.
- The order songs found in custom_sounds join 场景管理 follows the folder listing in Python (NTFS: by name); Rust sorts
  by name.
