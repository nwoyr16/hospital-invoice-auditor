import re
from decimal import Decimal
from pathlib import Path

import pandas as pd


def main():
    root = Path(__file__).resolve().parent
    output = root / "outputs" / "hospital_4"

    contract_path = (
        root
        / "contracts"
        / "hospital_4"
        / "conditional_reimbursement_agreement.txt"
    )
    contract = contract_path.read_text(encoding="utf-8-sig")

    section = contract.split(
        "7. BUNDLED DELIVERY", 1
    )[1].split("8. DISCOUNTS", 1)[0]

    rules = {}

    for row in section.splitlines():
        match = re.match(
            r"^(.+?)\s{2,}GBP ([\d,.]+)\s+(.+?)\s{2,}GBP ([\d,.]+)\s*$",
            row,
        )

        if match:
            service_a, rate_a, service_b, rate_b = match.groups()
            service_a = service_a.strip()
            service_b = service_b.strip()

            rules[service_a] = (
                service_b,
                int(Decimal(rate_a.replace(",", "")) * 100),
            )
            rules[service_b] = (
                service_a,
                int(Decimal(rate_b.replace(",", "")) * 100),
            )

    if len(rules) != 14:
        raise ValueError("Expected seven bundle pairs.")

    lines = pd.read_csv(
        output / "service_line_checks.csv",
        keep_default_na=False,
    )
    invoices = pd.read_csv(
        output / "json_invoice_checks.csv",
        keep_default_na=False,
    )

    if "patient_id" not in lines:
        lines = lines.merge(
            invoices[["record_id", "patient_id"]],
            on="record_id",
            validate="many_to_one",
        )

    dates = pd.to_datetime(
        lines["service_date"],
        format="%Y-%m-%d",
        errors="coerce",
    )
    lines["_day"] = dates

    bad_patients = set(
        lines.loc[dates.isna(), "patient_id"]
    )

    presence = (
        lines.loc[dates.notna()]
        .groupby(["patient_id", "_day"])["contract_service"]
        .agg(set)
        .to_dict()
    )

    lines["bundle_rate_mismatch"] = False
    lines["bundle_check_status"] = "not_applicable_or_unmapped"
    lines["bundle_expected_unit_price_cents"] = pd.Series(
        pd.NA,
        index=lines.index,
        dtype="Int64",
    )

    relevant = lines["contract_service"].isin(rules)

    for index, row in lines.loc[relevant].iterrows():
        observed = presence.get(
            (row["patient_id"], row["_day"]),
            set(),
        )

        wrong_unit = (
            str(row["wrong_unit_basis"]).lower() == "true"
        )

        uncertain = (
            pd.isna(row["_day"])
            or row["patient_id"] in bad_patients
            or "" in observed
            or wrong_unit
            or not (
                pd.Timestamp("2024-01-01")
                <= row["_day"]
                <= pd.Timestamp("2025-12-31")
            )
        )

        if uncertain:
            lines.at[index, "bundle_check_status"] = "needs_review"
            continue

        partner, bundled_rate = rules[row["contract_service"]]

        if partner in observed:
            expected = bundled_rate
            status = "paired_rate_checked"
        else:
            expected = int(row["base_rate_cents"])
            status = "standalone_rate_checked"

        lines.at[
            index, "bundle_expected_unit_price_cents"
        ] = expected

        lines.at[index, "bundle_check_status"] = status

        lines.at[index, "bundle_rate_mismatch"] = (
            int(row["unit_price_cents"]) != expected
        )

    grouped = (
        lines.groupby("record_id")["bundle_rate_mismatch"].any()
    )

    invoices["bundle_rate_mismatch"] = (
        invoices["record_id"]
        .map(grouped)
        .fillna(False)
        .astype(bool)
    )

    for index, row in invoices.iterrows():
        errors = [
            error
            for error in str(row["detected_errors"]).split("|")
            if error and error != "bundle_rate_mismatch"
        ]

        if row["bundle_rate_mismatch"]:
            errors.append("bundle_rate_mismatch")

        invoices.at[index, "detected_errors"] = "|".join(errors)
        invoices.at[index, "review_status"] = (
            "errors_detected"
            if errors
            else "remaining_checks_needed"
        )

    lines.drop(columns="_day").to_csv(
        output / "bundle_line_checks.csv",
        index=False,
    )

    invoices.to_csv(
        output / "invoice_checks_with_bundles.csv",
        index=False,
    )

    checked = lines["bundle_check_status"].isin([
        "paired_rate_checked",
        "standalone_rate_checked",
    ])

    print("Bundle lines checked:", int(checked.sum()))
    print(
        "Records with bundle mismatch:",
        int(invoices["bundle_rate_mismatch"].sum()),
    )
    print(
        "Total records with findings:",
        int(invoices["detected_errors"].ne("").sum()),
    )
    print("Saved: outputs/hospital_4/invoice_checks_with_bundles.csv")
    print("Partial audit; discounts and exclusions remain unchecked.")


if __name__ == "__main__":
    main()
    