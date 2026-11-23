# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "apache-airflow==3.3.1",
#   "apache-airflow-providers-cncf-kubernetes==10.18.0",
#   "pandas>=2.3.3",
#   "pytest==9.0.3",
# ]
# ///

"""
Validate DAG files in a directory before uploading to Cloud Composer.
Performs import validation, structure validation, and checks for common issues.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from airflow.models import DAG, DagBag


class DAGValidator:
    """Validates DAG files for common issues and proper structure."""

    def __init__(self, dags_directory: str):
        self.dags_directory = Path(dags_directory)
        self.errors = []
        self.warnings = []
        self.valid_dags = {}  # dag_id -> dag_file_path
        self.invalid_dags = {}  # dag_file -> error_message

    def validate_all(self) -> bool:
        """
        Validate all DAG files using DagBag.
        Continues processing all DAGs even if some have errors.
        Returns True if all validations pass, False otherwise.
        """
        # Use per-dag validation to process all files
        validation_results = self.validate_per_dag()
        
        # Return True only if all DAGs are valid
        return all(is_valid for is_valid, _ in validation_results.values())


    def validate_per_dag(self) -> dict[str, tuple[bool, str]]:
        """
        Validate each DAG file individually.
        Returns a dict mapping dag_id -> (is_valid: bool, error_message: str)
        Also tracks file paths for each DAG ID in self.valid_dags and self.invalid_dags
        """
        print(f"Validating DAGs in {self.dags_directory}...\n")
        
        # Load DAGs using DagBag
        dag_bag = self._load_dags_with_bagbag()
        
        if dag_bag is None:
            return {}
        
        validation_results = {}
        
        # Check for import errors per file
        if dag_bag.import_errors:
            print("Import Errors Found:\n")
            for file_path, error_message in dag_bag.import_errors.items():
                rel_path = os.path.relpath(file_path, str(self.dags_directory))
                error_text = error_message.strip()
                self.invalid_dags[rel_path] = error_text
                validation_results[rel_path] = (False, error_text)
                print(f"  ❌ FAIL - {rel_path}")
                print(f"           Error: {error_text}\n")
        
        # Validate structure of loaded DAGs
        if dag_bag.dags:
            print(f"Loaded DAGs:\n")
            for dag in dag_bag.dags.values():
                error = self._validate_dag_structure_return_error(dag)
                if error:
                    self.invalid_dags[dag.dag_id] = error
                    validation_results[dag.dag_id] = (False, error)
                    print(f"  ❌ FAIL - {dag.dag_id}")
                    print(f"           Error: {error}\n")
                else:
                    # Store relative file path from dags_directory for this DAG
                    rel_path = os.path.relpath(dag.fileloc, str(self.dags_directory))
                    self.valid_dags[dag.dag_id] = rel_path
                    validation_results[dag.dag_id] = (True, "")
                    print(f"  ✅ PASS - {dag.dag_id}\n")
        
        # Print comprehensive summary
        self._print_per_dag_summary(validation_results)
        
        return validation_results

    def get_valid_dag_file_path(self, dag_id: str) -> str | None:
        """Get the file path for a valid DAG ID."""
        return self.valid_dags.get(dag_id)
    
    def _print_per_dag_summary(self, validation_results: dict) -> None:
        """Print a comprehensive summary of all validation results."""
        valid_count = len({k: v for k, v in validation_results.items() if v[0]})
        invalid_count = len({k: v for k, v in validation_results.items() if not v[0]})
        
        print("\n" + "=" * 70)
        print("VALIDATION SUMMARY - ALL DAGS")
        print("=" * 70)
        print(f"Total DAGs: {len(validation_results)}")
        print(f"✅ Valid (will upload): {valid_count}")
        print(f"❌ Invalid (will skip): {invalid_count}\n")
        
        print("Detailed Breakdown:")
        print("-" * 70)
        
        for dag_name, (is_valid, error) in validation_results.items():
            status = "✅ PASS" if is_valid else "❌ FAIL"
            print(f"{status:8} | {dag_name:40} | ", end="")
            if error:
                print(f"Error: {error}")
            else:
                print("Valid")
        
        print("=" * 70 + "\n")

    def _load_dags_with_bagbag(self) -> DagBag | None:
        """
        Load all DAGs using DagBag.
        DagBag handles:
        - Python syntax validation
        - Import error detection
        - DAG object creation
        Returns DagBag object or None if initialization fails.
        """
        try:
            dag_bag = DagBag(dag_folder=str(self.dags_directory))
            return dag_bag
        except Exception as e:
            self.errors.append(f"Failed to initialize DagBag: {str(e)}")
            print(f" DagBag initialization failed: {str(e)}\n")
            return None

    def _report_import_errors(self, import_errors: dict) -> None:
        """Report import errors found by DagBag (syntax, imports, etc.)."""
        print("Import Errors Detected:\n")
        for file_path, error_message in import_errors.items():
            rel_path = os.path.relpath(file_path, str(self.dags_directory))
            error_text = error_message.strip()
            self.errors.append(f"{rel_path}: {error_text}")
            print(f"  File: {rel_path}")
            print(f"  Error: {error_text}\n")

    def _validate_dag_structure(self, dag: DAG) -> None:
        """Validate the structure and configuration of a DAG object."""
        print(f" Checking DAG: {dag.dag_id}")
        
        # Check DAG has required attributes
        if not dag.dag_id:
            self.errors.append("DAG has no dag_id")
            print(f" Missing dag_id\n")
            return

        # Check DAG has at least one task
        if len(dag.tasks) == 0:
            self.errors.append(f"{dag.dag_id}: DAG has no tasks")
            print(f" No tasks defined\n")
            return

        # Validate start_date is set
        if dag.start_date is None:
            self.errors.append(f"{dag.dag_id}: Missing start_date")
            print(f" Missing start_date\n")
            return

        # Validate all tasks have task_ids
        for task in dag.tasks:
            if not task.task_id:
                self.errors.append(f"{dag.dag_id}: Task has no task_id")
                print(f" Task missing task_id\n")
                return

        # Validate all tasks are properly configured
        task_count = len(dag.tasks)
        print(f"    DAG valid | Tasks: {task_count}\n")

    def _validate_dag_structure_return_error(self, dag: DAG) -> str | None:
        """
        Validate the structure and configuration of a DAG object.
        Returns error message if invalid, None if valid.
        """
        # Check DAG has required attributes
        if not dag.dag_id:
            return "DAG has no dag_id"

        # Check DAG has at least one task
        if len(dag.tasks) == 0:
            return f"{dag.dag_id}: DAG has no tasks"

        # Validate start_date is set
        if dag.start_date is None:
            return f"{dag.dag_id}: Missing start_date"

        # Validate all tasks have task_ids
        for task in dag.tasks:
            if not task.task_id:
                return f"{dag.dag_id}: Task has no task_id"

        return None

    def _print_results(self) -> bool:
        """Print validation results and return success status."""
        print("\n" + "=" * 50)
        print("VALIDATION SUMMARY")
        print("=" * 50)

        if self.warnings:
            print("\n⚠ Warnings:")
            for warning in self.warnings:
                print(f"  - {warning}")

        if self.errors:
            print("\n❌ Errors:")
            for error in self.errors:
                print(f"  - {error}")
            print("\nValidation FAILED")
            return False

        print("✅ -------All validations PASSED--------")
        return True


def main():
    """Main entry point for DAG validation."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate DAG files before uploading to Cloud Composer"
    )
    parser.add_argument(
        "--dag-directories",
        required=True,
        nargs="+",
        help="Paths to directories containing DAG files",
    )

    args = parser.parse_args()
    success = True
    for directory in args.dag_directories:
        directory_success = DAGValidator(directory).validate_all()
        if directory_success and (Path(directory) / "test").is_dir():
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-s", "test/"],
                cwd=directory,
                check=False,
            )
            directory_success = result.returncode == 0
        success = directory_success and success

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

