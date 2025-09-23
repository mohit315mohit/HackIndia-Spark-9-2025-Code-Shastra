from flask import Flask, request, jsonify
from flask_cors import CORS
import os, json
import time
from datetime import datetime
from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains import create_retrieval_chain
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFDirectoryLoader, JSONLoader
from langchain_huggingface import HuggingFaceEmbeddings


# -------------------------------------------------------------------
# Load environment variables
# -------------------------------------------------------------------
load_dotenv()
groq_api_key = os.getenv("GROQ_API_KEY")

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# # -------------------------------------------------------------------
# # Initialize LLM
# # -------------------------------------------------------------------
# def initialize_llm():
#     return ChatGroq(
#         groq_api_key=groq_api_key,
#         model_name="llama-3.3-70b-versatile"
#     )

# -------------------------------------------------------------------
# Prompt Template
# -------------------------------------------------------------------
def initialize_prompt():
    return ChatPromptTemplate.from_template("""
    You are *CampusCopilot, an AI Companion for students, providing **strictly accurate and helpful information* based on *official college data sources*.

    *STRICT RESPONSE GUIDELINES:*  
    1. Use ONLY the provided college data to answer queries. No assumptions.  
    2. Directly present the relevant information.  
    3. If unavailable, reply with:
       "Information not available in the current database."
    4. If related but missing, reply with:
       "This information is currently not available. For assistance, please contact the college helpdesk or refer to official resources."
    5. Provide a clear and complete answer.

    *Official College Data Sources:*  
    {context}

    *Query:* {input}
    """)

# -------------------------------------------------------------------
# Build Vector Database (FAISS)
# -------------------------------------------------------------------
vectors = None

# from langchain_huggingface import HuggingFaceEmbeddings

# def process_documents():
#     global vectors
#     try:
#         embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
#         loader = PyPDFDirectoryLoader("./Data")
#         docs = loader.load()
#         if not docs:
#             raise ValueError("No PDF documents found in ./Data folder")
#         text_splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=200)
#         final_docs = text_splitter.split_documents(docs)
#         vectors = FAISS.from_documents(final_docs, embeddings)
#         return True
#     except Exception as e:
#         print(f"Protocol database initialization error: {e}")
#         return False



def initialize_llm():
    model = "llama-3.1-8b-instant"  # <-- update if needed
    return ChatGroq(
        groq_api_key=os.getenv("GROQ_API_KEY"),
        model_name=model
    )

# 

def process_documents():
    global vectors
    try:
        embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )

        # Load PDFs
        pdf_loader = PyPDFDirectoryLoader("../data",recursive=True)
        pdf_docs = pdf_loader.load()

        # Load JSONs (loop over all JSON files in directory)
        json_docs = []
        for filename in os.listdir("../data"):
            if filename.endswith(".json"):
                loader = JSONLoader(
                    file_path=os.path.join("../data", filename),
                    jq_schema=".",   # you can customize what fields to extract
                    text_content=False
                )
                json_docs.extend(loader.load())

        # Combine docs
        docs = pdf_docs + json_docs

        if not docs:
            print("⚠ No documents found in ../data")
            return False

        # Split
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=2000, chunk_overlap=200
        )
        final_docs = splitter.split_documents(docs)

        # Vector DB
        vectors = FAISS.from_documents(final_docs, embeddings)
        return True

    except Exception as e:
        print(f"❌ Vector DB init error: {e}")
        return False


# Initialize documents at startup
if process_documents():
    print("Vector database initialized successfully")
else:
    print("Failed to initialize vector database")

# -------------------------------------------------------------------
# API Endpoints
# -------------------------------------------------------------------
@app.route('/api/query', methods=['POST'])
def process_query():
    global vectors
    if not vectors:
        return jsonify({"error": "Vector database not initialized"}), 500

    data = request.json
    query = data.get("query")
    if not query:
        return jsonify({"error": "No query provided"}), 400

    try:
        llm = initialize_llm()
        document_chain = create_stuff_documents_chain(llm, initialize_prompt())
        retrieval_chain = create_retrieval_chain(vectors.as_retriever(), document_chain)

        start_time = time.time()
        response = retrieval_chain.invoke({"input": query})
        processing_time = time.time() - start_time

        context_data = [
            {"page_content": doc.page_content, "metadata": doc.metadata}
            for doc in response["context"]
        ]

        return jsonify({
            "answer": response["answer"],
            "processing_time": processing_time,
            "context": context_data
        })

    except Exception as e:
        print(e)
        return jsonify({"error": str(e)}), 500


@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify({
        "system": "online",
        "updated": datetime.now().strftime('%Y-%m-%d'),
        "database": "active" if vectors else "offline"
    })

# -------------------------------------------------------------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5000)