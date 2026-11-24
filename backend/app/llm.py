import hashlib
import json
import os

from cachetools import TTLCache
from dotenv import load_dotenv
from litellm import completion
from litellm.exceptions import (
    InternalServerError,
    RateLimitError,
    ServiceUnavailableError,
)


load_dotenv()


# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

MODEL = os.getenv(
    "LLM_MODEL",
    "gemini/gemini-3.5-flash-lite",
)

ENABLE_FAILURE_SIMULATION = (
    os.getenv(
        "ENABLE_FAILURE_SIMULATION",
        "true",
    ).lower()
    == "true"
)

_raw_keys = os.getenv("LLM_API_KEYS", "")

API_KEYS = [
    key.strip()
    for key in _raw_keys.split(",")
    if key.strip()
]


# ---------------------------------------------------------
# CACHE
# ---------------------------------------------------------

# 10-minute in-memory cache
# Maximum 1000 cached responses
CACHE_TTL_SECONDS = 600

response_cache = TTLCache(
    maxsize=1000,
    ttl=CACHE_TTL_SECONDS,
)


# ---------------------------------------------------------
# EXCEPTIONS
# ---------------------------------------------------------

class AllProvidersUnavailable(Exception):
    pass


# ---------------------------------------------------------
# HEALTH HELPERS
# ---------------------------------------------------------

def get_key_count() -> int:
    return len(API_KEYS)


def is_cache_enabled() -> bool:
    return True


# ---------------------------------------------------------
# FAILURE SIMULATION
# ---------------------------------------------------------

def parse_simulated_failures(
    header: str | None,
) -> dict:

    failures = {}

    if (
        not header
        or not ENABLE_FAILURE_SIMULATION
    ):
        return failures

    allowed_statuses = {
        429,
        500,
        502,
        503,
    }

    for item in header.split(","):

        item = item.strip()

        if "=" not in item:
            continue

        key_name, status = item.split("=", 1)

        key_name = key_name.strip()
        status = status.strip()

        try:
            status_code = int(status)
        except ValueError:
            continue

        if status_code not in allowed_statuses:
            continue

        failures[key_name] = status_code

    return failures


# ---------------------------------------------------------
# CACHE KEY
# ---------------------------------------------------------

def create_cache_key(
    messages: list[dict],
) -> str:

    # Cache key = model + complete message list.
    #
    # This includes:
    # - system prompt
    # - previous conversation history
    # - newest user message

    serialized = json.dumps(
        {
            "model": MODEL,
            "messages": messages,
        },
        sort_keys=True,
        ensure_ascii=False,
    )

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()


# ---------------------------------------------------------
# LLM GENERATION
# ---------------------------------------------------------

def generate_reply(
    messages: list[dict],
    simulate_failure: str | None = None,
) -> dict:

    if not API_KEYS:
        raise AllProvidersUnavailable(
            "all providers unavailable"
        )

    # -----------------------------------------------------
    # 1. CHECK CACHE
    # -----------------------------------------------------

    cache_key = create_cache_key(messages)

    cached_response = response_cache.get(cache_key)

    if cached_response is not None:

        return {
            "reply": cached_response["reply"],
            "model": cached_response["model"],
            "input_tokens": cached_response[
                "input_tokens"
            ],
            "output_tokens": cached_response[
                "output_tokens"
            ],
            "key_id": None,
            "fallback_attempts": 0,
            "resolution_source": "LLM_CACHE",
        }

    # -----------------------------------------------------
    # 2. PARSE FAILURE-SIMULATION HEADER
    # -----------------------------------------------------

    simulated_failures = parse_simulated_failures(
        simulate_failure
    )

    fallback_attempts = 0

    # -----------------------------------------------------
    # 3. TRY API KEYS IN ORDER
    # -----------------------------------------------------

    for index, api_key in enumerate(API_KEYS):

        key_id = f"key_{index + 1}"

        simulated_status = (
            simulated_failures.get(key_id)
            or simulated_failures.get("*")
        )

        # -------------------------------------------------
        # Simulated provider failure
        # -------------------------------------------------

        if simulated_status is not None:
            fallback_attempts += 1
            continue

        try:

            response = completion(
                model=MODEL,
                messages=messages,
                api_key=api_key,
            )

            reply = (
                response
                .choices[0]
                .message
                .content
            )

            if not reply:
                fallback_attempts += 1
                continue

            # ---------------------------------------------
            # TOKEN USAGE
            # ---------------------------------------------

            input_tokens = 0
            output_tokens = 0

            if response.usage is not None:

                input_tokens = (
                    response.usage.prompt_tokens
                    or 0
                )

                output_tokens = (
                    response.usage.completion_tokens
                    or 0
                )

            # ---------------------------------------------
            # STORE COMPLETE CACHE ENTRY
            # ---------------------------------------------

            response_cache[cache_key] = {
                "reply": reply,
                "model": MODEL,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }

            # ---------------------------------------------
            # LIVE RESPONSE
            # ---------------------------------------------

            return {
                "reply": reply,
                "model": MODEL,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "key_id": key_id,
                "fallback_attempts": fallback_attempts,
                "resolution_source": "LIVE_INFERENCE",
            }

        except (
            RateLimitError,
            ServiceUnavailableError,
            InternalServerError,
        ):

            fallback_attempts += 1
            continue

    # -----------------------------------------------------
    # 4. EVERY KEY FAILED
    # -----------------------------------------------------

    raise AllProvidersUnavailable(
        "all providers unavailable"
    )