#!/usr/bin/env python3
"""
Parallel Optuna Optimization Monitor

Monitors real-time progress of distributed Optuna optimization across multiple workers.
Shows completed trials, running trials, and best RMSE value.

Usage:
    python scripts/advanced_features/monitor_parallel_optimization.py

    # With custom study name
    python scripts/advanced_features/monitor_parallel_optimization.py --study-name my_study

    # With custom update interval
    python scripts/advanced_features/monitor_parallel_optimization.py --interval 2

Requirements:
    - Optuna with PostgreSQL storage
    - PostgreSQL database accessible
    - Study must exist before monitoring

Author: MLOps Team
Version: 2.1.0
Date: January 3, 2025
"""

import argparse
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional

try:
    import optuna
    from optuna.storages import RDBStorage
except ImportError:
    print(
        "Error: Optuna not installed. Install with: pip install optuna psycopg2-binary"
    )
    sys.exit(1)


class OptimizationMonitor:
    """Monitor and display Optuna optimization progress in real-time."""

    def __init__(self, study_name: str, storage_url: str, update_interval: int = 5):
        """
        Initialize optimization monitor.

        Args:
            study_name: Name of the Optuna study to monitor
            storage_url: PostgreSQL connection URL
            update_interval: Seconds between updates
        """
        self.study_name = study_name
        self.storage_url = storage_url
        self.update_interval = update_interval
        self.storage = None
        self.study = None

    def connect(self) -> bool:
        """
        Connect to Optuna storage and load study.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Create storage with connection pooling
            self.storage = RDBStorage(
                url=self.storage_url,
                engine_kwargs={
                    "pool_size": 5,
                    "max_overflow": 10,
                    "pool_pre_ping": True,
                    "pool_recycle": 3600,
                    "connect_args": {
                        "connect_timeout": 10,
                    },
                },
            )

            # Load study
            self.study = optuna.load_study(
                study_name=self.study_name, storage=self.storage
            )

            print(f"✅ Connected to study: {self.study_name}")
            print(f"   Storage: {self.storage_url}")
            print(f"   Direction: {self.study.direction.name}")
            print(f"   Sampler: {self.study.sampler.__class__.__name__}")
            print()

            return True

        except Exception as e:
            print(f"❌ Failed to connect: {e}")
            return False

    def get_statistics(self) -> Dict:
        """
        Get current study statistics.

        Returns:
            Dictionary with study statistics
        """
        # Reload study to get latest data
        self.study = optuna.load_study(study_name=self.study_name, storage=self.storage)

        # Count trials by state
        completed = [
            t for t in self.study.trials if t.state == optuna.trial.TrialState.COMPLETE
        ]
        running = [
            t for t in self.study.trials if t.state == optuna.trial.TrialState.RUNNING
        ]
        failed = [
            t for t in self.study.trials if t.state == optuna.trial.TrialState.FAIL
        ]
        pruned = [
            t for t in self.study.trials if t.state == optuna.trial.TrialState.PRUNED
        ]
        waiting = [
            t for t in self.study.trials if t.state == optuna.trial.TrialState.WAITING
        ]

        # Calculate statistics
        stats = {
            "total": len(self.study.trials),
            "completed": len(completed),
            "running": len(running),
            "failed": len(failed),
            "pruned": len(pruned),
            "waiting": len(waiting),
            "best_value": self.study.best_value if self.study.best_trial else None,
            "best_trial_number": (
                self.study.best_trial.number if self.study.best_trial else None
            ),
            "best_params": (
                self.study.best_trial.params if self.study.best_trial else None
            ),
        }

        # Calculate recent trials per minute
        if len(completed) > 0:
            recent_completed = [t for t in completed if t.datetime_complete]
            if len(recent_completed) > 1:
                time_diffs = []
                for i in range(1, min(10, len(recent_completed))):
                    if (
                        recent_completed[-i].datetime_complete
                        and recent_completed[-i - 1].datetime_complete
                    ):
                        diff = (
                            recent_completed[-i].datetime_complete
                            - recent_completed[-i - 1].datetime_complete
                        ).total_seconds()
                        if diff > 0:
                            time_diffs.append(diff)

                if time_diffs:
                    avg_time_per_trial = sum(time_diffs) / len(time_diffs)
                    stats["trials_per_minute"] = (
                        60 / avg_time_per_trial if avg_time_per_trial > 0 else 0
                    )
                else:
                    stats["trials_per_minute"] = 0
            else:
                stats["trials_per_minute"] = 0
        else:
            stats["trials_per_minute"] = 0

        return stats

    def format_display(self, stats: Dict) -> str:
        """
        Format statistics for display.

        Args:
            stats: Statistics dictionary

        Returns:
            Formatted string for display
        """
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Progress bar
        if stats["total"] > 0:
            completed_pct = (stats["completed"] / stats["total"]) * 100
            bar_length = 30
            filled = int(bar_length * stats["completed"] / stats["total"])
            bar = "█" * filled + "░" * (bar_length - filled)
        else:
            completed_pct = 0
            bar = "░" * 30

        # Format best value
        if stats["best_value"] is not None:
            best_str = f"{stats['best_value']:.4f}"
        else:
            best_str = "N/A"

        # Build display string
        lines = [
            f"\r[{timestamp}] Study: {self.study_name}",
            f"",
            f"Progress: [{bar}] {completed_pct:.1f}%",
            f"",
            f"Trials:    Total: {stats['total']:>4}  |  Completed: {stats['completed']:>4}  |  Running: {stats['running']:>2}",
            f"Status:    Failed: {stats['failed']:>3}  |  Pruned: {stats['pruned']:>4}  |  Waiting: {stats['waiting']:>2}",
            f"",
            (
                f"Best RMSE: {best_str}  (Trial #{stats['best_trial_number']})"
                if stats["best_trial_number"]
                else f"Best RMSE: {best_str}"
            ),
            (
                f"Throughput: {stats['trials_per_minute']:.2f} trials/min"
                if stats["trials_per_minute"] > 0
                else "Throughput: Calculating..."
            ),
        ]

        # Add best params (limited to avoid clutter)
        if stats["best_params"]:
            lines.append("")
            lines.append("Best Parameters:")
            for key, value in list(stats["best_params"].items())[:5]:
                if isinstance(value, float):
                    lines.append(f"  {key}: {value:.4f}")
                else:
                    lines.append(f"  {key}: {value}")

        return "\n".join(lines)

    def monitor(self, max_duration: Optional[int] = None):
        """
        Start monitoring optimization progress.

        Args:
            max_duration: Maximum monitoring duration in seconds (None for infinite)
        """
        start_time = time.time()

        print(f"🔍 Monitoring optimization progress...")
        print(f"   Update interval: {self.update_interval} seconds")
        print(f"   Press Ctrl+C to stop")
        print()

        try:
            iteration = 0
            while True:
                # Check if max duration reached
                if max_duration and (time.time() - start_time) > max_duration:
                    print("\n⏱️  Maximum monitoring duration reached")
                    break

                # Get and display statistics
                stats = self.get_statistics()
                display = self.format_display(stats)

                # Clear screen and display (first iteration only shows, subsequent overwrites)
                if iteration == 0:
                    print(display)
                else:
                    # Move cursor up and overwrite
                    lines_count = display.count("\n") + 1
                    print(f"\033[{lines_count}A", end="")
                    print(display)

                iteration += 1
                time.sleep(self.update_interval)

        except KeyboardInterrupt:
            print("\n\n⏹️  Monitoring stopped by user")
        except Exception as e:
            print(f"\n\n❌ Error during monitoring: {e}")

    def get_summary(self) -> str:
        """
        Get final summary of optimization.

        Returns:
            Summary string
        """
        stats = self.get_statistics()

        summary = [
            "",
            "=" * 80,
            "OPTIMIZATION SUMMARY",
            "=" * 80,
            "",
            f"Study Name: {self.study_name}",
            f"Total Trials: {stats['total']}",
            f"Completed: {stats['completed']}",
            f"Running: {stats['running']}",
            f"Failed: {stats['failed']}",
            f"Pruned: {stats['pruned']}",
            "",
            (
                f"Best RMSE: {stats['best_value']:.4f}"
                if stats["best_value"]
                else "Best RMSE: N/A"
            ),
            (
                f"Best Trial: #{stats['best_trial_number']}"
                if stats["best_trial_number"]
                else "Best Trial: N/A"
            ),
            "",
        ]

        if stats["best_params"]:
            summary.append("Best Parameters:")
            for key, value in stats["best_params"].items():
                if isinstance(value, float):
                    summary.append(f"  {key}: {value:.6f}")
                else:
                    summary.append(f"  {key}: {value}")

        summary.extend(["", "=" * 80, ""])

        return "\n".join(summary)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Monitor parallel Optuna optimization progress",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Monitor with default settings
  python monitor_parallel_optimization.py

  # Monitor specific study
  python monitor_parallel_optimization.py --study-name my_custom_study

  # Update every 2 seconds
  python monitor_parallel_optimization.py --interval 2

  # Monitor for 5 minutes then show summary
  python monitor_parallel_optimization.py --duration 300
        """,
    )

    parser.add_argument(
        "--study-name",
        default=os.environ.get("OPTUNA_STUDY_NAME", "demand_forecasting_study"),
        help="Name of the Optuna study to monitor",
    )

    parser.add_argument(
        "--storage-url",
        default=os.environ.get(
            "OPTUNA_STORAGE_URL", "postgresql://airflow:airflow@localhost:5432/optuna"
        ),
        help="PostgreSQL connection URL",
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Update interval in seconds (default: 5)",
    )

    parser.add_argument(
        "--duration",
        type=int,
        default=None,
        help="Maximum monitoring duration in seconds (default: infinite)",
    )

    parser.add_argument(
        "--summary", action="store_true", help="Show summary and exit (no monitoring)"
    )

    args = parser.parse_args()

    # Create monitor
    monitor = OptimizationMonitor(
        study_name=args.study_name,
        storage_url=args.storage_url,
        update_interval=args.interval,
    )

    # Connect to storage
    if not monitor.connect():
        sys.exit(1)

    # Show summary or start monitoring
    if args.summary:
        print(monitor.get_summary())
    else:
        monitor.monitor(max_duration=args.duration)
        print(monitor.get_summary())


if __name__ == "__main__":
    main()
