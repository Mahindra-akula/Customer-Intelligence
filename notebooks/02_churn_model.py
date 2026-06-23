# Databricks notebook source
# 02_churn_model.py — Churn Risk Model
# Trains XGBoost classifier on gold.customer_360
# Logs to MLflow, registers model in Unity Catalog Model Registry
# Writes churn scores back to gold.churn_scores

# COMMAND ----------
%run ../config/pipeline_config

# COMMAND ----------
import mlflow
import mlflow.sklearn
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score
from mlflow.models.signature import infer_signature
import pandas as pd

mlflow.set_registry_uri("databricks-uc")
mlflow.set_experiment("/Shared/retail_demo_churn")

# COMMAND ----------
# ── Load features from gold.customer_360 ──────────────────────────────────────
df = spark.table(f"{CATALOG}.{PIPELINE_SCHEMA}.customer_360").toPandas()

FEATURES = [
    "order_count_90d",
    "total_spend_90d",
    "avg_order_value",
    "recency_days",
    "return_rate",
    "crm_events",
    "complaints",
    "days_since_last_contact",
    "age",
]

# Rank-based churn label: top 30% by recency_days = churned.
# rank(method="first") breaks ties deterministically, guaranteeing exactly 300 positives
# in a 1000-row dataset regardless of how clustered recency_days values are.
n_churned = max(2, int(len(df) * 0.30))
df["churn_label"] = 0
churn_idx = df["recency_days"].rank(method="first", ascending=False) <= n_churned
df.loc[churn_idx, "churn_label"] = 1
TARGET = "churn_label"

X = df[FEATURES].fillna(0)
y = df[TARGET].astype(int)

print(f"Dataset: {len(df):,} customers | Churn rate: {y.mean():.1%} ({y.sum()} churned)")

# COMMAND ----------
# ── Train / test split ────────────────────────────────────────────────────────
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# COMMAND ----------
# ── Train + log to MLflow ─────────────────────────────────────────────────────
with mlflow.start_run(run_name="churn_gbt_v1") as run:
    params = {"n_estimators": 100, "max_depth": 4, "learning_rate": 0.1, "random_state": 42}
    mlflow.log_params(params)

    model = GradientBoostingClassifier(**params)
    model.fit(X_train, y_train)

    y_prob  = model.predict_proba(X_test)[:, 1]
    auc     = roc_auc_score(y_test, y_prob)
    mlflow.log_metric("roc_auc", round(auc, 4))

    # Feature importance
    importances = dict(zip(FEATURES, model.feature_importances_.tolist()))
    for feat, imp in importances.items():
        mlflow.log_metric(f"feat_{feat}", round(imp, 4))

    X_example = X_train.astype(float)
    signature = infer_signature(X_example, model.predict(X_example))
    mlflow.sklearn.log_model(
        model,
        artifact_path="model",
        registered_model_name=f"{CATALOG}.{GOLD_SCHEMA}.{MODEL_NAME}",
        signature=signature,
    )
    run_id = run.info.run_id

print(f"ROC-AUC: {auc:.4f}")
print(f"Run ID: {run_id}")

# COMMAND ----------
# ── Score all customers + write churn_scores to Gold ─────────────────────────
X_all   = df[FEATURES].fillna(0)
probas  = model.predict_proba(X_all)[:, 1]

df["churn_probability"] = probas
df["risk_tier"] = pd.cut(
    df["churn_probability"],
    bins=[-0.001, 0.33, 0.66, 1.001],
    labels=["Low", "Medium", "High"]
)

scores_df = spark.createDataFrame(
    df[["customer_id", "customer_name", "store_id", "region", "segment",
        "recency_days", "order_count_90d", "total_spend_90d",
        "churn_probability", "risk_tier"]]
    .rename(columns={"churn_probability": "churn_prob"})
)

scores_df.write.format("delta").mode("overwrite").saveAsTable(f"{CATALOG}.{GOLD_SCHEMA}.churn_scores")
print(f"churn_scores written: {scores_df.count():,} rows")

# Distribution
display(
    scores_df.groupBy("risk_tier").count().orderBy("risk_tier")
)
