#!/usr/bin/env python3
"""
Test script for advanced features:
1. Live top-scorers leaderboard (Redis sorted set)
2. Real logout with token blocklist

Run this after starting the API server:
  uvicorn main:app --reload (from football-api directory)
"""

import requests
import time
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

def timestamp():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]

def test_live_scorers_leaderboard():
    """Test live scorers leaderboard with Redis sorted set"""
    print(f"\n{timestamp()} === Testing Live Top-Scorers Leaderboard ===")
    
    # First, get a token for admin operations
    print(f"\n{timestamp()} [Setup] Logging in as admin...")
    login_response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": "admin@example.com", "password": "admin_password"}
    )
    
    if login_response.status_code != 200:
        print(f"  Error: Could not login. Status {login_response.status_code}")
        print(f"  Response: {login_response.text}")
        return
    
    admin_token = login_response.json().get("access_token")
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Get a match to create events on
    print(f"\n{timestamp()} [Setup] Getting first match...")
    matches_response = requests.get(f"{BASE_URL}/matches")
    if matches_response.status_code != 200:
        print(f"  Error: Could not get matches. Status {matches_response.status_code}")
        return
    
    matches = matches_response.json().get("items", [])
    if not matches:
        print(f"  Warning: No matches found. Create a match first.")
        return
    
    match_id = matches[0]["id"]
    print(f"  Using match {match_id}")
    
    # Create goal events
    print(f"\n{timestamp()} [1] Creating goal events...")
    
    goal_data = [
        {"minute": 10, "player": {"id": 1, "name": "Player 1"}, "detail": {}},
        {"minute": 25, "player": {"id": 1, "name": "Player 1"}, "detail": {}},
        {"minute": 45, "player": {"id": 2, "name": "Player 2"}, "detail": {}},
        {"minute": 60, "player": {"id": 3, "name": "Player 3"}, "detail": {}},
    ]
    
    for i, goal in enumerate(goal_data, 1):
        event_response = requests.post(
            f"{BASE_URL}/matches/{match_id}/events",
            json={
                **goal,
                "type": "goal",
                "tags": ["open_play"]
            },
            headers=headers
        )
        if event_response.status_code == 201:
            print(f"  ✓ Goal {i} created: {goal['player']['name']}")
        else:
            print(f"  ✗ Goal {i} failed: {event_response.status_code}")
    
    # Get live scorers from Redis (should be fast)
    print(f"\n{timestamp()} [2] GET /stats/live-scorers (Redis - ZREVRANGE)...")
    start_time = time.time()
    live_response = requests.get(f"{BASE_URL}/stats/live-scorers?limit=10")
    if live_response.status_code == 200:
        data = live_response.json()
        print(f"  Status: {live_response.status_code}")
        print(f"  Scorers: {data.get('scorers', [])}")
        print(f"  Timing: {data.get('_timing_ms', 'N/A')}ms (Redis)")
    else:
        print(f"  Error: {live_response.status_code}")
    
    # Get top scorers from MongoDB (slower for comparison)
    print(f"\n{timestamp()} [3] GET /stats/top-scorers (MongoDB - Aggregation)...")
    start_time = time.time()
    mongo_response = requests.get(f"{BASE_URL}/stats/top-scorers?limit=10")
    if mongo_response.status_code == 200:
        data = mongo_response.json()
        print(f"  Status: {mongo_response.status_code}")
        print(f"  Scorers: {data.get('scorers', [])}")
        print(f"  Timing: {data.get('_timing_ms', 'N/A')}ms (MongoDB)")
    else:
        print(f"  Error: {mongo_response.status_code}")
    
    # Compare performance
    if live_response.status_code == 200 and mongo_response.status_code == 200:
        redis_timing = live_response.json().get("_timing_ms", 0)
        mongo_timing = mongo_response.json().get("_timing_ms", 0)
        if mongo_timing > 0:
            improvement = mongo_timing / redis_timing if redis_timing > 0 else 0
            print(f"\n✓ Performance Comparison:")
            print(f"  Redis:   {redis_timing}ms")
            print(f"  MongoDB: {mongo_timing}ms")
            print(f"  Improvement: {improvement:.1f}x faster with Redis")


def test_logout_blocklist():
    """Test logout with token blocklist"""
    print(f"\n{timestamp()} === Testing Logout with Token Blocklist ===")
    
    # 1. Login
    print(f"\n{timestamp()} [1] Login to get token...")
    login_response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": "testuser@example.com", "password": "password"}
    )
    
    if login_response.status_code != 200:
        print(f"  Error: Login failed. Status {login_response.status_code}")
        print(f"  Note: Create a test user first if needed")
        return
    
    token = login_response.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    print(f"  ✓ Login successful, got token: {token[:20]}...")
    
    # 2. Verify token works
    print(f"\n{timestamp()} [2] Verify token works - GET /users/me...")
    verify_response = requests.get(f"{BASE_URL}/users/me", headers=headers)
    if verify_response.status_code == 200:
        user_data = verify_response.json()
        print(f"  ✓ Token valid. User: {user_data.get('email', 'unknown')}")
    else:
        print(f"  ✗ Token not working. Status {verify_response.status_code}")
        return
    
    # 3. Logout (add token to blocklist)
    print(f"\n{timestamp()} [3] POST /auth/logout (add token to blocklist)...")
    logout_response = requests.post(f"{BASE_URL}/auth/logout", headers=headers)
    if logout_response.status_code == 200:
        print(f"  ✓ Logout successful")
    else:
        print(f"  ✗ Logout failed. Status {logout_response.status_code}")
        print(f"  Response: {logout_response.text}")
        return
    
    # 4. Try to use token after logout
    print(f"\n{timestamp()} [4] Try to use token after logout - GET /users/me...")
    blocked_response = requests.get(f"{BASE_URL}/users/me", headers=headers)
    if blocked_response.status_code == 401:
        error_data = blocked_response.json()
        print(f"  ✓ Token properly blocked. Error: {error_data.get('detail', 'unknown')}")
        print("\n✓ Logout blocklist works: PASS")
    else:
        print(f"  ✗ Token not blocked! Status {blocked_response.status_code}")
        print(f"  Response: {blocked_response.text}")
        print("\n✗ Logout blocklist failed: FAIL")


if __name__ == "__main__":
    print("=" * 60)
    print("Advanced Features Test Suite")
    print("=" * 60)
    
    try:
        # Test live scorers leaderboard
        test_live_scorers_leaderboard()
        
        # Test logout blocklist
        test_logout_blocklist()
        
        print("\n" + "=" * 60)
        print("Test suite complete")
        print("=" * 60)
        
    except requests.exceptions.ConnectionError:
        print(f"Error: Could not connect to API at {BASE_URL}")
        print("Make sure the API server is running")
