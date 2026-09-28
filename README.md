# Employee Policy & Reimbursement Support Service

A local employee-support application built using **Spring Boot** and **Python FastAPI**. The application provides two main capabilities:

- Answer employee policy-related questions using the applicable policy records.
- Process reimbursement documents and generate a structured report for human review.

Spring Boot acts as the public-facing API, while the Python service handles document processing, policy evaluation, and response generation.

The system is designed strictly as a **decision-support and review tool**. It does not approve reimbursement claims, trigger payments, or communicate decisions directly to employees.


## Architecture

The application uses two separate services: **Spring Boot** provides the public-facing API, while **Python FastAPI** is responsible for document processing, policy retrieval, and answer generation.

```text
                         Client
                           |
                           v
                  Spring Boot :8080
                    /             \
                   /               \
            POST /answer       POST /batches
                  |                  |
          Caller + request      Manifest + file
             validation           validation
                  |                  |
                  v                  v
       Python /internal/answer   Python /internal/document
                  |                  |
                  |           TXT / PDF extraction
                  |           + field identification
                  |                  |
                  +----------> Policy retrieval
                                     |
                                     v
                            Eligible policy records
                                     |
                                     v
                           Offline model provider
                                     |
                                     v
                          Evidence-backed response
```

### Spring Boot Responsibilities

Spring Boot acts as the main entry point for the application. Its responsibilities include:

- Resolving the caller using the `X-Caller-Id` header.
- Validating incoming requests and the `as_of` date.
- Validating multipart batch metadata and uploaded files.
- Detecting exact duplicate files within a batch.
- Isolating document-level failures so one failed item does not stop the remaining batch.
- Preserving the original manifest order in the final batch response.
- Returning the final response through the public API.

Caller information such as the **tenant** and **role** is obtained from the application's trusted caller lookup. Values written inside uploaded documents or request content cannot replace this identity information.

### Python FastAPI Responsibilities

The Python service performs the document and policy-processing operations. It is responsible for:

- Extracting text from supported TXT and text-based PDF files.
- Identifying reimbursement fields such as benefit, amount, currency, and reference.
- Keeping source quotations as evidence for extracted values.
- Selecting policies that are applicable to the caller's tenant, role, and requested date.
- Determining whether the available policy evidence supports an answer, provides insufficient evidence, or contains a conflict.
- Producing evidence-backed answers through the offline provider.

The Spring Boot service sends server-derived caller information to the Python service. The Python endpoints do not provide separate authentication for this assessment, so the service is intended to run on `127.0.0.1` and only the Spring Boot API should be exposed to clients.

### Offline Model

A deterministic offline model double is included so that the application and automated tests can run without an external AI service, paid model, or personal API key.

The project does not require a database, frontend, OCR service, or cloud deployment.

Uploaded documents, policy passages, and generated model output are treated as untrusted data. Instructions contained inside a reimbursement document cannot change caller identity, access rules, or application behavior. Only eligible policy evidence is allowed to participate in answer generation.


## Prerequisites and Local Setup

Before starting the application, make sure the following are installed:

- **Python 3.11 or later**
- **JDK 21**
- Internet access during the initial dependency installation

The Maven wrapper is already included in the repository, so a separate Maven installation is not required.

After the dependencies are installed, the project can run locally without an external model service or API key.

### 1. Start the Python Service

Open a PowerShell terminal from the repository root and run:

```powershell
cd policy-service

python -m venv .venv

.\.venv\Scripts\python.exe -m pip install -r requirements.txt

.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The FastAPI service will start locally on port `8000`.

Its API documentation can be accessed at:

`http://localhost:8000/docs`

### 2. Start the Spring Boot Service

Open another PowerShell terminal from the repository root and run:

```powershell
cd spring-api

.\mvnw.cmd spring-boot:run
```

The Spring Boot application runs on port `8080` by default.

Restart the Spring Boot service whenever Java source code is modified.

If Python reports that the `uvicorn` module is unavailable, install the dependencies using the Python executable inside the virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Configuration

The application uses the following default configuration:

