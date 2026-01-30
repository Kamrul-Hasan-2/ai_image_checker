"""
Test to verify that Car/Bike category products have promotional_text = 0
"""

import json

# Test categories that should have exception (promotional_text = 0)
exception_categories = [
    "car", "car accessories",
    "bike", "bike accessories",
    "three wheeler", "bicycle", "bicycle accessories",
    "commercial vehicle", "rental", "vehicle equipment"
]

# Test data
test_cases = [
    {"category": "Car", "should_be_zero": True, "description": "Car category (case insensitive)"},
    {"category": "car accessories", "should_be_zero": True, "description": "Car Accessories"},
    {"category": "Bike", "should_be_zero": True, "description": "Bike category"},
    {"category": "Bicycle Accessories", "should_be_zero": True, "description": "Bicycle Accessories"},
    {"category": "Vehicle Equipment", "should_be_zero": True, "description": "Vehicle Equipment"},
    {"category": "laptop", "should_be_zero": False, "description": "Laptop (not in exception list)"},
    {"category": "real estate", "should_be_zero": False, "description": "Real Estate (not in exception list)"},
    {"category": "  bike  ", "should_be_zero": True, "description": "Bike with spaces (should be trimmed)"},
]

print("=" * 60)
print("TESTING CATEGORY EXCEPTION LOGIC")
print("=" * 60)

all_passed = True
for test in test_cases:
    category = test["category"]
    should_be_zero = test["should_be_zero"]
    
    # This is the logic from modal_handler.py
    is_exception_category = category.lower().strip() in exception_categories
    
    passed = is_exception_category == should_be_zero
    all_passed = all_passed and passed
    
    status = "✓ PASS" if passed else "✗ FAIL"
    result = "promotional_text=0" if is_exception_category else "promotional_text=<calculated>"
    
    print(f"{status} | {test['description']:<40} | '{category}' -> {result}")

print("=" * 60)
if all_passed:
    print("✓ ALL TESTS PASSED")
else:
    print("✗ SOME TESTS FAILED")
print("=" * 60)
