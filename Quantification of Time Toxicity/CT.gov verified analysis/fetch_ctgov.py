#!/usr/bin/env python3
"""
Phase 1, Step 2: Fetch CT.gov v2 API arm-type designations for all 644 NCTs.

Cache-first: writes raw JSON to ctgov_cache/{NCT}.json. Re-runs are offline.
Produces ctgov_cache/_manifest.csv and ctgov_snapshot_meta.json.
"""

import os
import sys
import json
import time
import hashlib
import warnings

warnings.filterwarnings("ignore")

import pandas as pd
import requests

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
CACHE = os.path.join(BASE, "ctgov_cache")
API = "https://clinicaltrials.gov/api/v2/studies/{nct}"
FIELDS = "protocolSection.armsInterventionsModule,protocolSection.designModule,protocolSection.identificationModule"

os.makedirs(CACHE, exist_ok=True)


def fetch_one(nct, session, max_retries=3):
    """Fetch one NCT, cache-first. Returns (status, n_armgroups, sha256, from_cache)."""
    cache_path = os.path.join(CACHE, f"{nct}.json")
    sentinel_404 = os.path.join(CACHE, f"{nct}.404.json")

    if os.path.exists(cache_path):
        with open(cache_path) as f:
            raw = f.read()
        try:
            d = json.loads(raw)
            arms = d.get("protocolSection", {}).get("armsInterventionsModule", {}).get("armGroups", []) or []
            return 200, len(arms), hashlib.sha256(raw.encode()).hexdigest()[:16], True
        except Exception:
            pass
    if os.path.exists(sentinel_404):
        return 404, 0, "", True

    url = API.format(nct=nct)
    for attempt in range(max_retries):
        try:
            r = session.get(url, params={"fields": FIELDS}, timeout=20)
            if r.status_code == 200:
                raw = r.text
                with open(cache_path, "w") as f:
                    f.write(raw)
                d = r.json()
                arms = d.get("protocolSection", {}).get("armsInterventionsModule", {}).get("armGroups", []) or []
                return 200, len(arms), hashlib.sha256(raw.encode()).hexdigest()[:16], False
            elif r.status_code == 404:
                with open(sentinel_404, "w") as f:
                    json.dump({"nct": nct, "status": 404}, f)
                return 404, 0, "", False
            elif r.status_code in (429, 500, 502, 503, 504):
                time.sleep(1.5 * (attempt + 1))
                continue
            else:
                return r.status_code, 0, "", False
        except requests.RequestException:
            time.sleep(1.5 * (attempt + 1))
    return -1, 0, "", False  # fetch error after retries


def main():
    trials = pd.read_csv(os.path.join(DATA, "enriched_trials.csv"))
    ncts = trials[["filename", "NCT Number"]].dropna(subset=["NCT Number"]).copy()
    ncts["NCT Number"] = ncts["NCT Number"].astype(str).str.strip()
    unique_ncts = sorted(ncts["NCT Number"].unique())
    print(f"Fetching {len(unique_ncts)} unique NCTs (cache-first)...")

    session = requests.Session()
    session.headers.update({"Accept": "application/json"})

    rows = []
    n_fetched = n_cached = n_404 = n_err = 0
    for i, nct in enumerate(unique_ncts, 1):
        status, n_arms, sha, from_cache = fetch_one(nct, session)
        rows.append({"nct": nct, "http_status": status, "n_armgroups": n_arms,
                     "sha256": sha, "from_cache": from_cache})
        if status == 200:
            n_cached += from_cache
            n_fetched += (not from_cache)
        elif status == 404:
            n_404 += 1
        elif status < 0:
            n_err += 1
        if not from_cache and status >= 0:
            time.sleep(0.25)  # politeness
        if i % 50 == 0:
            print(f"  {i}/{len(unique_ncts)}  (fetched={n_fetched} cached={n_cached} 404={n_404} err={n_err})")

    manifest = pd.DataFrame(rows)
    manifest.to_csv(os.path.join(CACHE, "_manifest.csv"), index=False)

    meta = {
        "snapshot_note": "CT.gov v2 API arm-type snapshot for TimeToxSV verification",
        "n_ncts": len(unique_ncts),
        "n_fetched_live": int(n_fetched),
        "n_from_cache": int(n_cached),
        "n_404": int(n_404),
        "n_fetch_error": int(n_err),
        "api_endpoint": API,
        "fields": FIELDS,
        "requests_version": requests.__version__,
    }
    with open(os.path.join(BASE, "ctgov_snapshot_meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    print("\n=== FETCH SUMMARY ===")
    for k, v in meta.items():
        print(f"  {k}: {v}")
    print(f"\nArm-group count distribution:")
    print(manifest[manifest.http_status == 200]["n_armgroups"].value_counts().sort_index().to_string())


if __name__ == "__main__":
    main()
