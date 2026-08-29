import dataclasses
import importlib.util
from pathlib import Path

P = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "run_m77_19_6_5_2_9_structure_level_minimal_causal_intervention_replay.py"
)

spec = importlib.util.spec_from_file_location("m77_5291", P)
m = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(m)


@dataclasses.dataclass
class Level:
    price: float
    strength: float = 0.0
    timeframe: str = "1d"


@dataclasses.dataclass
class Zone:
    lower_bound: float
    upper_bound: float
    strength: float = 0.0


def test_version_is_repair():
    assert m.VERSION.startswith("M77.19.6.5.2.9.1-")


def test_parity_tolerance_unchanged():
    assert m.PARITY_TOLERANCE == 1e-9


def test_rehydrate_native_level_dataclass():
    native = [Level(price=100.0, strength=10.0)]
    frozen = [{"price": 99.5, "strength": 80.0, "timeframe": "1w"}]
    out = m.rehydrate_native_sequence(
        frozen,
        native,
        label="support_levels",
        required_attributes=("price",),
    )
    assert len(out) == 1
    assert isinstance(out[0], Level)
    assert out[0].price == 99.5
    assert out[0].strength == 80.0
    assert out[0].timeframe == "1w"


def test_rehydrate_uses_sibling_native_type_when_primary_empty():
    out = m.rehydrate_native_sequence(
        [{"price": 101.0, "strength": 50.0}],
        [],
        [Level(price=102.0)],
        label="support_levels",
        required_attributes=("price",),
    )
    assert isinstance(out[0], Level)
    assert out[0].price == 101.0


def test_rehydrate_native_structure_zone():
    out = m.rehydrate_native_sequence(
        [{"lower_bound": 90.0, "upper_bound": 95.0, "strength": 70.0}],
        [Zone(1.0, 2.0)],
        label="structure_zones",
        required_attributes=("lower_bound", "upper_bound"),
    )
    assert isinstance(out[0], Zone)
    assert out[0].lower_bound == 90.0
    assert out[0].upper_bound == 95.0


def test_level_patch_returns_typed_objects_and_preserves_other_outputs():
    class Levels:
        def analyze(self, _):
            return {
                "support_levels": [Level(100.0)],
                "resistance_levels": [Level(110.0)],
                "demand_zones": ["native-demand"],
                "supply_zones": ["native-supply"],
            }

    class Service:
        levels = Levels()

    s = Service()
    restore = m.patch_levels(
        s,
        {
            "support_levels": [{"price": 99.0, "strength": 75.0}],
            "resistance_levels": [{"price": 111.0, "strength": 65.0}],
        },
    )
    out = s.levels.analyze({})
    restore()

    assert isinstance(out["support_levels"][0], Level)
    assert isinstance(out["resistance_levels"][0], Level)
    assert out["support_levels"][0].price == 99.0
    assert out["resistance_levels"][0].price == 111.0
    assert out["demand_zones"] == ["native-demand"]
    assert out["supply_zones"] == ["native-supply"]


def test_structure_patch_executes_native_builder_and_returns_typed_zones():
    calls = []

    class Builder:
        def build(self, profile):
            calls.append(profile)
            return [Zone(1.0, 2.0)]

    class Service:
        structure_zones = Builder()

    s = Service()
    restore = m.patch_structure(
        s,
        {
            "structure_zones": [
                {"lower_bound": 90.0, "upper_bound": 95.0, "strength": 80.0}
            ]
        },
    )
    out = s.structure_zones.build("profile")
    restore()

    assert calls == ["profile"]
    assert isinstance(out[0], Zone)
    assert out[0].lower_bound == 90.0
    assert out[0].upper_bound == 95.0


def test_plain_dict_injection_markers_absent():
    text = P.read_text()
    assert 'result["support_levels"] = copy.deepcopy(frozen_support)' not in text
    assert 'result["resistance_levels"] = copy.deepcopy(frozen_resistance)' not in text
    assert 'return copy.deepcopy(frozen_zones)' not in text


def test_exact_arm_set_preserved():
    assert m.ARMS == (
        "CONTROL_WEEKLY_PARTICIPATION",
        "LEVELS_ONLY",
        "STRUCTURE_ONLY",
        "LEVELS_AND_STRUCTURE",
    )


def test_governance_flags_remain_blocked():
    text = P.read_text()
    assert '"controlled_exact_input_parity_certified": False' in text
    assert '"full_23_year_reconstruction_authorized": False' in text
    assert '"production_authority_effect": False' in text


def test_no_write_sql():
    text = P.read_text()
    assert "SET TRANSACTION READ ONLY" in text
    assert "session.commit(" not in text
    assert "INSERT " not in text
    assert "UPDATE " not in text
    assert "DELETE " not in text
