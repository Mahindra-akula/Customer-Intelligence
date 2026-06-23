# Databricks notebook source
# 04_rag_setup.py — GenAI / RAG Setup
# Creates a Vector Search index over CRM event notes + customer context
# Registers a RAG chain endpoint for the RetailAdvisor chatbot
# Pattern: Databricks Vector Search + Foundation Model API (DBRX / claude-3)

# COMMAND ----------
%run ../config/pipeline_config

# COMMAND ----------
# ── Step 1: Build document corpus from CRM events ─────────────────────────────
# Combine customer 360 context + CRM notes into a single text column for indexing

from pyspark.sql import functions as F

crm_raw = spark.table(f"{CATALOG}.{BRONZE_SCHEMA}.crm_events_raw")
c360    = spark.table(f"{CATALOG}.{GOLD_SCHEMA}.customer_360")

# Build a rich text document per customer for embedding
docs = (
    c360.alias("c")
    .join(
        crm_raw.groupBy("customer_id").agg(
            F.collect_list("notes").alias("all_notes"),
            F.count("*").alias("n_events"),
        ).alias("crm"),
        "customer_id",
        "left"
    )
    .withColumn("doc_id", F.col("c.customer_id").cast("string"))
    .withColumn("document", F.concat_ws(" | ",
        F.concat(F.lit("Customer: "), F.col("c.customer_name")),
        F.concat(F.lit("Segment: "),  F.col("c.segment")),
        F.concat(F.lit("Region: "),   F.col("c.region")),
        F.concat(F.lit("Orders 90d: "), F.col("c.order_count_90d").cast("string")),
        F.concat(F.lit("Spend 90d: $"), F.col("c.total_spend_90d").cast("string")),
        F.concat(F.lit("Recency days: "), F.col("c.recency_days").cast("string")),
        F.concat(F.lit("Churn risk: "), F.when(F.col("c.is_churned") == 1, "High").otherwise("Low")),
        F.concat(F.lit("CRM notes: "), F.array_join(F.col("crm.all_notes"), "; ")),
    ))
    .select("doc_id", "document", "c.customer_id", "c.customer_name", "c.segment", "c.region")
)

docs.write.format("delta").mode("overwrite").saveAsTable(f"{CATALOG}.{GOLD_SCHEMA}.rag_documents")
print(f"rag_documents: {docs.count():,} rows indexed")

# COMMAND ----------
# ── Step 2: Enable Change Data Feed on source table (required for Vector Search) ─
spark.sql(f"""
    ALTER TABLE {CATALOG}.{GOLD_SCHEMA}.rag_documents
    SET TBLPROPERTIES (delta.enableChangeDataFeed = true)
""")

# COMMAND ----------
# ── Step 3: Create Vector Search endpoint + index ─────────────────────────────
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.vectorsearch import (
    EndpointType, VectorIndexType, DeltaSyncVectorIndexSpecRequest,
    EmbeddingSourceColumn, PipelineType
)

w = WorkspaceClient()

ENDPOINT_NAME = "retail_demo_vs"
INDEX_NAME    = f"{CATALOG}.{GOLD_SCHEMA}.rag_documents_index"
SOURCE_TABLE  = f"{CATALOG}.{GOLD_SCHEMA}.rag_documents"

# Create endpoint (idempotent — skip if exists)
try:
    w.vector_search_endpoints.create_endpoint(name=ENDPOINT_NAME, endpoint_type=EndpointType.STANDARD)
    print(f"Vector Search endpoint '{ENDPOINT_NAME}' created.")
except Exception as e:
    print(f"Endpoint may already exist: {e}")

# Create delta-sync index with Databricks-managed embeddings
try:
    w.vector_search_indexes.create_index(
        name=INDEX_NAME,
        endpoint_name=ENDPOINT_NAME,
        primary_key="doc_id",
        index_type=VectorIndexType.DELTA_SYNC,
        delta_sync_index_spec=DeltaSyncVectorIndexSpecRequest(
            source_table=SOURCE_TABLE,
            pipeline_type=PipelineType.TRIGGERED,
            embedding_source_columns=[
                EmbeddingSourceColumn(
                    name="document",
                    embedding_model_endpoint_name="databricks-gte-large-en",
                )
            ],
        ),
    )
    print(f"Vector Search index '{INDEX_NAME}' created.")
except Exception as e:
    print(f"Index may already exist: {e}")

# COMMAND ----------
# ── Step 4: Register RAG chain with MLflow ────────────────────────────────────
import mlflow
import mlflow.pyfunc

mlflow.set_registry_uri("databricks-uc")

RAG_MODEL_NAME = f"{CATALOG}.{GOLD_SCHEMA}.retailadvisor_rag"

class RetailAdvisorChain(mlflow.pyfunc.PythonModel):
    """
    Simple RAG chain:
    1. Retrieve top-k documents from Vector Search
    2. Build prompt with retrieved context
    3. Call Databricks Foundation Model API (DBRX Instruct)
    4. Return response
    """

    def load_context(self, context):
        from databricks.sdk import WorkspaceClient
        self.w = WorkspaceClient()
        self.index_name = INDEX_NAME

    def predict(self, context, model_input):
        import pandas as pd
        query = model_input["query"].iloc[0] if hasattr(model_input, "iloc") else model_input["query"]

        # Retrieve relevant customer documents
        results = self.w.vector_search_indexes.query_index(
            index_name=self.index_name,
            columns=["doc_id", "document", "customer_name", "segment"],
            query_text=query,
            num_results=5,
        )
        chunks = [r["document"] for r in (results.result.data_array or [])]
        context_text = "\n\n".join(chunks) if chunks else "No relevant customer data found."

        prompt = f"""You are RetailAdvisor, an AI assistant for retail store managers.
Answer using only the customer data provided below. Be concise and actionable.

CUSTOMER DATA:
{context_text}

QUESTION: {query}

ANSWER:"""

        response = self.w.serving_endpoints.query(
            name="databricks-dbrx-instruct",
            dataframe_records=[{"prompt": prompt, "max_tokens": 300}],
        )
        return response.predictions[0] if response.predictions else "Unable to retrieve answer."


with mlflow.start_run(run_name="retailadvisor_rag_v1"):
    mlflow.pyfunc.log_model(
        artifact_path="rag_chain",
        python_model=RetailAdvisorChain(),
        registered_model_name=RAG_MODEL_NAME,
    )
    print(f"RAG chain registered as {RAG_MODEL_NAME}")

print("RAG setup complete. Deploy the model via Databricks Model Serving for the /api/chat endpoint.")
