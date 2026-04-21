import argparse
import json
import sqlite3
from pathlib import Path


def _quote_identifier(name: str) -> str:
	return '"' + name.replace('"', '""') + '"'


def _infer_sqlite_type(values: list[object]) -> str:
	non_null = [v for v in values if v is not None]
	if not non_null:
		return "TEXT"
	if all(isinstance(v, bool) or isinstance(v, int) for v in non_null):
		return "INTEGER"
	if all(isinstance(v, (bool, int, float)) for v in non_null):
		return "REAL"
	return "TEXT"


def convert_json_to_sqlite(json_path: Path, db_path: Path, table_name: str = "orders") -> int:
	with json_path.open("r", encoding="utf-8") as f:
		data = json.load(f)

	if not isinstance(data, list):
		raise ValueError("JSON root must be a list of objects")
	if not data:
		raise ValueError("JSON list is empty")
	if not all(isinstance(item, dict) for item in data):
		raise ValueError("All items in JSON list must be objects")

	columns: list[str] = []
	seen: set[str] = set()
	for row in data:
		for key in row.keys():
			if key not in seen:
				seen.add(key)
				columns.append(key)

	column_types: dict[str, str] = {}
	for col in columns:
		values = [row.get(col) for row in data]
		column_types[col] = _infer_sqlite_type(values)

	conn = sqlite3.connect(db_path)
	try:
		cur = conn.cursor()

		quoted_table = _quote_identifier(table_name)
		cur.execute(f"DROP TABLE IF EXISTS {quoted_table}")

		create_cols = ", ".join(
			f"{_quote_identifier(col)} {column_types[col]}" for col in columns
		)
		cur.execute(f"CREATE TABLE {quoted_table} ({create_cols})")

		col_names_sql = ", ".join(_quote_identifier(col) for col in columns)
		placeholders = ", ".join("?" for _ in columns)
		insert_sql = f"INSERT INTO {quoted_table} ({col_names_sql}) VALUES ({placeholders})"

		rows = [tuple(item.get(col) for col in columns) for item in data]
		cur.executemany(insert_sql, rows)
		conn.commit()
		return len(rows)
	finally:
		conn.close()


def main() -> None:
	parser = argparse.ArgumentParser(description="Convert a JSON array file to SQLite3 DB")
	parser.add_argument("--json", default="completed_orders.json", help="Input JSON file path")
	parser.add_argument("--db", default="completed_orders.db", help="Output SQLite DB file path")
	parser.add_argument("--table", default="orders", help="Table name")
	args = parser.parse_args()

	json_path = Path(args.json)
	db_path = Path(args.db)

	if not json_path.exists():
		raise FileNotFoundError(f"Input JSON file not found: {json_path}")

	inserted = convert_json_to_sqlite(json_path=json_path, db_path=db_path, table_name=args.table)
	print(f"Inserted {inserted} rows into {db_path} table '{args.table}'")


if __name__ == "__main__":
	main()
