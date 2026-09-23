import unittest
from datetime import datetime, timedelta

from app.schemas.remote_billing import GeneralBillingRules
from app.services.remote_billing import calculate_record_fee


def rule(**changes):
    return GeneralBillingRules(mode="general", **changes).model_dump(mode="json")


class GeneralBillingCalculationTests(unittest.TestCase):
    def test_additional_fees_fixed_actual_and_exclusions(self):
        rules = rule(
            currency="USD",
            hourly_rate=50,
            additional_fees=[
                {"id": "taxi", "name": "Taxi", "mode": "fixed", "amount": 100},
                {
                    "id": "commute",
                    "name": "Commute",
                    "mode": "hourly",
                    "amount": 20,
                    "minutes_source": "actual",
                    "increment_minutes": 30,
                },
            ],
        )
        args = (rules, "2026-09-23T10:00", "2026-09-23T12:00")
        result = calculate_record_fee(*args, context={"additional_fee_minutes": {"commute": 61}})
        self.assertEqual(result["total"], "230.00")
        self.assertEqual(
            calculate_record_fee(
                *args, context={"additional_fee_minutes": {"commute": 61}, "excluded_fee_ids": ["taxi"]}
            )["total"],
            "130.00",
        )
        self.assertIsNone(calculate_record_fee(*args)["total"])
        self.assertEqual(calculate_record_fee(*args, context={"excluded_fee_ids": ["commute"]})["total"], "200.00")
        self.assertEqual(
            calculate_record_fee(*args, customer_pricing={"kind": "fixed", "fixed_fee": 500, "currency": "USD"})[
                "total"
            ],
            "500.00",
        )

    def test_additional_fee_fixed_duration_and_work_duration(self):
        for source, expected in [("fixed", "62.50"), ("work", "77.50")]:
            rules = rule(
                currency="USD",
                hourly_rate=30,
                additional_fees=[
                    {
                        "id": "commute",
                        "name": "Commute",
                        "mode": "hourly",
                        "amount": 30,
                        "minutes_source": source,
                        "minutes": 60,
                        "increment_minutes": 30,
                    }
                ],
            )
            result = calculate_record_fee(rules, "2026-09-23T10:00", "2026-09-23T11:05")
            self.assertEqual(result["total"], expected)

    def test_fixed_quote_needs_no_rules_or_times_and_controls_expenses(self):
        price = {"kind": "fixed", "fixed_fee": 500, "currency": "USD"}
        context = {
            "emergency": True,
            "service_type": "project",
            "expenses": [
                {"name": "Taxi", "amount": 30, "currency": "USD"},
                {"name": "Material", "amount": 100, "currency": "CNY"},
            ],
        }
        result = calculate_record_fee(None, None, None, context=context, customer_pricing=price)
        self.assertEqual(result["totals"], {"USD": "530.00", "CNY": "100.00"})
        self.assertEqual(result["status"], "calculated")
        result = calculate_record_fee(
            rule(hourly_rate=100, emergency_fee=500, transport_mode="fixed", transport_fee=100),
            "2026-09-23T10:00",
            "2026-09-23T20:00",
            context=context,
            customer_pricing=price | {"expenses_included": True},
        )
        self.assertEqual(result["total"], "500.00")
        self.assertEqual(len(result["lines"]), 1)
        self.assertIsNone(calculate_record_fee(None, None, None, customer_pricing=price | {"fixed_fee": None})["total"])
        self.assertEqual(
            calculate_record_fee(None, None, None, customer_pricing=price | {"fixed_fee": 0})["total"], "0.00"
        )

    def test_new_york_minimum_and_la_separate_rounding(self):
        ny = rule(currency="USD", hourly_rate=60, minimum_minutes=120)
        self.assertEqual(calculate_record_fee(ny, "2026-09-23T10:00", "2026-09-23T10:01")["total"], "120.00")
        la = rule(
            currency="USD",
            hourly_rate=55,
            billing_increment_minutes=60,
            transport_mode="hourly",
            commute_mode="actual",
            commute_increment_minutes=30,
        )
        for work, commute, expected in [(60, 30, "82.50"), (61, 31, "165.00"), (1, 0, "55.00")]:
            start = datetime(2026, 9, 23, 10)
            result = calculate_record_fee(
                la, start, start + timedelta(minutes=work), context={"actual_commute_minutes": commute}
            )
            self.assertEqual(result["total"], expected)
        self.assertIsNone(calculate_record_fee(la, "2026-09-23T10:00", "2026-09-23T11:00")["total"])

    def test_customer_override_package_night_and_mixed_currency_expenses(self):
        rules = rule(
            pricing="package",
            currency="CNY",
            tiers=[{"up_to_minutes": 240, "total_fee": 1100}],
            night_enabled=True,
            night_start="22:00",
            night_end="06:00",
            night_multiplier="1.25",
            emergency_fee=500,
        )
        result = calculate_record_fee(
            rules,
            "2026-09-23T21:00",
            "2026-09-23T23:00",
            "Asia/Tokyo",
            context={"emergency": True, "expenses": [{"name": "大件打车", "amount": 100, "currency": "JPY"}]},
            customer_pricing={"kind": "hourly", "hourly_rate": 80, "currency": "USD"},
        )
        self.assertEqual(result["status"], "calculated")
        self.assertEqual(result["totals"], {"USD": "200.00", "CNY": "500.00", "JPY": "100.00"})
        self.assertIsNone(result["total"])

    def test_expenses_are_available_without_transport_rule_and_pending_is_not_zero(self):
        rules = rule(currency="USD", hourly_rate=50)
        for amount, expected in [(100, "150.00"), (0, "50.00"), (None, None)]:
            result = calculate_record_fee(
                rules,
                "2026-09-23T10:00",
                "2026-09-23T11:00",
                context={"expenses": [{"name": "Taxi", "amount": amount, "currency": "USD"}]},
            )
            self.assertEqual(result["total"], expected)
        result = calculate_record_fee(
            rules,
            "2026-09-23T10:00",
            "2026-09-23T10:00",
            context={"expenses": [{"name": "Taxi", "amount": 20, "currency": "USD"}]},
        )
        self.assertEqual(result["total"], "20.00")
        for price in [{"kind": "pending"}, {"kind": "hourly", "hourly_rate": None, "currency": "USD"}]:
            self.assertIsNone(
                calculate_record_fee(rules, "2026-09-23T10:00", "2026-09-23T11:00", customer_pricing=price)["total"]
            )

    def test_examples_and_no_invented_price(self):
        examples = [
            (
                rule(currency="USD", hourly_rate=30, transport_mode="fixed", transport_fee=100),
                "Asia/Singapore",
                "160.00",
            ),
            (rule(currency="USD", hourly_rate=50), "Asia/Seoul", "100.00"),
            (rule(currency="USD", hourly_rate=60), "America/Los_Angeles", "120.00"),
            (rule(currency="USD", hourly_rate=60), "America/New_York", "120.00"),
            (rule(currency="USD", hourly_rate=20, transport_mode="hourly"), "Europe/Berlin", "60.00"),
            (rule(currency="USD", hourly_rate=25, transport_mode="hourly"), "Europe/Berlin", "75.00"),
            (rule(currency="GBP", hourly_rate=30, transport_mode="hourly"), "Europe/London", "90.00"),
        ]
        for rules, zone, amount in examples:
            with self.subTest(zone=zone, amount=amount):
                result = calculate_record_fee(rules, "2026-09-22T10:00", "2026-09-22T12:00", zone)
                self.assertEqual(result["total"], amount, result)
                self.assertEqual(result["currency"], rules["currency"])
        self.assertIsNone(
            calculate_record_fee(rule(currency="USD", transport_mode="hourly"), "2026-09-22T10:00", "2026-09-22T12:00")[
                "total"
            ]
        )
        result = calculate_record_fee(
            rule(currency="GBP", hourly_rate=30, transport_mode="hourly"),
            "2026-09-22T10:00",
            "2026-09-22T13:30",
            "Europe/London",
        )
        self.assertEqual(result["total"], "135.00")

    def test_beijing_inputs_and_iana_night_windows(self):
        rules = rule(
            hourly_rate=60, night_enabled=True, night_start="22:00", night_end="06:00", night_multiplier="1.25"
        )
        japan = calculate_record_fee(rules, "2026-09-22T21:00", "2026-09-22T23:00", "Asia/Tokyo")
        self.assertEqual(japan["total"], "150.00")
        self.assertEqual(japan["night_minutes"], 120)
        self.assertEqual(japan["local_arrived_at"], "2026-09-22T22:00:00+09:00")
        la = calculate_record_fee(rules, "2026-09-22T21:00", "2026-09-22T23:00", "America/Los_Angeles")
        self.assertEqual(la["total"], "120.00")
        self.assertEqual(la["night_minutes"], 0)
        utc = calculate_record_fee(rules, "2026-09-22T13:00Z", "2026-09-22T15:00Z", "Asia/Tokyo")
        self.assertEqual(utc, japan)

    def test_spring_gap_and_autumn_repeated_hour(self):
        rules = rule(
            hourly_rate=60, night_enabled=True, night_start="01:00", night_end="04:00", night_multiplier="1.25"
        )
        spring = calculate_record_fee(rules, "2026-03-08T14:30", "2026-03-08T16:30", "America/New_York")
        self.assertEqual(spring["work_minutes"], 120)
        self.assertEqual(spring["night_minutes"], 90)
        self.assertEqual(spring["total"], "142.50")
        rules["night_end"] = "02:00"
        autumn = calculate_record_fee(rules, "2026-11-01T13:30", "2026-11-01T15:30", "America/New_York")
        self.assertEqual(autumn["work_minutes"], 120)
        self.assertEqual(autumn["night_minutes"], 90)
        self.assertEqual(autumn["total"], "142.50")

    def test_packages_overtime_emergency_and_transport_are_separate(self):
        rules = rule(
            pricing="package",
            tiers=[{"up_to_minutes": 240, "total_fee": 1100}, {"up_to_minutes": 480, "total_fee": 1650}],
            overtime_enabled=True,
            overtime_hourly_rate=300,
            overtime_threshold_minutes=30,
            overtime_rounding="half_hour_round",
            emergency_fee=500,
            emergency_regions=["东京"],
            emergency_confirmation_regions=["大阪"],
        )
        start = datetime(2026, 9, 22, 10)
        for minutes, expected in [
            (1, "1100.00"),
            (240, "1100.00"),
            (241, "1650.00"),
            (480, "1650.00"),
            (509, "1650.00"),
            (510, "1950.00"),
            (560, "1950.00"),
            (580, "2250.00"),
        ]:
            self.assertEqual(calculate_record_fee(rules, start, start + timedelta(minutes=minutes))["total"], expected)
        rules.update(night_enabled=True, night_start="19:00", night_end="06:00", night_multiplier="1.25")
        night = calculate_record_fee(
            rules, "2026-09-22T18:00", "2026-09-23T02:00", "Asia/Tokyo", "东京", {"emergency": True}
        )
        self.assertEqual(night["total"], "2562.50")
        osaka = calculate_record_fee(
            rules, "2026-09-22T18:00", "2026-09-23T02:00", "Asia/Tokyo", "大阪", {"emergency": True}
        )
        self.assertIsNone(osaka["total"])

    def test_missing_information_and_invalid_inputs_do_not_become_zero_prices(self):
        normal = rule(hourly_rate=30)
        for source, start, end, zone, ctx in [
            (None, "2026-09-22T10:00", "2026-09-22T12:00", "Asia/Shanghai", {}),
            (normal, "bad", "2026-09-22T12:00", "Asia/Shanghai", {}),
            (normal, "2026-09-22T12:00", "2026-09-22T10:00", "Asia/Shanghai", {}),
            (normal, "2026-09-22T10:00", "2026-09-22T12:00", "invalid", {}),
            (normal | {"night_enabled": True}, "2026-09-22T10:00", "2026-09-22T12:00", "Asia/Shanghai", {}),
            (normal, "2026-09-22T10:00", "2026-09-22T12:00", "Asia/Shanghai", {"service_type": "project"}),
        ]:
            result = calculate_record_fee(source, start, end, zone, context=ctx)
            self.assertIsNone(result["total"])
            self.assertTrue(result["notices"])

    def test_tax_reimbursement_and_minimum_increment(self):
        rules = rule(
            hourly_rate=30,
            minimum_minutes=60,
            billing_increment_minutes=30,
            transport_mode="reimburse",
            payment_methods=[{"name": "公司转账", "tax_mode": "extra", "tax_rate": 10}],
        )
        result = calculate_record_fee(
            rules,
            "2026-09-22T10:00",
            "2026-09-22T11:01",
            context={"payment_method": "公司转账", "reimbursed_transport": 100},
        )
        self.assertEqual(result["billable_minutes"], 90)
        self.assertEqual(result["total"], "159.50")
        pending = calculate_record_fee(rules, "2026-09-22T10:00", "2026-09-22T11:01")
        self.assertIsNone(pending["total"])
        self.assertEqual(calculate_record_fee(rules, "2026-09-22T10:00", "2026-09-22T10:00")["total"], "0.00")
