package com.employee.support.batch;

import java.io.IOException;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Base64;
import java.util.HashMap;
import java.util.HashSet;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import com.employee.support.answer.PythonClient;
import com.employee.support.answer.PythonServiceException;
import com.employee.support.caller.CallerContext;
import com.employee.support.caller.CallerContextService;

@Service
public class BatchService {

    private static final Logger LOG = LoggerFactory.getLogger(BatchService.class);

    private final CallerContextService callerContextService;
    private final PythonClient pythonClient;

    public BatchService(
        CallerContextService callerContextService,
        PythonClient pythonClient
    ) {
        this.callerContextService = callerContextService;
        this.pythonClient = pythonClient;
    }

    public BatchResponse process(
        String callerId,
        BatchRequest metadata,
        List<MultipartFile> files
    ) {
        CallerContext caller = callerContextService.requireKnownCaller(callerId);

        Map<String, MultipartFile> uploads = new HashMap<>();
        Set<String> documentIds = new HashSet<>();
        Set<String> filenames = new HashSet<>();

        for (var document : metadata.documents()) {
            boolean duplicateId = !documentIds.add(document.documentId());
            boolean duplicateFilename = !filenames.add(document.filename());

            if (duplicateId || duplicateFilename) {
                throw new InvalidBatchException(
                    "Manifest document IDs and filenames must be unique"
                );
            }
        }

        for (var file : files) {
            String filename = file.getOriginalFilename();

            if (filename == null || uploads.putIfAbsent(filename, file) != null) {
                throw new InvalidBatchException(
                    "Each uploaded filename must appear exactly once"
                );
            }
        }

        if (!uploads.keySet().equals(filenames)) {
            throw new InvalidBatchException(
                "Uploaded filenames must exactly match the manifest"
            );
        }

        List<DocumentResult> results = new ArrayList<>();
        Map<String, String> firstDocumentByHash = new HashMap<>();

        for (var document : metadata.documents()) {

            DocumentResult result;
            String duplicateOf = null;

            try {
                byte[] bytes = uploads.get(document.filename()).getBytes();

                String hash = digest(bytes);

                duplicateOf = firstDocumentByHash.putIfAbsent(
                    hash,
                    document.documentId()
                );

                String encodedContent = Base64.getEncoder()
                    .encodeToString(bytes);

                InternalDocumentRequest request = new InternalDocumentRequest(
                    caller.tenant(),
                    caller.role(),
                    metadata.asOf(),
                    metadata.batchId(),
                    document.documentId(),
                    document.filename(),
                    encodedContent
                );

                result = pythonClient.document(request);

            } catch (IOException exception) {
                result = DocumentResult.failed(
                    document.documentId(),
                    "FILE_READ_FAILURE",
                    "The uploaded file could not be read"
                );

            } catch (PythonServiceException exception) {
                result = DocumentResult.failed(
                    document.documentId(),
                    "PYTHON_SERVICE_FAILURE",
                    "The document service is temporarily unavailable or returned an invalid response"
                );
            }

            if (duplicateOf != null) {
                result = result.withDuplicate(duplicateOf);
            }

            results.add(result);

            LOG.info(
                "batch={} document={} status={} error={}",
                metadata.batchId(),
                document.documentId(),
                result.processingStatus(),
                result.error() == null ? "none" : result.error().code()
            );
        }

        int completed = (int) results.stream()
            .filter(result -> "COMPLETED".equals(result.processingStatus()))
            .count();

        int failed = results.size() - completed;

        BatchResponse.Summary summary = new BatchResponse.Summary(
            results.size(),
            completed,
            failed
        );

        return new BatchResponse(
            metadata.batchId(),
            summary,
            results
        );
    }

    private static String digest(byte[] bytes) {
        try {
            MessageDigest messageDigest = MessageDigest.getInstance("SHA-256");
            byte[] hash = messageDigest.digest(bytes);

            return HexFormat.of().formatHex(hash);

        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException(exception);
        }
    }
}