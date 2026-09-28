"""One bounded generation attempt using an offline provider by default."""

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from threading import BoundedSemaphore
from typing import Protocol


class ProviderFailure(Exception):

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class AnswerProvider(Protocol):

    def generate(self, quotations: tuple[str, ...]) -> object:
        ...


class OfflineProvider:
    """Returns an answer using only the provided quotations."""

    def generate(self, quotations: tuple[str, ...]) -> object:
        unique_quotations = dict.fromkeys(quotations)
        answer = " ".join(unique_quotations)

        return {"answer": answer}


_pool = ThreadPoolExecutor(
    max_workers=4,
    thread_name_prefix="answer-provider",
)

_slots = BoundedSemaphore(4)


class GenerationService:

    def __init__(
        self,
        provider: AnswerProvider | None = None,
        timeout: float = 1.0,
    ):
        if timeout <= 0:
            raise ValueError("Provider timeout must be positive")

        self.provider = provider or OfflineProvider()
        self.timeout = timeout

    def answer(self, quotations: tuple[str, ...]) -> str:

        if not _slots.acquire(blocking=False):
            raise ProviderFailure(
                "PROVIDER_UNAVAILABLE",
                "Answer provider is busy",
            )

        try:
            future = _pool.submit(
                self.provider.generate,
                quotations,
            )

        except Exception:
            _slots.release()

            raise ProviderFailure(
                "PROVIDER_UNAVAILABLE",
                "Answer provider is unavailable",
            ) from None

        future.add_done_callback(
            lambda _: _slots.release()
        )

        try:
            output = future.result(timeout=self.timeout)

        except FutureTimeout:
            future.cancel()

            raise ProviderFailure(
                "PROVIDER_TIMEOUT",
                "Answer provider timed out",
            ) from None

        except Exception:
            raise ProviderFailure(
                "PROVIDER_UNAVAILABLE",
                "Answer provider is unavailable",
            ) from None

        unique_quotations = dict.fromkeys(quotations)
        expected_answer = " ".join(unique_quotations)

        valid_output = (
            isinstance(output, dict)
            and set(output) == {"answer"}
            and output["answer"] == expected_answer
        )

        if not valid_output:
            raise ProviderFailure(
                "MALFORMED_MODEL_OUTPUT",
                "Answer provider returned unsupported output",
            )

        return expected_answer