import os
import pg8000
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from langserve import add_routes
from google.cloud.sql.connector import Connector

# LangChain Imports
from langchain_community.vectorstores.pgvector import PGVector
from langchain_google_vertexai import VertexAIEmbeddings, ChatVertexAI, HarmBlockThreshold, HarmCategory
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableParallel
from langchain_core.output_parsers import StrOutputParser

# 1. Database Connection Setup
connector = Connector()

def getconn() -> pg8000.dbapi.Connection:
    conn: pg8000.dbapi.Connection = connector.connect(
        os.environ.get("DB_INSTANCE_NAME", ""),
        "pg8000",
        user=os.environ.get("DB_USER", ""),
        password=os.environ.get("DB_PASS", ""),
        db=os.environ.get("DB_NAME", ""),
    )
    return conn

# 2. Initialize Vector Store
# Ensure this matches the model used in your indexer.py (text-embedding-004)
embedding_service = VertexAIEmbeddings(model_name="text-embedding-004")

vectorstore = PGVector(
    connection_string="postgresql+pg8000://",
    use_jsonb=True,
    engine_args=dict(
        creator=getconn,
    ),
    embedding_function=embedding_service,
)

# 3. Create the Retriever
retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

def format_docs(docs):
    # Debugging: Print retrieved docs to logs
    print(f"DEBUG: Retrieved {len(docs)} documents.")
    return "\n\n".join(doc.page_content for doc in docs)

# 4. Define the Prompt Template (Chat Prompt)
template = """You are a helper for Google Cloud Run developers.
Answer the question based only on the following context:
{context}

Question: {question}
"""
prompt = ChatPromptTemplate.from_template(template)

# 5. Initialize the LLM (Gemini) with Safety Settings
# CRITICAL FIX: Lowering safety thresholds to prevent empty responses
safety_settings = {
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
}

llm = ChatVertexAI(
    model="gemini-2.0-flash-001", 
    temperature=0,
    safety_settings=safety_settings
)

# 6. Build the RAG Chain
chain = (
    RunnableParallel({
        "context": retriever | format_docs,
        "question": RunnablePassthrough()
    })
    | prompt
    | llm
    | StrOutputParser()
)

# 7. FastAPI App Definition
app = FastAPI(
    title="LangChain Server",
    version="1.0",
    description="A simple API server using LangChain's Runnable interfaces",
)

@app.get("/")
async def redirect_root_to_docs():
    return RedirectResponse("/docs")

# 8. Add the Chain to the App
add_routes(app, chain, path="/rag")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)