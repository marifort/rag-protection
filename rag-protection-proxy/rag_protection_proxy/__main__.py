"""Run with: python -m rag_protection_proxy"""

import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "rag_protection_proxy.app:app",
        host=os.getenv("RAG_HOST", "0.0.0.0"),
        port=int(os.getenv("RAG_PORT", "8090")),
        reload=bool(os.getenv("RAG_RELOAD", "")),
    )
