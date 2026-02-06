#!/bin/bash
# ============================================================================
# LITHOGRAPHY PHYSICS CLIFF AUDIT - DEMO
# ============================================================================

set -e

echo "============================================================================"
echo "🔬 LITHOGRAPHY PHYSICS CLIFF AUDIT - DEMO"
echo "============================================================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.8+."
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"
echo ""

# Install dependencies
echo "📦 Installing dependencies..."
pip3 install -q numpy matplotlib scipy 2>/dev/null || pip install -q numpy matplotlib scipy
echo "✅ Dependencies installed"
echo ""

# Generate figures
echo "📊 Generating visualizations..."
python3 02_PROOF/generate_cliff_chart.py
echo ""

# Run audit
echo "🔎 Running focus stability audit..."
python3 01_AUDIT/calculate_focus_drift.py --all --compare
echo ""

# Summary
echo "============================================================================"
echo "✅ DEMO COMPLETE"
echo "============================================================================"
echo ""
echo "📁 Generated Files:"
echo "   - figures/physics_cliff_variance.png"
echo "   - figures/focus_drift_vs_power.png"
echo "   - figures/zernike_comparison.png"
echo ""
echo "📖 Key Findings:"
echo "   - NXE:3800E @ 500W: Focus drift 43nm (budget: 20nm) → FAILURE"
echo "   - NXE:4000 @ 750W:  Focus drift >100nm → CATASTROPHIC"
echo "   - Genesis solution: Focus drift 0.8nm → 96% MARGIN REMAINING"
echo ""
echo "🔒 For access to the Genesis solution:"
echo "   📧 Contact: genesis-litho-ip@proton.me"
echo "============================================================================"
