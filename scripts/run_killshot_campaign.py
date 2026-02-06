#!/usr/bin/env python3
"""
================================================================================
DESIGN-AROUND DESERT: COMPREHENSIVE KILL SHOT CAMPAIGN
================================================================================

This script runs a massive local FEA campaign to prove that EVERY alternative
approach to avoiding the Physics Cliff fails. The goal is to make the
design-around desert so deep and so well-mapped that a buyer's due diligence
team concludes: "There is no escape. We must license this."

Campaign Structure:
1. CLIFF MAPPING:      Map exact cliff shape with MC at 7 k_azi values (70 cases)
2. HARMONIC SWEEP MC:  Prove cliff at n=2,3,4,6 harmonics (40 cases)
3. SWEET SPOT B KILL:  Prove k_azi=1.3 is unmanufacturable (20 cases)
4. CROSS-LOAD:         Prove gradient_z and uniform loads hit same cliff (40 cases)
5. MORE MATERIALS:     SiC + GaAs close every escape route (40 cases)
6. SILICON CLIFF MC:   50 more chaos zone cases to match 100 stable (50 cases)

TOTAL: ~260 new verified FEA cases
ESTIMATED TIME: ~30 minutes on Apple Silicon

================================================================================
"""

import sys
import os
import json
import subprocess
import time
import numpy as np
from pathlib import Path
from datetime import datetime

# Add external generator
EUV_SCRIPTS = Path("/Users/nharris/Desktop/euv/scripts")
EUV_TEMPLATES = Path("/Users/nharris/Desktop/euv/templates")
sys.path.insert(0, str(EUV_SCRIPTS))
from generator import render_case

LOCAL_WORK_DIR = Path(__file__).parent.parent / "local_runs"
RESULTS_DIR = Path(__file__).parent.parent / "04_DATA" / "local_verified"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def find_ccx():
    """Find CalculiX executable."""
    for c in ["ccx", "/opt/homebrew/Caskroom/mambaforge/base/bin/ccx"]:
        try:
            result = subprocess.run([c, "-v"], capture_output=True, text=True, timeout=10)
            if "Version" in result.stdout or "Version" in result.stderr:
                return c
        except:
            continue
    raise RuntimeError("CalculiX not found")


def extract_warpage(case_dir):
    """Extract W_pv from CalculiX .dat file."""
    case_dir = Path(case_dir)
    dat_files = list(case_dir.glob("*.dat"))
    if not dat_files:
        return None
    
    displacements = []
    reading = False
    with open(dat_files[0]) as f:
        for line in f:
            if 'displacements' in line.lower():
                reading = True
                continue
            if reading:
                parts = line.strip().split()
                if len(parts) == 4:
                    try:
                        displacements.append(float(parts[3]))  # Uz
                    except ValueError:
                        pass
                elif len(parts) == 0 or 'total' in line.lower():
                    if displacements:
                        break
    
    if not displacements:
        return None
    
    arr = np.array(displacements)
    return {
        "W_pv_nm": (arr.max() - arr.min()) * 1e9,
        "W_exposure_max_nm": np.max(np.abs(arr)) * 1e9,
        "n_nodes": len(arr),
    }


def run_case(case_id, ccx, work_dir, **params):
    """Generate and run a single FEA case. Returns result dict or None."""
    case_dir = work_dir / case_id
    
    try:
        render_case(case_name=case_id, output_dir=str(case_dir),
                    templates_dir=str(EUV_TEMPLATES), **params)
    except Exception as e:
        print(f"    FAIL (gen): {e}")
        return None
    
    # Find input file
    inp_file = None
    for f in case_dir.glob("*.inp"):
        if f.name not in ("nodes.inp", "elements.inp", "materials.inp", "supports.inp", "loads.inp"):
            inp_file = f
            break
    if not inp_file:
        return None
    
    t0 = time.time()
    try:
        subprocess.run([ccx, "-i", inp_file.stem], capture_output=True, text=True,
                      timeout=120, cwd=str(case_dir))
    except:
        return None
    elapsed = time.time() - t0
    
    warpage = extract_warpage(case_dir)
    if not warpage:
        return None
    
    return {
        "case_id": case_id,
        "W_pv_nm": warpage["W_pv_nm"],
        "W_exposure_max_nm": warpage["W_exposure_max_nm"],
        "node_count": warpage["n_nodes"],
        "solver_time_s": round(elapsed, 1),
        "solver": "CalculiX 2.23 (local)",
        "timestamp": datetime.now().isoformat(),
        **{k: v for k, v in params.items() if isinstance(v, (int, float, str, bool))},
    }


