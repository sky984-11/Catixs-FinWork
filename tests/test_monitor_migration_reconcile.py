import copy
import unittest

from scripts.reconcile_monitor_event_migration import EXPECTED, INDEXES, validate_schema


class MonitorMigrationReconcileTests(unittest.TestCase):
    def setUp(self):
        defaults = {
            "id": "nextval('monitor_event_config_id_seq'::regclass)",
            "revision": "1",
            "created_at": "CURRENT_TIMESTAMP",
            "updated_at": "CURRENT_TIMESTAMP",
        }
        self.columns = [
            {"column_name": key, "data_type": value, "is_nullable": "NO", "column_default": defaults.get(key)}
            for key, value in EXPECTED.items()
        ]
        self.indexes = [
            {
                "indexname": name,
                "indexdef": f"CREATE INDEX {name} ON public.monitor_event_config USING btree ({column})",
            }
            for name, column in INDEXES.items()
        ]

    def test_matching_schema(self):
        validate_schema(self.columns, self.indexes, "PRIMARY KEY (id)")

    def test_refuses_missing_or_different_columns(self):
        with self.assertRaises(ValueError):
            validate_schema(self.columns[:-1], self.indexes, "PRIMARY KEY (id)")
        columns = copy.deepcopy(self.columns)
        columns[0]["data_type"] = "text"
        with self.assertRaises(ValueError):
            validate_schema(columns, self.indexes, "PRIMARY KEY (id)")

    def test_refuses_missing_indexes_or_wrong_key(self):
        with self.assertRaises(ValueError):
            validate_schema(self.columns, [], "PRIMARY KEY (id)")
        with self.assertRaises(ValueError):
            validate_schema(self.columns, self.indexes, "PRIMARY KEY (revision)")

    def test_refuses_defaults_or_nullability_mismatch(self):
        for field, value in [("is_nullable", "YES"), ("column_default", None)]:
            columns = copy.deepcopy(self.columns)
            columns[0][field] = value
            with self.assertRaises(ValueError):
                validate_schema(columns, self.indexes, "PRIMARY KEY (id)")
