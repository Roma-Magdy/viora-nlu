from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

from fanar_nlu import fanar_nlu
from router import route_nlu_result

app = FastAPI(title="Viora NLU Server (Fanar)", description="API for parsing Arabic/English commands.")

class QueryRequest(BaseModel):
    text: str

@app.post("/api/v1/parse")
async def parse_command(request: QueryRequest):
    try:
        # Pass text to Fanar
        nlu_result = fanar_nlu(request.text)
        
        # Get the routing decision
        decision, payload = route_nlu_result(nlu_result)
        
        return {
            "viora_reply": payload.viora_response,
            "decision": decision,
            "intent": payload.intent,
            "confidence": payload.confidence,
            "entities": payload.entities.model_dump(exclude_none=True),
            "needs_clarification": payload.needs_clarification
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)