import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import canonical_order_payment_runner as runner


class OrderBenefitRunnerTest(unittest.TestCase):
    def test_governed_benefit_is_nonempty_and_economically_conserved(self):
        application = runner.governed_benefit_application("benefit-test-01")
        allocations = application["allocations"]
        funding = allocations[0]["funding"]

        self.assertEqual(application["amountMinor"], runner.GOVERNED_DISCOUNT_MINOR)
        self.assertEqual(sum(item["amountMinor"] for item in allocations), application["amountMinor"])
        self.assertEqual(sum(item["amountMinor"] for item in funding), allocations[0]["amountMinor"])
        self.assertRegex(application["calculationDigest"], r"^[0-9a-f]{64}$")
        self.assertEqual({item["funderType"] for item in funding}, {"PLATFORM", "MERCHANT"})

    def test_governed_amounts_preserve_gross_discount_net_identity(self):
        discount, payable = runner.commerce_amounts("governed-split")
        self.assertGreater(discount, 0)
        self.assertEqual(runner.GROSS_AMOUNT_MINOR, discount + payable)

    def test_entitlement_benefit_locks_exact_promotion_identity_and_version(self):
        application = runner.governed_benefit_application(
            "benefit-test-02", "11111111-2222-3333-4444-555555555555", 4,
            "merchant-01")

        self.assertEqual(application["benefitType"], "COUPON")
        self.assertEqual(application["benefitSourceType"], "COUPON_ENTITLEMENT")
        self.assertEqual(application["benefitSourceId"], application["entitlementId"])
        self.assertEqual(application["benefitSourceVersion"], 4)
        self.assertEqual(
            {item["funderId"] for item in application["allocations"][0]["funding"]},
            {"cloudmold", "merchant-01"})

        discount, payable = runner.commerce_amounts("entitlement-backed")
        self.assertEqual(runner.GROSS_AMOUNT_MINOR, discount + payable)

    def test_stacked_entitlements_are_distinct_and_conserve_one_line_discount(self):
        applications = runner.stacked_entitlement_applications(
            "benefit-test-03",
            ["11111111-2222-3333-4444-555555555555",
             "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"],
            4, "merchant-01")

        self.assertEqual(len(applications), 2)
        self.assertEqual(sum(item["amountMinor"] for item in applications),
                         runner.GOVERNED_DISCOUNT_MINOR)
        self.assertEqual({item["benefitSourceVersion"] for item in applications}, {4})
        self.assertEqual(len({item["benefitSourceId"] for item in applications}), 2)
        self.assertEqual(
            {funding["funderType"] for application in applications
             for funding in application["allocations"][0]["funding"]},
            {"PLATFORM", "MERCHANT"})

    def test_legacy_default_remains_zero_discount(self):
        discount, payable = runner.commerce_amounts("none")
        self.assertEqual(discount, 0)
        self.assertEqual(payable, runner.GROSS_AMOUNT_MINOR)


if __name__ == "__main__":
    unittest.main()
