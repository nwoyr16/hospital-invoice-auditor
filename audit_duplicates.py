from pathlib import Path

import pandas as pd


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
        output / "invoice_checks_with_exclusions.csv",
        keep_default_na=False,
    )

    if "patient_id" not in lines:
        lines = lines.merge(
            invoices[["record_id", "patient_id"]],
            on="record_id",
            validate="many_to_one",
        )

    lines["_day"] = pd.to_datetime(
        lines["service_date"],
        format="%Y-%m-%d",
        errors="coerce",
    )

    eligible = (
        lines["contract_service"].ne("")
        & lines["_day"].notna()
        & lines["patient_id"].ne("")
    )

    groups = []
    evidence = []

    grouped = lines.loc[eligible].groupby(
        ["patient_id", "_day", "contract_service"]
    )

    for (patient, day, service), group in grouped:
        if len(group) < 2:
            continue

        across = group["record_id"].nunique() > 1
        within = bool(
            (group.groupby("record_id").size() > 1).any()
        )

        group_id = f"DUP-{len(groups) + 1:04d}"

        groups.append({
            "duplicate_group_id": group_id,
            "patient_id": patient,
            "service_date": str(day.date()),
            "contract_service": service,
            "line_count": len(group),
            "invoice_record_count": group["record_id"].nunique(),
            "within_invoice": within,
            "across_invoices": across,
            "allocation_status": "review_required_no_amount_removed",
        })

        for _, row in group.iterrows():
            evidence.append({
                "duplicate_group_id": group_id,
                "record_id": row["record_id"],
                "invoice_id": row["invoice_id"],
                "line_id": row["line_id"],
                "patient_id": patient,
                "service_date": str(day.date()),
                "contract_service": service,
                "description": row["description"],
                "quantity": row["quantity"],
                "unit_basis_as_billed": row["unit_basis_as_billed"],
                "unit_price_cents": row["unit_price_cents"],
                "line_total_cents": row["line_total_cents"],
            })

    group_table = pd.DataFrame(
        groups,
        columns=[
            "duplicate_group_id",
            "patient_id",
            "service_date",
            "contract_service",
            "line_count",
            "invoice_record_count",
            "within_invoice",
            "across_invoices",
            "allocation_status",
        ],
    )

    evidence_table = pd.DataFrame(
        evidence,
        columns=[
            "duplicate_group_id",
            "record_id",
            "invoice_id",
            "line_id",
            "patient_id",
            "service_date",
            "contract_service",
            "description",
            "quantity",
            "unit_basis_as_billed",
            "unit_price_cents",
            "line_total_cents",
        ],
    )

    group_table.to_csv(
        output / "duplicate_service_groups.csv",
        index=False,
    )

    evidence_table.to_csv(
        output / "duplicate_service_evidence.csv",
        index=False,
    )

    affected_records = set(evidence_table["record_id"])

    invoices["duplicate_service_review"] = (
        invoices["record_id"].isin(affected_records)
    )

    # Potential duplicates require review.
    # Do not remove amounts or declare duplicate billing automatically.
    invoices.to_csv(
        output / "invoice_checks_with_duplicates.csv",
        index=False,
    )

    print("Duplicate service groups:", len(group_table))
    print(
        "Groups within one invoice:",
        int(group_table["within_invoice"].sum()),
    )
    print(
        "Groups across invoices:",
        int(group_table["across_invoices"].sum()),
    )
    print(
        "Invoice records needing duplicate review:",
        int(invoices["duplicate_service_review"].sum()),
    )
    print(
        "Lines not assessed for duplication:",
        int((~eligible).sum()),
    )
    print(
        "Existing records with findings:",
        int(invoices["detected_errors"].ne("").sum()),
    )
    print("No amounts removed; duplicate groups need review.")


if __name__ == "__main__":
    main()