| Configuration | Default Value |
|---|---|
| Spring Boot port | `8080` |
| `PYTHON_SERVICE_BASE_URL` | `http://localhost:8000` |
| `python-service.connect-timeout` | `2s` |
| `python-service.read-timeout` | `5s` per internal request |
| Python `MODEL_TIMEOUT_SECONDS` | `1 second` |
| Maximum multipart file size | `5 MiB` |
| Maximum multipart request size | `25 MiB` |
| Maximum documents per batch | `20` |
| Maximum PDF pages | `50` |
| Maximum extracted characters | `100000` |

### Timeout and Retry Behaviour

The Python model timeout is intentionally configured to be shorter than the Java service read timeout. This allows model-related failures to be handled before the Java-to-Python request itself reaches its timeout.

Batch documents are processed sequentially. Because of this, the total time required to process a batch may be longer than the timeout configured for an individual internal request.

The application does not perform automatic application-level retries. The Java launcher also disables automatic connection retries from the JDK HTTP client.

For each supported policy question or reimbursement item, the model provider is called no more than once. Cases that result in **insufficient evidence** or a **policy conflict** are resolved without calling the model provider.


## Caller Identity and Access Context

For this assessment, the `X-Caller-Id` request header is used to simulate an authenticated user. Each valid caller is mapped to a predefined **tenant** and **role**.

| Caller ID | Organization | Role |
|---|---|---|
| `atlas-employee-01` | Atlas | employee |
| `atlas-contractor-01` | Atlas | contractor |
| `boreal-employee-01` | Boreal | employee |

### Identity Handling

The application uses the caller ID to determine which policy records the requester is allowed to access.

The following rules are applied:

- `X-Caller-Id` must be included with requests to the public endpoints.
- The caller must exist in the application's predefined identity lookup.
- Missing or unrecognized caller IDs are rejected.
- Tenant and role are determined only from the trusted caller mapping.
- Identity information written inside an uploaded document is treated as untrusted content.
- Request data cannot override the tenant or role associated with the caller.

For example, if `atlas-employee-01` submits a document claiming that the employee belongs to **Boreal**, the application continues to use the trusted **Atlas / employee** identity associated with the request header.

This approach is only used to simulate authentication for the local assessment and should not be considered a production authentication mechanism.


## Policy Question API

The application exposes the following endpoint for employee policy-related questions:

`POST /answer`

Requests must use `Content-Type: application/json` and include a valid `X-Caller-Id` header.

Example:

```http
POST /answer
Content-Type: application/json
X-Caller-Id: atlas-employee-01
```

Request body:

```json
{
  "question": "What is my annual certification reimbursement limit?",
  "as_of": "2026-09-21"
}
```

The `question` field must contain a non-empty string, and `as_of` must be a valid date in `YYYY-MM-DD` format.

### Example Request

With both services running, the example request can be executed from the repository root using:

```powershell
curl.exe -X POST http://localhost:8080/answer `
  -H "Content-Type: application/json" `
  -H "X-Caller-Id: atlas-employee-01" `
  --data-binary "@sample-data/answer-request.json"
