
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from pharmacy_core.conversation.image import IMAGE_MESSAGE, MAX_IMAGE_BYTES
from pharmacy_core.conversation.models import ChatRequest, ChatResponse
from pharmacy_contracts.interpretation import InferenceErrorResponse, InterpretationRequest, InterpretationResponse

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


@router.post(
    "/chat/image", response_model=ChatResponse,
    responses={413: {"description": "Image too large"}, 422: {"description": "Invalid image or conversation"},
               **{code: {"model": InferenceErrorResponse} for code in (502, 503, 504)}},
)
async def chat_image(
    request: Request,
    file: Annotated[UploadFile, File()],
    session_id: Annotated[str | None, Form()] = None,
    request_id: Annotated[str | None, Form()] = None,
):
    content_type = (file.content_type or "").lower()
    if content_type and not (content_type.startswith("image/") or content_type == "application/octet-stream"):
        raise HTTPException(status_code=422, detail={"code": "image_invalid",
            "message": "Envoyez une image (JPEG, PNG ou WebP)."})
    try:
        image_bytes = await file.read(MAX_IMAGE_BYTES + 1)
    finally:
        await file.close()
    if not image_bytes:
        raise HTTPException(status_code=422, detail={"code": "image_invalid",
            "message": "La photo envoyée est vide."})
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail={"code": "image_too_large",
            "message": "La photo dépasse la taille maximale de 15 Mo."})
    responder = getattr(request.app.state.chat, "respond_image", None)
    if responder is None:
        raise HTTPException(status_code=503, detail={"code": "image_unavailable",
            "message": "L'identification des photos n'est pas configurée."})
    payload = ChatRequest(text=IMAGE_MESSAGE, session_id=session_id, request_id=request_id)
    return await responder(payload, image_bytes, content_type or "application/octet-stream")
