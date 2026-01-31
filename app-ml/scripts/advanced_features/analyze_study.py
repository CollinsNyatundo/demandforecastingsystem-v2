#!/usr/bin/env python3
"""
Optuna Study Analyzer and Cleanup Utility

Analyzes Optuna study performance, creates visualizations, and provides
cleanup utilities for failed trials and old studies.

Usage:
    # Analyze study and create visualizations
    python scripts/advanced_features/analyze_study.py

    # Analyze specific study
    python scripts/advanced_features/analyze_study.py --study-name my_study

    # Clean up failed trials
    python scripts/advanced_features/analyze_study.py --cleanup-failed

    # Export study data to CSV
    python scripts/advanced_features/analyze_study.py --export study_data.csv

    # Compare multiple studies
    python scripts/advanced_features/analyze_study.py --compare study1 study2 study3

Requirements:
    - Optuna with PostgreSQL storage
    - Plotly for visualizations
    - Pandas for data analysis

Author: MLOps Team
Version: 2.1.0
Date: January 3, 2025
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

try:
    import optuna
    from optuna.storages import RDBStorage
except ImportError:
    print(
        "Error: Optuna not installed. Install with: pip install optuna psycopg2-binary"
    )
    sys.exit(1)

try:
    import pandas as pd
except ImportError:
    print("Error: Pandas not installed. Install with: pip install pandas")
    sys.exit(1)

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    print("Warning: Plotly not installed. Visualizations disabled.")
    print("Install with: pip install plotly")


class StudyAnalyzer:
    """Analyze and manage Optuna studies."""

    def __init__(self, study_name: str, storage_url: str):
        """
        Initialize study analyzer.

        Args:
            study_name: Name of the Optuna study
            storage_url: PostgreSQL connection URL
        """
        self.study_name = study_name
        self.storage_url = storage_url
        self.storage = None
        self.study = None

    def connect(self) -> bool:
        """
        Connect to Optuna storage and load study.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.storage = RDBStorage(
                url=self.storage_url,
                engine_kwargs={
                    "pool_size": 5,
                    "max_overflow": 10,
                    "pool_pre_ping": True,
                    "pool_recycle": 3600,
                },
            )

            self.study = optuna.load_study(
                study_name=self.study_name, storage=self.storage
            )

            print(f"✅ Connected to study: {self.study_name}")
            print(f"   Total trials: {len(self.study.trials)}")
            print()

            return True

        except Exception as e:
            print(f"❌ Failed to connect: {e}")
            return False

    def get_statistics(self) -> Dict:
        """
        Calculate study statistics.

        Returns:
            Dictionary with statistics
        """
        trials = self.study.trials

        # Filter by state
        completed = [t for t in trials if t.state == optuna.trial.TrialState.COMPLETE]
        running = [t for t in trials if t.state == optuna.trial.TrialState.RUNNING]
        failed = [t for t in trials if t.state == optuna.trial.TrialState.FAIL]
        pruned = [t for t in trials if t.state == optuna.trial.TrialState.PRUNED]

        # Extract values from completed trials
        values = [t.value for t in completed]

        stats = {
            "total_trials": len(trials),
            "completed": len(completed),
            "running": len(running),
            "failed": len(failed),
            "pruned": len(pruned),
            "best_value": self.study.best_value if self.study.best_trial else None,
            "best_trial": (
                self.study.best_trial.number if self.study.best_trial else None
            ),
            "best_params": (
                self.study.best_trial.params if self.study.best_trial else None
            ),
        }

        if values:
            stats.update(
                {
                    "mean_value": sum(values) / len(values),
                    "min_value": min(values),
                    "max_value": max(values),
                    "median_value": sorted(values)[len(values) // 2],
                    "std_value": (
                        sum((x - stats["mean_value"]) ** 2 for x in values)
                        / len(values)
                    )
                    ** 0.5,
                }
            )

        # Calculate duration statistics
        durations = []
        for t in completed:
            if t.datetime_complete and t.datetime_start:
                duration = (t.datetime_complete - t.datetime_start).total_seconds()
                durations.append(duration)

        if durations:
            stats.update(
                {
                    "mean_duration": sum(durations) / len(durations),
                    "min_duration": min(durations),
                    "max_duration": max(durations),
                }
            )

        return stats

    def print_summary(self):
        """Print study summary."""
        stats = self.get_statistics()

        print("=" * 80)
        print("STUDY SUMMARY")
        print("=" * 80)
        print()
        print(f"Study Name: {self.study_name}")
        print(f"Direction: {self.study.direction.name}")
        print(f"Sampler: {self.study.sampler.__class__.__name__}")
        print()
        print("Trial Statistics:")
        print(f"  Total Trials: {stats['total_trials']}")
        print(f"  Completed: {stats['completed']}")
        print(f"  Running: {stats['running']}")
        print(f"  Failed: {stats['failed']}")
        print(f"  Pruned: {stats['pruned']}")
        print()

        if stats["best_value"] is not None:
            print("Best Trial:")
            print(f"  Trial #{stats['best_trial']}")
            print(f"  Value (RMSE): {stats['best_value']:.6f}")
            print(f"  Parameters:")
            for key, value in stats["best_params"].items():
                if isinstance(value, float):
                    print(f"    {key}: {value:.6f}")
                else:
                    print(f"    {key}: {value}")
            print()

        if "mean_value" in stats:
            print("Value Statistics:")
            print(f"  Mean: {stats['mean_value']:.6f}")
            print(f"  Std: {stats['std_value']:.6f}")
            print(f"  Min: {stats['min_value']:.6f}")
            print(f"  Max: {stats['max_value']:.6f}")
            print(f"  Median: {stats['median_value']:.6f}")
            print()

        if "mean_duration" in stats:
            print("Duration Statistics:")
            print(f"  Mean: {stats['mean_duration']:.2f} seconds")
            print(f"  Min: {stats['min_duration']:.2f} seconds")
            print(f"  Max: {stats['max_duration']:.2f} seconds")
            print()

        print("=" * 80)

    def create_visualizations(self, output_dir: str = "."):
        """
        Create study visualizations.

        Args:
            output_dir: Directory to save visualizations
        """
        if not PLOTLY_AVAILABLE:
            print("⚠️  Plotly not available. Skipping visualizations.")
            return

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        completed_trials = [
            t for t in self.study.trials if t.state == optuna.trial.TrialState.COMPLETE
        ]

        if not completed_trials:
            print("⚠️  No completed trials. Cannot create visualizations.")
            return

        # 1. Optimization History
        self._create_optimization_history(completed_trials, output_path)

        # 2. Parameter Importance
        self._create_param_importance(output_path)

        # 3. Parallel Coordinate Plot
        self._create_parallel_coordinate(completed_trials, output_path)

        # 4. Trial Duration Analysis
        self._create_duration_analysis(completed_trials, output_path)

        print(f"✅ Visualizations saved to {output_path}/")

    def _create_optimization_history(self, trials: List, output_path: Path):
        """Create optimization history plot."""
        trial_numbers = [t.number for t in trials]
        values = [t.value for t in trials]

        # Calculate cumulative minimum
        cummin = []
        current_min = float("inf")
        for v in values:
            current_min = min(current_min, v)
            cummin.append(current_min)

        fig = go.Figure()

        # Add scatter plot of all trials
        fig.add_trace(
            go.Scatter(
                x=trial_numbers,
                y=values,
                mode="markers",
                name="Trial RMSE",
                marker=dict(
                    size=8,
                    color=values,
                    colorscale="Viridis",
                    showscale=True,
                    colorbar=dict(title="RMSE"),
                ),
                hovertemplate="Trial %{x}<br>RMSE: %{y:.4f}<extra></extra>",
            )
        )

        # Add best value line
        fig.add_trace(
            go.Scatter(
                x=trial_numbers,
                y=cummin,
                mode="lines",
                name="Best RMSE",
                line=dict(color="red", width=3),
                hovertemplate="Trial %{x}<br>Best RMSE: %{y:.4f}<extra></extra>",
            )
        )

        fig.update_layout(
            title=f"Optimization History: {self.study_name}",
            xaxis_title="Trial Number",
            yaxis_title="RMSE",
            hovermode="closest",
            height=600,
        )

        output_file = output_path / "optimization_history.html"
        fig.write_html(str(output_file))
        print(f"  📊 Created: {output_file}")

    def _create_param_importance(self, output_path: Path):
        """Create parameter importance plot."""
        try:
            from optuna.visualization import plot_param_importances

            fig = plot_param_importances(self.study)
            output_file = output_path / "param_importance.html"
            fig.write_html(str(output_file))
            print(f"  📊 Created: {output_file}")

        except Exception as e:
            print(f"  ⚠️  Could not create parameter importance plot: {e}")

    def _create_parallel_coordinate(self, trials: List, output_path: Path):
        """Create parallel coordinate plot."""
        try:
            from optuna.visualization import plot_parallel_coordinate

            fig = plot_parallel_coordinate(self.study)
            output_file = output_path / "parallel_coordinate.html"
            fig.write_html(str(output_file))
            print(f"  📊 Created: {output_file}")

        except Exception as e:
            print(f"  ⚠️  Could not create parallel coordinate plot: {e}")

    def _create_duration_analysis(self, trials: List, output_path: Path):
        """Create trial duration analysis plot."""
        durations = []
        trial_numbers = []

        for t in trials:
            if t.datetime_complete and t.datetime_start:
                duration = (t.datetime_complete - t.datetime_start).total_seconds()
                durations.append(duration)
                trial_numbers.append(t.number)

        if not durations:
            return

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=trial_numbers,
                y=durations,
                mode="markers",
                name="Duration",
                marker=dict(size=8, color="blue"),
                hovertemplate="Trial %{x}<br>Duration: %{y:.2f}s<extra></extra>",
            )
        )

        # Add moving average
        window = min(10, len(durations))
        if len(durations) >= window:
            moving_avg = []
            for i in range(len(durations)):
                start = max(0, i - window + 1)
                moving_avg.append(sum(durations[start : i + 1]) / (i - start + 1))

            fig.add_trace(
                go.Scatter(
                    x=trial_numbers,
                    y=moving_avg,
                    mode="lines",
                    name=f"{window}-trial Moving Avg",
                    line=dict(color="red", width=2),
                )
            )

        fig.update_layout(
            title=f"Trial Duration Analysis: {self.study_name}",
            xaxis_title="Trial Number",
            yaxis_title="Duration (seconds)",
            height=600,
        )

        output_file = output_path / "duration_analysis.html"
        fig.write_html(str(output_file))
        print(f"  📊 Created: {output_file}")

    def export_to_csv(self, output_file: str):
        """
        Export study data to CSV.

        Args:
            output_file: Path to output CSV file
        """
        data = []

        for trial in self.study.trials:
            row = {
                "trial_number": trial.number,
                "state": trial.state.name,
                "value": trial.value,
                "datetime_start": trial.datetime_start,
                "datetime_complete": trial.datetime_complete,
            }

            # Add duration
            if trial.datetime_complete and trial.datetime_start:
                duration = (
                    trial.datetime_complete - trial.datetime_start
                ).total_seconds()
                row["duration_seconds"] = duration

            # Add parameters
            for key, value in trial.params.items():
                row[f"param_{key}"] = value

            # Add user attributes
            for key, value in trial.user_attrs.items():
                row[f"attr_{key}"] = value

            data.append(row)

        df = pd.DataFrame(data)
        df.to_csv(output_file, index=False)

        print(f"✅ Exported {len(df)} trials to {output_file}")

    def cleanup_failed_trials(self, dry_run: bool = False) -> int:
        """
        Clean up failed trials.

        Args:
            dry_run: If True, don't actually delete

        Returns:
            Number of trials that would be/were deleted
        """
        failed = [
            t for t in self.study.trials if t.state == optuna.trial.TrialState.FAIL
        ]

        if not failed:
            print("✅ No failed trials to clean up")
            return 0

        print(f"Found {len(failed)} failed trials")

        if dry_run:
            print("🔍 DRY RUN: Would delete these trials")
            for t in failed[:5]:  # Show first 5
                print(f"  Trial #{t.number}: {t.state.name}")
            if len(failed) > 5:
                print(f"  ... and {len(failed) - 5} more")
            return len(failed)

        # Note: Optuna doesn't support individual trial deletion
        # Best practice is to create a new study with only successful trials
        print("⚠️  Individual trial deletion not supported by Optuna")
        print("    Recommendation: Create a new study with successful trials only")
        print("    Use --export to save data, then recreate study")

        return len(failed)

    def list_all_studies(self) -> List[str]:
        """
        List all studies in storage.

        Returns:
            List of study names
        """
        summaries = self.storage.get_all_study_summaries()

        print("\n" + "=" * 80)
        print("ALL STUDIES IN STORAGE")
        print("=" * 80)

        for summary in summaries:
            print(f"\n📚 {summary.study_name}")
            print(f"   Direction: {summary.direction.name}")
            print(f"   Trials: {summary.n_trials}")
            print(f"   Created: {summary.datetime_start}")

        print("\n" + "=" * 80)

        return [s.study_name for s in summaries]


