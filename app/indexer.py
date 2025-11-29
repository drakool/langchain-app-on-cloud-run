import os
import pg8000
from google.cloud import bigquery
from google.cloud.sql.connector import Connector
from langchain_community.vectorstores.pgvector import PGVector
from langchain_google_vertexai import VertexAIEmbeddings

# 1. Configuration
# Use the newer, more performant "text-embedding-004" model
EMBEDDING_MODEL = "text-embedding-004" 
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT") # Ensure this env var is set or inferred

def retrieve_release_notes():
    """Fetches Cloud Run release notes from BigQuery public datasets."""
    print("Fetching release notes from BigQuery...")
    client = bigquery.Client()
    query = """
    SELECT
      CONCAT(FORMAT_DATE("%B %d, %Y", published_at), ": ", description) AS release_note
    FROM `bigquery-public-data.google_cloud_release_notes.release_notes`
    WHERE product_name= "Cloud Run"
    ORDER BY published_at DESC
    """
    rows = client.query(query)
    results = list(rows)
    print(f"Retrieved {len(results)} release notes.")
    return results

def getconn() -> pg8000.dbapi.Connection:
    """Creates a connection to Cloud SQL using the Python Connector."""
    connector = Connector()
    conn: pg8000.dbapi.Connection = connector.connect(
        os.environ["DB_INSTANCE_NAME"],
        "pg8000",
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASS"],
        db=os.environ["DB_NAME"],
    )
    return conn

def index_data():
    # 2. Setup Embeddings
    embedding_service = VertexAIEmbeddings(
        model_name=EMBEDDING_MODEL
    )

    # 3. Initialize Vector Store
    # Note: We use the 'creator' argument to inject the Cloud SQL connector
    store = PGVector(
        connection_string="postgresql+pg8000://",
        use_jsonb=True,
        engine_args=dict(
            creator=getconn,
        ),
        embedding_function=embedding_service,
        pre_delete_collection=True  # Clears the table before re-indexing
    )

    # 4. Fetch and Index
    rows = retrieve_release_notes()
    if rows:
        texts = [row["release_note"] for row in rows]
        print(f"Generating embeddings for {len(texts)} documents...")
        
        # Add texts in batches is handled automatically by PGVector, 
        # but we call it once here for simplicity.
        ids = store.add_texts(texts)
        print(f"Successfully indexed {len(ids)} documents into Cloud SQL.")
    else:
        print("No release notes found to index.")

if __name__ == "__main__":
    index_data()