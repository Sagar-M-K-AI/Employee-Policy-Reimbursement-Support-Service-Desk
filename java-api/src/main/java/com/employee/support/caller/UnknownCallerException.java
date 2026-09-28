package com.employee.support.caller;

public class UnknownCallerException extends RuntimeException {

    public UnknownCallerException() {
        super("Missing or Unknown caller");
    }
}
