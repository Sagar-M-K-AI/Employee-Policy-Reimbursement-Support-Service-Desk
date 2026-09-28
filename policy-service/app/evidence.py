"""Small evidence rules. Unknown wording is left unresolved."""

import re
from decimal import Decimal


BENEFIT_TERMS: dict[str, tuple[str, ...]] = {
    "certification": ("certification",),
    "home-office": ("home-office", "home office"),
    "travel": ("travel",),
    "training": ("training",),
    "wellness": ("wellness", "gym"),
}

MONEY = re.compile(
    r"\b(INR|USD|EUR|GBP)\s+"
    r"([0-9]+(?:,[0-9]{3})*(?:\.[0-9]{1,2})?)"
    r"(?!\d|\.\d)",
    re.I,
)


def matches(text: str, term: str) -> bool:
    pattern = r"(?<!\w)" + re.escape(term) + r"(?!\w)"
    return re.search(pattern, text, re.I) is not None


def benefits(text: str) -> list[str]:
    found_benefits = []

    for benefit, terms in BENEFIT_TERMS.items():
        if any(matches(text, term) for term in terms):
            found_benefits.append(benefit)

    return found_benefits


def policy_fact(text: str) -> tuple[str, object] | None:
    normalized_text = text.casefold()

    unsafe_terms = (
        "system message",
        "ignore all",
        "ignore prior",
        "ignore the",
        "switch the caller",
    )

    if any(term in normalized_text for term in unsafe_terms):
        return None

    money = MONEY.search(text)

    amount_terms = (
        "limit",
        "allowance",
        "reimbursement",
        "budget",
    )

    if money and any(term in normalized_text for term in amount_terms):
        currency = money[1].upper()
        amount = Decimal(money[2].replace(",", ""))

        return "amount", (currency, amount)

    approval_terms = (
        "required",
        "must",
        "before",
        "not required",
    )

    if (
        "approval" in normalized_text
        and any(term in normalized_text for term in approval_terms)
    ):
        return "approval", " ".join(normalized_text.split())

    eligibility_terms = (
        "may claim",
        "eligible",
        "not reimbursable",
        "cannot claim",
    )

    if any(term in normalized_text for term in eligibility_terms):
        return "eligibility", " ".join(normalized_text.split())

    return None