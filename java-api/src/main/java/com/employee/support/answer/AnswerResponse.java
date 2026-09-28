package com.employee.support.answer;

import java.util.List;
import java.util.stream.Collectors;

public record AnswerResponse(
    PolicyStatus status,
    String answer,
    List<Citation> citations
) {

    public boolean valid() {

        if (status == null || citations == null) {
            return false;
        }

        boolean invalidCitation = citations.stream().anyMatch(citation ->
            citation == null
                || citation.chunkId() == null
                || citation.chunkId().isBlank()
                || citation.quote() == null
                || citation.quote().isBlank()
        );

        if (invalidCitation) {
            return false;
        }

        return switch (status) {

            case ANSWERED -> {
                String citationText = citations.stream()
                    .map(Citation::quote)
                    .distinct()
                    .collect(Collectors.joining(" "));

                yield answer != null
                    && !answer.isBlank()
                    && !citations.isEmpty()
                    && answer.equals(citationText);
            }

            case INSUFFICIENT_EVIDENCE ->
                answer == null && citations.isEmpty();

            case CONFLICT ->
                answer == null
                    && citations.stream()
                        .map(Citation::quote)
                        .distinct()
                        .count() >= 2;
        };
    }
}