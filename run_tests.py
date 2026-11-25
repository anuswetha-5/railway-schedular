#!/usr/bin/env python3
"""
Master Test Runner & Verification Suite for the Indian Railways AI Corridor Scheduler.
Executes all domain, security, efficiency, accessibility, and API test suites,
providing an executive verification report with performance telemetry.
"""

import os
import sys
import time
import unittest

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "database"))


def print_banner() -> None:
    """Prints the executive audit ASCII header and execution environment telemetry."""
    print("=" * 80)
    print("    INDIAN RAILWAYS AUTOMATIC BLOCK PLANNING SYSTEM (ABPS)")
    print("        COMPREHENSIVE TEST SUITE & PLATFORM VERIFICATION")
    print("=" * 80)
    print(f"  Execution Root: {BASE_DIR}")
    print(f"  Python Version: {sys.version.split()[0]}")
    print(f"  Timestamp:     {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()


def run_all_suites() -> int:
    """Executes all 5 verification dimensions and prints the executive test report."""
    print_banner()

    test_modules = [
        ("Domain Architecture & Core Engines", "tests.test_platform"),
        ("Security Policy & Threat Defenses", "tests.test_security"),
        ("REST API & Interoperability Endpoints", "tests.test_api_endpoints"),
        ("Performance & Query Speed Benchmarks", "tests.test_efficiency"),
        ("WCAG 2.1 Level AA Accessibility Standards", "tests.test_accessibility"),
    ]

    total_ran = 0
    total_failures = 0
    total_errors = 0
    total_time = 0.0
    suite_results = []

    for label, mod_name in test_modules:
        print(f"[*] Running: {label} [{mod_name}] ...")
        start_t = time.perf_counter()
        loader = unittest.TestLoader()
        try:
            suite = loader.loadTestsFromName(mod_name)
        except Exception as e:
            print(f"    [ERROR] Failed to import {mod_name}: {e}")
            total_errors += 1
            continue

        runner = unittest.TextTestRunner(verbosity=1, stream=sys.stdout)
        res = runner.run(suite)
        elapsed = time.perf_counter() - start_t
        total_time += elapsed

        n_ran = res.testsRun
        n_fail = len(res.failures)
        n_err = len(res.errors)

        total_ran += n_ran
        total_failures += n_fail
        total_errors += n_err

        status = "PASSED" if (n_fail == 0 and n_err == 0) else "FAILED"
        suite_results.append({
            "label": label,
            "tests": n_ran,
            "failures": n_fail,
            "errors": n_err,
            "time_ms": elapsed * 1000.0,
            "status": status,
        })
        print(f"    --> {status}: {n_ran} tests executed in {elapsed*1000.0:.1f}ms\n")

    print("=" * 80)
    print("                       EXECUTIVE TEST AUDIT REPORT")
    print("=" * 80)
    print(f"{'Verification Dimension':<42} | {'Tests':<6} | {'Status':<8} | {'Time (ms)':<9}")
    print("-" * 80)

    for r in suite_results:
        status_str = f"[OK] {r['status']}" if r["status"] == "PASSED" else f"[X] {r['status']}"
        print(f"{r['label']:<42} | {r['tests']:<6} | {status_str:<8} | {r['time_ms']:>8.1f}ms")

    print("-" * 80)
    print(f"{'TOTALS':<42} | {total_ran:<6} | {'ALL PASS' if (total_failures==0 and total_errors==0) else 'FAIL':<8} | {total_time*1000.0:>8.1f}ms")
    print("=" * 80)

    if total_failures == 0 and total_errors == 0:
        print("\n[SUCCESS] All 5 Quality Dimensions Fully Verified (100% Pass Rate).")
        print("          Platform is production-ready for Indian Railways deployment.\n")
        return 0
    else:
        print(f"\n[FAILURE] {total_failures} failures and {total_errors} errors detected across suites.\n")
        return 1


if __name__ == "__main__":
    exit_code = run_all_suites()
    sys.exit(exit_code)
