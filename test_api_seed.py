#!/usr/bin/env python3
"""
Test the Flask API with seed parameter to verify randomization works
"""

import json
from app import app

# Create test client
client = app.test_client()

# Test data
fencers = [
    {"name": "F1", "category": "F", "preference": {"foil": 5, "epee": 3, "sabre": 1}},
    {"name": "F2", "category": "F", "preference": {"foil": 4, "epee": 4, "sabre": 2}},
    {"name": "F3", "category": "F", "preference": {"foil": 3, "epee": 5, "sabre": 3}},
    {"name": "M1", "category": "M", "preference": {"foil": 2, "epee": 5, "sabre": 4}},
    {"name": "M2", "category": "M", "preference": {"foil": 1, "epee": 4, "sabre": 5}},
    {"name": "M3", "category": "M", "preference": {"foil": 3, "epee": 3, "sabre": 3}}
]

print("Testing Flask API with seed parameter...")
print("=" * 50)

# Test with different seeds
results = {}
for seed in [1, 2, 3, 42, 100]:
    payload = {
        "fencers": fencers,
        "seed": seed
    }

    response = client.post('/solve',
                          data=json.dumps(payload),
                          content_type='application/json')

    assert response.status_code == 200, f"Failed with seed {seed}: {response.status_code}"

    data = json.loads(response.data)

    # Create a string representation
    team_str = ""
    for team in data["teams"]:
        team_str += f"T{team['team']}: "
        team_str += f"({team['members']['foil']['name']}, "
        team_str += f"{team['members']['epee']['name']}, "
        team_str += f"{team['members']['sabre']['name']}) "

    print(f"Seed {seed:3}: {team_str}")

    if team_str in results:
        results[team_str].append(seed)
    else:
        results[team_str] = [seed]

print("\n" + "=" * 50)
print(f"Got {len(results)} unique configurations from 5 seeds")

if len(results) > 1:
    print("✓ SUCCESS: API randomization with seed parameter works!")
else:
    print("❌ FAIL: All seeds produced the same result")

# Test reproducibility
print("\n" + "=" * 50)
print("Testing reproducibility with same seed...")

test_seed = 42
response1 = client.post('/solve',
                        data=json.dumps({"fencers": fencers, "seed": test_seed}),
                        content_type='application/json')
response2 = client.post('/solve',
                        data=json.dumps({"fencers": fencers, "seed": test_seed}),
                        content_type='application/json')

data1 = json.loads(response1.data)
data2 = json.loads(response2.data)

# Compare team assignments
def teams_to_str(data):
    return str(sorted([(t["members"]["foil"]["name"],
                       t["members"]["epee"]["name"],
                       t["members"]["sabre"]["name"])
                      for t in data["teams"]]))

if teams_to_str(data1) == teams_to_str(data2):
    print(f"✓ SUCCESS: Seed {test_seed} produces reproducible results via API")
else:
    print(f"❌ FAIL: Same seed produces different results")

# Test without seed (should work too)
print("\n" + "=" * 50)
print("Testing API without seed parameter...")

response = client.post('/solve',
                       data=json.dumps({"fencers": fencers}),
                       content_type='application/json')

if response.status_code == 200:
    print("✓ SUCCESS: API works without seed parameter (backward compatible)")
else:
    print(f"❌ FAIL: API failed without seed: {response.status_code}")