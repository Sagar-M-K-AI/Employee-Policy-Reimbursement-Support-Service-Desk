# Implementation Decisions and Disclosure

## How I approached the solution

I divided the application into two main parts. The Spring Boot service handles the public API and caller-related validation, while the Python service handles policy lookup, document extraction, and answer generation.

For policy questions, I did not want the model to decide which policies a user is allowed to access. That filtering happens before the provider is called. The service checks the caller's tenant, role, policy approval status, and the requested date, and then works only with the policies that match those conditions.

The answer is created only from the policy information found by the service. If the required information is missing, the response is `INSUFFICIENT_EVIDENCE`. If the available policies disagree with each other, the response is `CONFLICT`. In both situations, there is no need to call the provider.

I used the offline provider for this implementation because the assignment can be completed without connecting to a real LLM. It also makes the project easier to run locally and gives consistent results during testing.

For uploaded reimbursement documents, I extract the available details such as the benefit, amount, currency, reference, and supporting text. If something cannot be identified clearly, I leave it empty instead of trying to guess it. Each document is handled separately so that one bad file does not stop the rest of the batch.

## What I would improve further

The current extraction logic works for the supplied documents and the cases covered by my tests, but it is not intended to handle every document format.

PDF processing currently works with text-based PDFs. Scanned documents would require OCR, which I have not added. More complex PDF layouts may also need better parsing.

The policy matching logic is rule based, so more policy formats and different ways of writing the same information would require additional handling.

This project also does not perform any real reimbursement approval or payment action. Human review is still required. Features such as real authentication, OCR, external approval systems, and production model integration would be separate improvements.

I have also kept the model calls bounded using timeout and concurrency controls. If I replaced the local provider with an external model API, I would add production-level network handling, monitoring, and stronger failure handling around that integration.

## Time spent and AI usage

I spent around 8 hours working on the assignment. This includes setting up the project, implementing the required flow, fixing issues, running tests, refactoring, and updating the documentation.

I used AI coding assistance while working on the project. It helped me with parts of the Java and Python implementation, debugging, test cases, refactoring, and documentation. I reviewed the changes before including them in the final project and I am responsible for understanding and explaining the submitted implementation.

The required `/answer` and `/batches` workflows are implemented, including the supplied mixed-document batch scenario. I kept the real LLM integration optional and did not add production systems such as authentication, payment processing, or external approval services.

The automated tests cover the main requirements and provided examples. They are not intended to cover every possible PDF structure, wording variation, malformed file, concurrency condition, or production integration.