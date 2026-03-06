import os
import random
from flask import Flask, request, jsonify
from ortools.linear_solver import pywraplp

app = Flask(__name__)

def solve_holistic(fencers, seed=None):
    """
    Solves the team assignment problem using a single holistic MILP model.
    Encodes constraints for:
    - Team Size (3 Main)
    - Roles (Main vs Reserve)
    - Gender constraints (avoid 3M/3F, prefer 2F/1M or 1F/2M)
    - Reserve Rules (Match 2F, Mismatch 1F, No 3M)
    - Objective: Maximize preference (Minimize for All-M)

    Args:
        fencers: List of fencer dicts with name, category, and preference
        seed: Optional random seed for reproducible but varied solutions.
              Different seeds produce different valid solutions.
    """
    solver = pywraplp.Solver.CreateSolver("SCIP") # SCIP is better for non-linear logic / indicators
    if not solver:
        return {"error": "Solver not found"}

    # --- Data Prep ---
    n_fencers = len(fencers)
    n_teams = n_fencers // 3
    if n_teams == 0:
        return {"teams": [], "reserves": fencers} # Not enough for 1 team

    # Initialize random generator for tie-breaking perturbations
    rng = random.Random(seed)

    # Create a copy and shuffle to vary solver exploration
    # This ensures different seeds produce different variable orderings
    fencers = fencers.copy()  # Don't modify the original input
    rng.shuffle(fencers)

    weapons = ["foil", "epee", "sabre"]
    n_weapons = 3

    # --- Variables ---
    # x[i, t, w, r]: 1 if fencer i is in team t with weapon w and role r (0=Main, 1=Reserve)
    # i: 0..N-1
    # t: 0..T-1
    # w: 0..2
    # r: 0..1
    x = {}
    for i in range(n_fencers):
        for t in range(n_teams):
            for w in range(n_weapons):
                for r in range(2): # 0=Main, 1=Reserve
                    x[i, t, w, r] = solver.BoolVar(f"x_{i}_{t}_{w}_{r}")

    # Auxiliary: Gender composition of MAIN slots
    # is_3m[t]: 1 if team t has 0 Females in Main
    # is_1f[t]: 1 if team t has 1 Female in Main
    # is_2f[t]: 1 if team t has 2 Females in Main
    # is_3f[t]: 1 if team t has 3 Females in Main
    is_3m = {t: solver.BoolVar(f"is_3m_{t}") for t in range(n_teams)}
    is_1f = {t: solver.BoolVar(f"is_1f_{t}") for t in range(n_teams)}
    is_2f = {t: solver.BoolVar(f"is_2f_{t}") for t in range(n_teams)}
    is_3f = {t: solver.BoolVar(f"is_3f_{t}") for t in range(n_teams)}

    # --- Hard Constraints ---

    # 1. Every fencer assigned exactly once (Main OR Reserve)
    for i in range(n_fencers):
        solver.Add(
            solver.Sum(x[i, t, w, r] for t in range(n_teams) for w in range(n_weapons) for r in range(2)) == 1
        )

    # 2. Team Composition: Main Slots
    # Each team has exactly 1 Main Person per Weapon
    for t in range(n_teams):
        for w in range(n_weapons):
            solver.Add(
                solver.Sum(x[i, t, w, 0] for i in range(n_fencers)) == 1
            )

    # 3. Reserve Constraint
    # Each team has AT MOST 1 Reserve (total across all weapons)
    for t in range(n_teams):
        solver.Add(
            solver.Sum(x[i, t, w, 1] for i in range(n_fencers) for w in range(n_weapons)) <= 1
        )
    
    # 4. Gender Classification Constraints (Indicators)
    # Define N_F_Main[t]
    for t in range(n_teams):
        n_f_main = solver.Sum(
            x[i, t, w, 0] for i in range(n_fencers) for w in range(n_weapons) 
            if fencers[i]["category"].upper() == "F"
        )
        
        # Link indicators: Strictly one is true
        solver.Add(is_3m[t] + is_1f[t] + is_2f[t] + is_3f[t] == 1)
        
        # Logic: if is_3m=1, n_f_main=0.
        # if is_1f=1, n_f_main=1.
        # if is_2f=1, n_f_main=2.
        # if is_3f=1, n_f_main=3.
        # Implementation via linear bounds:
        # n_f_main == 0*is_3m + 1*is_1f + 2*is_2f + 3*is_3f
        solver.Add(n_f_main == (0 * is_3m[t] + 1 * is_1f[t] + 2 * is_2f[t] + 3 * is_3f[t]))

    # 5. Reserve & Gender Interactions
    
    # 5a. NO Reserve on 3M Team
    # Sum(Reserve in T) <= 1 - is_3m[t]
    for t in range(n_teams):
        reserve_count = solver.Sum(x[i, t, w, 1] for i in range(n_fencers) for w in range(n_weapons))
        solver.Add(reserve_count <= 1 - is_3m[t])

    # 5b. Reserve Matching Rules (For Male Reserves, primarily, but let's apply generally if sensible or strict for M)
    # "If team has 2F... reserve M should have one of the 2F weapons"
    # "If team has 1F... reserve M should NOT have the F weapon"
    
    for t in range(n_teams):
        main_is_female_vars = []
        for w in range(n_weapons):
            var = solver.Sum(x[i, t, w, 0] for i in range(n_fencers) if fencers[i]["category"].upper() == "F")
            main_is_female_vars.append(var) # value is 0 or 1 (since slot filled by 1 person)

        for w_res in range(n_weapons):
            # Sum of Male Reserves assigned to Team T with Weapon W_res
            m_res_w = solver.Sum(x[i, t, w_res, 1] for i in range(n_fencers) if fencers[i]["category"].upper() == "M")
            
            # Constraint 1F: If is_1f[t]=1 AND m_res_w[t, w_res]=1 => main_is_female[t, w_res] MUST BE 0.
            solver.Add(m_res_w + main_is_female_vars[w_res] <= 2 - is_1f[t])
            
            # Constraint 2F: If is_2f[t]=1 AND m_res_w[t, w_res]=1 => main_is_female[t, w_res] MUST BE 1.
            solver.Add(m_res_w <= main_is_female_vars[w_res] + (1 - is_2f[t]))

    # --- Objective Function ---
    # Maximize sum of scores.
    # Scores: prefs[w] (1-5).
    # "Minimize" for 3M teams -> Contribution = -Score?
    # Or Weight * -Score.

    obj_expr = 0

    # Penalties/Bonuses constants
    P_3M = 1000 # Penalty for 3M team (try to avoid)
    P_3F = 500  # Penalty for 3F team ("unless strictly necessary")
    B_Res_2F = 200 # Bonus for assigning reserve to 2F team

    # Small perturbation range for tie-breaking (much smaller than preference scores)
    # This ensures different seeds explore different equally-optimal solutions
    PERTURBATION_SCALE = 0.01

    # Pre-generate perturbations for each (fencer, team, weapon, role) combination
    # This ensures reproducibility with the same seed
    perturbations = {}
    for i in range(n_fencers):
        for t in range(n_teams):
            for w in range(n_weapons):
                for r in range(2):
                    perturbations[i, t, w, r] = rng.uniform(-PERTURBATION_SCALE, PERTURBATION_SCALE)

    # Let valid_score(i, w) be fencer i's pref for w.
    def get_score(i, w):
        p = fencers[i]["preference"]
        w_name = weapons[w]
        return p.get(w_name, 1)

    for t in range(n_teams):
        # Add Team-level penalties
        obj_expr -= P_3M * is_3m[t]
        obj_expr -= P_3F * is_3f[t]
        
        # Add Bonus for 2F if it has a reserve
        res_sum = solver.Sum(x[i, t, w, 1] for i in range(n_fencers) for w in range(n_weapons))
        is_2f_res = solver.BoolVar(f"is_2f_res_{t}")
        # Linearize: is_2f_res <= is_2f
        solver.Add(is_2f_res <= is_2f[t])
        # is_2f_res <= res_sum  (binary <= sum? if sum>1? sum is constrained <=1 from earlier).
        solver.Add(is_2f_res <= res_sum)
        # is_2f_res >= is_2f + res_sum - 1
        solver.Add(is_2f_res >= is_2f[t] + res_sum - 1)
        
        obj_expr += B_Res_2F * is_2f_res
        
        # Individual Assignment Scores
        for i in range(n_fencers):
            for w in range(n_weapons):
                for r in range(2): # Main and Reserve
                    score = get_score(i, w)
                    # Add small random perturbation for tie-breaking
                    perturbed_score = score + perturbations[i, t, w, r]

                    # We want:
                    # If is_3m[t] is 0: + score * x
                    # If is_3m[t] is 1: - score * x  (Minimizing preference = Maximizing negative preference)

                    # Let z[i,t,w,r] = x[i,t,w,r] AND is_3m[t]
                    z = solver.BoolVar(f"z_{i}_{t}_{w}_{r}")
                    solver.Add(z <= x[i, t, w, r])
                    solver.Add(z <= is_3m[t])
                    solver.Add(z >= x[i, t, w, r] + is_3m[t] - 1)

                    # Term = score * (x - z)  +  (-score) * z
                    #      = score * x - score * z - score * z
                    #      = score * x - 2 * score * z

                    # Note: For reserves on 3M, constraint ban means x=0, so z=0. Term 0. Correct.

                    obj_expr += perturbed_score * x[i, t, w, r]
                    obj_expr -= 2 * perturbed_score * z

    solver.Maximize(obj_expr)

    # --- Solve ---
    status = solver.Solve()
    
    if status not in [pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE]:
        return {"error": "No solution found"}

    # --- Extract Results ---
    teams_out = {}
    for t in range(n_teams):
        teams_out[t] = {"team": t+1, "members": {}, "reserves": []} # 1-indexed team ID
    
    for t in range(n_teams):
        for i in range(n_fencers):
            for w in range(n_weapons):
                if x[i, t, w, 0].solution_value() > 0.5: # Main
                    teams_out[t]["members"][weapons[w]] = {
                        "name": fencers[i]["name"],
                        "category": fencers[i]["category"],
                        "preference": get_score(i, w) # Return scalar score
                    }
                if x[i, t, w, 1].solution_value() > 0.5: # Reserve
                    # For reserve, we include the assigned weapon
                    r_data = fencers[i].copy()
                    r_data["weapon"] = weapons[w]
                    r_data["preference"] = fencers[i]["preference"] # Keep dict
                    teams_out[t]["reserves"].append(r_data)
                    
    # Format output list
    result_list = [teams_out[t] for t in range(n_teams)]
    return {"teams": result_list}

@app.route('/solve', methods=['POST'])
def solve_endpoint():
    data = request.get_json()
    if not data or "fencers" not in data:
        return jsonify({"error": "Invalid input"}), 400

    # Optional seed parameter for reproducible but varied solutions
    seed = data.get("seed", None)

    result = solve_holistic(data["fencers"], seed=seed)
    return jsonify(result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
