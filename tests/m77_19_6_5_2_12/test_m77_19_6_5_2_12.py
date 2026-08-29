from pathlib import Path
import ast
P = Path(__file__).parents[2]/"scripts/run_m77_19_6_5_2_12_raw_support_resistance_candidate_generation_forensics.py"
T = P.read_text()

def test_runner_parses(): ast.parse(T)
def test_5211_report_pinned(): assert "88e9e9b4781727b59254c9ae6a583cea27dece55bc034bc0064c686638c101d6" in T
def test_native_runner_pinned(): assert "bcc5b49b87ddceba6ac417000d5af3d4a57efd14145595f4d712eb36ae81204b" in T
def test_level_service_pinned(): assert "8581c423956fd9d997af8098fb1065aab78b24646c72b9fb5ba1e8e446402490" in T
def test_readonly(): assert "SET TRANSACTION READ ONLY" in T and "session.commit(" not in T
def test_capture_raw(): assert "capture_raw_sr_candidates" in T
def test_source_forensics(): assert "source_semantics" in T and "ast.parse(source)" in T
def test_fixed_merge_threshold(): assert "MERGE_THRESHOLD = 0.003" in T
def test_no_threshold_search(): assert "optimize_threshold" not in T and "best_threshold" not in T
def test_classification_exact_anchor(): assert "EXACT_NATIVE_CLUSTER_ANCHOR" in T
def test_classification_exact_raw(): assert "EXACT_RAW_CANDIDATE_BUT_NOT_NATIVE_CLUSTER_ANCHOR" in T
def test_classification_near_raw(): assert "RAW_CANDIDATE_WITHIN_0_3PCT_BUT_PRICE_DIFFERS" in T
def test_classification_missing_raw(): assert "NO_NATIVE_RAW_CANDIDATE_WITHIN_0_3PCT" in T
def test_no_synthetic_candidates(): assert '"synthetic_candidate_replacement_used": False' in T
def test_production_unchanged(): assert '"production_authority_effect": False' in T
def test_reconstruction_blocked(): assert '"full_23_year_reconstruction_authorized": False' in T
