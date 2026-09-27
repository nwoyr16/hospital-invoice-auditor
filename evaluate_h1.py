from pathlib import Path

import pandas as pd


def main():
    root = Path(__file__).resolve().parent
    output = root / "outputs" / "hospital_1"

    checks = pd.read_csv(
        output / "json_invoice_checks.csv",
        keep_default_na=False,
    )
    labels = pd.read_csv(
        root / "labels" / "hospital_1_labels.csv",
        keep_default_na=False,
    )

    # Exclude ambiguous identifiers from both sides.
    duplicate_ids = set(
        checks.loc[
            checks["invoice_id"].duplicated(keep=False),
            "invoice_id",
        ]
    )
    duplicate_ids.update(
        labels.loc[
            labels["invoice_id"].duplicated(keep=False),
            "invoice_id",
        ]
    )

    predictions = checks.loc[
        ~checks["invoice_id"].isin(duplicate_ids)
    ].copy()

    reference = labels.loc[
        ~labels["invoice_id"].isin(duplicate_ids)
    ].copy()

    if set(predictions["invoice_id"]) != set(reference["invoice_id"]):
        raise ValueError("Prediction and label IDs do not match.")

    joined = predictions.merge(
        reference[["invoice_id", "is_erroneous", "error_categories"]],
        on="invoice_id",
        validate="one_to_one",
    )

    if not joined["is_erroneous"].isin([0, 1]).all():
        raise ValueError("Unexpected ground-truth label.")

    actual = joined["is_erroneous"].eq(1)
    predicted = joined["detected_errors"].ne("")

    tp = int((predicted & actual).sum())
    fp = int((predicted & ~actual).sum())
    fn = int((~predicted & actual).sum())
    tn = int((~predicted & ~actual).sum())

    matrix = pd.DataFrame(
        [
            ["finding", tp, fp],
            ["no_finding", fn, tn],
        ],
        columns=["prediction", "actually_wrong", "actually_correct"],
    )
    matrix.to_csv(output / "confusion_matrix.csv", index=False)

    actual_categories = joined["error_categories"].map(
        lambda value: set(filter(None, value.split("|")))
    )
    predicted_categories = joined["detected_errors"].map(
        lambda value: set(filter(None, value.split("|")))
    )

    categories = sorted(
        set().union(*actual_categories, *predicted_categories)
    )

    rows = []
    for category in categories:
        truth = actual_categories.map(lambda values: category in values)
        detected = predicted_categories.map(
            lambda values: category in values
        )

        category_tp = int((detected & truth).sum())
        category_fp = int((detected & ~truth).sum())
        category_fn = int((~detected & truth).sum())

        rows.append({
            "category": category,
            "invoices_evaluated": len(joined),
            "tp": category_tp,
            "fp": category_fp,
            "fn": category_fn,
            "precision": (
                category_tp / (category_tp + category_fp)
                if category_tp + category_fp else None
            ),
            "recall": (
                category_tp / (category_tp + category_fn)
                if category_tp + category_fn else None
            ),
        })

    pd.DataFrame(rows).to_csv(
        output / "all_category_metrics.csv",
        index=False,
    )

    joined["predicted_flag"] = predicted.astype(int)
    joined.to_csv(output / "invoice_evaluation.csv", index=False)

    print("Invoices evaluated:", len(joined))
    print("Excluded records:", len(checks) - len(joined))
    print("TP:", tp, "FP:", fp, "FN:", fn, "TN:", tn)
    print("Precision:", tp / (tp + fp) if tp + fp else "N/A")
    print("Recall:", tp / (tp + fn) if tp + fn else "N/A")
    print(
        "F1:",
        2 * tp / (2 * tp + fp + fn)
        if 2 * tp + fp + fn else "N/A",
    )
    print("Accuracy:", (tp + tn) / len(joined) if len(joined) else "N/A")
    print("Saved to:", output)
    print("Development evaluation; no finding does not mean clearance.")
    print("Category names are compared literally; no automatic relabeling.")


if __name__ == "__main__":
    main()