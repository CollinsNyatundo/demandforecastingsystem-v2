#!/usr/bin/env python3
"""Data Drift Detection System for Demand Forecasting.

Detects statistical drift in input features and target variables using
multiple statistical tests. Stores drift history in PostgreSQL for tracking.

Based on Priority 3 requirements and pg-aiguide best practices.

Usage:
    python scripts/production_ops/detect_data_drift.py --reference-data data/reference.csv
    python scripts/production_ops/detect_data_drift.py --production-data s3://bucket/prod/data.csv
    python scripts/production_ops/detect_data_drift.py --auto-detect --alert
"""

import argparse
import logging
import os
import smtplib
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import numpy as np
import pandas as pd
import s3fs
from scipy import stats
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

Base = declarative_base()


class DriftRecord(Base):
    """SQLAlchemy model for drift detection records."""

    __tablename__ = "drift_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    check_timestamp = Column(DateTime, nullable=False, index=True)
    feature_name = Column(String(255), nullable=False, index=True)
    drift_detected = Column(Boolean, nullable=False, index=True)
    drift_score = Column(Float, nullable=False)
    test_statistic = Column(Float, nullable=True)
    p_value = Column(Float, nullable=True)
    test_method = Column(String(50), nullable=False)
    reference_mean = Column(Float, nullable=True)
    reference_std = Column(Float, nullable=True)
    production_mean = Column(Float, nullable=True)
    production_std = Column(Float, nullable=True)
    metadata = Column(JSON, nullable=True)
    alert_sent = Column(Boolean, default=False)


