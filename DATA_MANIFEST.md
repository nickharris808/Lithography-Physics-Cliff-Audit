# DATA PROVENANCE MANIFEST

## Cryptographic Verification of Simulation Data

This manifest provides SHA-256 cryptographic hashes for all raw simulation data files included in this repository. These hashes enable independent verification that the data has not been modified since the original analysis.

**Verification Command:**
```bash
cd 04_DATA/raw
sha256sum -c ../DATA_MANIFEST.sha256
```

---

## Raw Simulation Data Files

| File | Cases | SHA-256 Hash | Description |
|:-----|------:|:-------------|:------------|
| `kazi_mc_stable_v3.json` | 100 | `61421a385e7bae8506e67a1f2a22ce49464278795334f46ca80633c95e65cbc0` | Monte Carlo: Stable Zone (k_azi=0.5) |
| `kazi_boundary_mc.json` | 21 | `ec2c468c5011d730d3fb6bb7aa51599f9325929d00d7b25b74f4cd9196df7af4` | Monte Carlo: Chaos Zone (k_azi=0.8) |
| `kazi_sweep_FINAL.json` | 237 | `138d184da65059200d0c25d630d6db85ccecbc8f6a2b39256de040f39f2057ba` | Parametric Sweep: k_azi 0.0–2.0 |
| `design_around_impossibility.json` | — | `47c1d861c5e210fdf436940c62b1eda71c0eb22e376337aa92c71769d2f4d177` | Metadata: Design-around analysis |
| `glass_substrates_FINAL.json` | 12 | `f0077b6d1f224871499fa42eb8bcb0aeb26fcf0ea44201f3a7833e349f1550bf` | Material Study: Glass substrates |
| `material_sweep_FINAL.json` | 15 | `15edb0f402887a64936e4a2190931aca129c536fcba5f5dc4ab0ddf7367779fc` | Material Study: InP, GaN, AlN |
| `harmonic_sweep_FINAL.json` | 48 | `22e3b47f4444c2a7a70b0e6427b65dcda8d21853e116511d23c0fa8c1de02e55` | Harmonic Analysis: n=2,3,4,6 |
| `asymmetric_patterns_FINAL.json` | 24 | `4e2628cda7611b3ee633cc397e7b80593b8a738a70b4bfb65afd3ccf048bf895` | Asymmetric Pattern Study |
| `multilayer_stacks_FINAL.json` | 18 | `1e56f8144fa44f6d249bee1d6cc24254229537ecd1f3429790530a1f2e2b0672` | Multilayer Stack Analysis |
| `kazi_crossload_expanded.json` | 36 | `39f82debe83bcebb3d82258ceba43fed04271e38d9187579b67a5cae1ce5bc5b` | Cross-loading Study |
| `mesh_convergence_summary.json` | — | `d25737a8fdc718025f34709cc0539494b3772d27b9203434b750d2bc2c13defe` | Mesh Convergence Metadata |
| `wafer450mm_sweep_FINAL.json` | 0 | `43038261561c54f348ca823a73dd46bd4dd49675a6d6390ee4aaf9d96a30502a` | 450mm Study (incomplete) |

**Total Verified Cases:** 511+ FEA simulations

---

## Simulation Infrastructure

### Finite Element Solver
- **Primary Solver:** CalculiX 2.21 (Open Source, GPL)
- **Element Type:** C3D20R (20-node reduced integration hexahedra)
- **Typical Mesh:** 35,000–50,000 nodes per case
- **Convergence Criterion:** Newton-Raphson, tolerance 1e-8

### Cloud Compute Infrastructure
- **Provider:** Inductiva API (https://inductiva.ai)
- **Machine Type:** c3d-highcpu-180 (180 vCPU, 360 GB RAM)
- **Total Compute Hours:** ~2,400 hours

### Task Verification
Each simulation case includes:
- `task_id`: Unique Inductiva job identifier (verifiable via API)
- `node_count`: Mesh density verification
- `status`: Solver completion status

---

## Reproduction Instructions

To independently verify the simulation results:

1. **Install CalculiX:**
   ```bash
   # Ubuntu/Debian
   sudo apt-get install calculix-ccx
   
   # macOS (via Homebrew)
   brew install calculix-ccx
   ```

2. **Run a sample case:**
   ```bash
   ccx -i 04_DATA/mesh/sample_chuck_k0.65
   ```

3. **Compare output:**
   The `.frd` file contains nodal displacements. Extract W_pv (peak-to-valley Z-displacement) using:
   ```bash
   python3 scripts/extract_warpage.py sample_chuck_k0.65.frd
   ```

---

## Private Data Room

The following data is available under NDA:

| Asset | Description | Size |
|:------|:------------|-----:|
| Full FEA Output Archive | All 1,469 `.frd` files | 47 GB |
| Trained ROM Model | `rom_stable_zone_v8.pkl` | 2.3 MB |
| Stability Classifier | `stability_classifier_v2.joblib` | 156 KB |
| ILC Convergence Logs | 99 iteration history | 8.2 MB |

**Contact:** genesis-litho-ip@proton.me  
**Subject:** "Patent 1 Data Room Access Request"

---

## Verification Checksums

```
# SHA-256 Checksums for 04_DATA/raw/
61421a385e7bae8506e67a1f2a22ce49464278795334f46ca80633c95e65cbc0  kazi_mc_stable_v3.json
ec2c468c5011d730d3fb6bb7aa51599f9325929d00d7b25b74f4cd9196df7af4  kazi_boundary_mc.json
138d184da65059200d0c25d630d6db85ccecbc8f6a2b39256de040f39f2057ba  kazi_sweep_FINAL.json
47c1d861c5e210fdf436940c62b1eda71c0eb22e376337aa92c71769d2f4d177  design_around_impossibility.json
f0077b6d1f224871499fa42eb8bcb0aeb26fcf0ea44201f3a7833e349f1550bf  glass_substrates_FINAL.json
15edb0f402887a64936e4a2190931aca129c536fcba5f5dc4ab0ddf7367779fc  material_sweep_FINAL.json
22e3b47f4444c2a7a70b0e6427b65dcda8d21853e116511d23c0fa8c1de02e55  harmonic_sweep_FINAL.json
4e2628cda7611b3ee633cc397e7b80593b8a738a70b4bfb65afd3ccf048bf895  asymmetric_patterns_FINAL.json
1e56f8144fa44f6d249bee1d6cc24254229537ecd1f3429790530a1f2e2b0672  multilayer_stacks_FINAL.json
39f82debe83bcebb3d82258ceba43fed04271e38d9187579b67a5cae1ce5bc5b  kazi_crossload_expanded.json
d25737a8fdc718025f34709cc0539494b3772d27b9203434b750d2bc2c13defe  mesh_convergence_summary.json
```
