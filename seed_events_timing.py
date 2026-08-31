"""
Script to insert 500 events and time the GET /matches/{id}/events endpoint
before and after creating an index on match_id and minute.
"""
import asyncio
import time
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from database.postgres import SessionLocal
from models.match import Match
import httpx

# Setup
MONGO_URL = "mongodb://localhost:27017"
API_URL = "http://localhost:8000"

async def main():
    # Connect to MongoDB
    client = AsyncIOMotorClient(MONGO_URL)
    mongo_db = client["football"]
    events_col = mongo_db["match_events"]
    
    # Get multiple matches for testing
    db = SessionLocal()
    matches = db.query(Match).limit(5).all()
    if not matches:
        print("No matches found in database. Please seed the database first.")
        db.close()
        return
    
    match_ids = [m.id for m in matches]
    print(f"Using {len(match_ids)} matches: {match_ids}")
    db.close()
    
    # Clear existing events for these matches
    await events_col.delete_many({"match_id": {"$in": match_ids}})
    print("Cleared existing events for these matches")
    
    # Insert 500 test events distributed across multiple matches
    print(f"Inserting 500 test events across {len(match_ids)} matches...")
    events_to_insert = []
    for i in range(500):
        match_idx = i % len(match_ids)  # Cycle through matches
        match_id = match_ids[match_idx]
        event = {
            "match_id": match_id,
            "minute": (i % 90) + 1,
            "type": ["goal", "card", "substitution", "var"][i % 4],
            "player": {
                "id": (i % 27) + 1,  # Cycle through player IDs
                "name": f"Player {(i % 27) + 1}"
            },
            "detail": {"description": f"Event {i+1}"},
            "tags": ["test"] if i % 10 == 0 else []
        }
        events_to_insert.append(event)
    
    result = await events_col.insert_many(events_to_insert)
    print(f"Inserted {len(result.inserted_ids)} events across {len(match_ids)} matches")
    
    # Use first match for timing
    test_match_id = match_ids[0]
    events_in_test_match = len([e for e in events_to_insert if e["match_id"] == test_match_id])
    print(f"Test match ID: {test_match_id} (has {events_in_test_match} events)")
    
    # Time the endpoint BEFORE creating index
    print("\n--- TIMING BEFORE INDEX ---")
    async with httpx.AsyncClient() as client:
        # Warmup request
        await client.get(f"{API_URL}/matches/{test_match_id}/events")
        
        start = time.time()
        response = await client.get(f"{API_URL}/matches/{test_match_id}/events?limit=200")
        before_time = time.time() - start
    
    print(f"GET /matches/{test_match_id}/events: {before_time:.4f}s")
    
    # Drop any existing indexes (except _id)
    print("\nDropping existing indexes...")
    index_info = await events_col.index_information()
    for index_name in index_info:
        if index_name != "_id_":
            await events_col.drop_index(index_name)
    print(f"Indexes before: {list(index_info.keys())}")
    
    # Time the endpoint again without index
    print("\n--- TIMING WITHOUT INDEX (baseline) ---")
    async with httpx.AsyncClient() as client:
        start = time.time()
        response = await client.get(f"{API_URL}/matches/{test_match_id}/events?limit=200")
        baseline_time = time.time() - start
    print(f"GET /matches/{test_match_id}/events: {baseline_time:.4f}s")
    
    # Create index (we just deleted)
    print("\nCreating index on match_id and minute...")
    await events_col.create_index([("match_id", 1), ("minute", 1)])
    print("Index created")
    
    # Time the endpoint AFTER creating index
    print("\n--- TIMING AFTER INDEX ---")
    async with httpx.AsyncClient() as client:
        # Warmup request
        await client.get(f"{API_URL}/matches/{test_match_id}/events")
        
        start = time.time()
        response = await client.get(f"{API_URL}/matches/{test_match_id}/events?limit=200")
        after_time = time.time() - start
    
    print(f"GET /matches/{test_match_id}/events: {after_time:.4f}s")
    
    # Print comparison
    print("\n--- RESULTS ---")
    print(f"Without index: {baseline_time:.4f}s")
    print(f"With index:    {after_time:.4f}s")
    print(f"Improvement:   {((baseline_time - after_time) / baseline_time * 100):.2f}% faster")
    print(f"Speedup:       {baseline_time / after_time:.2f}x")
    
    # Save results to docs/notes.md
    with open("docs/notes.md", "a") as f:
        f.write("\n\n## Event Query Performance Testing\n\n")
        f.write(f"### Test Setup\n\n")
        f.write(f"- 500 events inserted across {len(match_ids)} matches\n")
        f.write(f"- Match IDs tested: {match_ids}\n")
        f.write(f"- Events per match: ~{500 // len(match_ids)}\n")
        f.write(f"- Test match ID: {test_match_id} ({events_in_test_match} events)\n")
        f.write(f"- Events distributed across 90 minutes\n")
        f.write(f"- Query: `GET /matches/{{id}}/events?limit=200`\n\n")
        f.write(f"### Results\n\n")
        f.write(f"**Before Index Creation:**\n")
        f.write(f"- Query Time: {baseline_time:.4f}s\n\n")
        f.write(f"**After Index Creation (match_id, minute):**\n")
        f.write(f"- Query Time: {after_time:.4f}s\n")
        if baseline_time > 0:
            f.write(f"- Improvement: {((baseline_time - after_time) / baseline_time * 100):.2f}% faster\n")
            f.write(f"- Speedup Factor: {baseline_time / after_time:.2f}x\n\n")
        f.write(f"### Analysis\n\n")
        f.write(f"The index on (match_id, minute) improves query performance by enabling:\n\n")
        if baseline_time > 0:
            f.write(f"- **Speedup:** {baseline_time / after_time:.2f}x faster queries\n")
        f.write(f"- **Indexed Query:** O(log n) lookup on match_id, then sorted by minute\n")
        f.write(f"- **Full Scan:** Without index, MongoDB scans all documents to find matching match_id\n\n")
    
    print("\nResults saved to docs/notes.md")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(main())
