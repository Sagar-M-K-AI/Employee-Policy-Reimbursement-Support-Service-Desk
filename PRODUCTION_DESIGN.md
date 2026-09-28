# Production Design Note

For a production workload of around 10,000 requests per day, I would keep the Java API and Python processing service independently deployable. This would allow the document-processing side to scale separately when uploads increase without unnecessarily scaling the public API.

The biggest change I would make is to move batch processing to the background. Instead of keeping an API request open while every document is processed, the API would create a batch job and return its ID. Documents would then be processed through a queue with a fixed number of workers, and the client could check the batch status using another endpoint. This would make large batches and traffic spikes easier to handle.

I would store batch progress, document status, and audit information in a database. Uploaded files containing personal information would be encrypted, access controlled, and removed according to a defined retention policy. Policy data would also be versioned so that an answer can be traced back to the exact policy version used at that time.

For security, `X-Caller-Id` would be replaced with real authentication. Tenant and role information would come from verified identity claims rather than user-provided values. Tenant isolation would be enforced when accessing both policy and application data.

File uploads would have strict size and type limits and would be scanned before processing. Document contents and model responses would still be treated as untrusted input. Extracted values and generated responses would be validated before being accepted by the application.

External systems, especially an approval service, would be called with strict timeouts and clear failure handling. I would avoid blindly retrying requests that could create duplicate actions. Idempotency would be used where the external system supports it.

Finally, I would monitor API errors, queue backlog, document failures, processing time, model latency, and external-service failures. Logs would use correlation IDs and avoid exposing personal document content.

Before production rollout, I would confirm peak traffic, document sizes and formats, data-retention requirements, policy ownership, external API limits, security requirements, and review SLAs. Human review would remain mandatory; the system would assist reviewers rather than automatically approving or paying claims.