def run_mc_batch(name, ccx, work_dir, n_cases, base_params, rng=None):
    """Run a Monte Carlo batch with ±5% manufacturing tolerances."""
    if rng is None:
        rng = np.random.default_rng(42)
    
    results = []
    for seed in range(n_cases):
        k_azi_base = base_params.get("k_azi", 0.5)
        k_azi_perturbed = k_azi_base * (1 + 0.05 * (2 * rng.random() - 1))
        stiffness_scale = 1.0 + 0.05 * (2 * rng.random() - 1)
        bow = rng.uniform(-5e-6, 5e-6)
        
        case_id = f"{name}_seed{seed}"
        params = {**base_params}
        params["k_azi"] = k_azi_perturbed
        params["stiffness"] = 1.5e5 * stiffness_scale
        params["bow"] = bow
        params["k_azi_base"] = k_azi_base
        params["seed"] = seed
        
        result = run_case(case_id, ccx, work_dir, **params)
        if result:
            results.append(result)
            print(f"    [{seed+1}/{n_cases}] W_pv={result['W_pv_nm']:.1f} nm")
    
    return results


def compute_stats(results):
    """Compute statistics from a list of results."""
    if not results:
        return {}
    wpvs = np.array([r["W_pv_nm"] for r in results])
    return {
        "n": len(wpvs),
        "mean": float(np.mean(wpvs)),
        "std": float(np.std(wpvs, ddof=1)) if len(wpvs) > 1 else 0,
        "cv_pct": float(np.std(wpvs, ddof=1) / np.mean(wpvs) * 100) if len(wpvs) > 1 else 0,
        "min": float(np.min(wpvs)),
        "max": float(np.max(wpvs)),
    }


# ============================================================================
# CAMPAIGN FUNCTIONS
# ============================================================================

def campaign_cliff_mapping(ccx):
    """Map the exact cliff shape with MC at multiple k_azi values."""
    print("\n" + "="*70)
    print("CAMPAIGN 1: CLIFF SHAPE MAPPING (Silicon, scan load)")
    print("="*70)
    
    work_dir = LOCAL_WORK_DIR / "cliff_mapping"
    work_dir.mkdir(parents=True, exist_ok=True)
    
    base = dict(pattern="parametric", load="scan", n_radial=50, element_type="C3D8",
                n_layers=3, k_edge=2.0, pitch=0.005, rho_0=1.0, r_trans=0.13,
                support_profile="density_scaled")
    
    all_results = {}
    rng = np.random.default_rng(123)
    
    for k_azi in [0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9]:
        print(f"\n  k_azi = {k_azi}:")
        params = {**base, "k_azi": k_azi}
        results = run_mc_batch(f"cliff_k{str(k_azi).replace('.','p')}", ccx, work_dir, 10, params, rng)
        stats = compute_stats(results)
        all_results[f"k_azi_{k_azi}"] = {"stats": stats, "cases": results}
        if stats:
            print(f"  -> Mean={stats['mean']:.1f}nm, CV={stats['cv_pct']:.2f}%, Range=[{stats['min']:.0f}-{stats['max']:.0f}]")
    
    with open(RESULTS_DIR / "cliff_mapping_local.json", 'w') as f:
        json.dump(all_results, f, indent=2)
    return all_results


