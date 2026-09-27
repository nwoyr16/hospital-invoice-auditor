from pathlib import Path

import pandas as pd


def main():
    root = Path(__file__).resolve().parent
    h1_dir = root / "outputs" / "hospital_1"

    eval_df = pd.read_csv(
        h1_dir / "invoice_evaluation.csv",
        keep_default_na=False,
    )
    invoices_df = pd.read_csv(
        h1_dir / "json_invoice_checks.csv",
        keep_default_na=False,
    )
    lines_df = pd.read_csv(
        h1_dir / "service_line_checks.csv",
        keep_default_na=False,
    )

    actual = pd.to_numeric(
        eval_df["is_erroneous"],
        errors="raise",
    )

    if not actual.isin([0, 1]).all():
        raise ValueError("Ground-truth labels must be 0 or 1.")

    fn_invoices = eval_df.loc[
        actual.eq(1)
        & eval_df["detected_errors"].str.strip().eq("")
    ].copy()

    print("False Negative invoices:", len(fn_invoices))

    fn_invoices[
        ["invoice_id", "error_categories"]
    ].to_csv(
        h1_dir / "false_negative_invoices.csv",
        index=False,
    )

    if fn_invoices.empty:
        print("No false negatives found.")
        return

    # The evaluation excludes ambiguous duplicate invoice IDs.
    unique_invoices = invoices_df.loc[
        ~invoices_df["invoice_id"].duplicated(keep=False)
    ]

    fn_records = fn_invoices[
        ["invoice_id", "error_categories"]
    ].merge(
        unique_invoices[
            [
                "record_id",
                "invoice_id",
                "invoice_date",
                "invoice_total_cents",
            ]
        ],
        on="invoice_id",
        how="left",
        validate="one_to_one",
        indicator=True,
    )

    if not fn_records["_merge"].eq("both").all():
        raise ValueError("Some FN invoices have no unique source record.")

    fn_records = fn_records.drop(columns="_merge")

    line_columns = [
        "record_id",
        "line_id",
        "service_date",
        "description",
        "contract_service",
        "mapping_status",
        "unit_basis_as_billed",
        "expected_unit_basis",
        "unit_price_cents",
        "base_rate_cents",
        "expected_checked_unit_price_cents",
        "price_check_status",
    ]

    fn_lines = fn_records.merge(
        lines_df[line_columns],
        on="record_id",
        how="left",
        validate="one_to_many",
        indicator=True,
    )

    if not fn_lines["_merge"].eq("both").all():
        raise ValueError("Some FN invoices have no line-item evidence.")

    fn_lines = (
        fn_lines.drop(columns="_merge")
        .sort_values(["invoice_id", "line_id"])
    )

    output_path = h1_dir / "false_negatives_line_details.csv"
    fn_lines.to_csv(output_path, index=False)

    # Count each category separately, not combinations of categories.
    categories = (
        fn_invoices["error_categories"]
        .str.split("|")
        .explode()
        .str.strip()
    )
    category_counts = (
        categories[categories.ne("")]
        .value_counts()
        .rename_axis("error_category")
        .reset_index(name="missed_invoice_count")
    )

    category_counts.to_csv(
        h1_dir / "false_negative_category_counts.csv",
        index=False,
    )

    print("\nMissed categories:")
    print(category_counts.to_string(index=False))

    print("\nMapping status of all lines in FN invoices:")
    print(fn_lines["mapping_status"].value_counts())

    print("\nPrice check status of all lines in FN invoices:")
    print(fn_lines["price_check_status"].value_counts())

    print("\nSaved:", output_path)
    print(
        "These are all lines in missed invoices, "
        "not confirmed erroneous lines."
    )


if __name__ == "__main__":
    main()