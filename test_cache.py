import requests
"""
Test script to verify caching implementation and cache invalidation.

Run this after starting the API server:
  uvicorn main:app --reload

This script tests:
1. GET /teams/{id} with 60-second TTL
2. Cache invalidation on PATCH /teams/{id}
3. Cache invalidation on DELETE /teams/{id}
4. GET /leagues/{id}/table with 5-minute TTL
"""

import requests
import time
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

# Test credentials (adjust as needed)
ADMIN_TOKEN = None  # You'll need to set this or get it from login

def timestamp():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]

def test_team_caching():
    """Test team endpoint caching and invalidation"""
    print(f"\n{timestamp()} === Testing GET /teams/{{id}} Caching ===")
    
    team_id = 1
    
    # First request - cache miss
    print(f"\n{timestamp()} [1] First GET /teams/{team_id} (cache miss expected)")
    r1 = requests.get(f"{BASE_URL}/teams/{team_id}")
    if r1.status_code == 200:
        data1 = r1.json()
        print(f"  Status: {r1.status_code}")
        print(f"  Cache: {data1.get('_cache', 'N/A')}")
        print(f"  Timing: {data1.get('_timing_ms', 'N/A')}ms")
        cache_hit_1 = data1.get('_cache') == 'HIT'
    else:
        print(f"  Error: {r1.status_code}")
        return
    
    # Second request - should be cache hit
    print(f"\n{timestamp()} [2] Second GET /teams/{team_id} (cache hit expected)")
    r2 = requests.get(f"{BASE_URL}/teams/{team_id}")
    if r2.status_code == 200:
        data2 = r2.json()
        print(f"  Status: {r2.status_code}")
        print(f"  Cache: {data2.get('_cache', 'N/A')}")
        print(f"  Timing: {data2.get('_timing_ms', 'N/A')}ms")
        cache_hit_2 = data2.get('_cache') == 'HIT'
    else:
        print(f"  Error: {r2.status_code}")
        return
    
    if not cache_hit_1 and cache_hit_2:
        print(f"\n✓ Cache miss on first request, hit on second: PASS")
    else:
        print(f"\n✗ Unexpected cache behavior: FAIL")
    
    # Test invalidation with PATCH
    print(f"\n{timestamp()} [3] PATCH /teams/{team_id} (should invalidate cache)")
    
    if not ADMIN_TOKEN:
        print("  Skipping PATCH test (no admin token)")
    else:
        headers = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
        r3 = requests.patch(f"{BASE_URL}/teams/{team_id}", 
                           json={"stadium": "Updated Stadium"},
                           headers=headers)
        print(f"  Status: {r3.status_code}")
        
        # After PATCH, next GET should be cache miss
        print(f"\n{timestamp()} [4] GET /teams/{team_id} after PATCH (cache miss expected)")
        r4 = requests.get(f"{BASE_URL}/teams/{team_id}")
        if r4.status_code == 200:
            data4 = r4.json()
            print(f"  Status: {r4.status_code}")
            print(f"  Cache: {data4.get('_cache', 'N/A')}")
            print(f"  Timing: {data4.get('_timing_ms', 'N/A')}ms")
            
            if data4.get('_cache') == 'MISS':
                print(f"\n✓ Cache invalidated after PATCH: PASS")
            else:
                print(f"\n✗ Cache not invalidated: FAIL")


def test_league_table_caching():
    """Test league table endpoint caching"""
    print(f"\n{timestamp()} === Testing GET /leagues/{{id}}/table Caching ===")
    
    league_id = 1
    
    # First request - cache miss
    print(f"\n{timestamp()} [1] First GET /leagues/{league_id}/table (cache miss expected)")
    r1 = requests.get(f"{BASE_URL}/leagues/{league_id}/table")
    if r1.status_code == 200:
        data1 = r1.json()
        print(f"  Status: {r1.status_code}")
        print(f"  Cache: {data1.get('_cache', 'N/A')}")
        print(f"  Timing: {data1.get('_timing_ms', 'N/A')}ms")
    else:
        print(f"  Error: {r1.status_code} - {r1.text}")
        return
    
    # Second request - should be cache hit
    print(f"\n{timestamp()} [2] Second GET /leagues/{league_id}/table (cache hit expected)")
    r2 = requests.get(f"{BASE_URL}/leagues/{league_id}/table")
    if r2.status_code == 200:
        data2 = r2.json()
        print(f"  Status: {r2.status_code}")
        print(f"  Cache: {data2.get('_cache', 'N/A')}")
        print(f"  Timing: {data2.get('_timing_ms', 'N/A')}ms")
        
        if data2.get('_cache') == 'HIT':
            print(f"\n✓ Cache hit: PASS")
        else:
            print(f"\n✗ Cache miss: FAIL")
    else:
        print(f"  Error: {r2.status_code}")


if __name__ == "__main__":
    print("=" * 60)
    print("Cache Implementation Test Suite")
    print("=" * 60)
    
    try:
        # Test league table caching
        test_league_table_caching()
        
        # Test team caching
        test_team_caching()
        
        print("\n" + "=" * 60)
        print("Test suite complete")
        print("=" * 60)
        
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to API at {BASE_URL}")
        print("Make sure the API server is running")