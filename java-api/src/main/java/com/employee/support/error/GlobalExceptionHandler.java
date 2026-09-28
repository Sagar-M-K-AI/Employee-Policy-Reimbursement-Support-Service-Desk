package com.employee.support.error;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.multipart.MaxUploadSizeExceededException;
import org.springframework.web.multipart.MultipartException;
import org.springframework.web.multipart.support.MissingServletRequestPartException;

import com.employee.support.answer.PythonServiceException;
import com.employee.support.batch.InvalidBatchException;
import com.employee.support.caller.UnknownCallerException;

@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(UnknownCallerException.class)
    public ResponseEntity<ApiError> unknownCaller(
        UnknownCallerException exception
    ) {
        ApiError error = new ApiError(
            "INVALID_CALLER",
            exception.getMessage()
        );

        return ResponseEntity.badRequest().body(error);
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ApiError> invalidBody(
        MethodArgumentNotValidException exception
    ) {
        ApiError error = new ApiError(
            "INVALID_REQUEST",
            "Request fields are missing or invalid; check the API contract"
        );

        return ResponseEntity.badRequest().body(error);
    }

    @ExceptionHandler(HttpMessageNotReadableException.class)
    public ResponseEntity<ApiError> unreadableBody(
        HttpMessageNotReadableException exception
    ) {
        ApiError error = new ApiError(
            "INVALID_REQUEST",
            "Request JSON or as_of date is invalid"
        );

        return ResponseEntity.badRequest().body(error);
    }

    @ExceptionHandler(PythonServiceException.class)
    public ResponseEntity<ApiError> dependencyFailure(
        PythonServiceException exception
    ) {
        ApiError error = new ApiError(
            "PYTHON_SERVICE_FAILURE",
            "The answer service is temporarily unavailable"
        );

        return ResponseEntity
            .status(HttpStatus.SERVICE_UNAVAILABLE)
            .body(error);
    }

    @ExceptionHandler(InvalidBatchException.class)
    public ResponseEntity<ApiError> invalidBatch(
        InvalidBatchException exception
    ) {
        ApiError error = new ApiError(
            "INVALID_BATCH",
            exception.getMessage()
        );

        return ResponseEntity.badRequest().body(error);
    }

    @ExceptionHandler(MissingServletRequestPartException.class)
    public ResponseEntity<ApiError> missingPart(
        MissingServletRequestPartException exception
    ) {
        ApiError error = new ApiError(
            "INVALID_BATCH",
            "metadata and files multipart parts are required"
        );

        return ResponseEntity.badRequest().body(error);
    }

    @ExceptionHandler(MaxUploadSizeExceededException.class)
    public ResponseEntity<ApiError> uploadTooLarge(
        MaxUploadSizeExceededException exception
    ) {
        ApiError error = new ApiError(
            "UPLOAD_TOO_LARGE",
            "Upload exceeds the configured size limit"
        );

        return ResponseEntity
            .status(HttpStatus.PAYLOAD_TOO_LARGE)
            .body(error);
    }

    @ExceptionHandler(MultipartException.class)
    public ResponseEntity<ApiError> invalidMultipart(
        MultipartException exception
    ) {
        ApiError error = new ApiError(
            "INVALID_BATCH",
            "Multipart request could not be read"
        );

        return ResponseEntity.badRequest().body(error);
    }
}