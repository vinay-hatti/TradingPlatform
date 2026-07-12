from dataclasses import asdict, is_dataclass


def serialize_distribution_risk_value(
    value,
):
    if value is None:
        return None

    if isinstance(
        value,
        (
            str,
            int,
            float,
            bool,
        ),
    ):
        return value

    if is_dataclass(value):
        return {
            key:
                serialize_distribution_risk_value(
                    item
                )
            for key, item
            in asdict(value).items()
        }

    if isinstance(value, dict):
        return {
            str(key):
                serialize_distribution_risk_value(
                    item
                )
            for key, item
            in value.items()
        }

    if isinstance(
        value,
        (
            list,
            tuple,
            set,
        ),
    ):
        return [
            serialize_distribution_risk_value(
                item
            )
            for item in value
        ]

    return str(value)


def distribution_risk_profile_to_dict(
    profile,
):
    return serialize_distribution_risk_value(
        profile
    )


def portfolio_tail_risk_profile_to_dict(
    profile,
):
    return serialize_distribution_risk_value(
        profile
    )
