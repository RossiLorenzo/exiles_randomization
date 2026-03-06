#!/usr/bin/env python3
"""
Verification script to ensure randomization works with different seeds.
"""

from app import solve_holistic

# Test data with 9 fencers (3 teams)
fencers = [
    {"name": f"F{i}", "category": "F", "preference": {"foil": 5, "epee": 3, "sabre": 1}}
    for i in range(4)
] + [
    {"name": f"M{i}", "category": "M", "preference": {"foil": 1, "epee": 5, "sabre": 3}}
    for i in range(5)
]

print("Testing randomization with different seeds...")
print(f"Using {len(fencers)} fencers ({sum(1 for f in fencers if f['category'] == 'F')}F/{sum(1 for f in fencers if f['category'] == 'M')}M)\n")

# Check different seeds produce different results
results = {}
for seed in [1, 2, 3, 4, 5, 10, 42, 100]:
    result = solve_holistic(fencers, seed=seed)

    # Create a string representation of team assignments
    team_str = ""
    for t in sorted(result["teams"], key=lambda x: x["team"]):
        team_members = (t["members"]["foil"]["name"],
                       t["members"]["epee"]["name"],
                       t["members"]["sabre"]["name"])
        team_str += f"T{t['team']}: {team_members} "

    if team_str in results:
        results[team_str].append(seed)
    else:
        results[team_str] = [seed]

    print(f"Seed {seed:3}: {team_str}")

print(f"\n=== Results Summary ===")
print(f"Got {len(results)} unique team configurations from {8} different seeds")

if len(results) == 1:
    print("❌ FAIL: Randomization not working! All seeds produced the same result.")
else:
    print("✓ SUCCESS: Randomization is working! Different seeds produce different team assignments.")
    print("\nConfiguration distribution:")
    for i, (config, seeds) in enumerate(results.items(), 1):
        print(f"  Config {i}: Seeds {seeds}")

# Verify same seed produces same result
print("\n=== Reproducibility Test ===")
print("Testing that same seed produces identical results...")

test_seed = 42
result1 = solve_holistic(fencers, seed=test_seed)
result2 = solve_holistic(fencers, seed=test_seed)

# Create comparable representations
def team_to_str(result):
    team_str = ""
    for t in sorted(result["teams"], key=lambda x: x["team"]):
        team_members = (t["members"]["foil"]["name"],
                       t["members"]["epee"]["name"],
                       t["members"]["sabre"]["name"])
        team_str += f"{team_members}"
    return team_str

str1 = team_to_str(result1)
str2 = team_to_str(result2)

if str1 == str2:
    print(f"✓ SUCCESS: Seed {test_seed} produces reproducible results")
else:
    print(f"❌ FAIL: Seed {test_seed} produces different results on repeated runs")
    print(f"  Run 1: {str1}")
    print(f"  Run 2: {str2}")