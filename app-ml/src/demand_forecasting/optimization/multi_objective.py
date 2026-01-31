"""
Multi-objective optimization using Optuna for demand forecasting.
"""

import logging
import time
from typing import Dict, Any, List, Tuple, Callable

import numpy as np
import optuna
from catboost import CatBoostRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import cross_val_score

logger = logging.getLogger(__name__)


def compute_zero_safe_mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """
    Compute Mean Absolute Percentage Error with zero-division protection.

    Args:
        y_true: True values
        y_pred: Predicted values

    Returns:
        MAPE value
    """
    y_true, y_pred = np.array(y_true), np.array(y_pred)
    mask = y_true != 0
    if np.sum(mask) == 0:
        return 0.0

    return np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100


def objective_multi(
    trial, X_train, X_test, y_train, y_test, objectives: List[str] = None
) -> Tuple[float, ...]:
    """
    Multi-objective optimization function.

    Args:
        trial: Optuna trial object
        X_train, X_test, y_train, y_test: Data splits
        objectives: List of objectives to optimize

    Returns:
        Tuple of objective values
    """
    if objectives is None:
        objectives = ["rmse", "mae", "training_time"]

    # Suggest hyperparameters
    params = {
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "depth": trial.suggest_int("depth", 3, 10),
        "l2_leaf_reg": trial.suggest_float("l2_leaf_reg", 0.1, 10.0, log=True),
        "border_count": trial.suggest_int("border_count", 32, 255),
        "bagging_temperature": trial.suggest_float("bagging_temperature", 0.0, 1.0),
        "random_strength": trial.suggest_float("random_strength", 0.0, 1.0),
        "iterations": trial.suggest_int("iterations", 100, 1000),
        "verbose": False,
        "random_seed": trial.number,
    }

    # Track training time
    start_time = time.time()

    try:
        # Train model
        model = CatBoostRegressor(**params)
        model.fit(X_train, y_train, eval_set=(X_test, y_test), verbose=False)

        training_time = time.time() - start_time

        # Make predictions
        y_pred = model.predict(X_test)

        # Calculate objectives
        objectives_values = []

        if "rmse" in objectives:
            rmse = np.sqrt(mean_squared_error(y_test, y_pred))
            objectives_values.append(rmse)

        if "mae" in objectives:
            mae = mean_absolute_error(y_test, y_pred)
            objectives_values.append(mae)

        if "mape" in objectives:
            mape = compute_zero_safe_mape(y_test, y_pred)
            objectives_values.append(mape)

        if "training_time" in objectives:
            objectives_values.append(training_time)

        if "cv_score" in objectives:
            # Negative because we want to maximize CV score
            cv_scores = cross_val_score(
                model, X_train, y_train, cv=5, scoring="neg_root_mean_squared_error"
            )
            cv_rmse = -np.mean(cv_scores)
            objectives_values.append(cv_rmse)

        return (
            tuple(objectives_values)
            if len(objectives_values) > 1
            else objectives_values[0]
        )

    except Exception as e:
        logger.error(f"Trial {trial.number} failed: {e}")
        # Return worst possible values for failed trials
        worst_values = []
        for obj in objectives:
            if obj in ["rmse", "mae", "mape", "cv_score"]:
                worst_values.append(float("inf"))
            elif obj == "training_time":
                worst_values.append(float("inf"))
        return tuple(worst_values) if len(worst_values) > 1 else worst_values[0]


