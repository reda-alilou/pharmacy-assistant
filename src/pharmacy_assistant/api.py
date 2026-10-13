from typing import Annotated

from fastapi import FastAPI, Query

from pharmacy_assistant.search_medications import search_medications


app = FastAPI(
    title="Patient–Pharmacy Assistant API",
    version="0.1.0",
    description="Multilingual patient–pharmacy assistant for Morocco.",
)


@app.get("/medications/search")
def search_medication_endpoint(
    query: Annotated[
        str,
        Query(min_length=1, description="Medication name or active substance"),
    ],
):
    medications = search_medications(query)

    return {
        "query": query,
        "result_count": len(medications),
        "medications": medications,
        "catalog_scope": "partial",
    }