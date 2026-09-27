from datetime import datetime
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    project = Path(__file__).resolve().parent

    updates = Path(
        r"C:\Users\lenovo\Documents\Codex\2026-09-08"
        r"\business-analysis-requirements-gathering-business-process"
        r"\outputs\current_project_update"
    )

    files = [
        "audit.py",
        "vocabulary.py",
        "run.py",
        "evaluate.py",
        "review_queue.py",
        "test_engine.py",
    ]

    # Check everything before replacing any file.
    for folder in ["contracts", "invoices", "labels"]:
        if not (project / folder).is_dir():
            raise RuntimeError(
                f"Missing folder: {folder}. "
                "Save update_project.py inside your project folder."
            )

    for name in files:
        if not (updates / name).is_file():
            raise FileNotFoundError(
                f"Update file not found: {updates / name}"
            )

    # Preserve the previous code and submission.
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup = project / f"backup_before_update_{stamp}"
    backup.mkdir()

    for name in files + ["submission.csv"]:
        original = project / name
        if original.is_file():
            shutil.copy2(original, backup / name)

    print("Backup saved to:", backup, flush=True)

    # Update the existing project.
    for name in files:
        shutil.copy2(updates / name, project / name)
        print("Updated:", name, flush=True)

    print("\nRunning tests...", flush=True)

    subprocess.run(
        [sys.executable, "-m", "unittest", "-v", "test_engine"],
        cwd=project,
        check=True,
    )

    print("\nRunning audit and H1 evaluation...", flush=True)

    subprocess.run(
        [
            sys.executable,
            str(project / "run.py"),
            "--evaluate-h1",
        ],
        cwd=project,
        check=True,
    )

    print("\nDONE")
    print("Updated submission:", project / "submission.csv")
    print("Detailed results:", project / "results")
    print("The old PDF report has NOT been updated.")


if __name__ == "__main__":
    main()