class DriftDetector:
    """Statistical drift detector with PostgreSQL persistence.

    Implements multiple drift detection methods:
    - Kolmogorov-Smirnov test (continuous features)
    - Chi-square test (categorical features)
    - Population Stability Index (PSI)
    - Wasserstein distance

    Attributes:
        storage_url: PostgreSQL connection string
        alpha: Significance level for statistical tests (default: 0.05)
        psi_threshold: PSI threshold for drift detection (default: 0.2)
        wasserstein_threshold: Wasserstein distance threshold (default: 0.1)
    """

    def __init__(
        self,
        storage_url: str | None = None,
        alpha: float = 0.05,
        psi_threshold: float = 0.2,
        wasserstein_threshold: float = 0.1,
    ):
        """Initialize drift detector with PostgreSQL backend.

        Args:
            storage_url: PostgreSQL URL (default: from env)
            alpha: Significance level for statistical tests
            psi_threshold: PSI threshold (> 0.2 indicates drift)
            wasserstein_threshold: Wasserstein distance threshold
        """
        self.alpha = alpha
        self.psi_threshold = psi_threshold
        self.wasserstein_threshold = wasserstein_threshold

        # Get storage URL from environment or parameter
        self.storage_url = storage_url or os.getenv(
            "DRIFT_STORAGE_URL", "postgresql://airflow:airflow@localhost:5432/optuna"
        )

        # Create engine with connection pooling (pg-aiguide best practices)
        self.engine = create_engine(
            self.storage_url,
            poolclass=QueuePool,
            pool_size=3,
            max_overflow=5,
            pool_pre_ping=True,
            pool_recycle=3600,
            connect_args={
                "connect_timeout": 10,
                "options": "-c statement_timeout=30000",
            },
        )

        # Create tables if they don't exist
        Base.metadata.create_all(self.engine)

        # Create session factory
        self.Session = sessionmaker(bind=self.engine)

        logger.info(f"DriftDetector initialized with storage: {self.storage_url}")

    def detect_drift(
        self,
        reference_data: pd.DataFrame,
        production_data: pd.DataFrame,
        feature_cols: list[str] | None = None,
        categorical_cols: list[str] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Detect drift between reference and production data.

        Args:
            reference_data: Reference dataset (training data)
            production_data: Production dataset (recent predictions)
            feature_cols: List of features to check (default: all numeric)
            categorical_cols: List of categorical features

        Returns:
            Dictionary mapping feature names to drift results
        """
        logger.info("Starting drift detection...")
        logger.info(f"Reference data: {len(reference_data)} rows")
        logger.info(f"Production data: {len(production_data)} rows")

        # Auto-detect feature columns if not provided
        if feature_cols is None:
            feature_cols = reference_data.select_dtypes(
                include=[np.number]
            ).columns.tolist()

        if categorical_cols is None:
            categorical_cols = reference_data.select_dtypes(
                include=["object", "category"]
            ).columns.tolist()

        results = {}
        session = self.Session()

        try:
            # Check continuous features
            for feature in feature_cols:
                if feature not in production_data.columns:
                    logger.warning(
                        f"Feature '{feature}' not in production data, skipping"
                    )
                    continue

                result = self._test_continuous_drift(
                    reference_data[feature].dropna(),
                    production_data[feature].dropna(),
                    feature,
                )
                results[feature] = result

                # Store in database
                self._store_drift_record(session, feature, result)

            # Check categorical features
            for feature in categorical_cols:
                if feature not in production_data.columns:
                    logger.warning(
                        f"Feature '{feature}' not in production data, skipping"
                    )
                    continue

                result = self._test_categorical_drift(
                    reference_data[feature].dropna(),
                    production_data[feature].dropna(),
                    feature,
                )
                results[feature] = result

                # Store in database
                self._store_drift_record(session, feature, result)

            session.commit()
            logger.info(
                f"✅ Drift detection complete. Checked {len(results)} features."
            )

        except Exception as e:
            session.rollback()
            logger.error(f"Error during drift detection: {e}")
            raise
        finally:
            session.close()

        return results

    def _test_continuous_drift(
        self, reference: pd.Series, production: pd.Series, feature_name: str
    ) -> dict[str, Any]:
        """Test drift for continuous features using multiple methods.

        Methods:
        1. Kolmogorov-Smirnov test (distribution comparison)
        2. Population Stability Index (PSI)
        3. Wasserstein distance (distribution distance)

        Args:
            reference: Reference feature values
            production: Production feature values
            feature_name: Name of the feature

        Returns:
            Dictionary with test results and drift indicators
        """
        # Kolmogorov-Smirnov test
        ks_stat, ks_pvalue = stats.ks_2samp(reference, production)
        ks_drift = ks_pvalue < self.alpha

        # Population Stability Index (PSI)
        psi_score = self._calculate_psi(reference, production)
        psi_drift = psi_score > self.psi_threshold

        # Wasserstein distance
        wasserstein = stats.wasserstein_distance(reference, production)
        wasserstein_drift = wasserstein > self.wasserstein_threshold

        # Overall drift detection (if any test detects drift)
        drift_detected = ks_drift or psi_drift or wasserstein_drift

        # Calculate summary statistics
        ref_mean, ref_std = reference.mean(), reference.std()
        prod_mean, prod_std = production.mean(), production.std()

        result = {
            "drift_detected": drift_detected,
            "drift_score": max(ks_stat, psi_score, wasserstein),  # Worst score
            "tests": {
                "ks_test": {
                    "statistic": ks_stat,
                    "p_value": ks_pvalue,
                    "drift": ks_drift,
                },
                "psi": {"score": psi_score, "drift": psi_drift},
                "wasserstein": {"distance": wasserstein, "drift": wasserstein_drift},
            },
            "statistics": {
                "reference_mean": ref_mean,
                "reference_std": ref_std,
                "production_mean": prod_mean,
                "production_std": prod_std,
                "mean_shift": abs(prod_mean - ref_mean) / (ref_std + 1e-10),
                "std_ratio": prod_std / (ref_std + 1e-10),
            },
        }

        if drift_detected:
            logger.warning(f"⚠️  DRIFT DETECTED in '{feature_name}':")
            logger.warning(f"   KS test: p={ks_pvalue:.4f} (drift={ks_drift})")
            logger.warning(f"   PSI: {psi_score:.4f} (drift={psi_drift})")
            logger.warning(
                f"   Wasserstein: {wasserstein:.4f} (drift={wasserstein_drift})"
            )
        else:
            logger.info(f"✅ No drift in '{feature_name}'")

        return result

    def _test_categorical_drift(
        self, reference: pd.Series, production: pd.Series, feature_name: str
    ) -> dict[str, Any]:
        """Test drift for categorical features using chi-square test.

        Args:
            reference: Reference feature values
            production: Production feature values
            feature_name: Name of the feature

        Returns:
            Dictionary with test results and drift indicators
        """
        # Get value counts
        ref_counts = reference.value_counts(normalize=True).sort_index()
        prod_counts = production.value_counts(normalize=True).sort_index()

        # Align categories (handle new/missing categories)
        all_categories = sorted(set(ref_counts.index) | set(prod_counts.index))
        ref_aligned = ref_counts.reindex(all_categories, fill_value=1e-10)
        prod_aligned = prod_counts.reindex(all_categories, fill_value=1e-10)

        # Chi-square test
        chi2_stat, chi2_pvalue = stats.chisquare(prod_aligned, ref_aligned)
        chi2_drift = chi2_pvalue < self.alpha

        # PSI for categorical
        psi_score = self._calculate_psi_categorical(ref_aligned, prod_aligned)
        psi_drift = psi_score > self.psi_threshold

        drift_detected = chi2_drift or psi_drift

        result = {
            "drift_detected": drift_detected,
            "drift_score": max(chi2_stat / len(all_categories), psi_score),
            "tests": {
                "chi_square": {
                    "statistic": chi2_stat,
                    "p_value": chi2_pvalue,
                    "drift": chi2_drift,
                },
                "psi": {"score": psi_score, "drift": psi_drift},
            },
            "statistics": {
                "n_categories_reference": len(ref_counts),
                "n_categories_production": len(prod_counts),
                "new_categories": list(set(prod_counts.index) - set(ref_counts.index)),
                "missing_categories": list(
                    set(ref_counts.index) - set(prod_counts.index)
                ),
            },
        }

        if drift_detected:
            logger.warning(f"⚠️  DRIFT DETECTED in categorical '{feature_name}':")
            logger.warning(
                f"   Chi-square test: p={chi2_pvalue:.4f} (drift={chi2_drift})"
            )
            logger.warning(f"   PSI: {psi_score:.4f} (drift={psi_drift})")
        else:
            logger.info(f"✅ No drift in categorical '{feature_name}'")

        return result

    def _calculate_psi(
        self, reference: pd.Series, production: pd.Series, n_bins: int = 10
    ) -> float:
        """Calculate Population Stability Index (PSI).

        PSI measures the shift in distributions:
        - PSI < 0.1: No significant change
        - 0.1 <= PSI < 0.2: Moderate change
        - PSI >= 0.2: Significant change (drift detected)

        Args:
            reference: Reference distribution
            production: Production distribution
            n_bins: Number of bins for discretization

        Returns:
            PSI score
        """
        # Create bins based on reference data
        bins = np.percentile(reference, np.linspace(0, 100, n_bins + 1))
        bins = np.unique(bins)  # Remove duplicates

        if len(bins) < 2:
            return 0.0

        # Bin both distributions
        ref_binned = np.histogram(reference, bins=bins)[0]
        prod_binned = np.histogram(production, bins=bins)[0]

        # Convert to proportions
        ref_prop = ref_binned / len(reference)
        prod_prop = prod_binned / len(production)

        # Avoid log(0) by adding small epsilon
        ref_prop = np.where(ref_prop == 0, 1e-10, ref_prop)
        prod_prop = np.where(prod_prop == 0, 1e-10, prod_prop)

        # Calculate PSI
        psi = np.sum((prod_prop - ref_prop) * np.log(prod_prop / ref_prop))

        return float(psi)

    def _calculate_psi_categorical(
        self, reference: pd.Series, production: pd.Series
    ) -> float:
        """Calculate PSI for categorical features."""
        ref_prop = reference.values
        prod_prop = production.values

        # Avoid log(0)
        ref_prop = np.where(ref_prop == 0, 1e-10, ref_prop)
        prod_prop = np.where(prod_prop == 0, 1e-10, prod_prop)

        psi = np.sum((prod_prop - ref_prop) * np.log(prod_prop / ref_prop))
        return float(psi)

    def _store_drift_record(self, session, feature_name: str, result: dict[str, Any]):
        """Store drift detection result in PostgreSQL."""
        # Determine primary test method and statistics
        if "chi_square" in result["tests"]:
            test_method = "chi_square"
            test_stat = result["tests"]["chi_square"]["statistic"]
            p_value = result["tests"]["chi_square"]["p_value"]
        else:
            test_method = "ks_test"
            test_stat = result["tests"]["ks_test"]["statistic"]
            p_value = result["tests"]["ks_test"]["p_value"]

        record = DriftRecord(
            check_timestamp=datetime.now(),
            feature_name=feature_name,
            drift_detected=result["drift_detected"],
            drift_score=result["drift_score"],
            test_statistic=test_stat,
            p_value=p_value,
            test_method=test_method,
            reference_mean=result["statistics"].get("reference_mean"),
            reference_std=result["statistics"].get("reference_std"),
            production_mean=result["statistics"].get("production_mean"),
            production_std=result["statistics"].get("production_std"),
            metadata={"tests": result["tests"], "statistics": result["statistics"]},
            alert_sent=False,
        )

        session.add(record)

    def get_drift_history(
        self,
        feature_name: str | None = None,
        days: int = 30,
        drift_only: bool = False,
    ) -> pd.DataFrame:
        """Retrieve drift detection history from PostgreSQL.

        Args:
            feature_name: Filter by feature name (None for all)
            days: Number of days to look back
            drift_only: Only return records where drift was detected

        Returns:
            DataFrame with drift history
        """
        session = self.Session()
        try:
            query = session.query(DriftRecord)

            # Filter by feature
            if feature_name:
                query = query.filter(DriftRecord.feature_name == feature_name)

            # Filter by time
            cutoff = datetime.now() - pd.Timedelta(days=days)
            query = query.filter(DriftRecord.check_timestamp >= cutoff)

            # Filter by drift detected
            if drift_only:
                query = query.filter(DriftRecord.drift_detected)

            # Order by timestamp
            query = query.order_by(DriftRecord.check_timestamp.desc())

            # Convert to DataFrame
            records = query.all()

            if not records:
                logger.info("No drift records found matching criteria")
                return pd.DataFrame()

            data = [
                {
                    "timestamp": r.check_timestamp,
                    "feature": r.feature_name,
                    "drift_detected": r.drift_detected,
                    "drift_score": r.drift_score,
                    "test_statistic": r.test_statistic,
                    "p_value": r.p_value,
                    "test_method": r.test_method,
                    "ref_mean": r.reference_mean,
                    "ref_std": r.reference_std,
                    "prod_mean": r.production_mean,
                    "prod_std": r.production_std,
                }
                for r in records
            ]

            df = pd.DataFrame(data)
            logger.info(f"Retrieved {len(df)} drift records")

            return df

        finally:
            session.close()

    def send_alert(
        self, results: dict[str, dict[str, Any]], alert_email: str | None = None
    ):
        """Send email alert if drift detected.

        Args:
            results: Drift detection results
            alert_email: Email address for alerts (default: from env)
        """
        drift_features = [f for f, r in results.items() if r["drift_detected"]]

        if not drift_features:
            logger.info("No drift detected, no alert needed")
            return

        alert_email = alert_email or os.getenv("AIRFLOW_ALERT_EMAIL")
        if not alert_email:
            logger.warning("No alert email configured, skipping alert")
            return

        # Prepare alert message
        message = f"""
🚨 DATA DRIFT ALERT 🚨

Drift detected in {len(drift_features)} features:

"""
        for feature in drift_features:
            result = results[feature]
            message += f"\n• {feature}:\n"
            message += f"  - Drift Score: {result['drift_score']:.4f}\n"

            if "ks_test" in result["tests"]:
                ks = result["tests"]["ks_test"]
                message += f"  - KS test: p={ks['p_value']:.4f} (drift={ks['drift']})\n"

            if "psi" in result["tests"]:
                psi = result["tests"]["psi"]
                message += f"  - PSI: {psi['score']:.4f} (drift={psi['drift']})\n"

        message += f"\n\nTimestamp: {datetime.now()}\n"
        message += "Please investigate and consider retraining the model.\n"

        logger.warning(message)
        logger.warning(f"Alert should be sent to: {alert_email}")

        # Send email alert
        subject = f"[DRIFT ALERT] Data drift detected in {len(drift_features)} features"
        email_sent = send_drift_alert_email(alert_email, subject, message)

        if email_sent:
            logger.info("Drift alert email sent successfully")
        else:
            logger.warning("Failed to send drift alert email. Alert logged above.")


def send_drift_alert_email(alert_email: str, subject: str, message: str) -> bool:
    """Send drift alert email using SMTP configuration.

    Args:
        alert_email: Recipient email address
        subject: Email subject
        message: Email message content

    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        # Get SMTP configuration from environment
        smtp_host = os.getenv("AIRFLOW__SMTP__SMTP_HOST", "smtp.gmail.com")
        smtp_port = int(os.getenv("AIRFLOW__SMTP__SMTP_PORT", "587"))
        smtp_user = os.getenv("AIRFLOW__SMTP__SMTP_USER")
        smtp_password = os.getenv("AIRFLOW__SMTP__SMTP_PASSWORD")
        smtp_starttls = (
            os.getenv("AIRFLOW__SMTP__SMTP_STARTTLS", "true").lower() == "true"
        )
        smtp_ssl = os.getenv("AIRFLOW__SMTP__SMTP_SSL", "false").lower() == "true"
        from_email = os.getenv(
            "AIRFLOW__SMTP__SMTP_MAIL_FROM", "airflow@demand-forecasting.local"
        )

        if not smtp_user or not smtp_password:
            logger.warning("SMTP credentials not configured. Email not sent.")
            return False

        # Create message
        msg = MIMEMultipart()
        msg["From"] = from_email
        msg["To"] = alert_email
        msg["Subject"] = subject

        # Convert plain text message to HTML
        html_message = f"""
        <html>
        <body>
            <pre style="font-family: monospace; white-space: pre-wrap;">{message}</pre>
        </body>
        </html>
        """

        msg.attach(MIMEText(html_message, "html"))

        # Send email
        if smtp_ssl:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port)

        if smtp_starttls and not smtp_ssl:
            server.starttls()

        server.login(smtp_user, smtp_password)
        server.send_message(msg)
        server.quit()

        logger.info(f"Drift alert email sent to {alert_email}")
        return True

    except Exception as e:
        logger.error(f"Failed to send drift alert email: {e}")
        return False