def campaign_harmonic_sweep(ccx):
    """Prove cliff exists at all harmonic orders."""
    print("\n" + "="*70)
    print("CAMPAIGN 2: HARMONIC UNIVERSALITY (n=2,3,4,6 @ k_azi=0.5 and 0.8)")
    print("="*70)
    
    work_dir = LOCAL_WORK_DIR / "harmonic_sweep"
    work_dir.mkdir(parents=True, exist_ok=True)
    
    all_results = {}
    rng = np.random.default_rng(456)
    
    for n_harm in [2, 3, 4, 6]:
        for k_azi in [0.5, 0.8]:
            zone = "stable" if k_azi == 0.5 else "cliff"
            print(f"\n  Harmonic n={n_harm}, k_azi={k_azi} ({zone}):")
            
            base = dict(pattern="parametric", load="scan", n_radial=50, element_type="C3D8",
                        n_layers=3, k_edge=2.0, pitch=0.005, rho_0=1.0, r_trans=0.13,
                        support_profile="density_scaled", k_azi=k_azi, n_harmonic=n_harm)
            
            results = run_mc_batch(f"harm_n{n_harm}_k{str(k_azi).replace('.','p')}", ccx, work_dir, 5, base, rng)
            stats = compute_stats(results)
            key = f"n{n_harm}_{zone}"
            all_results[key] = {"stats": stats, "cases": results, "n_harmonic": n_harm, "k_azi": k_azi}
            if stats:
                print(f"  -> Mean={stats['mean']:.1f}nm, CV={stats['cv_pct']:.2f}%")
    
    with open(RESULTS_DIR / "harmonic_universality_local.json", 'w') as f:
        json.dump(all_results, f, indent=2)
    return all_results


def campaign_sweet_spot_b_kill(ccx):
    """Prove Sweet Spot B (k_azi=1.3) has unacceptable variance."""
    print("\n" + "="*70)
    print("CAMPAIGN 3: SWEET SPOT B KILL (k_azi=1.3, proving CV too high)")
    print("="*70)
    
    work_dir = LOCAL_WORK_DIR / "sweetspot_b"
    work_dir.mkdir(parents=True, exist_ok=True)
    
    base = dict(pattern="parametric", load="scan", n_radial=50, element_type="C3D8",
                n_layers=3, k_edge=2.0, pitch=0.005, rho_0=1.0, r_trans=0.13,
                support_profile="density_scaled", k_azi=1.3)
    
    rng = np.random.default_rng(789)
    results = run_mc_batch("ssb_k1p3", ccx, work_dir, 20, base, rng)
    stats = compute_stats(results)
    
    if stats:
        print(f"\n  Sweet Spot B: Mean={stats['mean']:.1f}nm, CV={stats['cv_pct']:.2f}%")
        if stats['cv_pct'] > 5:
            print(f"  ❌ CV={stats['cv_pct']:.1f}% EXCEEDS 5% manufacturing threshold")
            print(f"     Sweet Spot B is NOT a viable operating region")
        else:
            print(f"  ⚠️  CV={stats['cv_pct']:.1f}% — low variance but may be viable")
    
    output = {"stats": stats, "cases": results}
    with open(RESULTS_DIR / "sweetspot_b_kill_local.json", 'w') as f:
        json.dump(output, f, indent=2)
    return output


def campaign_crossload(ccx):
    """Prove all thermal load patterns hit the same cliff."""
    print("\n" + "="*70)
    print("CAMPAIGN 4: CROSS-LOAD VERIFICATION (gradient_z + uniform)")
    print("="*70)
    
    work_dir = LOCAL_WORK_DIR / "crossload"
    work_dir.mkdir(parents=True, exist_ok=True)
    
    all_results = {}
    rng = np.random.default_rng(101)
    
    for load_type in ["gradient_z", "uniform"]:
        for k_azi in [0.5, 0.8]:
            zone = "stable" if k_azi == 0.5 else "cliff"
            print(f"\n  Load={load_type}, k_azi={k_azi} ({zone}):")
            
            base = dict(pattern="parametric", load=load_type, n_radial=50, element_type="C3D8",
                        n_layers=3, k_edge=2.0, pitch=0.005, rho_0=1.0, r_trans=0.13,
                        support_profile="density_scaled", k_azi=k_azi)
            
            results = run_mc_batch(f"xload_{load_type}_k{str(k_azi).replace('.','p')}", ccx, work_dir, 10, base, rng)
            stats = compute_stats(results)
            key = f"{load_type}_{zone}"
            all_results[key] = {"stats": stats, "cases": results}
            if stats:
                print(f"  -> Mean={stats['mean']:.1f}nm, CV={stats['cv_pct']:.2f}%")
    
    with open(RESULTS_DIR / "crossload_verification_local.json", 'w') as f:
        json.dump(all_results, f, indent=2)
    return all_results


