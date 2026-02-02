"""Ensemble methods for demand forecasting using scikit-learn."""

import logging
import time
from typing import Any

import joblib
import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from lightgbm import LGBMRegressor
from sklearn.ensemble import RandomForestRegressor, StackingRegressor, VotingRegressor
from sklearn.linear_model import RidgeCV
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import cross_val_score
from xgboost import XGBRegressor

logger = logging.getLogger(__name__)


class EnsembleManager:
    """Manage ensemble methods for demand forecasting."""

    def __init__(self):
        """Initialize ensemble manager."""
        self.ensemble = None
        self.base_models = {}
        self.meta_model = None
        self.ensemble_type = None

    def create_stacking_ensemble(
        self,
        catboost_params: dict[str, Any] | None = None,
        rf_params: dict[str, Any] | None = None,
        xgb_params: dict[str, Any] | None = None,
        lgbm_params: dict[str, Any] | None = None,
        cv_folds: int = 5,
    ) -> StackingRegressor:
        """Create a stacking ensemble of multiple models.

        Args:
            catboost_params: CatBoost hyperparameters
            rf_params: Random Forest hyperparameters
            xgb_params: XGBoost hyperparameters
            lgbm_params: LightGBM hyperparameters
            cv_folds: Number of CV folds for stacking

        Returns:
            Configured StackingRegressor
        """
        try:
            # Default parameters
            default_catboost = {
                "iterations": 500,
                "learning_rate": 0.1,
                "depth": 6,
                "l2_leaf_reg": 3.0,
                "verbose": False,
                "random_state": 42,
            }

            default_rf = {
                "n_estimators": 100,
                "max_depth": 10,
                "min_samples_split": 2,
                "min_samples_leaf": 1,
                "random_state": 42,
                "n_jobs": -1,
            }

            default_xgb = {
                "n_estimators": 500,
                "learning_rate": 0.1,
                "max_depth": 6,
                "subsample": 0.8,
                "colsample_bytree": 0.8,
                "random_state": 42,
                "n_jobs": -1,
                "verbosity": 0,
            }

            default_lgbm = {
                "n_estimators": 500,
                "learning_rate": 0.1,
                "max_depth": 6,
                "subsample": 0.8,
                "colsample_bytree": 0.8,
                "random_state": 42,
                "n_jobs": -1,
                "verbose": -1,
            }

            # Merge with provided parameters
            catboost_params = {**default_catboost, **(catboost_params or {})}
            rf_params = {**default_rf, **(rf_params or {})}
            xgb_params = {**default_xgb, **(xgb_params or {})}
            lgbm_params = {**default_lgbm, **(lgbm_params or {})}

            # Create base models
            base_models = [
                ("catboost", CatBoostRegressor(**catboost_params)),
                ("rf", RandomForestRegressor(**rf_params)),
                ("xgb", XGBRegressor(**xgb_params)),
                ("lgbm", LGBMRegressor(**lgbm_params)),
            ]

            # Store base models for reference
            self.base_models = {
                "catboost": CatBoostRegressor(**catboost_params),
                "rf": RandomForestRegressor(**rf_params),
                "xgb": XGBRegressor(**xgb_params),
                "lgbm": LGBMRegressor(**lgbm_params),
            }

            # Meta-learner (Ridge regression with cross-validation)
            self.meta_model = RidgeCV(alphas=[0.1, 1.0, 10.0], cv=cv_folds)

            # Create stacking ensemble
            self.ensemble = StackingRegressor(
                estimators=base_models,
                final_estimator=self.meta_model,
                cv=cv_folds,
                n_jobs=-1,
                passthrough=False,  # Don't pass original features to meta-model
            )

            self.ensemble_type = "stacking"

            logger.info(
                f"Created stacking ensemble with {len(base_models)} base models"
            )
            logger.info(f"Base models: {list(self.base_models.keys())}")
            logger.info(f"Meta-model: RidgeCV with CV folds={cv_folds}")

            return self.ensemble

        except Exception as e:
            logger.error(f"Failed to create stacking ensemble: {e}")
            raise

    def create_voting_ensemble(
        self, models: list[tuple[str, object]], weights: list[float] | None = None
    ) -> object:
        """Create a voting ensemble (simplified version).

        Args:
            models: List of (name, model) tuples
            weights: Optional weights for each model

        Returns:
            Voting ensemble implementation
        """
        try:
            self.ensemble = VotingRegressor(estimators=models, weights=weights)

            self.ensemble_type = "voting"
            self.base_models = dict(models)

            logger.info(f"Created voting ensemble with {len(models)} models")
            if weights:
                logger.info(
                    f"Model weights: {dict(zip([m[0] for m in models], weights, strict=False))}"
                )

            return self.ensemble

        except Exception as e:
            logger.error(f"Failed to create voting ensemble: {e}")
            raise

    def train_ensemble(
        self, X_train: pd.DataFrame, y_train: pd.Series, X_val: pd.DataFrame | None = None, y_val: pd.Series | None = None
    ) -> dict[str, Any]:
        """Train the ensemble and individual base models.

        Args:
            X_train: Training features
            y_train: Training target values
            X_val: Validation features
            y_val: Validation target values

        Returns:
            Training results
        """
        if self.ensemble is None:
            raise ValueError("Ensemble not created. Call create_*_ensemble() first.")

        try:
            start_time = time.time()

            # Train ensemble
            self.ensemble.fit(X_train, y_train)
            training_time = time.time() - start_time

            # Train individual base models for comparison
            base_model_results = {}
            for name, model in self.base_models.items():
                start_time = time.time()
                model.fit(X_train, y_train)
                base_train_time = time.time() - start_time

                # Make predictions
                train_pred = model.predict(X_train)
                val_pred = model.predict(X_val) if X_val is not None else None

                base_model_results[name] = {
                    "training_time": base_train_time,
                    "train_rmse": np.sqrt(mean_squared_error(y_train, train_pred)),
                    "train_mae": mean_absolute_error(y_train, train_pred),
                }

                if X_val is not None and y_val is not None:
                    base_model_results[name]["val_rmse"] = np.sqrt(
                        mean_squared_error(y_val, val_pred)
                    )
                    base_model_results[name]["val_mae"] = mean_absolute_error(
                        y_val, val_pred
                    )

            # Ensemble predictions
            ensemble_train_pred = self.ensemble.predict(X_train)
            ensemble_val_pred = (
                self.ensemble.predict(X_val) if X_val is not None else None
            )

            results = {
                "ensemble_type": self.ensemble_type,
                "training_time": training_time,
                "base_models": base_model_results,
                "ensemble": {
                    "train_rmse": np.sqrt(
                        mean_squared_error(y_train, ensemble_train_pred)
                    ),
                    "train_mae": mean_absolute_error(y_train, ensemble_train_pred),
                },
            }

            if X_val is not None and y_val is not None:
                results["ensemble"]["val_rmse"] = np.sqrt(
                    mean_squared_error(y_val, ensemble_val_pred)
                )
                results["ensemble"]["val_mae"] = mean_absolute_error(
                    y_val, ensemble_val_pred
                )

                # Calculate improvement over best base model
                best_base_val_rmse = min(
                    [
                        r.get("val_rmse", float("inf"))
                        for r in base_model_results.values()
                    ]
                )
                improvement = (
                    (best_base_val_rmse - results["ensemble"]["val_rmse"])
                    / best_base_val_rmse
                ) * 100

                results["improvement_over_best_base"] = improvement
                results["best_base_model"] = min(
                    base_model_results.keys(),
                    key=lambda k: base_model_results[k].get("val_rmse", float("inf")),
                )

            logger.info(f"Ensemble training completed in {training_time:.2f} seconds")
            if X_val is not None:
                logger.info(
                    f"Ensemble validation RMSE: {results['ensemble']['val_rmse']:.4f}"
                )
                if "improvement_over_best_base" in results:
                    logger.info(
                        f"Improvement over best base model: {results['improvement_over_best_base']:.2f}%"
                    )

            return results

        except Exception as e:
            logger.error(f"Ensemble training failed: {e}")
            raise

    def evaluate_ensemble(self, X_test: pd.DataFrame, y_test: pd.Series) -> dict[str, Any]:
        """Evaluate ensemble performance on test set.

        Args:
            X_test: Test features
            y_test: Test target values

        Returns:
            Evaluation results
        """
        if self.ensemble is None:
            raise ValueError("Ensemble not trained.")

        try:
            start_time = time.time()

            # Make predictions
            y_pred = self.ensemble.predict(X_test)
            prediction_time = time.time() - start_time

            # Calculate metrics
            rmse = np.sqrt(mean_squared_error(y_test, y_pred))
            mae = mean_absolute_error(y_test, y_pred)

            # Calculate MAPE (zero-safe)
            y_test_array, y_pred_array = np.array(y_test), np.array(y_pred)
            mask = y_test_array != 0
            if np.sum(mask) > 0:
                mape = (
                    np.mean(
                        np.abs(
                            (y_test_array[mask] - y_pred_array[mask])
                            / y_test_array[mask]
                        )
                    )
                    * 100
                )
            else:
                mape = 0.0

            # Evaluate individual base models
            base_model_evaluations = {}
            for name, model in self.base_models.items():
                start_time = time.time()
                base_pred = model.predict(X_test)
                base_pred_time = time.time() - start_time

                base_rmse = np.sqrt(mean_squared_error(y_test, base_pred))
                base_mae = mean_absolute_error(y_test, base_pred)

                base_model_evaluations[name] = {
                    "rmse": base_rmse,
                    "mae": base_mae,
                    "prediction_time": base_pred_time,
                }

            # Calculate ensemble improvement
            best_base_rmse = min([e["rmse"] for e in base_model_evaluations.values()])
            rmse_improvement = ((best_base_rmse - rmse) / best_base_rmse) * 100

            best_base_mae = min([e["mae"] for e in base_model_evaluations.values()])
            mae_improvement = ((best_base_mae - mae) / best_base_mae) * 100

            results = {
                "ensemble_type": self.ensemble_type,
                "ensemble_metrics": {
                    "rmse": rmse,
                    "mae": mae,
                    "mape": mape,
                    "prediction_time": prediction_time,
                },
                "base_model_metrics": base_model_evaluations,
                "improvements": {
                    "rmse_improvement_percent": rmse_improvement,
                    "mae_improvement_percent": mae_improvement,
                    "best_base_model_rmse": min(
                        base_model_evaluations.keys(),
                        key=lambda k: base_model_evaluations[k]["rmse"],
                    ),
                    "best_base_model_mae": min(
                        base_model_evaluations.keys(),
                        key=lambda k: base_model_evaluations[k]["mae"],
                    ),
                },
            }

            logger.info(
                f"Ensemble test RMSE: {rmse:.4f} ({rmse_improvement:+.2f}% vs best base)"
            )
            logger.info(
                f"Ensemble test MAE: {mae:.4f} ({mae_improvement:+.2f}% vs best base)"
            )

            return results

        except Exception as e:
            logger.error(f"Ensemble evaluation failed: {e}")
            raise

    def get_feature_importance(self) -> dict[str, Any]:
        """Get feature importance from ensemble components.

        Returns:
            Feature importance from base models
        """
        if not self.base_models:
            return {"error": "No base models available"}

        try:
            feature_importance = {}

            for name, model in self.base_models.items():
                if hasattr(model, "feature_importances_"):
                    importance = model.feature_importances_
                    feature_importance[name] = importance
                elif hasattr(model, "coef_"):
                    # For linear models
                    importance = np.abs(model.coef_)
                    feature_importance[name] = importance
                else:
                    feature_importance[name] = np.array([])

            # Calculate average importance across models
            if feature_importance:
                all_importances = []
                for importance in feature_importance.values():
                    if len(importance) > 0:
                        all_importances.append(importance)

                if all_importances:
                    avg_importance = np.mean(all_importances, axis=0)
                    feature_importance["ensemble_average"] = avg_importance

            return feature_importance

        except Exception as e:
            logger.error(f"Failed to get feature importance: {e}")
            return {"error": str(e)}

    def cross_validate_ensemble(self, X: pd.DataFrame, y: pd.Series, cv_folds: int = 5) -> dict[str, Any]:
        """Perform cross-validation on the ensemble.

        Args:
            X: Features for cross-validation
            y: Target values for cross-validation
            cv_folds: Number of CV folds

        Returns:
            Cross-validation results
        """
        if self.ensemble is None:
            raise ValueError("Ensemble not created.")

        try:
            # Cross-validate ensemble
            cv_scores = cross_val_score(
                self.ensemble, X, y, cv=cv_folds, scoring="neg_root_mean_squared_error"
            )
            cv_rmse_scores = -cv_scores

            # Cross-validate individual base models
            base_model_cv = {}
            for name, model in self.base_models.items():
                base_cv_scores = cross_val_score(
                    model, X, y, cv=cv_folds, scoring="neg_root_mean_squared_error"
                )
                base_model_cv[name] = {
                    "rmse_scores": -base_cv_scores,
                    "mean_rmse": np.mean(-base_cv_scores),
                    "std_rmse": np.std(-base_cv_scores),
                }

            results = {
                "ensemble_cv": {
                    "rmse_scores": cv_rmse_scores.tolist(),
                    "mean_rmse": np.mean(cv_rmse_scores),
                    "std_rmse": np.std(cv_rmse_scores),
                    "cv_folds": cv_folds,
                },
                "base_model_cv": base_model_cv,
                "ensemble_improvement": {},
            }

            # Calculate improvement over best base model
            best_base_mean_rmse = min(
                [cv["mean_rmse"] for cv in base_model_cv.values()]
            )
            improvement = (
                (best_base_mean_rmse - results["ensemble_cv"]["mean_rmse"])
                / best_base_mean_rmse
            ) * 100

            results["ensemble_improvement"] = {
                "mean_rmse_improvement_percent": improvement,
                "best_base_model": min(
                    base_model_cv.keys(), key=lambda k: base_model_cv[k]["mean_rmse"]
                ),
            }

            logger.info(
                f"Ensemble CV RMSE: {results['ensemble_cv']['mean_rmse']:.4f} ± {results['ensemble_cv']['std_rmse']:.4f}"
            )
            logger.info(f"Improvement over best base model: {improvement:+.2f}%")

            return results

        except Exception as e:
            logger.error(f"Cross-validation failed: {e}")
            raise

    def save_ensemble(self, filepath: str):
        """Save the trained ensemble to disk."""
        if self.ensemble is None:
            raise ValueError("No ensemble to save.")

        try:
            joblib.dump(self.ensemble, filepath)
            logger.info(f"Ensemble saved to {filepath}")

        except Exception as e:
            logger.error(f"Failed to save ensemble: {e}")
            raise

    def load_ensemble(self, filepath: str):
        """Load a trained ensemble from disk."""
        try:
            self.ensemble = joblib.load(filepath)
            self.ensemble_type = "loaded"
            logger.info(f"Ensemble loaded from {filepath}")

        except Exception as e:
            logger.error(f"Failed to load ensemble: {e}")
            raise