def load_data(path: str) -> pd.DataFrame:
    """Load data from CSV or S3 path."""
    if path.startswith("s3://"):
        # Load data from S3 using s3fs
        try:
            logger.info(f"Loading data from S3: {path}")

            # Get S3 configuration from environment
            s3_endpoint = os.getenv(
                "MINIO_ENDPOINT", "http://host.docker.internal:9000"
            )
            s3_key = os.getenv("MINIO_ROOT_USER")
            s3_secret = os.getenv("MINIO_ROOT_PASSWORD")
            
            if not s3_key or not s3_secret:
                raise ValueError(
                    "S3 credentials must be provided via environment variables: "
                    "MINIO_ROOT_USER and MINIO_ROOT_PASSWORD are required"
                )

            # Create S3 filesystem
            fs = s3fs.S3FileSystem(
                client_kwargs={"endpoint_url": s3_endpoint},
                key=s3_key,
                secret=s3_secret,
            )

            # Load data from S3
            with fs.open(path, "r") as f:
                df = pd.read_csv(f)

            logger.info(f"Successfully loaded {len(df)} rows from S3")
            return df

        except Exception as e:
            logger.error(f"Failed to load data from S3 {path}: {e}")
            raise
    else:
        logger.info(f"Loading data from local file: {path}")
        return pd.read_csv(path)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Detect data drift between reference and production datasets"
    )
    parser.add_argument(
        "--reference-data",
        type=str,
        help="Path to reference dataset (CSV or S3)",
        default="data/01_raw/superstore_train.csv",
    )
    parser.add_argument(
        "--production-data",
        type=str,
        help="Path to production dataset (CSV or S3)",
        required=False,
    )
    parser.add_argument(
        "--feature-cols",
        type=str,
        nargs="+",
        help="List of feature columns to check",
        default=None,
    )
    parser.add_argument(
        "--categorical-cols",
        type=str,
        nargs="+",
        help="List of categorical columns",
        default=None,
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.05,
        help="Significance level for statistical tests",
    )
    parser.add_argument(
        "--psi-threshold",
        type=float,
        default=0.2,
        help="PSI threshold for drift detection",
    )
    parser.add_argument(
        "--alert", action="store_true", help="Send email alert if drift detected"
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="Show drift history instead of running detection",
    )
    parser.add_argument(
        "--days", type=int, default=30, help="Number of days for drift history"
    )

    args = parser.parse_args()

    # Initialize detector
    detector = DriftDetector(alpha=args.alpha, psi_threshold=args.psi_threshold)

    # Show history if requested
    if args.history:
        history = detector.get_drift_history(days=args.days, drift_only=False)
        if not history.empty:

            # Summary
            history["drift_detected"].sum()
        else:
            pass
        return

    # Run drift detection
    if not args.production_data:
        logger.error("--production-data is required for drift detection")
        sys.exit(1)

    # Load data
    logger.info("Loading datasets...")
    reference_data = load_data(args.reference_data)
    production_data = load_data(args.production_data)

    # Detect drift
    results = detector.detect_drift(
        reference_data=reference_data,
        production_data=production_data,
        feature_cols=args.feature_cols,
        categorical_cols=args.categorical_cols,
    )

    # Print summary

    drift_detected = [f for f, r in results.items() if r["drift_detected"]]
    no_drift = [f for f, r in results.items() if not r["drift_detected"]]

    for feature in no_drift:
        results[feature]["drift_score"]

    if drift_detected:
        for feature in drift_detected:
            result = results[feature]

            for _test_name, test_result in result["tests"].items():
                "⚠️ " if test_result.get("drift", False) else "✅"
                if (
                    "p_value" in test_result
                    or "score" in test_result
                    or "distance" in test_result
                ):
                    pass

    # Send alert if requested
    if args.alert:
        detector.send_alert(results)

    # Exit with error code if drift detected
    if drift_detected:
        logger.warning(f"⚠️  Drift detected in {len(drift_detected)} features")
        sys.exit(1)
    else:
        logger.info("✅ No drift detected")
        sys.exit(0)


if __name__ == "__main__":
    main()
