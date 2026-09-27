import re
from decimal import Decimal
from pathlib import Path

import pandas as pd


def truth(value):
    return str(value).lower() == "true"


def main():
    root = Path(__file__).resolve().parent
    output = root / "outputs" / "hospital_4"

    def read(name):
        return pd.read_csv(
            output / name,
            keep_default_na=False,
        )

    lines = read("service_line_checks.csv")
    invoices = read("invoice_checks_with_duplicates.csv")

    bundles = read("bundle_line_checks.csv").set_index("line_id")
    discounts = read("discount_line_checks.csv").set_index("line_id")

    if not bundles.index.is_unique or not discounts.index.is_unique:
        raise ValueError("Repeated line IDs in pricing inputs.")

    contract = (
        root
        / "contracts"
        / "hospital_4"
        / "conditional_reimbursement_agreement.txt"
    ).read_text(encoding="utf-8-sig")

    section = contract.split(
        "9. EXCLUSION WINDOWS", 1
    )[1].split("10. NON-BUSINESS-DAY UPLIFTS", 1)[0]

    exclusions = {}

    for row in section.splitlines():
        match = re.match(
            r"^(.+?)\s{2,}(\d+) days\s+(.+?)\s*$",
            row,
        )
        if match:
            exclusions[match[1].strip()] = (
                int(match[2]),
                match[3].strip(),
            )

    lines["_date"] = pd.to_datetime(
        lines["service_date"],
        format="%Y-%m-%d",
        errors="coerce",
    )

    patient_lines = {
        patient: group
        for patient, group in lines.groupby("patient_id")
    }

    duplicate_records = set(
        invoices.loc[
            invoices["duplicate_service_review"].map(truth),
            "record_id",
        ]
    )

    reused_ids = set(
        invoices.loc[
            invoices["duplicate_invoice_id"].map(truth),
            "record_id",
        ]
    )

    expected_totals = []
    explanations = []

    for _, row in lines.iterrows():
        reasons = []
        service = row["contract_service"]
        line_id = row["line_id"]
        rate = None

        if row["price_check_status"] in [
            "base_rate_checked",
            "quantity_premium_checked",
        ]:
            rate = int(row["expected_checked_unit_price_cents"])

        if line_id in bundles.index:
            bundle = bundles.loc[line_id]

            if bundle["bundle_check_status"] in [
                "paired_rate_checked",
                "standalone_rate_checked",
            ]:
                rate = int(
                    bundle["bundle_expected_unit_price_cents"]
                )

        if line_id in discounts.index:
            discount = discounts.loc[line_id]

            if discount["discount_check_status"] == "checked_bounds_agree":
                rate = int(
                    discount["discount_expected_unit_price_cents"]
                )
            else:
                reasons.append("discount_uncertain")

        if str(row.get("daily_quantity_limit", "")) != "":
            if (
                row["daily_quantity_status"] == "checked"
                and not truth(row["daily_cap_exceeded"])
            ):
                rate = int(row["base_rate_cents"])
            else:
                reasons.append(
                    "daily_cap_allocation_or_quantity_uncertain"
                )

        patient = patient_lines[row["patient_id"]]

        if service in exclusions:
            window, trigger = exclusions[service]

            if pd.notna(row["_date"]):
                distance = (
                    patient["_date"] - row["_date"]
                ).abs().dt.days

                potential = (
                    patient["contract_service"].eq("")
                    & (
                        patient["candidate_services"].eq("")
                        | patient["candidate_services"]
                        .str.split("|")
                        .map(lambda values: trigger in values)
                    )
                )

                unknown_trigger = (
                    (
                        potential
                        & (
                            distance.le(window)
                            | patient["_date"].isna()
                        )
                    ).any()
                    or (
                        patient["contract_service"].eq(trigger)
                        & patient["_date"].isna()
                    ).any()
                )

                trigger_distances = distance.loc[
                    patient["contract_service"].eq(trigger)
                ].dropna()

                if trigger_distances.lt(window).any():
                    rate = 0
                elif trigger_distances.eq(window).any():
                    reasons.append("exclusion_boundary_uncertain")
                elif unknown_trigger:
                    reasons.append(
                        "exclusion_trigger_mapping_uncertain"
                    )
                else:
                    rate = int(row["base_rate_cents"])
            else:
                reasons.append("invalid_service_date")

        if not service:
            reasons.append("unmapped_service")

        if (
            truth(row["wrong_unit_basis"])
            or row["unit_check_status"] != "checked"
        ):
            reasons.append("unit_or_quantity_conversion_uncertain")

        if (
            truth(row["malformed_service_date"])
            or truth(row["service_date_out_of_window"])
        ):
            reasons.append("date_not_eligible_for_pricing")

        if row["record_id"] in duplicate_records:
            reasons.append("duplicate_service_allocation_uncertain")

        if row["record_id"] in reused_ids:
            reasons.append("reused_invoice_id")

        same_day = patient["_date"].eq(row["_date"])

        possible_same_service = (
            patient["contract_service"].eq("")
            & (
                patient["candidate_services"].eq("")
                | patient["candidate_services"]
                .str.split("|")
                .map(lambda values: service in values)
            )
        )

        if (
            possible_same_service
            & (same_day | patient["_date"].isna())
        ).any():
            reasons.append("possible_unmapped_duplicate")

        quantity = Decimal(str(row["quantity"]))

        if (
            not quantity.is_finite()
            or quantity < 0
            or quantity != quantity.to_integral_value()
        ):
            reasons.append("quantity_uncertain")

        if rate is None:
            reasons.append("no_complete_rate_rule")

        if reasons:
            expected_totals.append(None)
        else:
            expected_totals.append(
                int(Decimal(rate) * quantity)
            )

        explanations.append(
            "|".join(sorted(set(reasons)))
        )

    lines["expected_line_total_cents"] = pd.array(
        expected_totals,
        dtype="Int64",
    )
    lines["pricing_review_reasons"] = explanations

    report_rows = []

    for _, invoice in invoices.iterrows():
        group = lines.loc[
            lines["record_id"].eq(invoice["record_id"])
        ]

        reasons = set()

        for value in group["pricing_review_reasons"]:
            reasons.update(
                reason
                for reason in value.split("|")
                if reason
            )

        if truth(invoice["malformed_invoice_date"]):
            reasons.add("invalid_invoice_date")

        if group.empty:
            reasons.add("missing_line_items")

        complete = (
            not reasons
            and group["expected_line_total_cents"].notna().all()
        )

        amount = (
            int(group["expected_line_total_cents"].sum())
            if complete
            else None
        )

        errors = list(
            filter(None, invoice["detected_errors"].split("|"))
        )

        if complete and amount != int(invoice["invoice_total_cents"]):
            errors.append("recomputed_total_mismatch")

        report_rows.append({
            "record_id": invoice["record_id"],
            "invoice_id": invoice["invoice_id"],
            "pricing_status": (
                "complete_under_documented_rules"
                if complete
                else "needs_review"
            ),
            "expected_total_cents": amount,
            "billed_total_cents": int(
                invoice["invoice_total_cents"]
            ),
            "detected_errors": "|".join(sorted(set(errors))),
            "review_reasons": "|".join(sorted(reasons)),
        })

    report = pd.DataFrame(report_rows)

    report["expected_total_cents"] = (
        report["expected_total_cents"].astype("Int64")
    )

    report.to_csv(
        output / "invoice_pricing_review.csv",
        index=False,
    )

    lines.drop(columns="_date").to_csv(
        output / "line_pricing_review.csv",
        index=False,
    )

    complete = report["expected_total_cents"].notna()

    report.loc[complete].to_csv(
        output / "priced_invoice_candidates.csv",
        index=False,
    )

    different = (
        report.loc[complete, "expected_total_cents"]
        != report.loc[complete, "billed_total_cents"]
    )

    print("Invoice records:", len(report))
    print(
        "Invoices with complete calculated totals:",
        int(complete.sum()),
    )
    print(
        "Invoices needing pricing review:",
        int((~complete).sum()),
    )
    print(
        "Complete totals differing from billed:",
        int(different.sum()),
    )
    print(
        "Candidates only: confidence and submission "
        "validation are not complete."
    )


if __name__ == "__main__":
    main()