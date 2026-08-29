from pathlib import Path
import py_compile
ROOT=Path(__file__).resolve().parents[2]
P=ROOT/"src/trading_ai/historical_underlying_replay/jpl_horizons_ephemeris.py"; V=ROOT/"src/trading_ai/historical_underlying_replay/vedic_conventions.py"; R=ROOT/"scripts/run_m77_15_0_vedic_ephemeris_foundation.py"
def test_compile():
    for p in (P,V,R): py_compile.compile(str(p),doraise=True)
def test_jpl_authority():
    x=P.read_text(); assert "https://ssd.jpl.nasa.gov/api/horizons.api" in x; assert 'DOCUMENTED_API_VERSION="1.3"' in x; assert 'SUPPORTED_OBSERVED_API_VERSIONS={"1.2","1.3"}' in x; assert '"VEC_CORR":"\'NONE\'"' in x; assert '"REF_PLANE":"\'ECLIPTIC\'"' in x; assert '"CENTER":"\'500@399\'"' in x
def test_conventions():
    x=V.read_text(); assert '"zodiac":"SIDEREAL"' in x; assert '"ayanamsha":"LAHIRI_CHITRAPAKSHA"' in x; assert '"node_convention":"TRUE_NODE"' in x
def test_fail_closed():
    x=V.read_text(); assert "require_ayanamsha" in x and "fail-closed" in x
def test_no_production():
    x=R.read_text(); assert '"production_authority_effect":False' in x; assert '"database_writes":False' in x
def test_phase0_blocks_sidereal():
    x=R.read_text(); assert '"lahiri_ayanamsha_parity":False' in x; assert '"true_node_authority":False' in x
