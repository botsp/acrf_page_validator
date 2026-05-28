#!/usr/bin/env python
"""
Verification tests for PyMuPDF Parser v2.1 improvements
"""

from modules.pymupdf_parser import (
    extract_candidates, classify_term, parse_supp_variable,
    extract_not_submitted_entries
)

def test_suite():
    print('='*60)
    print('FINAL VERIFICATION TEST: PyMuPDF Parser v2.1')
    print('='*60)
    print()
    
    tests_passed = 0
    tests_total = 0
    
    # Test 1: Issue 3 - Exact match priority
    tests_total += 1
    print('Test 1: Issue 3 - Exact match priority')
    standard_terms = {'variable': {'DSTERM', 'VSDTC'}, 'dataset': {'VS', 'LB'}}
    cat, flag = classify_term('DSTERM', 'DSTERM value', standard_terms, {}, set())
    if cat == 'standard_variable' and flag == 'exact_match':
        print('  ✓ PASS: DSTERM marked as standard_variable/exact_match')
        tests_passed += 1
    else:
        print(f'  ✗ FAIL: Got {cat}/{flag}')
    print()
    
    # Test 2: Issue 5 - RawTexts preservation
    tests_total += 1
    print('Test 2: Issue 5 - RawTexts preservation (full text)')
    text = 'ACNDD in SUPPAE for temperature control'
    candidates = extract_candidates(text)
    if 'ACNDD' in candidates and 'SUPPAE' in candidates:
        print('  ✓ PASS: Full extraction without truncation')
        tests_passed += 1
    else:
        print(f'  ✗ FAIL: Got {candidates}')
    print()
    
    # Test 3: Issue 6 - SUPP variable dataset extraction
    tests_total += 1
    print('Test 3: Issue 6 - SUPP variable dataset extraction')
    cat, flag = classify_term('SUPPAE', 'AEPTRTPT in SUPPAE', {}, {}, set())
    if cat == 'SUPPAE' and flag == 'supp_match':
        print('  ✓ PASS: SUPPAE extracted as category')
        tests_passed += 1
    else:
        print(f'  ✗ FAIL: Got {cat}/{flag}')
    print()
    
    # Test 4: Issue 4/8 - Conservative extraction
    tests_total += 1
    print('Test 4: Issue 4/8 - Conservative candidate extraction')
    text = 'DDORRE is wrong. DDORRES is correct. A is too short.'
    candidates = extract_candidates(text)
    has_ddorre = 'DDORRE' in candidates
    has_ddorres = 'DDORRES' in candidates
    no_single_a = 'A' not in candidates  # Single letter should not be extracted
    if has_ddorre and has_ddorres and no_single_a:
        print('  ✓ PASS: Correct filtering (DDORRE, DDORRES extracted, single letters rejected)')
        tests_passed += 1
    else:
        print(f'  ✗ FAIL: Got {sorted(candidates)}')
    print()
    
    # Test 5: NOT SUBMITTED handling
    tests_total += 1
    print('Test 5: NOT SUBMITTED case-insensitive count')
    text_ns = 'Not Submitted on page and NOT SUBMITTED'
    entries = extract_not_submitted_entries(text_ns, 10)
    if entries and entries[0].get('Count') >= 1:
        print(f'  ✓ PASS: Found NOT SUBMITTED entries')
        tests_passed += 1
    else:
        print(f'  ✗ FAIL: Got {entries}')
    print()
    
    # Test 6: SUPP pair parsing
    tests_total += 1
    print('Test 6: SUPP variable pair parsing')
    text_supp = 'AEPTRTPT in SUPPAE and SUPPFAQ.QNAM'
    pairs = parse_supp_variable(text_supp)
    if len(pairs) >= 2:
        print(f'  ✓ PASS: Found {len(pairs)} SUPP pairs')
        tests_passed += 1
    else:
        print(f'  ✗ FAIL: Got {pairs}')
    print()
    
    # Test 7: Priority escalation
    tests_total += 1
    print('Test 7: Classification priority escalation')
    # First classify as unknown, then re-classify as exact match
    cat1, flag1 = classify_term('TEST', 'test data', {}, {}, set())
    cat2, flag2 = classify_term('TEST', 'test data', {'variable': {'TEST'}}, {}, set())
    if flag1 == 'potential_nonstandard' and flag2 == 'exact_match':
        print('  ✓ PASS: Priority properly escalates from unknown to exact_match')
        tests_passed += 1
    else:
        print(f'  ✗ FAIL: Got flag1={flag1}, flag2={flag2}')
    print()
    
    # Summary
    print('='*60)
    print(f'RESULTS: {tests_passed}/{tests_total} tests passed')
    if tests_passed == tests_total:
        print('✅ All verification tests passed!')
        return 0
    else:
        print(f'⚠️  {tests_total - tests_passed} test(s) failed')
        return 1
    print('='*60)

if __name__ == '__main__':
    exit(test_suite())
