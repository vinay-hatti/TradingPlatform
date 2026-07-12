from dataclasses import asdict, is_dataclass


def serialize_scenario_value(value):
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
                serialize_scenario_value(item)
            for key, item
            in asdict(value).items()
        }

    if isinstance(value, dict):
        return {
            str(key):
                serialize_scenario_value(item)
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
            serialize_scenario_value(item)
            for item in value
        ]

    return str(value)


def scenario_result_to_dict(
    result,
):
    return serialize_scenario_value(
        result
    )


def portfolio_scenario_result_to_dict(
    result,
):
    return serialize_scenario_value(
        result
    )
