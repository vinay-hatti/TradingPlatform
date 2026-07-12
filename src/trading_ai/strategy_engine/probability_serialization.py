from dataclasses import asdict


def probability_profile_to_dict(
    profile,
) -> dict:
    return asdict(profile)
