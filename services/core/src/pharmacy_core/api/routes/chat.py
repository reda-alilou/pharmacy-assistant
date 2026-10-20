
from fastapi import Request

from pharmacy_core.conversation.models import ChatRequest, ChatResponse
from pharmacy_contracts.interpretation import InferenceErrorResponse, InterpretationRequest, InterpretationResponse


from fastapi import APIRouter

router = APIRouter()


@router.post(
    "/interpret", response_model=InterpretationResponse,
    responses={code: {"model": InferenceErrorResponse} for code in (429, 502, 503, 504)},
)
async def interpret_patient_request(payload: InterpretationRequest, request: Request):
    return await request.app.state.interpreter.interpret(payload)


@router.post(
    "/chat", response_model=ChatResponse,
    responses={410: {"description": "Clarification expired or lost after server restart"},
               **{code: {"model": InferenceErrorResponse} for code in (429, 502, 503, 504)}},
)
async def chat(payload: ChatRequest, request: Request):
    return await request.app.state.chat.respond(payload)
