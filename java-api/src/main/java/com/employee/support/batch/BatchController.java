package com.employee.support.batch;

import java.util.List;

import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import jakarta.validation.Valid;

@RestController
public class BatchController {

    private final BatchService batchService;

    public BatchController(BatchService batchService) {
        this.batchService = batchService;
    }

    @PostMapping(value = "/batches", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public BatchResponse batches(
        @RequestHeader(value = "X-Caller-Id", required = false) String callerId,
        @Valid @RequestPart("metadata") BatchRequest metadata,
        @RequestPart("files") List<MultipartFile> files
    ) {
        return batchService.process(callerId, metadata, files);
    }
}