import json
import requests

# 1. Configuration
API_KEY = "m5MujHcl04_wHAppc1rBEbmvsxUBbBdK"  # Replace with your actual Massive API key
BASE_URL = "https://api.massive.com"

# Massive utilizes the Authorization Bearer header or a URL param
headers = {"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"}


def test_spx_options_fixed():
    print("--- Testing Massive REST API for SPX Options ---")

    # 1. FIXED ENDPOINT: Reference Options Contracts
    contracts_url = f"{BASE_URL}/v3/reference/options/contracts"
    params = {
        "underlying_ticker": "SPX",
        "limit": 2,  # Small limit to quickly test connection
    }

    print("\n[Step 1] Fetching active SPX contracts...")
    res_contracts = requests.get(contracts_url, headers=headers, params=params)

    print(f"Status Code: {res_contracts.status_code}")
    if res_contracts.status_code == 200:
        print("Success! JSON Output:")
        print(json.dumps(res_contracts.json(), indent=2))
    else:
        print(f"Failed: {res_contracts.text[:300]}")

    # 2. FIXED ENDPOINT: Market Snapshot Chain
    # Using 'I:SPX' for index option chains
    snapshot_url = f"{BASE_URL}/v3/snapshot/options/I:SPX"

    print("\n[Step 2] Fetching live options chain snapshot...")
    res_snapshot = requests.get(snapshot_url, headers=headers)

    print(f"Status Code: {res_snapshot.status_code}")
    if res_snapshot.status_code == 200:
        data = res_snapshot.json()
        results_count = len(data.get("results", []))
        print(f"Success! Found {results_count} active chains.")
    else:
        print(f"Failed: {res_snapshot.text[:300]}")


if __name__ == "__main__":
    test_spx_options_fixed()
