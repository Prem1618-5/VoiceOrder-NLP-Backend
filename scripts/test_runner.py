import argparse
import json
import os
import sys

from app.nlp.pipeline import extract_entities, load_model

def run_tests(test_file, start_idx, end_idx):
    with open(test_file, "r") as f:
        cases = json.load(f)
        
    slice_cases = cases[start_idx:end_idx]
    print(f"Running {len(slice_cases)} test cases (from index {start_idx} to {end_idx-1})...")
    
    # Pre-load model to avoid loading overhead in timing
    load_model()
    
    passed = 0
    failed = 0
    
    for i, case in enumerate(slice_cases):
        text = case["text"]
        expected = case["expected_items"]
        
        try:
            result = extract_entities(text)
        except Exception as e:
            print(f"FAIL [Exception] Case {start_idx+i}: {text}")
            print(f"  Error: {str(e)}")
            failed += 1
            continue
            
        # Convert result items to match expected dicts for easy comparison
        # Only compare name, quantity, size, modifiers
        actual = []
        for item in result.items:
            actual.append({
                "name": item.name,
                "quantity": item.quantity,
                "size": item.size,
                # Convert list of modifiers to set to ignore order
                "modifiers": sorted(item.modifiers)
            })
            
        expected_normalized = []
        for e_item in expected:
            expected_normalized.append({
                "name": e_item["name"],
                "quantity": e_item["quantity"],
                "size": e_item["size"],
                "modifiers": sorted(e_item["modifiers"])
            })
            
        # Sort both lists by name to ignore order of items
        actual = sorted(actual, key=lambda x: x["name"])
        expected_normalized = sorted(expected_normalized, key=lambda x: x["name"])
        
        if actual == expected_normalized:
            print(f"PASS Case {start_idx+i}: {text}")
            passed += 1
        else:
            print(f"FAIL Case {start_idx+i}: {text}")
            print(f"  Expected: {expected_normalized}")
            print(f"  Actual:   {actual}")
            failed += 1
            
    print(f"\nSummary: {passed} passed, {failed} failed.")
    if failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, help="Path to test cases JSON file")
    parser.add_argument("--start", type=int, default=0, help="Start index")
    parser.add_argument("--end", type=int, default=1000, help="End index (exclusive)")
    args = parser.parse_args()
    
    run_tests(args.file, args.start, args.end)
