from typing import Any, Dict, List

from toon_format import decode, encode


def encode_toon(json_data: Any) -> str:
    toon_data = encode(json_data)

    return toon_data


def decode_toon(toon_data: str) -> Any:
    json_data = decode(toon_data)

    return json_data


if __name__ == "__main__":
    from helpers.filehandler import read_json_file
    from toon_format import estimate_savings, compare_formats

    json_data = read_json_file(
        "ExpertSearch/mock-responses/2_openalex_search_response_works.json"
    )

    result = estimate_savings(json_data)
    print(f"Saves {result['savings_percent']:.1f}% tokens")

    # Get formatted comparison
    print(compare_formats(json_data))

    # Saves 18.3% tokens
    # Format Comparison
    # ────────────────────────────────────────────────
    # Format      Tokens    Size (chars)
    # JSON      192,832        821,926
    # TOON      157,494        621,455
    # ────────────────────────────────────────────────
    # Savings: 35,338 tokens (18.3%)
