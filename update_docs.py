from datetime import datetime
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    project = Path(__file__).resolve().parent

    source = Path(
        r"C:\Users\lenovo\Documents\Codex\2026-09-08"
        r"\business-analysis-requirements-gathering-business-process"
        r"\outputs\current_project_update"
    )

    files = [
        "build_report.py",
        "README.md",
        "requirements.txt",
        "run_audit.cmd",
        "prompts/07_h3_and_report_revision.md",
    ]

    # Check everything before changing project files.
    for name in files:
        if not (source / name).is_file():
            raise FileNotFoundError(
                f"Missing prepared update: {source / name}"
            )

    required = [
        "results/summary.json",
        "results/submission.csv",
        "results/hospital_1/category_metrics.csv",
        "results/hospital_1/invoice_evaluation.csv",
        "submission.csv",
        "submission_config.json",
    ]

    for name in required:
        if not (project / name).is_file():
            raise FileNotFoundError(
                f"Missing project input: {project / name}"
            )

    try:
        import reportlab
    except ImportError:
        raise SystemExit(
            "Install the PDF library first:\n"
            f'"{sys.executable}" -m pip install reportlab==4.4.9'
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup = project / f"backup_before_docs_{timestamp}"
    backup.mkdir()

    for name in files:
        existing = project / name
        if existing.is_file():
            saved = backup / name
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(existing, saved)

    reports = project / "reports"
    if reports.exists():
        shutil.copytree(reports, backup / "reports")

    print("Backup saved to:", backup)

    for name in files:
        destination = project / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / name, destination)
        print("Updated:", name)

    # Build the report from this project's current results.
    subprocess.run(
        [sys.executable, str(project / "build_report.py")],
        cwd=project,
        check=True,
    )

    print("\nDONE")
    print("Updated README:", project / "README.md")
    print("Updated report:", reports / "report.pdf")
    print("Decision log:", reports / "decision_log.md")
    print("Submission and audit code were not changed.")


if __name__ == "__main__":
    main()