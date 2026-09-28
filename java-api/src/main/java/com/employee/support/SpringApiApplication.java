package com.employee.support;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class SpringApiApplication {

    public static void main(String[] args) {
        // Disable HTTP retries
        System.setProperty("jdk.httpclient.disableRetryConnect", "true");

        SpringApplication.run(SpringApiApplication.class, args);
    }
}