```

### Response Structure

Valid business outcomes return HTTP `200` with the following structure:

```json
{
  "status": "ANSWERED",
  "answer": "Supported answer text",
  "citations": [
    {
      "chunk_id": "policy-id",
      "quote": "Exact quotation from the eligible policy."
    }
  ]
}
```

Every citation contains:

- `chunk_id` – identifier of the supporting policy record.
- `quote` – verbatim text taken from that policy record.

The API can return one of three policy outcomes:

| Status | Meaning |
|---|---|
| `ANSWERED` | The eligible policy evidence is sufficient to provide a supported answer. |
| `INSUFFICIENT_EVIDENCE` | The available policy records do not provide enough evidence to answer the question. |
| `CONFLICT` | Multiple applicable policy records provide contradictory information and no precedence rule is available to resolve them. |

For `INSUFFICIENT_EVIDENCE`, the `answer` is `null` and the citation list is empty.

For `CONFLICT`, the `answer` is also `null`, while the citations contain the eligible policy quotations that demonstrate the disagreement.

### Policy Selection

Before policy information can be used, records are filtered using the caller context and requested date.

A policy is eligible only when:

- The policy tenant matches the caller's tenant.
- The permitted role matches the caller's role.
- Its approval state is exactly `Approved`.
- The requested date satisfies:

```text
effective_from <= as_of < effective_to
```

Policy records are stored separately from the application logic. Their eligibility should therefore continue to behave correctly when records are reordered, duplicated, added, or modified within the supported data structure.

Exact duplicate records containing the same policy ID and text are deduplicated before producing the final result. Citations are returned in a deterministic order.

### Evidence Handling

Policy selection is based on relevant policy assertions rather than simple keyword matching.

For example, a policy containing the word `certification` is not automatically sufficient for every certification-related question. If the question asks for an annual reimbursement amount, the selected evidence must actually contain information that supports that amount.

Different policy statements may complement one another when they describe separate facts. However, when simultaneously applicable policies disagree about the same fact and no precedence rule is defined, the result is reported as `CONFLICT`.

The application does not use general knowledge or reimbursement request text to fill missing information in the policy corpus.

### Supported Policy Topics

The current implementation recognizes policy questions related to:

- Certification reimbursement
- Home-office / home office allowance
- Business travel
- External training
- Wellness / gym benefits

Questions about individual claim approval, remaining annual balance, expense eligibility, or the exact payable reimbursement amount are handled conservatively when those conclusions cannot be established from the supplied policy data.

For example, knowing that an employee has an annual certification limit does not establish how much of that limit remains available or whether a particular submitted expense should be paid.


## Batch Reimbursement Processing

The `/batches` endpoint accepts multiple reimbursement documents in a single request and processes them synchronously.

`POST /batches`

The request must use `multipart/form-data` and include the same `X-Caller-Id` header used by the policy question endpoint.

### Request Components

A batch request contains:

- One `metadata` part containing JSON with `Content-Type: application/json`.
- One or more `files` parts containing the reimbursement documents.
- A single caller identity and `as_of` date that apply to the complete batch.

Each uploaded filename must have a corresponding entry in the metadata manifest.

Within a batch:

- Every `document_id` must be unique.
- Every filename must be unique.
- Document IDs may contain letters, numbers, underscores (`_`), and hyphens (`-`).
- Filenames may contain letters, numbers, dots (`.`), underscores (`_`), and hyphens (`-`).
- File paths are not accepted as manifest filenames.

If the manifest contains duplicate identifiers, duplicate filenames, missing files, or unexpected additional files, the complete batch request is rejected before document processing starts.

### Example Metadata

```json
{
  "batch_id": "demo-01",
  "as_of": "2026-09-21",
  "documents": [
    {
      "document_id": "request-01",
      "filename": "request-01.txt"
    }
  ]
}
```

The manifest containing all supplied sample requests is available at:

`sample-data/batch-metadata.json`

The corresponding reimbursement documents are stored under:

`sample-data/requests`

The supplied dataset contains eight requests with different scenarios, including:

- Standard TXT reimbursement requests.
- A text-based PDF document.
- Conflicting values inside a document.
- A request for a benefit without sufficient policy evidence.
- Untrusted instructions attempting to change caller context.
- An exact byte-level duplicate.
- Missing reimbursement information.
- A zero-byte file.

In the supplied sample-data files, `request-02.pdf` is the text-based PDF, `request-06.txt` contains the exact bytes of `request-01.txt`, and `request-08.txt` is intentionally empty.

### Running the Sample Batch

Start both the Spring Boot and Python services, then run the demonstration script from the repository root:

```powershell
python scripts/demo.py
```

The script exercises both public endpoints, validates the expected behaviour, and writes representative response JSON files to:

`sample-data/responses`

A different Spring Boot URL can also be supplied:

```powershell
python scripts/demo.py --base-url http://localhost:8081
```

### Batch Processing Behaviour

Each manifest entry produces its own result.

Documents are processed independently so that a failure in one item does not prevent the remaining items from being processed.

Readable documents with missing or ambiguous information are not considered processing failures. Instead, unresolved information is preserved in the result and highlighted for human review.

Exact duplicate files are also retained as individual submissions. The later duplicate points to the earlier document through `duplicate_of`, but it is still processed and returned as a separate result.

Every reimbursement request requires human review. The service only reports extracted information and applicable policy evidence; it does not make a final reimbursement approval or payment decision.

### Expected Results for the Supplied Batch

When the supplied eight-document batch is processed using `atlas-employee-01` with an `as_of` date of `2026-09-21`, the expected high-level outcomes are:

| Document | Status | Expected behaviour |
|---|---|---|
| `request-01` | `COMPLETED` | Extracts the INR 18000 certification request and finds the INR 25000 annual certification limit. Whether the individual claim is payable remains unresolved. |
| `request-02` | `COMPLETED` | Extracts the text-based PDF and reports the conflicting INR 12000 and INR 15000 home-office policy amounts. |
| `request-03` | `COMPLETED` | Keeps the requested amount unresolved because both INR 22000 and INR 28000 appear as candidates, while the applicable certification policy can still be determined. |
| `request-04` | `COMPLETED` | Identifies the wellness request, but the policy corpus does not provide sufficient evidence for the requested benefit. |
| `request-05` | `COMPLETED` | Treats the embedded Boreal and approval instructions as untrusted content and continues using the Atlas caller context. |
| `request-06` | `COMPLETED` | Returns an independent result and identifies `request-01` as its exact duplicate source. |
| `request-07` | `COMPLETED` | Reports missing amount/currency information and identifies the manager-approval requirement for external training. |
| `request-08` | `FAILED` | Returns an `EMPTY_FILE` item-level failure without preventing the other documents from completing. |


### Batch Response Structure

A successful batch request returns a response containing the batch identifier, processing summary, and one result for every document listed in the manifest.

The top-level response contains:

- `batch_id` – identifies the submitted batch.
- `summary` – contains `total`, `completed`, and `failed` counts.
- `results` – contains document results in the same order as the input manifest.

### Document Result Fields

Each entry in `results` uses the following fields:

| Field | Description |
|---|---|
| `document_id` | Identifier assigned to the document in the batch manifest. |
| `processing_status` | Indicates whether processing resulted in `COMPLETED` or `FAILED`. |
| `extracted` | Contains the detected `benefit`, `amount`, `currency`, and `reference`. It is `null` when document processing fails. |
| `field_evidence` | Stores supporting quotations from the extracted document for each identified field. |
| `policy` | Contains the same policy-result structure used by `/answer`. It is `null` when processing fails or when the requested benefit cannot be identified. |
| `review_required` | Always `true` because every submitted reimbursement request requires human review. |
| `issues` | Lists conditions that require reviewer attention, including missing or ambiguous information and relevant policy limitations. |
| `duplicate_of` | Contains the earlier document ID when the uploaded file is an exact byte-for-byte duplicate; otherwise `null`. |
| `error` | Contains a stable error `code` and safe `message` when processing fails; otherwise `null`. |

### Extracted Values and Evidence

The `extracted` object contains four fields:

```json
{
  "benefit": "certification",
  "amount": "18000",
  "currency": "INR",
  "reference": "CERT-101"
}
```

Amounts are represented as **decimal strings** rather than floating-point numbers. For example:

```json
"amount": "18000"
```

This avoids unnecessary floating-point precision or rounding problems.

When an extracted value is missing or cannot be resolved confidently, that field is returned as `null`.

Its corresponding `field_evidence` array remains empty when no supported value can be established.

If multiple amount candidates are found and the document does not establish which one is correct, the amount remains unresolved. The relevant candidate quotations are retained through the review information rather than selecting one arbitrarily.

The currency can still be returned when it is clearly identified even if the numerical amount itself is ambiguous.

For PDF documents, evidence quotations refer to the text extracted from the PDF rather than locations in the raw PDF byte stream.

### Completed vs Failed Items

A document can have unresolved information and still have:

```text
processing_status = COMPLETED
```

Missing or ambiguous business information is treated as a **review condition**, not automatically as a technical processing failure.

A document is marked as `FAILED` when processing cannot be completed because of conditions such as:

- An unreadable or empty file.
- Document parsing failure.
- Internal service failure.
- Model provider timeout or unavailability.
- Invalid model output.

When an item fails, its `policy` value is `null` and the `error` object describes the failure using a stable error code and safe message.

### Duplicate Documents

Duplicate detection is based on the exact uploaded file bytes.

When a document is identical to an earlier document in the same batch, `duplicate_of` contains the earlier document ID.

For example:

```json
{
  "document_id": "request-06",
  "processing_status": "COMPLETED",
  "duplicate_of": "request-01"
}
```

A duplicate is **not removed or skipped**. It remains an independent manifest entry, is processed independently, and receives its own result.

### Human Review

Every successfully processed reimbursement request still requires human review:

```json
"review_required": true
```

The generated result is intended to assist the reviewer by presenting extracted request information, supporting evidence, applicable policy information, and unresolved issues.

It does not represent claim approval, payment authorization, or a final reimbursement decision.


### Testing the APIs with Postman

Both public endpoints can also be tested using Postman.

#### Testing `/answer`

Create a new `POST` request:

```text
http://localhost:8080/answer
```

Add the following headers:

| Key | Value |
|---|---|
| `X-Caller-Id` | `atlas-employee-01` |
| `Content-Type` | `application/json` |

Under **Body → raw → JSON**, provide a request such as:

```json
{
  "question": "What is my annual certification reimbursement limit?",
  "as_of": "2026-09-21"
}
```

Send the request to receive the corresponding policy result with its status, answer, and supporting citations.

#### Testing `/batches`

Create another `POST` request:

```text
http://localhost:8080/batches
```

Add the caller header:

```text
X-Caller-Id: atlas-employee-01
```

Then open **Body → form-data** and configure the request as follows:

1. Add a field named `metadata`.
   - Keep its type as **Text**.
   - Paste the batch manifest JSON into the value.
   - Set the Content-Type of this individual part to `application/json`.

2. Add a field named `files`.
   - Change its type to **File**.
   - Select the reimbursement documents referenced by the manifest.
   - If necessary, repeat the `files` field for multiple documents.

3. Confirm that every uploaded filename exactly matches the corresponding filename declared in the metadata manifest.

4. Send the request after both the Spring Boot and Python services are running.

A sample metadata value is:

```json
{
  "batch_id": "demo-01",
  "as_of": "2026-09-21",
  "documents": [
    {
      "document_id": "request-01",
      "filename": "request-01.txt"
    }
  ]
}
```

Postman should generate the multipart request boundary automatically.

Do **not** manually configure the complete `/batches` request with:

```text
Content-Type: application/json
```

The `/batches` endpoint expects `multipart/form-data`. Only the `metadata` part inside that multipart request should use `application/json`.


## Error Handling

The application separates request-level validation errors, document-level processing failures, and downstream dependency failures.

Errors that invalidate the complete public request use the following response structure:

```json
{
  "code": "INVALID_REQUEST",
  "message": "Safe description of the error"
}
```

### Public API Errors

| HTTP Status / Location | Error Codes |
|---|---|
| `400 Bad Request` | `INVALID_CALLER`, `INVALID_REQUEST`, `INVALID_BATCH` |
| `413 Payload Too Large` | `UPLOAD_TOO_LARGE` |
| `503` from `/answer` | `PYTHON_SERVICE_FAILURE` |

A request-level error prevents the complete request from being processed. Examples include an invalid caller, malformed request data, or invalid batch metadata.

### Document-Level Errors

Failures affecting only one document are returned inside that document's batch result.

Possible file-processing errors include:

| Error Code | Meaning |
|---|---|
| `EMPTY_FILE` | The submitted document contains no data. |
| `UNREADABLE_FILE` | The uploaded file cannot be read successfully. |
| `NO_EXTRACTABLE_TEXT` | No usable text could be extracted from the document. |
| `UNSUPPORTED_FILE_TYPE` | The document format is not supported. |
| `FILE_TOO_LARGE` | The uploaded file exceeds the configured file-size limit. |
| `DOCUMENT_TOO_LARGE` | The extracted document exceeds the configured processing limits. |
| `FILE_READ_FAILURE` | An unexpected failure occurred while reading the file. |
| `PROCESSING_FAILURE` | An unexpected document-processing error occurred. |

An item-level failure does not terminate the complete batch. Other valid documents continue to be processed independently.

### Dependency and Model Errors

Failures involving the model provider or communication between services are treated as technical failures rather than policy outcomes.

Possible dependency errors include:

| Error Code | Meaning |
|---|---|
| `PROVIDER_TIMEOUT` | The model provider did not respond within the configured timeout. |
| `PROVIDER_UNAVAILABLE` | The model provider could not be reached or used. |
| `MALFORMED_MODEL_OUTPUT` | The provider returned output that did not satisfy the expected response format. |
| `PYTHON_SERVICE_FAILURE` | Communication with or processing by the Python service failed. |

These failures must not be converted into:

```text
INSUFFICIENT_EVIDENCE
```

`INSUFFICIENT_EVIDENCE` represents a valid policy finding, while provider and service failures represent technical processing problems.

### Internal Service Responses

FastAPI may return:

- `422` for internal request validation failures.
- `503` for internal answer-provider failures.

The Spring Boot layer converts downstream failures into safe public responses and validates the information returned by the Python service.

This includes checking:

- Returned policy status values.
- Evidence and citation structure.
- Consistency between generated answers and supporting quotations.

If a batch item fails during processing, its `policy` field is returned as `null`.

### Logging

Application logs are designed to provide enough information to trace processing without recording complete reimbursement documents.

Useful identifiers such as the following may be logged:

- Batch ID
- Document ID
- Processing status
- Error code

Raw uploaded document text, reimbursement amounts, credentials, and other sensitive information should not intentionally be written to application logs.

Verbose HTTP or request-body logging should remain disabled when processing potentially sensitive employee information.


## Automated Testing and Verification

Both services include automated tests to verify policy behaviour, document extraction, error handling, and communication between the Spring Boot and Python components.

### Running Python Tests

From the repository root:

```powershell
cd policy-service

