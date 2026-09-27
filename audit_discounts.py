from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import pandas as pd


RULES = {
    "Ambulatory Musculoskeletal Ventilation Support": [
        (80, 15),
        (240, 30),
    ],
    "Standard Oncology Ward Bed Occupancy": [
        (120, 10),
    ],
    "Standard Orthopaedic Critical Care Occupancy": [
        (120, 10),
    ],
}


def discount_for(units, rules):
    return max(
        [
            percent
            for threshold, percent in rules
            if units > threshold
        ]
        or [0]
    )


def main():
    output = (
        Path(__file__).resolve().parent
        / "outputs"
        / "hospital_4"
    )

    lines = pd.read_csv(
        output / "service_line_checks.csv",
        keep_default_na=False,
    )
    invoices = pd.read_csv(
        output / "invoice_checks_with_bundles.csv",
        keep_default_na=False,
    )

    dates = pd.to_datetime(
        lines["service_date"],
        format="%Y-%m-%d",
        errors="coerce",
    )

    lines["_date"] = dates
    lines["discount_rate_mismatch"] = False
    lines["discount_check_status"] = "not_applicable_or_unmapped"

    for column in [
        "utilisation_lower_before",
        "utilisation_upper_before",
        "discount_percent",
        "discount_expected_unit_price_cents",
    ]:
        lines[column] = pd.Series(
            pd.NA,
            index=lines.index,
            dtype="Int64",
        )

    quantities = pd.to_numeric(
        lines["quantity"],
        errors="coerce",
    )

    for service, rules in RULES.items():
        mapped = lines["contract_service"].eq(service)

        candidates = (
            lines["candidate_services"]
            .fillna("")
            .astype(str)
        )

        possible = (
            lines["contract_service"].eq("")
            & (
                candidates.eq("")
                | candidates.str.split("|").map(
                    lambda values: service in values
                )
            )
        )

        relevant = mapped | possible

        wrong_units = (
            lines.loc[mapped, "wrong_unit_basis"]
            .astype(str)
            .str.lower()
            .eq("true")
            .any()
        )

        invalid_quantities = (
            quantities.loc[relevant].isna().any()
            or (quantities.loc[relevant] < 0).any()
            or (quantities.loc[relevant] % 1 != 0).any()
        )

        if invalid_quantities or wrong_units:
            lines.loc[mapped, "discount_check_status"] = (
                "needs_quantity_or_unit_review"
            )
            continue

        valid_date = (
            dates.notna()
            & dates.between("2024-01-01", "2025-12-31")
        )

        certain = mapped & valid_date
        uncertain = possible | (mapped & ~valid_date)

        # Upper bound includes all unresolved possible units.
        extra = int(quantities.loc[uncertain].sum())
        prior = 0

        ordered = lines.loc[certain].sort_values(
            ["_date", "line_id"]
        )

        lines.loc[
            mapped & ~valid_date,
            "discount_check_status",
        ] = "needs_date_review"

        for index, row in ordered.iterrows():
            lower = prior
            upper = prior + extra

            lines.at[
                index, "utilisation_lower_before"
            ] = lower

            lines.at[
                index, "utilisation_upper_before"
            ] = upper

            low_percent = discount_for(lower, rules)
            high_percent = discount_for(upper, rules)

            if low_percent != high_percent:
                lines.at[index, "discount_check_status"] = (
                    "needs_mapping_review_threshold_uncertain"
                )
            else:
                expected = int(
                    (
                        Decimal(int(row["base_rate_cents"]))
                        * Decimal(100 - low_percent)
                        / 100
                    ).quantize(
                        Decimal("1"),
                        rounding=ROUND_HALF_UP,
                    )
                )

                lines.at[
                    index, "discount_percent"
                ] = low_percent

                lines.at[
                    index, "discount_expected_unit_price_cents"
                ] = expected

                lines.at[
                    index, "discount_rate_mismatch"
                ] = int(row["unit_price_cents"]) != expected

                lines.at[index, "discount_check_status"] = (
                    "checked_bounds_agree"
                )

            # Current quantity affects subsequent lines only.
            prior += int(quantities.at[index])

    flags = (
        lines.groupby("record_id")["discount_rate_mismatch"]
        .any()
    )

    invoices["discount_rate_mismatch"] = (
        invoices["record_id"]
        .map(flags)
        .fillna(False)
        .astype(bool)
    )

    for index, row in invoices.iterrows():
        errors = [
            error
            for error in str(row["detected_errors"]).split("|")
            if error and error != "discount_rate_mismatch"
        ]

        if row["discount_rate_mismatch"]:
            errors.append("discount_rate_mismatch")

        invoices.at[index, "detected_errors"] = "|".join(errors)
        invoices.at[index, "review_status"] = (
            "errors_detected"
            if errors
            else "remaining_checks_needed"
        )

    (
        lines.loc[lines["contract_service"].isin(RULES)]
        .drop(columns="_date")
        .to_csv(
            output / "discount_line_checks.csv",
            index=False,
        )
    )

    invoices.to_csv(
        output / "invoice_checks_with_discounts.csv",
        index=False,
    )

    print(
        "Discount lines checked:",
        int(
            lines["discount_check_status"]
            .eq("checked_bounds_agree")
            .sum()
        ),
    )
    print(
        "Discount lines needing review:",
        int(
            lines["discount_check_status"]
            .str.startswith("needs_")
            .sum()
        ),
    )
    print(
        "Records with discount mismatch:",
        int(invoices["discount_rate_mismatch"].sum()),
    )
    print(
        "Total records with findings:",
        int(invoices["detected_errors"].ne("").sum()),
    )
    print("Partial audit; not a submission file.")


if __name__ == "__main__":
    main()