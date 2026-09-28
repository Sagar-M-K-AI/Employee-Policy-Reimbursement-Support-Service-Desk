import logging
import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.document_service import DocumentService
from app.models import (
    DocumentResult,
    InternalAnswerRequest,
    InternalDocumentRequest,
    PolicyAnswer,
)
from app.policy_repository import PolicyRepository
from app.policy_service import PolicyService
from app.provider import GenerationService, ProviderFailure


logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Employee Policy and Reimbursement Service")

model_timeout = float(os.getenv("MODEL_TIMEOUT_SECONDS", "1"))

policy_repository = PolicyRepository()
generation_service = GenerationService(timeout=model_timeout)
policy_service = PolicyService(policy_repository, generation_service)
document_service = DocumentService(policy_service)


@app.exception_handler(ProviderFailure)
def provider_failure(request, exception: ProviderFailure):
    error = {
        "code": exception.code,
        "message": str(exception),
    }

    return JSONResponse(
        status_code=503,
        content=error,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "UP",
        "service": "python-service",
    }


@app.post("/internal/answer", response_model=PolicyAnswer)
def answer(request: InternalAnswerRequest) -> PolicyAnswer:
    return policy_service.answer_question(
        tenant=request.tenant,
        role=request.role,
        as_of=request.as_of,
        question=request.question,
    )


@app.post("/internal/document", response_model=DocumentResult)
def document(request: InternalDocumentRequest) -> DocumentResult:
    return document_service.process(request)