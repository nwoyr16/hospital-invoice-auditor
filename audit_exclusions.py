import re
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
        "9. EXCLUSION WINDOWS", 1
    )[1].split("10. NON-BUSINESS-DAY UPLIFTS", 1)[0]

    rules = {}

    for row in section.splitlines():
        match = re.match(
            r"^(.+?)\s{2,}(\d+) days\s+(.+?)\s*$",
            row,
        )
        if match:
            rules[match[1].strip()] = (
                int(match[2]),
                match[3].strip(),
            )

    if len(rules) != 15:
        raise ValueError("Expected 15 exclusion rules.")

    lines = pd.read_csv(
        output / "service_line_checks.csv",
        keep_default_na=False,
    )
    invoices = pd.read_csv(
        output / "invoice_checks_with_discounts.csv",
        keep_default_na=False,
    )

    if "patient_id" not in lines:
        lines = lines.merge(
            invoices[["record_id", "patient_id"]],
            on="record_id",
            validate="many_to_one",
        )

    lines["_date"] = pd.to_datetime(
        lines["service_date"],
        format="%Y-%m-%d",
        errors="coerce",
    )

    lookup = {
        key: group
        for key, group in lines.loc[
            lines["_date"].notna()
        ].groupby(["patient_id", "contract_service"])
    }

    findings = []
    coverage = []

    relevant = lines["contract_service"].isin(rules)

    for _, row in lines.loc[relevant].iterrows():
        window, trigger = rules[row["contract_service"]]

        if pd.isna(row["_date"]):
            coverage.append({
                "line_id": row["line_id"],
                "status": "invalid_date_needs_review",
            })
            continue

        candidates = lookup.get(
            (row["patient_id"], trigger)
        )

        if candidates is None:
            coverage.append({
                "line_id": row["line_id"],
                "status": "no_mapped_trigger_found_not_clearance",
            })
            continue

        distances = (
            candidates["_date"] - row["_date"]
        ).abs().dt.days

        matches = candidates.loc[distances <= window]

        coverage.append({
            "line_id": row["line_id"],
            "status": (
                "potential_exclusion_found"
                if len(matches)
                else "no_mapped_trigger_in_window_not_clearance"
            ),
        })

        for _, other in matches.iterrows():
            distance = abs(
                (other["_date"] - row["_date"]).days
            )

            findings.append({
                "record_id": row["record_id"],
                "invoice_id": row["invoice_id"],
                "patient_id": row["patient_id"],
                "line_id": row["line_id"],
                "service": row["contract_service"],
                "service_date": row["service_date"],
                "trigger_line_id": other["line_id"],
                "trigger_invoice_id": other["invoice_id"],
                "trigger_service": trigger,
                "trigger_date": other["service_date"],
                "window_days": window,
                "distance_days": distance,
                "boundary_sensitive": distance == window,
            })

    evidence = pd.DataFrame(
        findings,
        columns=[
            "record_id",
            "invoice_id",
            "patient_id",
            "line_id",
            "service",
            "service_date",
            "trigger_line_id",
            "trigger_invoice_id",
            "trigger_service",
            "trigger_date",
            "window_days",
            "distance_days",
            "boundary_sensitive",
        ],
    )

    evidence.to_csv(
        output / "exclusion_evidence.csv",
        index=False,
    )

    pd.DataFrame(coverage).to_csv(
        output / "exclusion_coverage.csv",
        index=False,
    )

    strict_records = set(
        evidence.loc[
            evidence["boundary_sensitive"].eq(False),
            "record_id",
        ]
    )

    boundary_records = set(
        evidence.loc[
            evidence["boundary_sensitive"].eq(True),
            "record_id",
        ]
    )

    invoices["exclusion_window"] = (
        invoices["record_id"].isin(strict_records)
    )
    invoices["exclusion_boundary_review"] = (
        invoices["record_id"].isin(boundary_records)
    )

    for index, row in invoices.iterrows():
        errors = [
            error
            for error in str(row["detected_errors"]).split("|")
            if error and error != "exclusion_window"
        ]

        if row["exclusion_window"]:
            errors.append("exclusion_window")

        invoices.at[index, "detected_errors"] = "|".join(errors)
        invoices.at[index, "review_status"] = (
            "errors_detected"
            if errors
            else "remaining_checks_needed"
        )

    invoices.to_csv(
        output / "invoice_checks_with_exclusions.csv",
        index=False,
    )

    print("Exclusion rules:", len(rules))
    print("Records strictly inside window:", len(strict_records))
    print("Records needing boundary review:", len(boundary_records))
    print(
        "Total records with findings:",
        int(invoices["detected_errors"].ne("").sum()),
    )
    print("Partial audit; unmatched services still need review.")


if __name__ == "__main__":
    main()
    