class MultiObjectiveOptimizer:
    """Multi-objective optimization using Optuna."""

    def __init__(self, objectives: List[str], directions: List[str] = None):
        """
        Initialize multi-objective optimizer.

        Args:
            objectives: List of objectives to optimize
            directions: List of optimization directions ('minimize' or 'maximize')
        """
        self.objectives = objectives
        self.directions = directions or ["minimize"] * len(objectives)
        self.study = None
        self.best_trials = []

    def create_study(
        self,
        study_name: str = "demand_forecasting_multi_objective",
        storage: str = None,
        sampler: optuna.samplers.BaseSampler = None,
    ) -> optuna.Study:
        """
        Create Optuna study for multi-objective optimization.

        Args:
            study_name: Name of the study
            storage: Database storage URL
            sampler: Optuna sampler

        Returns:
            Optuna study object
        """
        try:
            self.study = optuna.create_study(
                study_name=study_name,
                directions=self.directions,
                sampler=sampler or optuna.samplers.NSGAIISampler(),
                storage=storage,
                load_if_exists=True,
            )

            logger.info(f"Created multi-objective study: {study_name}")
            logger.info(f"Objectives: {self.objectives}")
            logger.info(f"Directions: {self.directions}")

            return self.study

        except Exception as e:
            logger.error(f"Failed to create study: {e}")
            raise

    def optimize(
        self,
        X_train,
        X_test,
        y_train,
        y_test,
        n_trials: int = 100,
        timeout: float = None,
    ) -> Dict[str, Any]:
        """
        Run multi-objective optimization.

        Args:
            X_train, X_test, y_train, y_test: Data splits
            n_trials: Number of trials to run
            timeout: Timeout in seconds

        Returns:
            Dictionary with optimization results
        """
        if self.study is None:
            raise ValueError("Study not created. Call create_study() first.")

        try:
            # Define objective function with data
            def objective(trial):
                return objective_multi(
                    trial, X_train, X_test, y_train, y_test, self.objectives
                )

            # Run optimization
            logger.info(f"Starting optimization with {n_trials} trials...")
            self.study.optimize(objective, n_trials=n_trials, timeout=timeout)

            # Get Pareto front (best trials)
            self.best_trials = self.study.best_trials

            # Analyze results
            results = self._analyze_results()

            logger.info(
                f"Optimization completed. Found {len(self.best_trials)} Pareto-optimal solutions."
            )

            return results

        except Exception as e:
            logger.error(f"Optimization failed: {e}")
            raise

    def _analyze_results(self) -> Dict[str, Any]:
        """Analyze optimization results."""
        if not self.best_trials:
            return {"error": "No successful trials found"}

        # Extract objective values
        objective_values = []
        for trial in self.best_trials:
            values = trial.values
            objective_values.append(values)

        objective_values = np.array(objective_values)

        # Calculate statistics for each objective
        stats = {}
        for i, obj_name in enumerate(self.objectives):
            obj_values = objective_values[:, i]
            stats[obj_name] = {
                "best": (
                    np.min(obj_values)
                    if self.directions[i] == "minimize"
                    else np.max(obj_values)
                ),
                "worst": (
                    np.max(obj_values)
                    if self.directions[i] == "minimize"
                    else np.min(obj_values)
                ),
                "mean": np.mean(obj_values),
                "std": np.std(obj_values),
                "median": np.median(obj_values),
            }

        # Find best trial for each objective
        best_trials_per_objective = {}
        for i, obj_name in enumerate(self.objectives):
            if self.directions[i] == "minimize":
                best_idx = np.argmin(objective_values[:, i])
            else:
                best_idx = np.argmax(objective_values[:, i])

            best_trials_per_objective[obj_name] = {
                "trial_number": self.best_trials[best_idx].number,
                "params": self.best_trials[best_idx].params,
                "values": dict(zip(self.objectives, self.best_trials[best_idx].values)),
            }

        return {
            "n_pareto_trials": len(self.best_trials),
            "objective_statistics": stats,
            "best_trials_per_objective": best_trials_per_objective,
            "pareto_front": [
                {
                    "trial_number": trial.number,
                    "params": trial.params,
                    "values": dict(zip(self.objectives, trial.values)),
                }
                for trial in self.best_trials
            ],
            "total_trials": len(self.study.trials),
            "study_name": self.study.study_name,
        }

    def get_pareto_analysis(self) -> Dict[str, Any]:
        """Get detailed analysis of Pareto front."""
        if not self.best_trials:
            return {"error": "No Pareto solutions available"}

        # Calculate hypervolume (simplified)
        # For true hypervolume, we need a reference point
        objective_values = np.array([trial.values for trial in self.best_trials])

        # Find reference point (worst values + 10% margin)
        reference_point = []
        for i, obj_name in enumerate(self.objectives):
            if self.directions[i] == "minimize":
                ref_val = np.max(objective_values[:, i]) * 1.1
            else:
                ref_val = np.min(objective_values[:, i]) * 0.9
            reference_point.append(ref_val)

        # Calculate diversity metrics
        diversity_metrics = self._calculate_diversity_metrics(objective_values)

        return {
            "pareto_size": len(self.best_trials),
            "reference_point": dict(zip(self.objectives, reference_point)),
            "diversity_metrics": diversity_metrics,
            "convergence_metrics": self._calculate_convergence_metrics(
                objective_values
            ),
        }

    def _calculate_diversity_metrics(
        self, objective_values: np.ndarray
    ) -> Dict[str, float]:
        """Calculate diversity metrics for Pareto front."""
        try:
            # Calculate pairwise distances
            from scipy.spatial.distance import pdist

            distances = pdist(objective_values)

            return {
                "mean_distance": np.mean(distances),
                "min_distance": np.min(distances),
                "max_distance": np.max(distances),
                "std_distance": np.std(distances),
            }
        except ImportError:
            # Fallback if scipy not available
            return {"error": "scipy not available for distance calculations"}
        except Exception as e:
            return {"error": f"Failed to calculate diversity: {e}"}

    def _calculate_convergence_metrics(
        self, objective_values: np.ndarray
    ) -> Dict[str, float]:
        """Calculate convergence metrics."""
        try:
            # Calculate distance to ideal point (0 for minimization)
            ideal_point = np.zeros(objective_values.shape[1])
            distances_to_ideal = np.linalg.norm(objective_values - ideal_point, axis=1)

            return {
                "min_distance_to_ideal": np.min(distances_to_ideal),
                "mean_distance_to_ideal": np.mean(distances_to_ideal),
                "std_distance_to_ideal": np.std(distances_to_ideal),
            }
        except Exception as e:
            return {"error": f"Failed to calculate convergence: {e}"}

    def recommend_solution(
        self, preference_weights: Dict[str, float] = None
    ) -> Dict[str, Any]:
        """
        Recommend a solution based on preference weights.

        Args:
            preference_weights: Weights for each objective

        Returns:
            Recommended trial with weighted score
        """
        if not self.best_trials:
            return {"error": "No solutions available"}

        if preference_weights is None:
            # Equal weights by default
            preference_weights = {obj: 1.0 for obj in self.objectives}

        # Normalize weights
        total_weight = sum(preference_weights.values())
        normalized_weights = {
            k: v / total_weight for k, v in preference_weights.items()
        }

        # Calculate weighted scores
        best_trial = None
        best_score = float("inf") if "minimize" in self.directions else float("-inf")

        for trial in self.best_trials:
            # Normalize objectives to [0, 1]
            objective_values = np.array(trial.values)

            # Get min/max for each objective across all trials
            all_values = np.array([t.values for t in self.best_trials])
            min_vals = np.min(all_values, axis=0)
            max_vals = np.max(all_values, axis=0)

            # Normalize (0 = best, 1 = worst)
            normalized_values = []
            for i, (val, direction) in enumerate(
                zip(objective_values, self.directions)
            ):
                if direction == "minimize":
                    norm_val = (val - min_vals[i]) / (max_vals[i] - min_vals[i] + 1e-8)
                else:
                    norm_val = (max_vals[i] - val) / (max_vals[i] - min_vals[i] + 1e-8)
                normalized_values.append(norm_val)

            # Calculate weighted score
            weighted_score = sum(
                normalized_values[i] * normalized_weights.get(self.objectives[i], 0)
                for i in range(len(self.objectives))
            )

            if weighted_score < best_score:
                best_score = weighted_score
                best_trial = trial

        return {
            "recommended_trial": {
                "trial_number": best_trial.number,
                "params": best_trial.params,
                "values": dict(zip(self.objectives, best_trial.values)),
                "weighted_score": best_score,
            },
            "preference_weights": normalized_weights,
            "selection_criteria": "weighted_sum",
        }
