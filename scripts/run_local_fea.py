#!/usr/bin/env python3
"""
================================================================================
LOCAL FEA RUNNER — Runs CalculiX simulations locally on macOS
================================================================================

This script uses the existing Genesis generator (from Desktop/euv) to create
CalculiX input decks and runs them locally. It handles:

1. Mesh convergence study (C3D8, N=25,30,40,50,70)
2. Material Monte Carlo (InP, GaN, AlN — 20 cases each)
3. Result extraction and JSON output

Requirements:
    - CalculiX (ccx) installed: brew install calculix-ccx or conda
    - Python packages: numpy, scipy, jinja2

Usage:
    python3 scripts/run_local_fea.py --mesh-convergence
    python3 scripts/run_local_fea.py --material-mc
    python3 scripts/run_local_fea.py --all

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

# Add the external euv scripts to path so we can use the real generator
EUV_SCRIPTS = Path("/Users/nharris/Desktop/euv/scripts")
EUV_TEMPLATES = Path("/Users/nharris/Desktop/euv/templates")
sys.path.insert(0, str(EUV_SCRIPTS))

from generator import render_case

# Output directory for local runs
LOCAL_WORK_DIR = Path(__file__).parent.parent / "local_runs"
LOCAL_RESULTS_DIR = Path(__file__).parent.parent / "04_DATA" / "local_verified"

def find_ccx():
    """Find CalculiX executable."""
    # Check common locations
    candidates = [
        "ccx",
        "/opt/homebrew/bin/ccx",
        "/opt/homebrew/Caskroom/mambaforge/base/bin/ccx",
        "/usr/local/bin/ccx",
    ]
    for c in candidates:
        try:
            result = subprocess.run([c, "-v"], capture_output=True, text=True, timeout=10)
            if "Version" in result.stdout or "Version" in result.stderr:
                print(f"  Found CalculiX: {c}")
                return c
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    raise RuntimeError("CalculiX (ccx) not found! Install with: brew install calculix-ccx")


def extract_warpage(case_dir_path):
    """
    Extract peak-to-valley warpage (W_pv) from CalculiX .dat output file.
    
    The .dat file contains nodal displacements in the format:
        node_id  Ux  Uy  Uz
    
    We parse ALL displacement lines after the 'displacements' header,
    extract Uz, and compute peak-to-valley warpage.
    """
    # Find the .dat file
    case_dir = Path(case_dir_path) if not isinstance(case_dir_path, Path) else case_dir_path
    if case_dir.is_file():
        case_dir = case_dir.parent
    
    dat_files = list(case_dir.glob("*.dat"))
    if not dat_files:
        return None
    
    dat_path = dat_files[0]
    
    displacements = []
    reading = False
    
    with open(dat_path, 'r') as f:
        for line in f:
            if 'displacements' in line.lower():
                reading = True
                continue
            if reading:
                parts = line.strip().split()
                if len(parts) == 4:
                    try:
                        nid = int(parts[0])
                        ux = float(parts[1])
                        uy = float(parts[2])
                        uz = float(parts[3])
                        displacements.append(uz)
                    except ValueError:
                        pass
                elif len(parts) == 0 or 'total' in line.lower() or 'step' in line.lower():
                    if displacements:
                        break
    
    if not displacements:
        return None
    
    z_arr = np.array(displacements)
    w_pv = (np.max(z_arr) - np.min(z_arr)) * 1e9  # Convert m to nm
    w_max = np.max(np.abs(z_arr)) * 1e9
    
    return {
        "W_pv_nm": w_pv,
        "W_exposure_max_nm": w_max,
        "n_nodes_read": len(displacements),
        "U3_max_m": float(np.max(z_arr)),
        "U3_min_m": float(np.min(z_arr)),
    }


def run_single_case(case_id, ccx_path, work_dir, templates_dir, **params):
    """
    Generate input deck, run CalculiX, and extract results for a single case.
    
    Returns dict with results or None on failure.
    """
    case_dir = work_dir / case_id
    
    print(f"  [{case_id}] Generating mesh...", end=" ", flush=True)
    
    # Generate the input deck using the real generator
    try:
        render_case(
            case_name=case_id,
            output_dir=str(case_dir),
            templates_dir=str(templates_dir),
            **params
        )
    except Exception as e:
        print(f"FAILED (generator: {e})")
        return None
    
    # Find the main input file
    inp_file = case_dir / f"{case_id}.inp"
    if not inp_file.exists():
        # Try to find any .inp file
        inp_files = list(case_dir.glob("*.inp"))
        # Filter out included files (nodes.inp, elements.inp, etc.)
        main_inp = [f for f in inp_files if f.name not in ("nodes.inp", "elements.inp", "materials.inp", "supports.inp", "loads.inp")]
        if main_inp:
            inp_file = main_inp[0]
        else:
            print(f"FAILED (no input file)")
            return None
    
    # Count nodes for reporting
    nodes_file = case_dir / "nodes.inp"
    node_count = 0
    if nodes_file.exists():
        with open(nodes_file) as f:
            node_count = sum(1 for line in f if not line.startswith("*")) 
    
    print(f"({node_count} nodes) Running CCX...", end=" ", flush=True)
    
    # Run CalculiX
    start_time = time.time()
    try:
        result = subprocess.run(
            [ccx_path, "-i", str(inp_file.stem)],
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
            cwd=str(case_dir)
        )
        elapsed = time.time() - start_time
    except subprocess.TimeoutExpired:
        print(f"TIMEOUT (>600s)")
        return None
    except Exception as e:
        print(f"FAILED (run: {e})")
        return None
    
    # Check for solver errors
    if result.returncode != 0 and "error" in result.stderr.lower():
        print(f"SOLVER ERROR ({elapsed:.1f}s)")
        # Save error log
        with open(case_dir / "error.log", 'w') as f:
            f.write(result.stdout + "\n" + result.stderr)
        return None
    
    # Extract results from .dat file (more reliable than .frd parsing)
    warpage = extract_warpage(case_dir)
    if warpage is None:
        print(f"PARSE FAILED ({elapsed:.1f}s)")
        return None
    
    print(f"W_pv={warpage['W_pv_nm']:.1f} nm ({elapsed:.1f}s)")
    
    return {
        "case_id": case_id,
        "W_pv_nm": warpage["W_pv_nm"],
        "W_exposure_max_nm": warpage["W_exposure_max_nm"],
        "node_count": node_count,
        "solver_time_s": round(elapsed, 1),
        "solver": "CalculiX 2.23 (local)",
        "machine": "Apple Silicon (local)",
        "timestamp": datetime.now().isoformat(),
        **{k: v for k, v in params.items() if k not in ("stiffness",)},
    }


def run_mesh_convergence(ccx_path):
    """
    Run mesh convergence study with C3D8 elements at k_azi=0.5.
    Tests N=25, 30, 40, 50, 70 (and 100 if feasible).
    """
    print("\n" + "="*80)
    print("🔬 MESH CONVERGENCE STUDY (C3D8 Solid Elements)")
    print("="*80)
    print(f"Element: C3D8 (8-node hex, 3 layers through thickness)")
    print(f"Material: Silicon (E=130GPa, CTE=2.6e-6)")
    print(f"k_azi: 0.5 (stable zone)")
    print(f"Load: scan pattern")
    print("="*80)
    
    work_dir = LOCAL_WORK_DIR / "mesh_convergence"
    work_dir.mkdir(parents=True, exist_ok=True)
    
    results = []
    
    # Test mesh densities — start small to verify, then go larger
    for n_radial in [25, 30, 40, 50, 70]:
        case_id = f"mesh_c3d8_n{n_radial}_kazi0p5"
        
        result = run_single_case(
            case_id=case_id,
            ccx_path=ccx_path,
            work_dir=work_dir,
            templates_dir=EUV_TEMPLATES,
            pattern="parametric",
            load="scan",
            stiffness=1.5e5,
            n_radial=n_radial,
            element_type="C3D8",
            n_layers=3,
            k_edge=2.0,
            k_azi=0.5,
            pitch=0.005,
            rho_0=1.0,
            r_trans=0.13,
            support_profile="density_scaled",
        )
        
        if result:
            results.append(result)
    
    # Compute convergence metrics
    if len(results) >= 2:
        print("\n" + "-"*60)
        print("CONVERGENCE ANALYSIS:")
        print("-"*60)
        print(f"{'N':>6} {'Nodes':>10} {'W_pv (nm)':>12} {'Change':>10} {'Time':>8}")
        print("-"*60)
        
        for i, r in enumerate(results):
            change = ""
            if i > 0:
                prev = results[i-1]["W_pv_nm"]
                curr = r["W_pv_nm"]
                pct = (curr - prev) / prev * 100
                change = f"{pct:+.1f}%"
            print(f"{r.get('n_radial', '?'):>6} {r['node_count']:>10} {r['W_pv_nm']:>12.1f} {change:>10} {r['solver_time_s']:>7.1f}s")
        
        # Check if last two are within 5%
        if len(results) >= 2:
            last_change = abs(results[-1]["W_pv_nm"] - results[-2]["W_pv_nm"]) / results[-2]["W_pv_nm"] * 100
            if last_change < 5:
                print(f"\n✅ CONVERGED: Last refinement changed by {last_change:.1f}% (< 5% threshold)")
            else:
                print(f"\n⚠️  NOT YET CONVERGED: Last refinement changed by {last_change:.1f}% (> 5% threshold)")
    
    # Save results
    output_file = LOCAL_RESULTS_DIR / "mesh_convergence_c3d8_local.json"
    LOCAL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    
    output = {
        "study": "Mesh Convergence (C3D8 Solid Elements)",
        "timestamp": datetime.now().isoformat(),
        "solver": "CalculiX 2.23 (local, Apple Silicon)",
        "element_type": "C3D8",
        "material": "silicon",
        "k_azi": 0.5,
        "load": "scan",
        "cases": results,
    }
    
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n📁 Results saved: {output_file}")
    return results


def run_material_monte_carlo(ccx_path):
    """
    Run Monte Carlo for InP, GaN, AlN materials.
    20 cases per material at k_azi=0.5 and k_azi=0.8 with manufacturing tolerances.
    """
    print("\n" + "="*80)
    print("🧪 MATERIAL MONTE CARLO STUDY")
    print("="*80)
    
    work_dir = LOCAL_WORK_DIR / "material_mc"
    work_dir.mkdir(parents=True, exist_ok=True)
    
    all_results = {}
    
    for material in ["inp", "gan", "aln"]:
        for k_azi_base in [0.5, 0.8]:
            zone = "stable" if k_azi_base == 0.5 else "cliff"
            print(f"\n--- {material.upper()} @ k_azi={k_azi_base} ({zone}) ---")
            
            results = []
            rng = np.random.default_rng(42)
            
            for seed in range(20):
                # Apply ±5% manufacturing tolerances
                k_azi_perturbed = k_azi_base * (1 + 0.05 * (2 * rng.random() - 1))
                stiffness_scale = 1.0 + 0.05 * (2 * rng.random() - 1)
                bow = rng.uniform(-5e-6, 5e-6)  # ±5μm bow
                
                case_id = f"mc_{material}_k{str(k_azi_base).replace('.','p')}_seed{seed}"
                
                result = run_single_case(
                    case_id=case_id,
                    ccx_path=ccx_path,
                    work_dir=work_dir,
                    templates_dir=EUV_TEMPLATES,
                    pattern="parametric",
                    load="scan",
                    stiffness=1.5e5 * stiffness_scale,
                    n_radial=50,
                    element_type="C3D8",
                    n_layers=3,
                    k_edge=2.0,
                    k_azi=k_azi_perturbed,
                    pitch=0.005,
                    rho_0=1.0,
                    r_trans=0.13,
                    material=material,
                    bow=bow,
                    support_profile="density_scaled",
                    seed=seed,
                    k_azi_base=k_azi_base,
                    stiffness_scale=stiffness_scale,
                    bow_um=bow * 1e6,
                )
                
                if result:
                    results.append(result)
            
            # Compute statistics
            if results:
                wpvs = [r["W_pv_nm"] for r in results]
                stats = {
                    "material": material,
                    "k_azi_base": k_azi_base,
                    "zone": zone,
                    "n_cases": len(results),
                    "mean_wpv_nm": float(np.mean(wpvs)),
                    "std_wpv_nm": float(np.std(wpvs, ddof=1)),
                    "cv_percent": float(np.std(wpvs, ddof=1) / np.mean(wpvs) * 100),
                    "min_wpv_nm": float(np.min(wpvs)),
                    "max_wpv_nm": float(np.max(wpvs)),
                }
                
                print(f"\n  STATS: Mean={stats['mean_wpv_nm']:.1f}nm, "
                      f"CV={stats['cv_percent']:.2f}%, "
                      f"Range=[{stats['min_wpv_nm']:.1f}, {stats['max_wpv_nm']:.1f}]")
                
                key = f"{material}_{zone}"
                all_results[key] = {"stats": stats, "cases": results}
    
    # Save all results
    output_file = LOCAL_RESULTS_DIR / "material_monte_carlo_local.json"
    LOCAL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\n📁 Results saved: {output_file}")
    return all_results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Local FEA Runner for Patent 1 Verification")
    parser.add_argument("--mesh-convergence", action="store_true", help="Run mesh convergence study")
    parser.add_argument("--material-mc", action="store_true", help="Run material Monte Carlo")
    parser.add_argument("--all", action="store_true", help="Run everything")
    parser.add_argument("--test", action="store_true", help="Quick test with tiny mesh (N=15)")
    
    args = parser.parse_args()
    
    if not any([args.mesh_convergence, args.material_mc, args.all, args.test]):
        parser.print_help()
        return
    
    print("\n" + "="*80)
    print("🔬 GENESIS PATENT 1 — LOCAL FEA VERIFICATION")
    print("="*80)
    print(f"Solver: CalculiX (local)")
    print(f"Generator: {EUV_SCRIPTS / 'generator.py'}")
    print(f"Templates: {EUV_TEMPLATES}")
    print(f"Work Dir: {LOCAL_WORK_DIR}")
    print("="*80)
    
    # Find CalculiX
    print("\nLocating CalculiX...")
    ccx_path = find_ccx()
    
    if args.test:
        print("\n--- QUICK TEST (N=15, ~5 seconds) ---")
        work_dir = LOCAL_WORK_DIR / "test"
        work_dir.mkdir(parents=True, exist_ok=True)
        result = run_single_case(
            case_id="test_n15",
            ccx_path=ccx_path,
            work_dir=work_dir,
            templates_dir=EUV_TEMPLATES,
            pattern="parametric",
            load="scan",
            stiffness=1.5e5,
            n_radial=15,
            element_type="C3D8",
            n_layers=3,
            k_edge=2.0,
            k_azi=0.5,
            pitch=0.010,
            rho_0=1.0,
            r_trans=0.13,
            support_profile="density_scaled",
        )
        if result:
            print(f"\n✅ TEST PASSED: W_pv = {result['W_pv_nm']:.1f} nm")
        else:
            print(f"\n❌ TEST FAILED — check error logs in {work_dir}")
        return
    
    if args.mesh_convergence or args.all:
        run_mesh_convergence(ccx_path)
    
    if args.material_mc or args.all:
        run_material_monte_carlo(ccx_path)
    
    print("\n" + "="*80)
    print("✅ ALL LOCAL FEA RUNS COMPLETE")
    print("="*80)


if __name__ == "__main__":
    main()