def campaign_more_materials(ccx):
    """Close SiC and GaAs escape routes."""
    print("\n" + "="*70)
    print("CAMPAIGN 5: ADDITIONAL MATERIALS (SiC + GaAs)")
    print("="*70)
    
    work_dir = LOCAL_WORK_DIR / "more_materials"
    work_dir.mkdir(parents=True, exist_ok=True)
    
    all_results = {}
    rng = np.random.default_rng(202)
    
    for material in ["sic", "gaas"]:
        for k_azi in [0.5, 0.8]:
            zone = "stable" if k_azi == 0.5 else "cliff"
            print(f"\n  {material.upper()} @ k_azi={k_azi} ({zone}):")
            
            base = dict(pattern="parametric", load="scan", n_radial=50, element_type="C3D8",
                        n_layers=3, k_edge=2.0, pitch=0.005, rho_0=1.0, r_trans=0.13,
                        support_profile="density_scaled", k_azi=k_azi, material=material)
            
            results = run_mc_batch(f"mat_{material}_k{str(k_azi).replace('.','p')}", ccx, work_dir, 10, base, rng)
            stats = compute_stats(results)
            key = f"{material}_{zone}"
            all_results[key] = {"stats": stats, "cases": results}
            if stats:
                print(f"  -> Mean={stats['mean']:.1f}nm, CV={stats['cv_pct']:.2f}%")
    
    with open(RESULTS_DIR / "additional_materials_local.json", 'w') as f:
        json.dump(all_results, f, indent=2)
    return all_results


def campaign_silicon_cliff_mc(ccx):
    """Run 50 more Silicon chaos zone MC cases."""
    print("\n" + "="*70)
    print("CAMPAIGN 6: SILICON CHAOS ZONE MC (50 additional cases at k_azi=0.8)")
    print("="*70)
    
    work_dir = LOCAL_WORK_DIR / "silicon_cliff_mc"
    work_dir.mkdir(parents=True, exist_ok=True)
    
    base = dict(pattern="parametric", load="scan", n_radial=50, element_type="C3D8",
                n_layers=3, k_edge=2.0, pitch=0.005, rho_0=1.0, r_trans=0.13,
                support_profile="density_scaled", k_azi=0.8)
    
    rng = np.random.default_rng(303)
    results = run_mc_batch("si_cliff", ccx, work_dir, 50, base, rng)
    stats = compute_stats(results)
    
    if stats:
        print(f"\n  Silicon Cliff MC: Mean={stats['mean']:.1f}nm, CV={stats['cv_pct']:.2f}%")
    
    output = {"stats": stats, "cases": results}
    with open(RESULTS_DIR / "silicon_cliff_mc_local.json", 'w') as f:
        json.dump(output, f, indent=2)
    return output


# ============================================================================
# MAIN
# ============================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Design-Around Desert Kill Shot Campaign")
    parser.add_argument("--campaign", type=int, default=0, help="Run specific campaign (1-6) or 0 for all")
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("🎯 DESIGN-AROUND DESERT: KILL SHOT CAMPAIGN")
    print("="*70)
    
    ccx = find_ccx()
    print(f"Solver: {ccx}")
    print(f"Output: {RESULTS_DIR}")
    
    campaigns = {
        1: ("Cliff Mapping", campaign_cliff_mapping),
        2: ("Harmonic Universality", campaign_harmonic_sweep),
        3: ("Sweet Spot B Kill", campaign_sweet_spot_b_kill),
        4: ("Cross-Load Verification", campaign_crossload),
        5: ("Additional Materials", campaign_more_materials),
        6: ("Silicon Cliff MC", campaign_silicon_cliff_mc),
    }
    
    if args.campaign > 0:
        name, func = campaigns[args.campaign]
        print(f"\nRunning Campaign {args.campaign}: {name}")
        func(ccx)
    else:
        for num, (name, func) in campaigns.items():
            print(f"\n{'='*70}")
            print(f"Campaign {num}/6: {name}")
            print(f"{'='*70}")
            func(ccx)
    
    print("\n" + "="*70)
    print("✅ KILL SHOT CAMPAIGN COMPLETE")
    print(f"Results in: {RESULTS_DIR}")
    print("="*70)


if __name__ == "__main__":
    main()