.\.venv\Scripts\python.exe -m pytest -q
```

### Running Spring Boot Tests

After the Python tests complete, run the Java test suite:

```powershell
cd ../spring-api

.\mvnw.cmd test
```

### Test Coverage

The automated tests cover the main functional and failure scenarios of the application, including:

- Caller identity and tenant/role access rules.
- Policy effective-date filtering.
- Policy evidence and exact source quotations.
- Policy records being reordered, duplicated, or changed.
- Relevant evidence selection.
- Complementary policy rules.
- TXT document extraction.
- Text-based PDF extraction.
- Missing and ambiguous reimbursement fields.
- Prompt-injection-style instructions inside submitted documents.
- Empty, invalid, and unsupported file scenarios.
- Exact duplicate document handling.
- Batch item failure isolation.
- Provider timeout behaviour.
- Provider unavailability.
- Malformed provider output.
- Single-attempt provider behaviour.
- Java HTTP request and response serialization.
- Multipart request validation.
- Spring Boot application startup.

### Test Doubles

The Python test suite uses controllable provider doubles to reproduce model-related scenarios without depending on an external AI service.

These doubles allow tests to simulate conditions such as:

```text
Successful provider response
Provider timeout
Provider unavailable
Malformed provider response
```

The Java client tests use a local HTTP stub to test communication behaviour without requiring the real Python service for every test.

This keeps the automated test suite deterministic and allows it to run without a paid model provider or external model API.

### End-to-End Demonstration

Unit and integration tests verify the services independently, while the demonstration script checks the complete communication path:

```text
Client
   |
   v
Spring Boot
   |
   v
Python FastAPI
   |
   v
Policy / Document Processing
```

With both services running, execute:

```powershell
python scripts/demo.py
```

The script sends requests through the actual public Spring Boot endpoints and verifies the Java-to-Python integration.

Representative response files are written to:

```text
examples/responses
```

### Recreating Sample Fixtures

The supplied synthetic request fixtures can be regenerated using:

```powershell
python scripts/create_fixtures.py
```

The script recreates only the synthetic request files and example request JSON used by the project.

### Current Limitations

The current test suite and implementation are focused on the assessment requirements rather than production-scale behaviour.

Known limitations include:

- Limited support for arbitrary natural-language variations.
- No complete protection against resource-intensive or hostile PDF files.
- No production-scale load or performance testing.

Additional implementation decisions and known limitations are documented in:

```text
docs/DECISIONS.md
```

The live demonstration script complements the automated tests by verifying that the Spring Boot and Python services work together through the complete local request flow.