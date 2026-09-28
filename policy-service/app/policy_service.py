from datetime import date
import re
from typing import Any

from app.evidence import BENEFIT_TERMS, benefits, matches, policy_fact
from app.models import Citation, PolicyAnswer, PolicyStatus
from app.policy_repository import PolicyRepository
from app.provider import GenerationService


class PolicyService:

    def __init__(
        self,
        repository: PolicyRepository,
        generation: GenerationService | None = None,
    ) -> None:
        self._repository = repository
        self._generation = generation or GenerationService()

    @staticmethod
    def insufficient() -> PolicyAnswer:
        return PolicyAnswer(
            status=PolicyStatus.INSUFFICIENT_EVIDENCE,
            answer=None,
            citations=[],
        )

    def answer(
        self,
        tenant: str,
        role: str,
        as_of: date,
        benefit: str,
        required_fact: str | None = None,
    ) -> PolicyAnswer:

        normalized_benefit = benefit.strip().lower()
        terms = BENEFIT_TERMS.get(
            normalized_benefit,
            (normalized_benefit,),
        )

        eligible_policies = [
            policy
            for policy in self._repository.find_all()
            if self._is_eligible(policy, tenant, role, as_of)
            and self._is_relevant(policy, terms)
            and policy_fact(policy["text"]) is not None
        ]

        unique_policies = {
            (policy["id"], policy["text"]): policy
            for policy in eligible_policies
        }

        policies = sorted(
            unique_policies.values(),
            key=lambda policy: (policy["id"], policy["text"]),
        )

        if required_fact:
            policies = [
                policy
                for policy in policies
                if policy_fact(policy["text"])[0] == required_fact
            ]

        if not policies:
            return self.insufficient()

        citations = [
            Citation(
                chunk_id=policy["id"],
                quote=policy["text"],
            )
            for policy in policies
        ]

        facts: dict[str, set] = {}

        for policy in policies:
            kind, value = policy_fact(policy["text"])
            facts.setdefault(kind, set()).add(value)

        # Different values for the same fact mean the policy is conflicting
        if any(len(values) > 1 for values in facts.values()):
            return PolicyAnswer(
                status=PolicyStatus.CONFLICT,
                answer=None,
                citations=citations,
            )

        policy_texts = tuple(
            policy["text"]
            for policy in policies
        )

        generated_answer = self._generation.answer(policy_texts)

        return PolicyAnswer(
            status=PolicyStatus.ANSWERED,
            answer=generated_answer,
            citations=citations,
        )

    def answer_question(
        self,
        tenant: str,
        role: str,
        as_of: date,
        question: str,
    ) -> PolicyAnswer:

        matched_benefits = benefits(question)

        if len(matched_benefits) != 1:
            return self.insufficient()

        normalized_question = question.casefold()

        unsupported_questions = (
            r"\b(remaining|balance|payable|paid|payment|"
            r"approve my|eligible|eligibility)\b"
        )

        if re.search(unsupported_questions, normalized_question):
            return self.insufficient()

        required_fact = None

        if re.search(
            r"\b(limit|amount|how much|budget)\b",
            normalized_question,
        ):
            required_fact = "amount"

        elif "approval" in normalized_question:
            required_fact = "approval"

        return self.answer(
            tenant,
            role,
            as_of,
            matched_benefits[0],
            required_fact,
        )

    @staticmethod
    def _is_eligible(
        policy: dict[str, Any],
        tenant: str,
        role: str,
        as_of: date,
    ) -> bool:

        return (
            policy["tenant"].casefold() == tenant.casefold()
            and policy["permitted_role"].casefold() == role.casefold()
            and policy["approval_state"] == "Approved"
            and date.fromisoformat(policy["effective_from"])
            <= as_of
            < date.fromisoformat(policy["effective_to"])
        )

    @staticmethod
    def _is_relevant(
        policy: dict[str, Any],
        terms: tuple[str, ...],
    ) -> bool:
        return any(
            matches(policy["text"], term)
            for term in terms
        )