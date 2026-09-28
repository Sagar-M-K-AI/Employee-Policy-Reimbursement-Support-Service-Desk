import base64
import binascii
import logging
import re
from decimal import Decimal
from io import BytesIO
from pathlib import PurePath

from pypdf import PdfReader

from app.evidence import BENEFIT_TERMS, MONEY, benefits, matches
from app.models import (
    DocumentResult,
    ExtractedFields,
    FieldEvidence,
    InternalDocumentRequest,
    ItemError,
)
from app.policy_service import PolicyService
from app.provider import ProviderFailure


logger = logging.getLogger(__name__)

REVIEW_MESSAGE = (
    "Human review is required; this report does not approve a claim "
    "or authorize payment."
)


class DocumentFailure(Exception):

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def read_document(filename: str, content: bytes) -> str:

    if not content:
        raise DocumentFailure(
            "EMPTY_FILE",
            "The submitted file is empty",
        )

    if len(content) > 5 * 1024 * 1024:
        raise DocumentFailure(
            "FILE_TOO_LARGE",
            "Files must be at most 5 MiB",
        )

    extension = PurePath(filename).suffix.casefold()

    try:
        if extension == ".txt":
            text = content.decode("utf-8-sig")

            if "\x00" in text:
                raise ValueError("Binary text")

        elif extension == ".pdf":
            if not content.startswith(b"%PDF-"):
                raise ValueError("Not a PDF")

            reader = PdfReader(
                BytesIO(content),
                strict=False,
            )

            if reader.is_encrypted:
                raise ValueError("Encrypted PDF")

            if len(reader.pages) > 50:
                raise DocumentFailure(
                    "DOCUMENT_TOO_LARGE",
                    "PDFs must contain at most 50 pages",
                )

            text = "\n".join(
                page.extract_text() or ""
                for page in reader.pages
            )

        else:
            raise DocumentFailure(
                "UNSUPPORTED_FILE_TYPE",
                "Only UTF-8 TXT and text-based PDF files are supported",
            )

    except DocumentFailure:
        raise

    except Exception:
        raise DocumentFailure(
            "UNREADABLE_FILE",
            "The file could not be read as supported text",
        ) from None

    if not text.strip():
        raise DocumentFailure(
            "NO_EXTRACTABLE_TEXT",
            "The file contains no readable text; OCR is not supported",
        )

    if len(text) > 100_000:
        raise DocumentFailure(
            "DOCUMENT_TOO_LARGE",
            "Extracted text exceeds 100000 characters",
        )

    return text


def extract_fields(
    text: str,
) -> tuple[ExtractedFields, FieldEvidence, list[str]]:

    fields = ExtractedFields()
    evidence = FieldEvidence()
    issues = [REVIEW_MESSAGE]

    # Keep the original text as evidence
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", text)
        if sentence.strip()
    ]

    detected_benefits = benefits(text)

    if len(detected_benefits) == 1:
        benefit = detected_benefits[0]

        fields.benefit = benefit

        evidence.benefit = [
            sentence
            for sentence in sentences
            if any(
                matches(sentence, term)
                for term in BENEFIT_TERMS[benefit]
            )
        ]

    else:
        issues.append(
            "Benefit is missing or ambiguous; "
            "policy selection requires clarification."
        )

    money_matches = list(MONEY.finditer(text))

    amounts = {
        Decimal(match[2].replace(",", ""))
        for match in money_matches
    }

    currencies = {
        match[1].upper()
        for match in money_matches
    }

    if len(amounts) == 1 and len(currencies) == 1:
        fields.amount = next(iter(amounts))

        evidence.amount = list(
            dict.fromkeys(
                match[0]
                for match in money_matches
            )
        )

    elif money_matches:
        issues.append(
            "Amount is ambiguous; candidate quotations: "
            + " | ".join(
                dict.fromkeys(
                    match[0]
                    for match in money_matches
                )
            )
        )

    else:
        issues.append(
            "Amount is missing or unsupported; no unambiguous "
            "currency-qualified amount was found."
        )

    if len(currencies) == 1:
        fields.currency = next(iter(currencies))

        evidence.currency = list(
            dict.fromkeys(
                match[0]
                for match in money_matches
            )
        )

    else:
        issues.append("Currency is missing or ambiguous.")

    references = list(
        re.finditer(
            r"\bReference\s*:\s*([A-Za-z0-9][A-Za-z0-9_-]*)",
            text,
            re.I,
        )
    )

    reference_values = {
        match[1]
        for match in references
    }

    if len(reference_values) == 1:
        fields.reference = next(iter(reference_values))

        evidence.reference = list(
            dict.fromkeys(
                match[0]
                for match in references
            )
        )

    else:
        issues.append("Reference is missing or ambiguous.")

    if re.search(
        r"system message|ignore.{0,30}(header|rules)|mark.{0,30}approved",
        text,
        re.I,
    ):
        issues.append(
            "Instruction-like document text was treated as untrusted data; "
            "caller identity and review requirements were not changed."
        )

    return fields, evidence, issues


class DocumentService:

    def __init__(self, policy_service: PolicyService):
        self.policy_service = policy_service

    def process(
        self,
        request: InternalDocumentRequest,
    ) -> DocumentResult:

        try:
            try:
                content = base64.b64decode(
                    request.content_base64,
                    validate=True,
                )

            except (ValueError, binascii.Error):
                raise DocumentFailure(
                    "UNREADABLE_FILE",
                    "File encoding is invalid",
                ) from None

            text = read_document(
                request.filename,
                content,
            )

            fields, evidence, issues = extract_fields(text)

            policy = None

            if fields.benefit:
                policy = self.policy_service.answer(
                    request.tenant,
                    request.role,
                    request.as_of,
                    fields.benefit,
                )

                if policy.status == "CONFLICT":
                    issues.append(
                        "Applicable policies disagree; a reviewer must "
                        "resolve the policy conflict."
                    )

                elif policy.status == "INSUFFICIENT_EVIDENCE":
                    issues.append(
                        "No supported applicable policy terms were "
                        "found for this benefit."
                    )

                else:
                    issues.append(
                        "Policy terms do not establish remaining balance, "
                        "individual expense eligibility, or a payable amount; "
                        "no claims history is supplied."
                    )

                    if any(
                        "approval" in citation.quote.casefold()
                        for citation in policy.citations
                    ):
                        issues.append(
                            "A reviewer must verify the policy's approval "
                            "requirement, including whether approval "
                            "preceded booking."
                        )

            result = DocumentResult(
                document_id=request.document_id,
                processing_status="COMPLETED",
                extracted=fields,
                field_evidence=evidence,
                policy=policy,
                issues=issues,
            )

        except (DocumentFailure, ProviderFailure) as exception:
            result = self.failed(
                request.document_id,
                exception.code,
                str(exception),
            )

        except Exception:
            # Keep the error response safe
            result = self.failed(
                request.document_id,
                "PROCESSING_FAILURE",
                "Document processing failed",
            )

        logger.info(
            "batch=%r document=%r status=%s error=%s",
            request.batch_id,
            request.document_id,
            result.processing_status,
            result.error.code if result.error else "none",
        )

        return result

    @staticmethod
    def failed(
        document_id: str,
        code: str,
        message: str,
    ) -> DocumentResult:

        return DocumentResult(
            document_id=document_id,
            processing_status="FAILED",
            issues=[REVIEW_MESSAGE],
            error=ItemError(
                code=code,
                message=message,
            ),
        )