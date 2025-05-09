import pandas as pd
from pulp import LpProblem, LpMinimize, LpVariable, lpSum, PULP_CBC_CMD, LpStatus
from datetime import datetime
import time

def run_optimization(demand_path, nurses_path):
    """Run the nurse scheduling optimization"""
    print("Loading data...")
    demand = pd.read_excel(demand_path)
    nurses = pd.read_excel(nurses_path)
    
    # Convert and validate dates
    demand['date'] = pd.to_datetime(demand['date'])
    demand = demand.sort_values('date')
    
    # Get date range
    start_date = demand['date'].min().strftime('%Y-%m-%d')
    end_date = demand['date'].max().strftime('%Y-%m-%d')
    print(f"Scheduling period: {start_date} to {end_date}")
    
    # Extract unique values
    dates = demand['date'].unique()
    units = demand['unit'].unique()
    shifts = demand['shift'].unique()
    nurse_ids = nurses['nurse_id'].unique()
    
    print(f"Problem dimensions - Nurses: {len(nurse_ids)}, Dates: {len(dates)}, Shifts: {len(shifts)}")
    
    # Create the problem
    prob = LpProblem("Nurse_Scheduling", LpMinimize)
    
    # Decision variables
    x = LpVariable.dicts(
        "assignment",
        [(nurse_id, str(date), shift, unit)
         for nurse_id in nurse_ids
         for date in dates
         for shift in shifts
         for unit in [nurses[nurses['nurse_id'] == nurse_id]['unit'].values[0]]],
        cat='Binary'
    )
    
    # Understaffing variables
    under_staff = LpVariable.dicts(
        "under_staff",
        [(str(date), unit, shift) for date in dates for unit in units for shift in shifts],
        lowBound=0
    )
    
    # Objective: Minimize understaffing
    prob += lpSum(1000 * under_staff[(str(date), unit, shift)] 
                 for date in dates for unit in units for shift in shifts)
    
    print("Adding constraints...")
    # Demand coverage constraints
    for date in dates:
        for unit in units:
            for shift in shifts:
                req = demand[
                    (demand['date'] == date) & 
                    (demand['unit'] == unit) & 
                    (demand['shift'] == shift)
                ]['required_RN'].values[0]
                
                prob += (
                    lpSum(x[(nurse_id, str(date), shift, unit)]
                         for nurse_id in nurse_ids
                         if nurses[nurses['nurse_id'] == nurse_id]['unit'].values[0] == unit) +
                    under_staff[(str(date), unit, shift)] >= req
                )
    
    # No double shifts
    for nurse_id in nurse_ids:
        for date in dates:
            prob += lpSum(
                x[(nurse_id, str(date), shift, unit)]
                for shift in shifts
                for unit in [nurses[nurses['nurse_id'] == nurse_id]['unit'].values[0]]
            ) <= 1
    
    print("Solving...")
    start_time = time.time()
    prob.solve(PULP_CBC_CMD(msg=True))
    solve_time = time.time() - start_time
    print(f"Solved in {solve_time:.2f} seconds")
    
    if LpStatus[prob.status] != "Optimal":
        raise ValueError(f"No optimal solution found. Status: {LpStatus[prob.status]}")
    
    # Extract solution
    schedule = []
    for (nurse_id, date, shift, unit), var in x.items():
        if var.varValue == 1:
            nurse_skills = nurses[nurses['nurse_id'] == nurse_id]['skills'].values[0]
            schedule.append({
                'nurse_id': nurse_id,
                'date': date,
                'shift': shift,
                'unit': unit,
                'skills': nurse_skills,
                'period_start': start_date,
                'period_end': end_date
            })
    
    schedule_df = pd.DataFrame(schedule)
    
    # Calculate metrics
    total_required = demand['required_RN'].sum()
    total_assigned = len(schedule_df)
    understaffed = sum(under_staff[var].varValue > 0 for var in under_staff)
    
    metrics = {
        'total_assigned': total_assigned,
        'understaffed': understaffed,
        'coverage_percentage': (total_assigned / total_required) * 100 if total_required > 0 else 0
    }
    
    print(f"Results - Assigned: {total_assigned}, Understaffed: {understaffed}, Coverage: {metrics['coverage_percentage']:.1f}%")
    return schedule_df, metrics