def compare_studies(study_names: List[str], storage_url: str, output_dir: str = "."):
    """
    Compare multiple studies.

    Args:
        study_names: List of study names to compare
        storage_url: PostgreSQL connection URL
        output_dir: Directory to save comparison plots
    """
    if not PLOTLY_AVAILABLE:
        print("⚠️  Plotly not available. Cannot create comparison.")
        return

    storage = RDBStorage(url=storage_url)

    fig = go.Figure()

    for study_name in study_names:
        try:
            study = optuna.load_study(study_name=study_name, storage=storage)

            completed = [
                t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE
            ]

            if not completed:
                print(f"⚠️  No completed trials in {study_name}")
                continue

            # Calculate cumulative minimum
            values = [t.value for t in completed]
            cummin = []
            current_min = float("inf")
            for v in values:
                current_min = min(current_min, v)
                cummin.append(current_min)

            fig.add_trace(
                go.Scatter(
                    x=list(range(len(cummin))),
                    y=cummin,
                    mode="lines",
                    name=study_name,
                    line=dict(width=2),
                )
            )

        except Exception as e:
            print(f"⚠️  Could not load {study_name}: {e}")

    fig.update_layout(
        title="Study Comparison: Best RMSE Over Trials",
        xaxis_title="Trial Number",
        yaxis_title="Best RMSE",
        hovermode="closest",
        height=600,
    )

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    output_file = output_path / "study_comparison.html"
    fig.write_html(str(output_file))

    print(f"✅ Comparison saved to {output_file}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze and manage Optuna studies",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze study and show summary
  python analyze_study.py

  # Create visualizations
  python analyze_study.py --visualize

  # Export to CSV
  python analyze_study.py --export study_data.csv

  # Clean up failed trials (dry run)
  python analyze_study.py --cleanup-failed --dry-run

  # Compare multiple studies
  python analyze_study.py --compare study1 study2 study3

  # List all studies
  python analyze_study.py --list-studies
        """,
    )

    parser.add_argument(
        "--study-name",
        default=os.environ.get("OPTUNA_STUDY_NAME", "demand_forecasting_study"),
        help="Name of the Optuna study",
    )

    parser.add_argument(
        "--storage-url",
        default=os.environ.get(
            "OPTUNA_STORAGE_URL", "postgresql://airflow:airflow@localhost:5432/optuna"
        ),
        help="PostgreSQL connection URL",
    )

    parser.add_argument(
        "--visualize", action="store_true", help="Create visualization plots"
    )

    parser.add_argument(
        "--output-dir",
        default="./study_analysis",
        help="Output directory for visualizations (default: ./study_analysis)",
    )

    parser.add_argument(
        "--export", metavar="FILE", help="Export study data to CSV file"
    )

    parser.add_argument(
        "--cleanup-failed", action="store_true", help="Clean up failed trials"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run for cleanup (don't actually delete)",
    )

    parser.add_argument(
        "--compare", nargs="+", metavar="STUDY", help="Compare multiple studies"
    )

    parser.add_argument(
        "--list-studies", action="store_true", help="List all studies in storage"
    )

    args = parser.parse_args()

    # Handle study comparison
    if args.compare:
        compare_studies(args.compare, args.storage_url, args.output_dir)
        return

    # Create analyzer
    analyzer = StudyAnalyzer(args.study_name, args.storage_url)

    # Connect to storage
    if not analyzer.connect():
        sys.exit(1)

    # List all studies
    if args.list_studies:
        analyzer.list_all_studies()
        return

    # Print summary (always)
    analyzer.print_summary()

    # Create visualizations
    if args.visualize:
        print("\n📊 Creating visualizations...")
        analyzer.create_visualizations(args.output_dir)

    # Export to CSV
    if args.export:
        print(f"\n💾 Exporting to CSV...")
        analyzer.export_to_csv(args.export)

    # Cleanup failed trials
    if args.cleanup_failed:
        print(f"\n🧹 Cleaning up failed trials...")
        count = analyzer.cleanup_failed_trials(dry_run=args.dry_run)
        if count > 0 and not args.dry_run:
            print(f"   Use --export and recreate study to remove failed trials")


if __name__ == "__main__":
    main()
