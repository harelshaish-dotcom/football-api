#!/usr/bin/env python3
"""
Test script for new caching and rate limiting features.

Tests:
1. GET /teams caching with league_id, limit, offset parameters
2. Rate limiting on POST /auth/login (5 attempts per minute per IP)

Run this after starting the API server:
  uvicorn main:app --reload
"""

import requests
import time
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

def timestamp():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]

def test_teams_list_caching():
    """Test GET /teams caching with different pagination params"""
    print(f"\n{timestamp()} === Testing GET /teams Caching with Pagination ===")
    
    # Test page 1
    print(f"\n{timestamp()} [1] First GET /teams?league_id=1&limit=5&offset=0 (page 1, cache miss expected)")
    r1 = requests.get(f"{BASE_URL}/teams/?league_id=1&limit=5&offset=0")
    if r1.status_code == 200:
        data1 = r1.json()
        print(f"  Status: {r1.status_code}")
        print(f"  Cache: {data1.get('_cache', 'N/A')}")
        print(f"  Timing: {data1.get('_timing_ms', 'N/A')}ms")
        print(f"  Teams count: {len(data1.get('teams', []))}")
        print(f"  Total: {data1.get('total', 'N/A')}")
        page1_data = data1.get('teams', [])
    else:
        print(f"  Error: {r1.status_code} - {r1.text}")
        return
    
    # Test page 1 again (should be cache hit)
    print(f"\n{timestamp()} [2] Second GET /teams?league_id=1&limit=5&offset=0 (cache hit expected)")
    r2 = requests.get(f"{BASE_URL}/teams/?league_id=1&limit=5&offset=0")
    if r2.status_code == 200:
        data2 = r2.json()
        print(f"  Status: {r2.status_code}")
        print(f"  Cache: {data2.get('_cache', 'N/A')}")
        print(f"  Timing: {data2.get('_timing_ms', 'N/A')}ms")
        
        if data2.get('_cache') == 'HIT':
            print(f"✓ Page 1 cache hit: PASS")
        else:
            print(f"✗ Page 1 cache miss: FAIL")
    
    # Test page 2 (different offset, cache miss expected)
    print(f"\n{timestamp()} [3] GET /teams?league_id=1&limit=5&offset=5 (page 2, cache miss expected)")
    r3 = requests.get(f"{BASE_URL}/teams/?league_id=1&limit=5&offset=5")
    if r3.status_code == 200:
        data3 = r3.json()
        print(f"  Status: {r3.status_code}")
        print(f"  Cache: {data3.get('_cache', 'N/A')}")
        print(f"  Timing: {data3.get('_timing_ms', 'N/A')}ms")
        print(f"  Teams count: {len(data3.get('teams', []))}")
        page2_data = data3.get('teams', [])
        
        # Verify page 1 and page 2 have different data
        if page1_data != page2_data:
            print(f"✓ Page 1 and page 2 have different data: PASS")
        else:
            print(f"✗ Page 1 and page 2 have same data: FAIL")
    
    # Test page 2 again (cache hit expected)
    print(f"\n{timestamp()} [4] Second GET /teams?league_id=1&limit=5&offset=5 (cache hit expected)")
    r4 = requests.get(f"{BASE_URL}/teams/?league_id=1&limit=5&offset=5")
    if r4.status_code == 200:
        data4 = r4.json()
        print(f"  Status: {r4.status_code}")
        print(f"  Cache: {data4.get('_cache', 'N/A')}")
        
        if data4.get('_cache') == 'HIT':
            print(f"✓ Page 2 cache hit: PASS")
        else:
            print(f"✗ Page 2 cache miss: FAIL")


def test_login_rate_limiting():
    """Test rate limiting on POST /auth/login (5 attempts per minute per IP)"""
    print(f"\n{timestamp()} === Testing POST /auth/login Rate Limiting ===")
    print(f"Note: Rate limit is 5 attempts per minute per IP")
    
    test_email = "nonexistent@example.com"
    test_password = "wrongpassword"
    
    successful_attempts = 0
    rate_limited = False
    
    # Try to make 7 login attempts (should be limited after 5)
    for attempt in range(7):
        print(f"\n{timestamp()} [Attempt {attempt + 1}]")
        r = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email": test_email, "password": test_password}
        )
        
        print(f"  Status: {r.status_code}")
        
        if r.status_code == 429:
            rate_limited = True
            retry_after = r.headers.get("Retry-After", "N/A")
            print(f"  Rate limited! Retry-After: {retry_after}s")
            print(f"  Detail: {r.json().get('detail', 'N/A')}")
        elif r.status_code == 401:
            successful_attempts += 1
            print(f"  Login attempt counted (invalid credentials)")
        else:
            print(f"  Unexpected status: {r.status_code}")
    
    if successful_attempts == 5 and rate_limited:
        print(f"\n✓ Rate limiting works: 5 attempts allowed, 6th+ blocked: PASS")
    else:
        print(f"\n✗ Rate limiting failed: {successful_attempts} attempts allowed, rate_limited={rate_limited}: FAIL")


if __name__ == "__main__":
    print("=" * 60)
    print("New Features Test Suite")
    print("=" * 60)
    
    try:
        # Test teams list caching
        test_teams_list_caching()
        
        # Test login rate limiting
        test_login_rate_limiting()
        
        print("\n" + "=" * 60)
        print("Test suite complete")
        print("=" * 60)
        
    except requests.exceptions.ConnectionError:
        print(f"Error: Could not connect to API at {BASE_URL}")
        print("Make sure the API server is running")
