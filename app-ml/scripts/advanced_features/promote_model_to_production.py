#!/usr/bin/env python3
"""
MLflow Model Promotion Script

Promotes a model version to production stage in MLflow Model Registry.
Includes validation checks and approval workflow.

Usage:
    # Promote latest model (with validation)
    python scripts/advanced_features/promote_model_to_production.py

    # Promote specific version
    python scripts/advanced_features/promote_model_to_production.py --version 3

    # Skip validation checks
    python scripts/advanced_features/promote_model_to_production.py --force

    # Dry run (show what would happen)
    python scripts/advanced_features/promote_model_to_production.py --dry-run

Requirements:
    - MLflow server running and accessible
    - Model registered in MLflow Model Registry
    - Appropriate permissions to transition model stages

Author: MLOps Team
Version: 2.1.0
Date: January 3, 2025
"""

import argparse
import os
import sys
from datetime import datetime
from typing import Dict, Optional, Tuple

try:
    import mlflow
    from mlflow.exceptions import MlflowException
    from mlflow.tracking import MlflowClient
except ImportError:
    print("Error: MLflow not installed. Install with: pip install mlflow")
    sys.exit(1)


class ModelPromoter:
    """Handles model promotion to production with validation."""

    def __init__(
        self,
        model_name: str,
        tracking_uri: str,
        rmse_threshold: float = 52.0,
        improvement_threshold: float = 1.0,
    ):
        """
        Initialize model promoter.

        Args:
            model_name: Name of the registered model
            tracking_uri: MLflow tracking server URI
            rmse_threshold: Maximum acceptable RMSE
            improvement_threshold: Minimum improvement % required
        """
        self.model_name = model_name
        self.tracking_uri = tracking_uri
        self.rmse_threshold = rmse_threshold
        self.improvement_threshold = improvement_threshold
        self.client = None

    def connect(self) -> bool:
        """
        Connect to MLflow tracking server.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            mlflow.set_tracking_uri(self.tracking_uri)
            self.client = MlflowClient()

            # Test connection
            self.client.list_experiments()

            print(f"✅ Connected to MLflow: {self.tracking_uri}")
            return True

        except Exception as e:
            print(f"❌ Failed to connect to MLflow: {e}")
            return False

    def get_latest_version(self, stage: str = "None") -> Optional[Dict]:
        """
        Get latest model version in specified stage.

        Args:
            stage: Model stage to filter by

        Returns:
            Dictionary with version info or None
        """
        try:
            versions = self.client.get_latest_versions(self.model_name, stages=[stage])

            if not versions:
                return None

            latest = versions[0]

            return {
                "version": latest.version,
                "run_id": latest.run_id,
                "stage": latest.current_stage,
                "creation_time": latest.creation_timestamp,
            }

        except MlflowException as e:
            if "RESOURCE_DOES_NOT_EXIST" in str(e):
                print(f"⚠️  Model '{self.model_name}' not found in registry")
                return None
            raise

    def get_current_production_model(self) -> Optional[Dict]:
        """
        Get currently deployed production model.

        Returns:
            Dictionary with production model info or None
        """
        return self.get_latest_version(stage="Production")

    def get_model_metrics(self, run_id: str) -> Dict[str, float]:
        """
        Get metrics for a model run.

        Args:
            run_id: MLflow run ID

        Returns:
            Dictionary of metrics
        """
        try:
            run = self.client.get_run(run_id)

            metrics = {
                "rmse": run.data.metrics.get("final_rmse"),
                "mae": run.data.metrics.get("final_mae"),
                "mape": run.data.metrics.get("final_mape"),
                "training_time": run.data.metrics.get("training_time_seconds"),
                "model_size": run.data.metrics.get("model_size_mb"),
            }

            return {k: v for k, v in metrics.items() if v is not None}

        except Exception as e:
            print(f"⚠️  Could not retrieve metrics: {e}")
            return {}

    def validate_model(
        self, version_info: Dict, current_production: Optional[Dict] = None
    ) -> Tuple[bool, str]:
        """
        Validate model before promotion.

        Args:
            version_info: Candidate model version info
            current_production: Current production model info (if any)

        Returns:
            Tuple of (is_valid, reason)
        """
        # Get candidate metrics
        candidate_metrics = self.get_model_metrics(version_info["run_id"])

        if not candidate_metrics:
            return False, "No metrics available for candidate model"

        candidate_rmse = candidate_metrics.get("rmse")

        if candidate_rmse is None:
            return False, "RMSE metric not found"

        # Check absolute threshold
        if candidate_rmse > self.rmse_threshold:
            return (
                False,
                f"RMSE {candidate_rmse:.4f} exceeds threshold {self.rmse_threshold:.4f}",
            )

        # If there's a production model, check improvement
        if current_production:
            prod_metrics = self.get_model_metrics(current_production["run_id"])
            prod_rmse = prod_metrics.get("rmse")

            if prod_rmse:
                improvement = ((prod_rmse - candidate_rmse) / prod_rmse) * 100

                if improvement < self.improvement_threshold:
                    return (
                        False,
                        f"Improvement {improvement:.2f}% is below threshold {self.improvement_threshold:.2f}%",
                    )

        return True, "All validation checks passed"

    def promote_model(
        self, version: str, archive_existing: bool = True, dry_run: bool = False
    ) -> bool:
        """
        Promote model to production.

        Args:
            version: Model version to promote
            archive_existing: Whether to archive existing production models
            dry_run: If True, don't actually promote

        Returns:
            True if promotion successful, False otherwise
        """
        try:
            if dry_run:
                print(
                    f"🔍 DRY RUN: Would promote {self.model_name} v{version} to Production"
                )
                if archive_existing:
                    print(f"🔍 DRY RUN: Would archive existing production versions")
                return True

            self.client.transition_model_version_stage(
                name=self.model_name,
                version=version,
                stage="Production",
                archive_existing_versions=archive_existing,
            )

            print(
                f"✅ Successfully promoted {self.model_name} v{version} to Production"
            )

            if archive_existing:
                print("   Existing production versions archived")

            return True

        except Exception as e:
            print(f"❌ Failed to promote model: {e}")
            return False

    def display_comparison(
        self, candidate: Dict, current_production: Optional[Dict] = None
    ):
        """
        Display comparison between candidate and current production model.

        Args:
            candidate: Candidate model info
            current_production: Current production model info
        """
        print("\n" + "=" * 80)
        print("MODEL COMPARISON")
        print("=" * 80)

        # Candidate model
        candidate_metrics = self.get_model_metrics(candidate["run_id"])
        print(f"\n📦 Candidate Model (Version {candidate['version']}):")
        print(f"   Run ID: {candidate['run_id']}")

        if candidate_metrics:
            if "rmse" in candidate_metrics:
                print(f"   RMSE: {candidate_metrics['rmse']:.4f}")
            if "mae" in candidate_metrics:
                print(f"   MAE: {candidate_metrics['mae']:.4f}")
            if "mape" in candidate_metrics:
                print(f"   MAPE: {candidate_metrics['mape']:.4f}%")
            if "training_time" in candidate_metrics:
                print(f"   Training Time: {candidate_metrics['training_time']:.2f}s")
            if "model_size" in candidate_metrics:
                print(f"   Model Size: {candidate_metrics['model_size']:.2f} MB")
        else:
            print("   ⚠️  No metrics available")

        # Current production model
        if current_production:
            prod_metrics = self.get_model_metrics(current_production["run_id"])
            print(
                f"\n🏭 Current Production Model (Version {current_production['version']}):"
            )
            print(f"   Run ID: {current_production['run_id']}")

            if prod_metrics:
                if "rmse" in prod_metrics:
                    print(f"   RMSE: {prod_metrics['rmse']:.4f}")
                if "mae" in prod_metrics:
                    print(f"   MAE: {prod_metrics['mae']:.4f}")
                if "mape" in prod_metrics:
                    print(f"   MAPE: {prod_metrics['mape']:.4f}%")
            else:
                print("   ⚠️  No metrics available")

            # Calculate improvements
            if candidate_metrics and prod_metrics:
                print("\n📊 Improvements:")

                if "rmse" in candidate_metrics and "rmse" in prod_metrics:
                    rmse_improvement = (
                        (prod_metrics["rmse"] - candidate_metrics["rmse"])
                        / prod_metrics["rmse"]
                    ) * 100
                    print(f"   RMSE: {rmse_improvement:+.2f}%")

                if "mae" in candidate_metrics and "mae" in prod_metrics:
                    mae_improvement = (
                        (prod_metrics["mae"] - candidate_metrics["mae"])
                        / prod_metrics["mae"]
                    ) * 100
                    print(f"   MAE: {mae_improvement:+.2f}%")

        else:
            print("\n🏭 Current Production Model: None")
            print("   This will be the first production deployment")

        print("\n" + "=" * 80)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Promote ML model to production in MLflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Promote latest model with validation
  python promote_model_to_production.py

  # Promote specific version
  python promote_model_to_production.py --version 5

  # Skip validation (force promotion)
  python promote_model_to_production.py --version 3 --force

  # Dry run (show what would happen)
  python promote_model_to_production.py --dry-run

  # Custom thresholds
  python promote_model_to_production.py --rmse-threshold 53.0 --improvement-threshold 0.5
        """,
    )

    parser.add_argument(
        "--model-name",
        default=os.environ.get("MLFLOW_MODEL_NAME", "demand_forecasting_catboost"),
        help="Name of the registered model",
    )

    parser.add_argument(
        "--tracking-uri",
        default=os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"),
        help="MLflow tracking server URI",
    )

    parser.add_argument(
        "--version",
        type=int,
        default=None,
        help="Specific version to promote (default: latest)",
    )

    parser.add_argument(
        "--rmse-threshold",
        type=float,
        default=52.0,
        help="Maximum acceptable RMSE (default: 52.0)",
    )

    parser.add_argument(
        "--improvement-threshold",
        type=float,
        default=1.0,
        help="Minimum improvement %% required (default: 1.0)",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip validation checks and force promotion",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without actually promoting",
    )

    parser.add_argument(
        "--no-archive",
        action="store_true",
        help="Don't archive existing production versions",
    )

    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Skip approval prompt and promote automatically",
    )

    args = parser.parse_args()

    # Create promoter
    promoter = ModelPromoter(
        model_name=args.model_name,
        tracking_uri=args.tracking_uri,
        rmse_threshold=args.rmse_threshold,
        improvement_threshold=args.improvement_threshold,
    )

    # Connect to MLflow
    if not promoter.connect():
        sys.exit(1)

    # Get candidate version
    if args.version:
        candidate = {
            "version": str(args.version),
            "run_id": None,  # Will be fetched when needed
            "stage": "Unknown",
        }
        # Get run_id for the specific version
        try:
            version_details = promoter.client.get_model_version(
                name=args.model_name, version=str(args.version)
            )
            candidate["run_id"] = version_details.run_id
        except Exception as e:
            print(f"❌ Could not find version {args.version}: {e}")
            sys.exit(1)
    else:
        candidate = promoter.get_latest_version(stage="None")
        if not candidate:
            print("❌ No candidate models found (stage='None')")
            print("   Models must be registered first before promotion")
            sys.exit(1)

    # Get current production model
    current_production = promoter.get_current_production_model()

    # Display comparison
    promoter.display_comparison(candidate, current_production)

    # Validate model (unless force flag is set)
    if not args.force:
        print("\n🔍 Validating candidate model...")
        is_valid, reason = promoter.validate_model(candidate, current_production)

        if is_valid:
            print(f"✅ Validation passed: {reason}")
        else:
            print(f"❌ Validation failed: {reason}")
            print("\n   Use --force to skip validation and promote anyway")
            sys.exit(1)
    else:
        print("\n⚠️  Skipping validation (--force flag set)")

    # Get approval (unless auto-approve or dry-run)
    if not args.auto_approve and not args.dry_run:
        print(f"\n❓ Promote {args.model_name} v{candidate['version']} to Production?")
        response = input("   Type 'yes' to confirm: ")

        if response.lower() != "yes":
            print("❌ Promotion cancelled by user")
            sys.exit(0)

    # Promote model
    success = promoter.promote_model(
        version=candidate["version"],
        archive_existing=not args.no_archive,
        dry_run=args.dry_run,
    )

    if success:
        if not args.dry_run:
            print("\n🎉 Model promotion complete!")
            print(f"\n   Model: {args.model_name}")
            print(f"   Version: {candidate['version']}")
            print(f"   Stage: Production")
            print(f"\n   Load with:")
            print(
                f"   model = mlflow.pyfunc.load_model('models:/{args.model_name}/Production')"
            )
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
