# ignore ruff rule for mathematical symbols
# ruff: noqa: RUF003

# %% [markdown]
# # BeCoMe Visualizations -  Results Analysis
#
# This file contains visualizations for demonstrating the BeCoMe algorithm
# (Best Compromise Method) on three example datasets:
# - Budget Case: COVID-19 budget estimates (22 experts)
# - Floods Case: arable land reduction for flood prevention (13 experts)
# - Pendlers Case: cross-border worker travel assessment using Likert scale (22 experts)

# %%
# Imports
import sys
from pathlib import Path

# Add project root to Python path for imports to work
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import ipywidgets as widgets
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from IPython.display import display
from matplotlib.gridspec import GridSpec
from tabulate import tabulate

from examples.utils import calculate_agreement_level, load_data_from_txt
from src.calculators.become_calculator import BeCoMeCalculator

# Plot settings
plt.style.use("seaborn-v0_8-darkgrid")
sns.set_palette("husl")
plt.rcParams["figure.figsize"] = (12, 6)
plt.rcParams["font.size"] = 10

# Define paths
data_dir = Path(__file__).parent.parent / "data"
output_dir = Path(__file__).parent / "output"

# %%

# %% [markdown]
# ## 1. Data Loading
#
# Load all three datasets and compute BeCoMe results

# %%
# Load data from files

# Budget Case
budget_opinions, budget_metadata = load_data_from_txt(str(data_dir / "budget_case.txt"))
budget_calculator = BeCoMeCalculator()
budget_result = budget_calculator.calculate_compromise(budget_opinions)

# Floods Case
floods_opinions, floods_metadata = load_data_from_txt(str(data_dir / "floods_case.txt"))
floods_calculator = BeCoMeCalculator()
floods_result = floods_calculator.calculate_compromise(floods_opinions)

# Pendlers Case
pendlers_opinions, pendlers_metadata = load_data_from_txt(str(data_dir / "pendlers_case.txt"))
pendlers_calculator = BeCoMeCalculator()
pendlers_result = pendlers_calculator.calculate_compromise(pendlers_opinions)

print("Data loaded:")
print(f"  Budget: {len(budget_opinions)} experts, delta_max = {budget_result.max_error:.2f}")
print(f"  Floods: {len(floods_opinions)} experts, delta_max = {floods_result.max_error:.2f}")
print(f"  Pendlers: {len(pendlers_opinions)} experts, delta_max = {pendlers_result.max_error:.2f}")

# %% [markdown]
# ## 2. Visualization #1: Triangular Membership Functions
#
# ### Purpose and Overview
# This visualization displays triangular membership functions (TMFs) for all expert opinions
# and overlays three key aggregation methods: arithmetic mean (Gamma), median (Omega),
# and the "best compromise" (GammaOmegaMean). It provides a complete picture of how
# individual expert opinions are distributed and how they aggregate into consensus values.
#
# ### What Are Triangular Fuzzy Numbers?
# Each expert provides their opinion as a **triangular fuzzy number** (TFN), which represents
# uncertainty and flexibility in their estimate. A TFN has three parameters:
# - **Lower bound (a)**: The minimum plausible value
# - **Peak (b)**: The most likely or preferred value
# - **Upper bound (c)**: The maximum plausible value
#
# The triangular shape means the expert is most confident about the peak value (membership = 1.0),
# with confidence decreasing linearly toward the bounds (membership = 0.0). This captures
# the inherent vagueness in expert judgment better than single-point estimates.
#
# ### Visualization Components
#
# **Individual Expert Opinions (Light Blue Triangles):**
# - Each light blue triangle represents one expert's opinion
# - The base of the triangle spans from lower bound to upper bound on the x-axis
# - The peak of the triangle (height = 1.0) occurs at the expert's most preferred value
# - Wider triangles indicate greater uncertainty; narrower ones show more confidence
# - Overlapping triangles reveal areas of consensus; separated ones show disagreement
#
# **Aggregated Results (Colored Lines with Shaded Regions):**
# Three aggregation methods are visualized as bold colored lines:
#
# 1. **Arithmetic Mean - Gamma (Red)**
#    - Computed by averaging the lower bounds, peaks, and upper bounds separately
#    - Formula: Gamma = (1/n) * Σ(TFNᵢ) where n = number of experts
#    - Represents the "average opinion" across all experts
#    - Sensitive to extreme values and outliers
#    - Tends to be wider (more uncertain) when opinions vary greatly
#
# 2. **Median - Omega (Teal/Cyan)**
#    - Computed by taking the median of lower bounds, peaks, and upper bounds separately
#    - More robust to outliers than the arithmetic mean
#    - Represents the "middle ground" opinion
#    - Better reflects the central tendency when there are extreme opinions
#
# 3. **Best Compromise - GammaOmegaMean (Yellow)**
#    - Computed as the average of Gamma and Omega: (Gamma + Omega) / 2
#    - Balances the properties of both mean and median
#    - Provides a compromise between sensitivity to all opinions (mean) and robustness (median)
#    - This is the final recommended consensus value from the BeCoMe method
#    - The light shaded regions under each line show the "support" area for that aggregate
#
# ### How Aggregation Compresses Opinion Distribution
# The visualization demonstrates a key property of fuzzy aggregation: **compression of uncertainty**.
# When individual experts have wide, overlapping triangular opinions, the aggregated results
# (especially the Best Compromise) tend to be:
# - Narrower than most individual opinions (reduced uncertainty through consensus)
# - Positioned in areas of highest overlap (capturing collective agreement)
# - More reliable than any single expert's estimate
#
# ### Interpreting the Three Cases
#
# **Budget Case (COVID-19 budget in billion CZK, 22 experts):**
# - Shows moderate spread of opinions clustered around 45-60 billion CZK
# - Most triangular opinions overlap significantly in the 50-55 range
# - Some experts have wider triangles (more uncertainty), others narrower (more confident)
# - All three aggregation methods (Gamma, Omega, Compromise) are relatively close together
# - This indicates good overall agreement with minor differences in how extreme the estimates are
# - The Best Compromise (yellow) sits between the mean and median, providing a balanced estimate
#
# **Floods Case (Arable land reduction in %, 13 experts):**
# - Shows the greatest spread among all three scenarios
# - Expert opinions range from near 0% to over 40% reduction
# - Clear separation into distinct opinion clusters: pessimistic (0-10%), moderate (10-25%), optimistic (25-40+%)
# - The arithmetic mean (red) is pulled toward higher values by outliers
# - The median (teal) is more conservative, sitting in the middle cluster
# - Large distance between Gamma and Omega indicates **high disagreement** (high delta_max)
# - The Best Compromise attempts to balance these divergent views
# - This visualization reveals that experts fundamentally disagree, suggesting need for further discussion
#
# **Pendlers Case (Likert scale 0-100, 22 experts):**
# - Shows **strong core agreement** with most triangular opinions tightly clustered around 24-26
# - Approximately 18 out of 22 experts (82%) have very similar triangles in the low range
# - However, there is **one clear outlier** at the maximum Likert value (100)
# - A few additional experts provided mid-range estimates around 50
# - The arithmetic mean (Gamma, red) is **pulled significantly higher** (36.36) by the high outlier
# - The median (Omega, teal) remains **robust at 25.00**, better representing the majority view
# - The Best Compromise (yellow) falls at 30.68, between the two aggregates
# - **δ_max = 5.68** (MODERATE - but misleading, as it's inflated by the single outlier)
# - **Interpretation**: Despite moderate δ_max, the true consensus is strong among the core group
# - This case demonstrates the value of comparing Gamma and Omega: when they diverge significantly,
#   it signals the presence of outliers, and Omega (median) provides a more reliable consensus estimate
#
# ### Key Insights from This Visualization
# 1. **Visual Consensus Assessment**: You can immediately see whether experts agree (tight clustering)
#    or disagree (wide spread) without looking at numerical metrics
#
# 2. **Outlier Detection**: Individual triangles that don't overlap with others are easily spotted
#    and may warrant investigation or discussion
#
# 3. **Uncertainty Patterns**: Wide triangles indicate uncertain experts; narrow ones show confidence
#
# 4. **Aggregation Behavior**: By comparing the three colored aggregates, you can see:
#    - Whether outliers are influencing the mean (red) significantly
#    - Where the robust median (teal) sits relative to the mean
#    - How the compromise (yellow) balances between the two
#
# 5. **Decision Support**: The Best Compromise (yellow) provides a defensible consensus value
#    that accounts for all expert input while being robust to extreme opinions
#
# ### Technical Notes
# - The y-axis "Membership Degree mu(x)" ranges from 0 to 1, representing degree of membership
#   in the fuzzy set defined by each opinion
# - The x-axis shows the actual values being estimated (budget in CZK, percentage, Likert score)
# - The shaded areas under aggregated curves indicate the "support" of those fuzzy numbers
# - All visualizations use consistent color coding for easy cross-case comparison


# %%
def plot_triangular_membership_functions(opinions, result, title, case_name):
    """
    Plot triangular membership functions for all experts
    with overlaid aggregated results
    """
    _fig, ax = plt.subplots(figsize=(14, 7))

    # Color scheme
    expert_color = "lightblue"
    expert_alpha = 0.3
    mean_color = "#FF6B6B"
    median_color = "#4ECDC4"
    compromise_color = "#FFD93D"

    # Draw triangles for all experts
    for opinion in opinions:
        lower = opinion.opinion.lower_bound
        peak = opinion.opinion.peak
        upper = opinion.opinion.upper_bound

        # Triangle: (lower, 0) -> (peak, 1) -> (upper, 0)
        x = [lower, peak, upper, lower]
        y = [0, 1, 0, 0]
        ax.fill(x, y, color=expert_color, alpha=expert_alpha, edgecolor="gray", linewidth=0.5)

    # Function to draw aggregated triangle
    def draw_aggregate_triangle(fuzzy_num, color, label, linewidth=3):
        x = [fuzzy_num.lower_bound, fuzzy_num.peak, fuzzy_num.upper_bound, fuzzy_num.lower_bound]
        y = [0, 1, 0, 0]
        ax.plot(x, y, color=color, linewidth=linewidth, label=label, zorder=5)
        ax.fill(x, y, color=color, alpha=0.15, zorder=4)

    # Draw aggregated results
    draw_aggregate_triangle(result.arithmetic_mean, mean_color, "Arithmetic Mean (Gamma)")
    draw_aggregate_triangle(result.median, median_color, "Median (Omega)")
    draw_aggregate_triangle(
        result.best_compromise, compromise_color, "Best Compromise (GammaOmegaMean)"
    )

    ax.set_xlabel("Value", fontsize=12, fontweight="bold")
    ax.set_ylabel("Membership Degree mu(x)", fontsize=12, fontweight="bold")
    ax.set_title(
        f"{title}\nTriangular Membership Functions ({len(opinions)} experts)",
        fontsize=14,
        fontweight="bold",
    )
    ax.set_ylim(-0.05, 1.1)
    ax.legend(fontsize=11, loc="upper right")
    ax.grid(True, alpha=0.3)

    # Add patch for individual expert opinions in legend
    expert_patch = mpatches.Patch(
        facecolor=expert_color, alpha=expert_alpha, edgecolor="gray", label="Expert Opinions"
    )
    handles, labels = ax.get_legend_handles_labels()
    handles.insert(0, expert_patch)
    labels.insert(0, "Expert Opinions")
    ax.legend(handles, labels, fontsize=11, loc="upper right")

    plt.tight_layout()
    plt.savefig(
        output_dir / f"{case_name}_membership_functions.png",
        dpi=300,
        bbox_inches="tight",
    )
    plt.show()


# Plot for all three cases
plot_triangular_membership_functions(
    budget_opinions, budget_result, "Budget Case: COVID-19 budget (billion CZK)", "budget"
)
plot_triangular_membership_functions(
    floods_opinions, floods_result, "Floods Case: Arable land reduction (%)", "floods"
)
plot_triangular_membership_functions(
    pendlers_opinions, pendlers_result, "Pendlers Case: Likert scale (0-100)", "pendlers"
)

# %% [markdown]
# ## 2. Visualization #2: Centroid Chart
#
# ### Purpose and Overview
# The Centroid Chart provides a complementary view to the triangular membership functions by
# reducing each expert's fuzzy opinion to a single representative value: its **centroid**.
# This visualization sorts experts from lowest to highest centroid and overlays the three
# aggregated centroid values (Gamma, Omega, GammaOmegaMean), making it easy to see the
# distribution of expert opinions along a single dimension and measure the degree of consensus.
#
# ### What is a Centroid?
# The **centroid** (also called the center of gravity) of a triangular fuzzy number is a single
# crisp value that represents the "weighted center" of the triangle. For a TFN with lower bound (a),
# peak (b), and upper bound (c), the centroid is calculated as:
#
# **Centroid = (a + b + c) / 3**
#
# This is the arithmetic mean of the three defining points. The centroid provides a useful
# defuzzification of the expert's opinion - a single number that captures where their opinion
# is "centered" on the scale, taking into account both their most preferred value and their
# uncertainty range.
#
# **Why centroids matter:**
# - Simplifies comparison: Reduces complex triangular opinions to single comparable values
# - Preserves information: Unlike just using the peak, the centroid accounts for the full range
# - Enables sorting: Allows us to order experts from most pessimistic to most optimistic
# - Facilitates analysis: Makes it easier to spot clusters, outliers, and the overall distribution
#
# ### Visualization Components
#
# **Blue Bars (Individual Expert Centroids):**
# - Each vertical bar represents one expert's centroid value
# - Bar height = centroid value (the average of lower, peak, and upper bounds)
# - Bars are sorted from smallest to largest centroid (left to right)
# - Expert IDs are labeled on the x-axis (rotated for readability)
# - The bar chart creates a "skyline" showing the overall distribution of opinions
#
# **Horizontal Dashed Lines (Aggregated Centroids):**
# Three key reference lines show the aggregated consensus values:
#
# 1. **Red Dashed Line - Arithmetic Mean (Γ)**
#    - The centroid of the arithmetic mean fuzzy number
#    - Computed as: centroid(Gamma) = centroid(average of all TFNs)
#    - Shows where the "average expert" opinion is centered
#    - Sensitive to extreme values - can be pulled up or down by outliers
#
# 2. **Teal Dashed Line - Median (Ω)**
#    - The centroid of the median fuzzy number
#    - Computed as: centroid(Omega) = centroid(median of all TFNs)
#    - Shows where the "middle expert" opinion is centered
#    - More robust to outliers - represents the 50th percentile
#
# 3. **Yellow Dashed Line - Best Compromise (ΓΩMean)**
#    - The centroid of the best compromise fuzzy number
#    - Computed as: centroid((Gamma + Omega)/2)
#    - This is the BeCoMe method's final recommended consensus value
#    - Balances between the mean and median properties
#
# **Legend Information - Delta Max (δ_max):**
# The legend displays a critical metric: **δ_max = distance between Γ and Ω**
#
# This is the key quality indicator in the BeCoMe method:
# - **δ_max = |centroid(Gamma) - centroid(Omega)|**
# - Measures the **distance** between arithmetic mean and median centroids
# - Small δ_max (< 5) = **High agreement** - experts are closely aligned
# - Medium δ_max (5-15) = **Moderate agreement** - some divergence in opinions
# - Large δ_max (> 15) = **Low agreement** - experts fundamentally disagree
#
# The Best Compromise centroid always falls exactly halfway between Gamma and Omega,
# so δ_max also represents the maximum deviation from the compromise to either aggregate.
#
# ### How to Read This Visualization
#
# **Assessing Consensus:**
# - Look at the vertical spread of bars: Wide range = diverse opinions, narrow range = agreement
# - Check if bars are evenly distributed or clustered in groups
# - Compare the three horizontal lines:
#   - Lines close together = good agreement (low δ_max)
#   - Lines far apart = poor agreement (high δ_max)
#
# **Identifying Patterns:**
# - **Gradual slope**: Smooth increase from left to right indicates continuous opinion spectrum
# - **Clusters**: Groups of similar-height bars indicate expert subgroups with aligned views
# - **Gaps**: Large jumps between adjacent bars suggest polarization
# - **Outliers**: Bars far from the main distribution indicate experts with extreme views
#
# **Understanding Position of Aggregates:**
# - If Gamma (red) is **above** Omega (teal): High-value outliers are pulling the mean up
# - If Gamma (red) is **below** Omega (teal): Low-value outliers are pulling the mean down
# - If Gamma ≈ Omega: Distribution is relatively symmetric, few extreme outliers
# - The Best Compromise (yellow) is always between them, providing a balanced view
#
# ### Interpreting the Three Cases
#
# **Budget Case (COVID-19 budget in billion CZK, 22 experts):**
# - Expert centroids range from ~26 to ~80 billion CZK (roughly 3x spread)
# - Relatively smooth, gradual increase from left to right (no major gaps or clusters)
# - Most experts concentrated in the 40-55 billion CZK range
# - Aggregated values:
#   - Arithmetic Mean (Γ): 50.23 billion CZK
#   - Median (Ω): 45.83 billion CZK
#   - Best Compromise (ΓΩMean): 48.03 billion CZK
#   - **δ_max = 2.20** (EXCELLENT - very low disagreement)
# - The three lines are very close together, indicating strong consensus
# - Gamma slightly above Omega suggests a few higher estimates are gently pulling the mean up
# - The small δ_max indicates this is a reliable consensus despite the range of estimates
# - **Interpretation**: Experts generally agree, with the consensus around 48 billion CZK
#
# **Floods Case (Arable land reduction in %, 13 experts):**
# - Expert centroids range from ~0.5% to ~47% (nearly 100x spread!)
# - Clear **bimodal distribution**: Two distinct clusters
#   - Low cluster: 5 experts with centroids 0.5-8% (pessimistic about land loss)
#   - High cluster: 5 experts with centroids 37-47% (optimistic about land loss)
#   - Middle zone: 3 experts around 14-42% (bridge the gap)
# - Large gap between clusters around 8-14% reveals fundamental disagreement
# - Aggregated values:
#   - Arithmetic Mean (Γ): 20.28%
#   - Median (Ω): 8.33%
#   - Best Compromise (ΓΩMean): 14.31%
#   - **δ_max = 5.97** (MODERATE - notable disagreement)
# - Wide separation between Gamma and Omega shows the impact of the high-value cluster
# - Gamma (20.28%) is pulled significantly upward by the experts predicting high land reduction
# - Omega (8.33%) is more conservative, staying closer to the lower cluster
# - **Interpretation**: Experts are divided - some expect minimal impact, others expect severe impact
# - The moderate δ_max suggests caution: consensus is weak, further discussion needed
#
# **Pendlers Case (Likert scale 0-100, 22 experts):**
# - Most expert centroids tightly clustered around 24-26 (extremely narrow range!)
# - 18 out of 22 experts have centroids in the 24-30 range (strong main cluster)
# - A few experts provided mid-range estimates around 48-50
# - One clear outlier at ~100 (maximum Likert value)
# - Aggregated values:
#   - Arithmetic Mean (Γ): 36.36
#   - Median (Ω): 25.00
#   - Best Compromise (ΓΩMean): 30.68
#   - **δ_max = 5.68** (MODERATE - but misleading due to outlier)
# - Despite the tight main cluster, δ_max is elevated due to the single high outlier
# - The outlier pulls Gamma (36.36) significantly higher than Omega (25.00)
# - Omega (25.00) better represents the majority consensus by being robust to the outlier
# - **Interpretation**: Strong core agreement around 25, but one outlier inflates the mean
# - This demonstrates the value of using median: it captures the true consensus despite outliers
# - The Best Compromise (30.68) falls between, but may over-weight the outlier
#
# ### Key Insights from This Visualization
#
# 1. **Quick Consensus Check**: The distance between red and teal lines (δ_max) immediately
#    reveals agreement quality - closer lines mean better consensus
#
# 2. **Distribution Patterns**: The bar "skyline" shows whether opinions are:
#    - Uniformly distributed (gradual slope)
#    - Clustered (groups of similar bars)
#    - Polarized (gaps and separate clusters)
#
# 3. **Outlier Impact**: By comparing Gamma and Omega positions:
#    - If far apart: outliers are significantly influencing the mean
#    - If close: distribution is balanced and symmetric
#
# 4. **Individual Expert Positioning**: Each expert can see where they stand relative to:
#    - Other experts (their bar height vs others)
#    - The consensus (how close their bar is to the yellow line)
#    - The overall distribution (percentile within the group)
#
# 5. **Complement to Triangle View**: While triangular membership functions show the full
#    fuzzy structure, centroid charts provide a simplified, sortable view that's easier
#    for comparing many experts at once
#
# 6. **Robustness Demonstration**: When Gamma and Omega diverge significantly, it signals
#    that the median-based approach (Omega) may be more reliable than the mean (Gamma)
#
# ### Practical Applications
#
# **For Decision Makers:**
# - Use the Best Compromise (yellow line) as the recommended consensus value
# - Check δ_max to assess confidence in the consensus (lower is better)
# - Identify experts far from consensus for follow-up discussion
#
# **For Facilitators:**
# - Clusters and gaps reveal subgroups that may need targeted dialogue
# - Outliers may represent important minority perspectives or misunderstandings
# - The visualization can guide iterative consensus-building by showing progress
#
# **For Researchers:**
# - Centroid distribution patterns can reveal cognitive biases or information asymmetries
# - Comparing before/after centroid charts shows the impact of deliberation
# - δ_max serves as a quantitative measure for statistical analysis of agreement
#
# ### Technical Notes
# - X-axis shows experts sorted by ascending centroid value (leftmost = most pessimistic)
# - Y-axis shows the centroid value in the problem's units (CZK, %, or Likert value)
# - Expert labels are rotated 45° for readability when there are many participants
# - The legend displays exact numerical values for all three aggregates plus δ_max
# - Grid lines on the y-axis facilitate reading approximate values from the chart


# %%
def plot_centroid_chart(opinions, result, title, case_name):
    """
    Centroid chart for experts with highlighted aggregated metrics
    """
    # Sort experts by centroid
    sorted_opinions = sorted(opinions, key=lambda op: op.centroid)

    expert_ids = [op.expert_id for op in sorted_opinions]
    centroids = [op.centroid for op in sorted_opinions]

    # Create DataFrame for convenience
    df = pd.DataFrame({"expert_id": expert_ids, "centroid": centroids})

    _fig, ax = plt.subplots(figsize=(14, 7))

    # Bars for experts
    ax.bar(
        range(len(df)),
        df["centroid"],
        color="steelblue",
        alpha=0.7,
        edgecolor="black",
        linewidth=0.5,
    )

    # Horizontal lines for aggregated values
    mean_centroid = result.arithmetic_mean.centroid
    median_centroid = result.median.centroid
    compromise_centroid = result.best_compromise.centroid

    ax.axhline(
        y=mean_centroid,
        color="#FF6B6B",
        linestyle="--",
        linewidth=2.5,
        label=f"Arithmetic Mean (Γ): {mean_centroid:.2f}",
        zorder=5,
    )
    ax.axhline(
        y=median_centroid,
        color="#4ECDC4",
        linestyle="--",
        linewidth=2.5,
        label=f"Median (Ω): {median_centroid:.2f}",
        zorder=5,
    )
    ax.axhline(
        y=compromise_centroid,
        color="#FFD93D",
        linestyle="--",
        linewidth=2.5,
        label=f"Best Compromise (ΓΩMean): {compromise_centroid:.2f}",
        zorder=5,
    )

    # Add delta_max as invisible line for legend
    delta_max = result.max_error
    ax.plot([], [], " ", label=f"δ_max = {delta_max:.2f} (distance between Γ and Ω)")

    ax.set_xlabel("Experts (sorted by centroid)", fontsize=12, fontweight="bold")
    ax.set_ylabel("Centroid Value", fontsize=12, fontweight="bold")
    ax.set_title(
        f"{title}\nExpert Centroids and Aggregated Values",
        fontsize=14,
        fontweight="bold",
    )

    ax.set_xticks(range(len(df)))
    ax.set_xticklabels(df["expert_id"], rotation=45, ha="right")
    ax.legend(fontsize=11, loc="upper left")
    ax.grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    plt.savefig(
        output_dir / f"{case_name}_centroids.png",
        dpi=300,
        bbox_inches="tight",
    )
    plt.show()


# Plot for all three cases
plot_centroid_chart(budget_opinions, budget_result, "Budget Case: COVID-19 budget", "budget")
plot_centroid_chart(floods_opinions, floods_result, "Floods Case: Land reduction", "floods")
plot_centroid_chart(pendlers_opinions, pendlers_result, "Pendlers Case: Likert scale", "pendlers")

# %% [markdown]
# ## 2. Visualization #3: Interactive Sensitivity Analysis
#
# ### Purpose and Overview
# The Interactive Sensitivity Analysis is a powerful tool for exploring how the consensus
# results change when individual experts are included or excluded from the aggregation.
# By providing real-time recalculation and visualization updates, this interactive widget
# demonstrates the **robustness** of the BeCoMe method and helps identify which expert
# opinions have the greatest influence on the final consensus. This is crucial for
# understanding the stability of the results and for identifying potentially problematic
# outliers or influential experts.
#
# ### What is Sensitivity Analysis?
# **Sensitivity analysis** is a technique used to determine how different values of input
# variables affect output variables. In the context of expert consensus:
#
# - **Input variables**: Which experts are included in the aggregation
# - **Output variables**: The aggregated fuzzy numbers (Gamma, Omega, Best Compromise) and δ_max
# - **Goal**: Assess whether removing one or more experts significantly changes the consensus
#
# **Why sensitivity analysis matters:**
# - **Robustness testing**: A robust consensus should not dramatically change when a single
#   expert is removed (especially if there are many experts)
# - **Outlier identification**: If removing one expert causes δ_max to drop significantly,
#   that expert may be an outlier whose opinion differs from the group
# - **Influential expert detection**: Some experts may have disproportionate impact on the
#   consensus due to extreme positions
# - **Quality assurance**: Ensures the final recommendation is not overly dependent on any
#   single opinion
# - **Stakeholder confidence**: Demonstrates that the method produces stable results even
#   with slight variations in expert panel composition
#
# ### Visualization Components
#
# **Interactive Controls (Checkboxes):**
# - Each expert has an associated checkbox labeled with their ID and centroid value
# - Format: "Expert_ID (c=XX.X)" where c is the centroid
# - Checkboxes are initially all checked (all experts included)
# - Clicking a checkbox immediately toggles that expert in/out of the calculation
# - Multiple experts can be deselected simultaneously
# - Checkboxes are organized in columns for easy scanning
# - The interface requires at least 2 experts to remain selected for valid calculations
#
# **Dynamic Visualization Panel:**
# The widget displays two side-by-side plots that update in real-time:
#
# **Left Plot - Triangular Membership Functions:**
# - Shows the triangular fuzzy numbers for all currently selected experts
# - Light blue filled triangles for individual expert opinions
# - Three bold colored lines for aggregates:
#   - Red: Arithmetic Mean (Gamma)
#   - Teal: Median (Omega)
#   - Yellow: Best Compromise
# - Title updates to show the current number of selected experts
# - Provides visual feedback on how the fuzzy number distribution changes
#
# **Right Plot - Centroid Bar Chart:**
# - Displays bars for currently selected experts sorted by centroid
# - Three horizontal dashed lines for aggregated centroids
# - Title shows the current δ_max value
# - Expert labels on x-axis (may rotate for readability)
# - Provides quantitative view of how centroids shift
#
# **Metrics Display (Below Plots):**
# After each recalculation, key metrics are printed:
# - Number of experts currently selected
# - δ_max value with agreement level (good/moderate/low)
# - Best Compromise bounds: [lower, peak, upper]
# - Best Compromise centroid value
#
# ### How to Use This Interactive Tool
#
# **Basic Exploration:**
# 1. Start with all experts selected (default state)
# 2. Note the initial δ_max and Best Compromise values
# 3. Deselect one expert at a time and observe changes
# 4. Watch both plots update and read the new metrics
# 5. Reselect the expert to return to previous state
#
# **Outlier Testing:**
# 1. Identify experts with extreme centroids (far left or far right in the centroid chart)
# 2. Deselect these experts one by one
# 3. Observe whether δ_max decreases significantly (suggests they were outliers)
# 4. Check if the Best Compromise shifts noticeably (indicates influence)
#
# **Robustness Assessment:**
# 1. Try removing different combinations of 1-3 experts
# 2. Check if δ_max remains relatively stable
# 3. Verify that Best Compromise doesn't change dramatically
# 4. A robust consensus will show minimal variation across different expert subsets
#
# **Cluster Analysis:**
# 1. If you identified clusters in the centroid chart, test them
# 2. Try removing an entire cluster (e.g., all low-value experts)
# 3. Observe how this affects the balance between Gamma and Omega
# 4. This reveals the impact of different opinion groups
#
# **Minimum Viable Panel:**
# 1. Gradually remove experts to find the minimum number needed for stable consensus
# 2. Watch when δ_max starts to increase significantly
# 3. This identifies the threshold for reliable consensus
#
# ### What Patterns to Look For
#
# **Stable Consensus (Robust Method):**
# - Removing individual experts causes only small changes in δ_max (< 10-20% variation)
# - Best Compromise centroid shifts by less than 5-10% when removing single experts
# - Gamma and Omega remain relatively close together regardless of who's excluded
# - The triangular membership functions' aggregate shapes remain similar
# - **Interpretation**: The consensus is reliable and not overly dependent on any individual
#
# **Unstable Consensus (Sensitive to Composition):**
# - Removing one expert causes δ_max to change dramatically (> 50%)
# - Best Compromise shifts significantly with single expert removal
# - Aggregated triangular shapes change noticeably
# - **Interpretation**: Results are sensitive to panel composition; may need more experts
#   or further discussion to reach stable consensus
#
# **Influential Outliers:**
# - Removing a specific expert causes δ_max to **decrease** substantially
# - The Best Compromise moves closer to the remaining majority
# - Gamma shifts more than Omega (mean is more affected than median)
# - **Interpretation**: That expert holds an extreme position; consider whether their
#   perspective is valid or based on different assumptions
#
# **Symmetric Impact:**
# - Removing low-centroid experts shifts consensus upward proportionally to removing
#   high-centroid experts shifts it downward
# - δ_max increases when removing experts from either extreme
# - **Interpretation**: Opinions are evenly distributed; both ends contribute to balance
#
# **Clustered Opinions:**
# - Removing experts from one cluster causes large shifts in Gamma
# - Removing experts from another cluster causes offsetting shifts
# - Omega remains more stable than Gamma
# - **Interpretation**: Expert panel has distinct subgroups with different perspectives
#
# ### Interpreting Results for the Three Cases
#
# **Budget Case (22 experts, δ_max = 2.20):**
# - **Expected behavior**: Very robust to individual expert removal
# - Removing any single expert should cause δ_max to change by less than 0.5
# - Best Compromise should remain in the 46-50 billion CZK range
# - Removing the lowest centroid expert (~26 CZK) should slightly increase the consensus
# - Removing the highest centroid expert (~80 CZK) should slightly decrease the consensus
# - Even removing 3-4 experts simultaneously should maintain δ_max < 5.0
# - **What this demonstrates**: The low initial δ_max indicates strong consensus that
#   doesn't rely on any particular expert; the method is highly robust
#
# **Floods Case (13 experts, δ_max = 5.97):**
# - **Expected behavior**: Moderate sensitivity due to bimodal distribution
# - Removing experts from the low cluster (0.5-8%) should:
#   - Increase Gamma (mean shifts toward high cluster)
#   - Keep Omega relatively stable or shift it up
#   - Potentially increase δ_max (less balance between clusters)
# - Removing experts from the high cluster (37-47%) should:
#   - Decrease Gamma significantly
#   - Omega may shift down slightly
#   - δ_max should decrease (removing outliers reduces disagreement)
# - Removing the middle-range experts (14-42%) should:
#   - Increase δ_max (removes the "bridge" between clusters)
#   - Emphasize the bimodal nature
# - **What this demonstrates**: The moderate δ_max reflects real disagreement; removing
#   high-cluster experts improves apparent consensus but may lose important perspectives
#
# **Pendlers Case (22 experts, δ_max = 5.68):**
# - **Expected behavior**: Main cluster is robust; outlier has significant impact
# - Removing experts from the main cluster (24-30 centroids) should:
#   - Cause minimal changes in δ_max (maybe ±0.5)
#   - Keep Best Compromise around 30-31
# - Removing the high outlier (~100) should:
#   - Decrease δ_max dramatically (potentially to < 2.0)
#   - Decrease Gamma significantly (was pulled up by outlier)
#   - Keep Omega nearly unchanged (median is robust)
#   - Shift Best Compromise down toward the main cluster consensus
# - Removing mid-range experts (48-50) should have moderate impact
# - **What this demonstrates**: The moderate δ_max is misleading; it's caused by one
#   outlier rather than genuine disagreement. Sensitivity analysis reveals the true
#   consensus lies with the main cluster, and the outlier disproportionately affects
#   the arithmetic mean
#
# ### Key Insights from This Visualization
#
# 1. **Robustness Validation**: Real-time recalculation proves the BeCoMe method's
#    stability by showing minimal changes when individual experts are excluded
#
# 2. **Outlier Impact Quantification**: You can measure exactly how much each expert
#    influences the consensus by comparing δ_max before and after their removal
#
# 3. **Median Superiority**: When outliers are present, you'll observe that Omega (median)
#    remains much more stable than Gamma (mean) during sensitivity testing, demonstrating
#    the value of the median-based approach
#
# 4. **Transparent Decision-Making**: Stakeholders can see that removing or adding any
#    single expert doesn't fundamentally change the consensus, building confidence
#
# 5. **Interactive Learning**: The immediate visual feedback helps users understand how
#    fuzzy aggregation works and how different experts contribute to the final result
#
# 6. **Cluster Validation**: Testing different combinations helps confirm whether
#    apparent clusters in the centroid chart represent real opinion groups
#
# 7. **Minimum Panel Size**: By progressively removing experts, you can identify the
#    minimum number needed to maintain a stable consensus for future similar studies
#
# ### Practical Applications
#
# **For Decision Makers:**
# - Verify that the consensus is not overly dependent on controversial experts
# - Test "what-if" scenarios: "What if this stakeholder had not participated?"
# - Build confidence in the recommendation by demonstrating robustness
# - Identify which experts are close to the consensus (aligned) vs. outliers (divergent)
#
# **For Facilitators:**
# - Use during deliberation to show participants their influence on the group consensus
# - Identify experts whose removal improves consensus (potential for targeted follow-up)
# - Demonstrate the value of diverse perspectives or the cost of polarization
# - Guide discussion by showing which opinions are "pulling" the consensus in certain directions
#
# **For Researchers:**
# - Perform systematic robustness analysis by testing all possible single-expert removals
# - Quantify the influence of each expert (e.g., Δδ_max when removed)
# - Identify cognitive or informational biases by seeing which experts cluster together
# - Validate the statistical properties of fuzzy aggregation methods
# - Generate data for meta-analysis on consensus quality
#
# **For Quality Assurance:**
# - Ensure that data entry errors (e.g., one expert's values recorded incorrectly) can
#   be detected by their disproportionate impact on δ_max
# - Verify that no single expert can "veto" or dominate the consensus
# - Document the sensitivity analysis as part of the methodological rigor
#
# ### Advantages of Interactive vs. Static Analysis
#
# **Immediate Feedback:**
# - No need to run separate scripts or wait for recalculation
# - Changes are visualized instantly, facilitating exploration
#
# **Visual Learning:**
# - Seeing the triangles and bars move in real-time builds intuition
# - Easier to understand fuzzy aggregation dynamics than reading tables of numbers
#
# **Flexible Exploration:**
# - Users can test any combination they're curious about
# - Not limited to pre-computed scenarios
#
# **Stakeholder Engagement:**
# - Interactive tools are more engaging in presentations and workshops
# - Participants can "play with" the data and develop ownership of the results
#
# ### Limitations and Considerations
#
# **Computational Load:**
# - With very large expert panels (>50), recalculation may be slower
# - Consider using a non-interactive batch analysis for very large datasets
#
# **Interpretation Complexity:**
# - Users need training to correctly interpret sensitivity patterns
# - Risk of over-interpreting small fluctuations as meaningful
#
# **Selection Bias:**
# - Manually choosing which experts to exclude could introduce bias
# - For rigorous analysis, test all possible combinations systematically
#
# **Minimum Requirements:**
# - Requires at least 2 experts; removing too many invalidates the consensus
# - Small residual panels may not be representative
#
# ### Technical Notes
# - Built using ipywidgets for Jupyter notebook environments
# - Requires interactive backend (not available in static HTML exports)
# - Recalculation triggered by checkbox state change events
# - BeCoMeCalculator is re-instantiated for each recalculation
# - Checkboxes display expert IDs and centroids for easy reference
# - Both plots use consistent styling with the static visualizations
# - Metrics are printed below plots after each update
# - Error handling prevents calculation with fewer than 2 experts


# %%
def create_sensitivity_analysis_widget(opinions, title, case_name):
    """
    Interactive widget for sensitivity analysis
    """
    # Create checkboxes for each expert
    checkboxes = {}
    for op in opinions:
        checkboxes[op.expert_id] = widgets.Checkbox(
            value=True,
            description=f"{op.expert_id} (c={op.centroid:.1f})",
            style={"description_width": "initial"},
            layout=widgets.Layout(width="200px"),
        )

    # Output widget for plots
    output = widgets.Output()

    def update_plot(change=None):
        """Update plot when expert selection changes"""
        # Get list of selected experts
        selected_opinions = [op for op in opinions if checkboxes[op.expert_id].value]

        if len(selected_opinions) < 2:
            with output:
                output.clear_output(wait=True)
                print("WARNING: Select at least 2 experts for calculation")
            return

        # Recalculate results
        calculator = BeCoMeCalculator()
        result = calculator.calculate_compromise(selected_opinions)

        with output:
            output.clear_output(wait=True)

            _fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

            # Plot 1: Triangular functions
            expert_color = "lightblue"
            for op in selected_opinions:
                x = [
                    op.opinion.lower_bound,
                    op.opinion.peak,
                    op.opinion.upper_bound,
                    op.opinion.lower_bound,
                ]
                y = [0, 1, 0, 0]
                ax1.fill(x, y, color=expert_color, alpha=0.3, edgecolor="gray", linewidth=0.5)

            # Aggregates
            for fuzzy_num, color, label in [
                (result.arithmetic_mean, "#FF6B6B", "Mean"),
                (result.median, "#4ECDC4", "Median"),
                (result.best_compromise, "#FFD93D", "Compromise"),
            ]:
                x = [
                    fuzzy_num.lower_bound,
                    fuzzy_num.peak,
                    fuzzy_num.upper_bound,
                    fuzzy_num.lower_bound,
                ]
                y = [0, 1, 0, 0]
                ax1.plot(x, y, color=color, linewidth=2.5, label=label)

            ax1.set_xlabel("Value", fontweight="bold")
            ax1.set_ylabel("Membership Degree mu(x)", fontweight="bold")
            ax1.set_title(
                f"Membership Functions ({len(selected_opinions)} experts)", fontweight="bold"
            )
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            ax1.set_ylim(-0.05, 1.1)

            # Plot 2: Centroids
            sorted_ops = sorted(selected_opinions, key=lambda x: x.centroid)
            centroids = [op.centroid for op in sorted_ops]
            expert_ids = [op.expert_id for op in sorted_ops]

            ax2.bar(range(len(centroids)), centroids, color="steelblue", alpha=0.7)
            ax2.axhline(
                y=result.arithmetic_mean.centroid,
                color="#FF6B6B",
                linestyle="--",
                linewidth=2,
                label="Mean",
            )
            ax2.axhline(
                y=result.median.centroid,
                color="#4ECDC4",
                linestyle="--",
                linewidth=2,
                label="Median",
            )
            ax2.axhline(
                y=result.best_compromise.centroid,
                color="#FFD93D",
                linestyle="--",
                linewidth=2,
                label="Compromise",
            )

            ax2.set_xlabel("Experts", fontweight="bold")
            ax2.set_ylabel("Centroid", fontweight="bold")
            ax2.set_title(f"Centroids (delta_max = {result.max_error:.2f})", fontweight="bold")
            ax2.set_xticks(range(len(expert_ids)))
            ax2.set_xticklabels(expert_ids, rotation=45, ha="right")
            ax2.legend()
            ax2.grid(True, alpha=0.3, axis="y")

            plt.tight_layout()
            plt.show()

            # Display metrics
            agreement = calculate_agreement_level(result.max_error, (5.0, 15.0))
            print(f"\nMetrics ({len(selected_opinions)} experts):")
            print(f"   delta_max = {result.max_error:.2f} ({agreement})")
            print(
                f"   Compromise: [{result.best_compromise.lower_bound:.2f}, "
                f"{result.best_compromise.peak:.2f}, {result.best_compromise.upper_bound:.2f}]"
            )
            print(f"   Compromise centroid: {result.best_compromise.centroid:.2f}")

    # Bind event handlers
    for checkbox in checkboxes.values():
        checkbox.observe(update_plot, names="value")

    # Initial drawing
    update_plot()

    # Layout widgets
    checkbox_cols = []
    items_per_col = 8
    checkbox_list = list(checkboxes.values())

    for i in range(0, len(checkbox_list), items_per_col):
        checkbox_cols.append(widgets.VBox(checkbox_list[i : i + items_per_col]))

    controls = widgets.HBox(checkbox_cols)

    title_widget = widgets.HTML(f"<h3>{title} - Sensitivity Analysis</h3>")
    info_widget = widgets.HTML(
        "<p><i>Select/deselect experts to see the impact on BeCoMe results</i></p>"
    )

    display(widgets.VBox([title_widget, info_widget, controls, output]))


# Create widgets for each case
print("Budget Case - Interactive Analysis:")
create_sensitivity_analysis_widget(budget_opinions, "Budget Case: COVID-19 budget", "budget")

print("\nFloods Case - Interactive Analysis:")
create_sensitivity_analysis_widget(floods_opinions, "Floods Case: Land reduction", "floods")

print("\nPendlers Case - Interactive Analysis:")
create_sensitivity_analysis_widget(pendlers_opinions, "Pendlers Case: Likert scale", "pendlers")

# %% [markdown]
# ## 2. Visualization #4: Scenario Dashboard
#
# ### Purpose and Overview
# The Scenario Dashboard provides a **comprehensive comparison view** of all three case studies
# (Budget, Floods, Pendlers) in a single integrated visualization. By combining a detailed
# metrics table with compact visual charts, the dashboard enables rapid cross-scenario analysis
# and highlights patterns, similarities, and differences across different expert consensus
# contexts. This is particularly valuable for understanding how the BeCoMe method performs
# across diverse domains, expert panel sizes, and opinion distributions.
#
# ### What Does This Visualization Show?
# The dashboard integrates multiple information layers:
#
# **Quantitative Comparison**: A tabular summary of key numerical metrics for each scenario,
# including expert counts, compromise bounds (lower/peak/upper), centroids, δ_max values,
# and agreement levels.
#
# **Visual Comparison**: Mini-charts showing centroid distributions and triangular membership
# functions for each scenario side-by-side, enabling quick visual pattern recognition.
#
# **Quality Assessment**: Color-coded agreement levels in the table provide instant quality
# indication for each scenario.
#
# The dashboard answers questions like:
# - Which scenarios have the strongest/weakest consensus?
# - How do expert panel sizes relate to agreement quality?
# - Are the Best Compromise values similar or different across cases?
# - What visual patterns distinguish high-agreement from low-agreement scenarios?
#
# ### Visualization Components
#
# The dashboard is organized in a grid layout with three main sections:
#
# **Top Section - Metrics Summary Table:**
#
# A comprehensive table displaying 8 columns of information for each scenario:
#
# 1. **Scenario**: Case name (Budget Case, Floods Case, Pendlers Case)
#    - Identifies which domain/context is being analyzed
#
# 2. **Experts**: Number of experts who provided opinions
#    - Shows panel size (e.g., 22, 13, 22)
#    - Larger panels don't necessarily mean better consensus
#
# 3. **Compromise (Lower)**: Lower bound of Best Compromise fuzzy number with units
#    - Minimum plausible value of the consensus estimate
#    - Format: "XX.XX [unit]" (e.g., "45.93 billion CZK")
#
# 4. **Compromise (Peak)**: Peak value of Best Compromise with units
#    - Most likely/preferred consensus value
#    - This is often the single number presented to decision makers
#
# 5. **Compromise (Upper)**: Upper bound of Best Compromise with units
#    - Maximum plausible value of the consensus estimate
#    - Together with lower/peak, defines the uncertainty range
#
# 6. **Centroid**: Centroid of Best Compromise with units
#    - The "center of mass" of the consensus: (lower + peak + upper) / 3
#    - Useful for defuzzified comparisons across scenarios
#
# 7. **delta_max**: The quality metric δ_max (distance between Gamma and Omega centroids)
#    - Numerical value without units (e.g., "2.20", "5.97")
#    - Lower is better; indicates degree of expert agreement
#
# 8. **Agreement**: Qualitative assessment based on δ_max thresholds
#    - **"good"**: δ_max < 5.0 (cell colored light green)
#    - **"moderate"**: 5.0 ≤ δ_max ≤ 15.0 (cell colored light yellow/gold)
#    - **"low"**: δ_max > 15.0 (cell colored light red/pink)
#    - Color coding enables instant visual scanning
#
# **Table Styling:**
# - Header row has teal background with white bold text
# - Agreement column cells are color-coded based on quality level
# - Consistent column widths for readability
# - All numerical values formatted to 2 decimal places
# - Units included in each cell for clarity
#
# **Middle Section - Centroid Mini-Charts (3 columns):**
#
# For each scenario, a compact bar chart shows:
# - **Blue bars**: Individual expert centroids sorted from low to high
# - **Yellow dashed line**: Best Compromise centroid (horizontal reference)
# - **Title**: Scenario name + "Centroids"
# - **Axes**: Expert indices on x-axis, centroid values on y-axis
# - **Grid**: Light y-axis gridlines for value estimation
#
# These mini-charts provide a "skyline view" of opinion distribution:
# - Smooth gradual slopes indicate continuous opinion spectra
# - Steep jumps reveal clusters or gaps
# - Tight clustering shows strong agreement
# - Wide spread indicates divergent opinions
#
# **Bottom Section - Triangular Membership Function Mini-Charts (3 columns):**
#
# For each scenario, a compact plot shows:
# - **Light blue filled triangles**: Individual expert fuzzy numbers
# - **Yellow bold line**: Best Compromise fuzzy number
# - **Title**: "Membership Functions"
# - **Axes**: Value on x-axis, membership degree mu(x) on y-axis (0-1)
# - **Grid**: Light gridlines for easier reading
#
# These mini-charts show the full fuzzy structure:
# - Overlapping triangles indicate consensus zones
# - Separated triangles show disagreement
# - Triangle widths reveal expert confidence levels
# - Best Compromise position shows where the consensus lies
#
# **Overall Layout:**
# - Fixed figure size (18 x 12 inches) for consistency
# - GridSpec layout manager for precise positioning
# - Title at top: "BeCoMe Scenario Comparison Dashboard"
# - 3 rows × 3 columns (table spans full width, then 3 mini-chart pairs)
# - Consistent styling across all subplots
#
# ### How to Interpret the Dashboard
#
# **Quick Scan Strategy:**
# 1. Look at the Agreement column in the table - identify which scenarios are green/yellow/red
# 2. Compare δ_max values - lower numbers indicate stronger consensus
# 3. Scan the centroid mini-charts - look for tight vs. dispersed distributions
# 4. Check the membership function mini-charts - overlapping vs. separated triangles
#
# **Detailed Comparison Strategy:**
# 1. Compare expert panel sizes - note that smaller panels aren't necessarily worse
# 2. Compare Best Compromise ranges (upper - lower) - wider ranges mean more uncertainty
# 3. Look for patterns between panel characteristics and agreement quality
# 4. Identify whether high δ_max is due to genuine disagreement or outliers
#
# **Visual Pattern Recognition:**
# - **Budget Case**: Should show tight centroid clustering + overlapping triangles = good agreement
# - **Floods Case**: Should show bimodal centroid distribution + separated triangle groups = moderate agreement
# - **Pendlers Case**: Should show tight main cluster with outlier + one distant triangle = moderate (misleading)
#
# ### Interpreting the Three Cases in Dashboard Context
#
# **Budget Case Row:**
# - **Metrics**: 22 experts, δ_max = 2.20, Agreement = "good" (green)
# - **Compromise**: [45.93, 48.67, 49.50] billion CZK, Centroid = 48.03
# - **Centroid chart**: Smooth gradient from ~26 to ~80, most experts clustered 40-55
# - **Membership chart**: Many overlapping light blue triangles, yellow Best Compromise fits naturally
# - **Interpretation**: Exemplary consensus - green cell confirms reliability
# - **Comparison insight**: This is the gold standard scenario in the dashboard
#
# **Floods Case Row:**
# - **Metrics**: 13 experts, δ_max = 5.97, Agreement = "moderate" (yellow/gold)
# - **Compromise**: [10.00, 14.67, 18.25] %, Centroid = 14.31
# - **Centroid chart**: Clear gap between low cluster (0.5-8%) and high cluster (37-47%)
# - **Membership chart**: Separated triangle groups, yellow Best Compromise tries to bridge the gap
# - **Interpretation**: Real disagreement - yellow cell signals caution needed
# - **Comparison insight**: Fewer experts doesn't mean worse quality; the issue is polarization
# - **Notable**: Despite only 13 experts, the bimodal pattern is clearly visible
#
# **Pendlers Case Row:**
# - **Metrics**: 22 experts, δ_max = 5.68, Agreement = "moderate" (yellow/gold)
# - **Compromise**: [27.08, 31.67, 33.29] Likert value, Centroid = 30.68
# - **Centroid chart**: Tight main cluster 24-30, then jump to outlier at ~100
# - **Membership chart**: Massive overlap of triangles around 30-35, one distant triangle at 100
# - **Interpretation**: Misleading moderate rating - actually strong core consensus + outlier
# - **Comparison insight**: Same yellow color as Floods, but very different underlying pattern!
# - **Key lesson**: Table alone isn't enough; visual charts reveal the true story
#
# ### Key Insights from the Dashboard
#
# **Cross-Scenario Patterns:**
#
# 1. **Panel Size ≠ Agreement Quality**:
#    - Budget (22 experts): excellent agreement (δ_max = 2.20)
#    - Floods (13 experts): moderate agreement (δ_max = 5.97)
#    - Pendlers (22 experts): moderate agreement (δ_max = 5.68)
#    - Conclusion: Quality depends on opinion alignment, not just quantity of experts
#
# 2. **Same Agreement Level, Different Causes**:
#    - Floods and Pendlers both show "moderate" agreement (yellow)
#    - But Floods has genuine bimodal disagreement
#    - While Pendlers has tight consensus corrupted by one outlier
#    - The mini-charts clearly distinguish these two situations
#
# 3. **Visual Patterns Predict Agreement Levels**:
#    - Smooth centroid gradients + heavy triangle overlap = good (Budget)
#    - Clustered centroids with gaps + separated triangles = moderate/low (Floods)
#    - Tight cluster with outlier + mostly overlapping triangles = moderate* (Pendlers)
#
# 4. **Best Compromise Positioning**:
#    - Budget: Best Compromise sits naturally in the overlap zone
#    - Floods: Best Compromise bridges between distinct opinion groups
#    - Pendlers: Best Compromise is pulled away from main cluster by outlier
#
# 5. **Uncertainty Ranges Vary**:
#    - Budget: Range = 49.50 - 45.93 = 3.57 billion CZK (~7.7% of centroid)
#    - Floods: Range = 18.25 - 10.00 = 8.25% (~57.7% of centroid)
#    - Pendlers: Range = 33.29 - 27.08 = 6.21 Likert value (~20.2% of centroid)
#    - Relative uncertainty varies significantly across domains
#
# ### Practical Applications
#
# **For Executive Presentations:**
# - Use the dashboard as a single-page summary slide
# - The table provides talking points: "22 experts reached excellent agreement on budget..."
# - The mini-charts provide visual evidence to support the numbers
# - Color-coded agreement column allows instant prioritization
#
# **For Comparative Studies:**
# - Analyze whether certain domains (budgets vs. environmental vs. social) tend to have better consensus
# - Identify whether expert panel composition (size, diversity) correlates with agreement
# - Track changes over time by creating dashboards from multiple rounds of elicitation
#
# **For Method Validation:**
# - Demonstrate that BeCoMe handles diverse scenarios (different scales, units, panel sizes)
# - Show that the method produces interpretable results across all cases
# - Use the dashboard to explain how δ_max relates to visual patterns
#
# **For Stakeholder Communication:**
# - Present all three cases together to show method consistency
# - Use the color coding to frame discussions: "We achieved green-level agreement on..."
# - Mini-charts help non-technical stakeholders understand what "consensus" means visually
#
# **For Research Documentation:**
# - Include the dashboard in papers/reports as a compact summary figure
# - The table provides all key numbers for replication
# - The mini-charts give readers quick visual understanding without reading full-size plots
#
# ### Advantages of the Dashboard Approach
#
# **Information Density:**
# - Consolidates 3 scenarios × 8 metrics = 24 data points in one table
# - Adds 6 mini-charts (3 centroid + 3 membership) for visual context
# - All on a single page/screen - no need to flip between separate visualizations
#
# **Comparative Efficiency:**
# - Side-by-side layout enables direct visual comparison
# - Patterns and anomalies stand out when cases are juxtaposed
# - Faster than examining three separate full-size visualizations
#
# **Multi-Level Analysis:**
# - Table provides exact numerical values for precision
# - Centroid charts show distribution patterns
# - Membership charts show full fuzzy structure
# - Users can drill down from high-level (table) to detailed (charts) as needed
#
# **Accessibility:**
# - Color coding makes key insights (agreement levels) accessible to color-vision
# - Consistent structure helps users quickly orient and find information
# - Mini-charts are simple enough to understand at a glance
#
# **Presentation Ready:**
# - Professional appearance suitable for reports and publications
# - High-resolution export (300 DPI) ensures print quality
# - Self-contained: title, table, and charts tell the full story
#
# ### When to Use This Visualization
#
# **Ideal for:**
# - Comparing multiple expert consensus studies simultaneously
# - Executive summaries requiring comprehensive yet concise presentation
# - Method demonstrations showing BeCoMe performance across diverse scenarios
# - Progress reports tracking multiple ongoing consensus processes
# - Publications requiring a compact multi-scenario summary figure
#
# **Less suitable for:**
# - Deep dive into a single scenario (use full-size visualizations instead)
# - Presentations to audiences who need more explanation of fuzzy concepts
# - Cases with very large numbers of experts (mini-charts become crowded)
# - Situations requiring detailed centroid values for each expert (table doesn't show individuals)
#
# ### Design Rationale
#
# **Why Table First?**
# - Provides context before visuals: readers know what they're looking at
# - Numbers anchor the visual interpretation
# - Color-coded agreement levels create visual hierarchy (green = good catches the eye)
#
# **Why Mini-Charts Instead of Full-Size?**
# - Enables side-by-side comparison in limited space
# - Focus shifts to patterns rather than individual data points
# - Reduces cognitive load: simpler = easier to compare
# - Users can always refer to full-size versions for details
#
# **Why Centroid Charts AND Membership Function Charts?**
# - Centroid charts show simplified 1D distribution (easy to scan)
# - Membership function charts show full fuzzy structure (complete picture)
# - Together they provide both abstraction (centroids) and detail (triangles)
# - Different cognitive styles prefer different representations
#
# **Why Color Code the Agreement Column?**
# - Instant visual scanning: green = good, yellow = caution, red = concern
# - Aligns with universal traffic light metaphor
# - Reduces need to interpret numerical δ_max values
# - Creates visual priority: green scenarios are "safe," yellow need attention
#
# ### Limitations and Considerations
#
# **Information Overload Risk:**
# - Dashboard contains a lot of information in small space
# - First-time viewers may feel overwhelmed
# - Solution: Guide viewers through table first, then charts
#
# **Mini-Chart Resolution:**
# - Compressed charts lose some detail
# - Expert IDs may not be readable in centroid charts
# - Individual expert triangles may be hard to distinguish
# - Solution: Provide full-size versions as backup/appendix
#
# **Fixed Scenario Count:**
# - Current design assumes exactly 3 scenarios
# - More scenarios would require layout redesign
# - Fewer scenarios would leave unused space
# - Solution: Adapt GridSpec layout for different scenario counts
#
# **Metric Selection:**
# - Dashboard shows subset of available metrics
# - Some users might want additional columns (e.g., individual Gamma/Omega values)
# - Adding columns reduces readability
# - Solution: Document that full details are in individual visualizations
#
# **Color Accessibility:**
# - Color-blind individuals may have difficulty with green/yellow/red coding
# - Solution: Agreement column also has text labels ("good"/"moderate"/"low")
#
# ### Customization Options
#
# **For Different Domains:**
# - Adjust units in the table (CZK → USD, % → fraction, etc.)
# - Modify thresholds for agreement levels if domain-specific standards exist
# - Change scenario names to match your context
#
# **For Different Panel Sizes:**
# - Mini-charts automatically adjust to number of experts
# - Very large panels (>50) might need layout tweaks
# - Very small panels (<5) might look sparse
#
# **For Different Numbers of Scenarios:**
# - 2 scenarios: Use 1 row × 2 columns for mini-charts
# - 4 scenarios: Use 2 rows × 2 columns
# - 6 scenarios: Use 2 rows × 3 columns
# - Adjust GridSpec accordingly
#
# **For Different Metrics:**
# - Add/remove columns in the metrics DataFrame
# - Adjust column widths in table creation
# - Ensure total width sums to reasonable value (e.g., 1.0)
#
# ### Technical Notes
# - Figure size: 18 × 12 inches optimized for landscape presentations
# - GridSpec: 3 rows × 3 columns with adjustable spacing (hspace=0.4, wspace=0.3)
# - Table: Uses matplotlib.table with custom styling
# - Header row: Teal background (#4ECDC4), white bold text
# - Agreement cell colors: Light green (#90EE90), gold (#FFD700), light pink (#FFB6C1)
# - Mini-charts: Consistent with full-size versions but compressed
# - Font sizes reduced for mini-charts (8-10pt vs. 10-12pt for full-size)
# - Export: 300 DPI PNG with tight bounding box
# - File naming: "scenario_dashboard.png"
# - Console output: Prints formatted table to terminal after visualization
# - Data source: Uses result objects from BeCoMeCalculator for consistency


# %%
def create_scenario_dashboard():
    """
    Dashboard for comparing all three scenarios
    """
    # Prepare data for metrics table
    scenarios = [
        ("Budget Case", budget_result, len(budget_opinions), "billion CZK"),
        ("Floods Case", floods_result, len(floods_opinions), "%"),
        ("Pendlers Case", pendlers_result, len(pendlers_opinions), ""),
    ]

    metrics_data = []
    for name, result, num_experts, unit in scenarios:
        agreement = calculate_agreement_level(result.max_error, (5.0, 15.0))
        metrics_data.append(
            {
                "Scenario": name,
                "Experts": num_experts,
                "Compromise (Lower)": f"{result.best_compromise.lower_bound:.2f} {unit}",
                "Compromise (Peak)": f"{result.best_compromise.peak:.2f} {unit}",
                "Compromise (Upper)": f"{result.best_compromise.upper_bound:.2f} {unit}",
                "Best Compromise": f"{result.best_compromise.centroid:.2f} {unit}",
                "delta_max": f"{result.max_error:.2f}",
                "Agreement": agreement,
            }
        )

    df_metrics = pd.DataFrame(metrics_data)

    # Create figure with subplots
    fig = plt.figure(figsize=(18, 12))
    gs = GridSpec(3, 3, figure=fig, hspace=0.3, wspace=0.3)

    # Title
    fig.suptitle("BeCoMe Scenario Comparison Dashboard", fontsize=16, fontweight="bold", y=0.88)

    # Metrics table (occupies entire first row)
    ax_table = fig.add_subplot(gs[0, :])
    ax_table.axis("tight")
    ax_table.axis("off")

    table = ax_table.table(
        cellText=df_metrics.values,
        colLabels=df_metrics.columns,
        cellLoc="center",
        loc="center",
        colWidths=[0.15, 0.08, 0.15, 0.15, 0.15, 0.12, 0.08, 0.12],
    )

    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 2.5)

    # Table styling
    for i in range(len(df_metrics.columns)):
        table[(0, i)].set_facecolor("#4ECDC4")
        table[(0, i)].set_text_props(weight="bold", color="white")

    for i in range(1, len(df_metrics) + 1):
        for j in range(len(df_metrics.columns)):
            if j == len(df_metrics.columns) - 1:  # Agreement column
                agreement_level = df_metrics.iloc[i - 1, j]
                if agreement_level == "good":
                    table[(i, j)].set_facecolor("#90EE90")
                elif agreement_level == "moderate":
                    table[(i, j)].set_facecolor("#FFD700")
                else:
                    table[(i, j)].set_facecolor("#FFB6C1")

    # Mini-charts for each scenario
    scenarios_data = [
        (budget_opinions, budget_result, "Budget Case", 0),
        (floods_opinions, floods_result, "Floods Case", 1),
        (pendlers_opinions, pendlers_result, "Pendlers Case", 2),
    ]

    for opinions, result, name, col_idx in scenarios_data:
        # Centroid chart (upper row)
        ax1 = fig.add_subplot(gs[1, col_idx])
        sorted_ops = sorted(opinions, key=lambda x: x.centroid)
        centroids = [op.centroid for op in sorted_ops]

        ax1.bar(range(len(centroids)), centroids, color="steelblue", alpha=0.7, width=0.6)
        ax1.axhline(y=result.best_compromise.centroid, color="#FFD93D", linestyle="--", linewidth=2)
        ax1.set_title(f"{name}\nCentroids", fontsize=10, fontweight="bold")
        ax1.set_xlabel("Experts", fontsize=8)
        ax1.set_ylabel("Value", fontsize=8)
        ax1.tick_params(labelsize=7)
        ax1.grid(True, alpha=0.3, axis="y")

        # Triangular functions chart (lower row)
        ax2 = fig.add_subplot(gs[2, col_idx])

        for op in opinions:
            x = [
                op.opinion.lower_bound,
                op.opinion.peak,
                op.opinion.upper_bound,
                op.opinion.lower_bound,
            ]
            y = [0, 1, 0, 0]
            ax2.fill(x, y, color="lightblue", alpha=0.3, edgecolor="gray", linewidth=0.3)

        # Compromise
        x = [
            result.best_compromise.lower_bound,
            result.best_compromise.peak,
            result.best_compromise.upper_bound,
            result.best_compromise.lower_bound,
        ]
        y = [0, 1, 0, 0]
        ax2.plot(x, y, color="#FFD93D", linewidth=2.5, label="Compromise")

        ax2.set_title("Membership Functions", fontsize=10, fontweight="bold")
        ax2.set_xlabel("Value", fontsize=8)
        ax2.set_ylabel("mu(x)", fontsize=8)
        ax2.tick_params(labelsize=7)
        ax2.legend(fontsize=7)
        ax2.grid(True, alpha=0.3)
        ax2.set_ylim(-0.05, 1.1)

    plt.savefig(
        output_dir / "scenario_dashboard.png",
        dpi=300,
        bbox_inches="tight",
    )
    plt.show()

create_scenario_dashboard()


# %% [markdown]
# ## 2. Visualization #5: Accuracy Gauge Indicator
#
# ### Purpose and Overview
# The Accuracy Gauge Indicator provides an intuitive, at-a-glance assessment of expert
# agreement quality by visualizing δ_max (the key quality metric in BeCoMe) as a
# **speedometer-style gauge** combined with a **horizontal bar chart**. This dual visualization
# allows both technical and non-technical stakeholders to immediately understand whether
# the consensus is strong, moderate, or weak without needing to interpret raw numerical values.
# The gauge uses universally recognized color coding (green/yellow/red) and visual metaphors
# (speedometer zones) to communicate agreement quality instantly.
#
# ### What Does This Visualization Show?
# The visualization translates the abstract concept of δ_max into concrete visual indicators:
#
# **δ_max (delta max)** is the distance between the Gamma (arithmetic mean) and Omega (median)
# centroids. It serves as the BeCoMe method's primary quality indicator:
# - **Low δ_max** (< 5.0) = **Good/High Agreement** - Experts are closely aligned
# - **Medium δ_max** (5.0-15.0) = **Moderate Agreement** - Some divergence exists
# - **High δ_max** (> 15.0) = **Low Agreement** - Experts fundamentally disagree
#
# The visualization makes these thresholds immediately visible through color zones and
# the position of an indicator arrow/bar, enabling instant quality assessment.
#
# ### Visualization Components
#
# The accuracy gauge consists of two complementary plots side-by-side:
#
# **Left Plot - Semicircular Speedometer Gauge:**
#
# 1. **Three Colored Zones (Background):**
#    - **Green zone (Good)**: Right third of semicircle (δ_max < 5.0)
#      - Indicates excellent agreement among experts
#      - Consensus is highly reliable and actionable
#    - **Yellow zone (Moderate)**: Middle third (δ_max 5.0-15.0)
#      - Indicates acceptable but not ideal agreement
#      - Consensus is reasonable but may benefit from further discussion
#    - **Red zone (Low)**: Left third (δ_max > 15.0)
#      - Indicates poor agreement among experts
#      - Consensus is weak; results should be used with caution
#
# 2. **Indicator Arrow:**
#    - Bold colored arrow pointing from the center to the current δ_max position
#    - Arrow color matches the zone it points to (green/yellow/red)
#    - Length extends from center to near the outer arc
#    - Visually similar to a speedometer needle
#
# 3. **Central Metrics Display:**
#    - δ_max value shown prominently below the gauge center
#    - Agreement level text (e.g., "EXCELLENT AGREEMENT", "MODERATE AGREEMENT")
#    - Large, bold font for easy reading from a distance
#
# 4. **Zone Labels:**
#    - Text labels around the semicircle arc
#    - "High (< 5.0)" on the right (green zone)
#    - "Moderate (5.0-15.0)" at the top (yellow zone)
#    - "Low (> 15.0)" on the left (red zone)
#    - Helps viewers understand the thresholds
#
# 5. **Title:**
#    - Case name and "Expert Agreement Quality Indicator"
#    - Identifies which scenario is being assessed
#
# **Right Plot - Horizontal Bar Chart with Thresholds:**
#
# 1. **Colored Bar:**
#    - Single horizontal bar showing the δ_max value
#    - Bar color matches the agreement level (green/yellow/red)
#    - Length proportional to δ_max magnitude
#    - Black outline for definition
#
# 2. **Background Zone Shading:**
#    - Three transparent colored bands matching the thresholds:
#      - Light green: 0 to 5.0 (good zone)
#      - Light yellow: 5.0 to 15.0 (moderate zone)
#      - Light red: 15.0+ (low zone)
#    - Provides context for the bar position
#
# 3. **Threshold Lines:**
#    - Green dashed vertical line at δ_max = 5.0 ("Good Threshold")
#    - Red dashed vertical line at δ_max = 15.0 ("Low Threshold")
#    - Shows the boundaries between quality levels
#
# 4. **Numerical Label:**
#    - δ_max value annotated next to the bar end
#    - Provides exact numerical value for precision
#
# 5. **Legend:**
#    - Identifies the meaning of threshold lines
#    - Helps interpret the visualization
#
# ### How to Interpret the Gauge
#
# **Reading the Speedometer (Left Plot):**
# - Look at where the arrow points on the semicircle
# - **Arrow in green zone** = Strong consensus, high confidence in results
# - **Arrow in yellow zone** = Moderate consensus, results are usable but not optimal
# - **Arrow in red zone** = Weak consensus, consider gathering more expert input
# - The closer the arrow is to the right (green side), the better the agreement
#
# **Reading the Bar Chart (Right Plot):**
# - Check where the bar ends relative to the threshold lines:
#   - **Left of green line** (< 5.0) = Excellent agreement
#   - **Between green and red lines** (5.0-15.0) = Moderate agreement
#   - **Right of red line** (> 15.0) = Poor agreement
# - The shorter the bar, the better the agreement quality
#
# **Comparing Cases:**
# - When viewing multiple gauges side-by-side (all three cases), you can instantly see
#   which scenarios have stronger consensus
# - Cases with arrows pointing right and short bars have better agreement
# - Cases with arrows pointing left and long bars need attention
#
# ### Interpreting the Three Cases
#
# **Budget Case (COVID-19 budget, δ_max = 2.20):**
# - **Speedometer gauge**: Arrow points firmly in the **green zone** (far right)
#   - Positioned at approximately 85-90% of the way to the right edge
#   - Green color signals "EXCELLENT AGREEMENT"
# - **Bar chart**: Very short green bar
#   - Bar extends only to ~2.2, well left of the 5.0 threshold line
#   - Sits comfortably in the light green "good" background zone
# - **Interpretation**:
#   - This is exemplary consensus quality
#   - The δ_max of 2.20 is less than half the "good" threshold
#   - Decision makers can have high confidence in the Best Compromise value
#   - No need for additional expert consultation
#   - The visualization provides strong evidence of agreement to stakeholders
#
# **Floods Case (Arable land reduction, δ_max = 5.97):**
# - **Speedometer gauge**: Arrow points in the **yellow zone** (middle-upper area)
#   - Positioned at approximately 45-50% from the left
#   - Yellow/orange color signals "MODERATE AGREEMENT"
# - **Bar chart**: Medium-length yellow bar
#   - Bar extends to ~6.0, just past the 5.0 green threshold line
#   - Sits in the light yellow "moderate" background zone
#   - Bar length is about 40% of the way to the red threshold at 15.0
# - **Interpretation**:
#   - Agreement is acceptable but not strong
#   - The δ_max of 5.97 is just over the "good" threshold
#   - Results are usable, but decision makers should be aware of moderate disagreement
#   - Consider whether further expert discussion could improve consensus
#   - The bimodal distribution (revealed in other visualizations) explains this moderate score
#   - Proceed with caution and monitor for issues during implementation
#
# **Pendlers Case (Likert scale, δ_max = 5.68):**
# - **Speedometer gauge**: Arrow points in the **yellow zone** (middle area)
#   - Positioned at approximately 50% from the left
#   - Yellow/orange color signals "MODERATE AGREEMENT"
# - **Bar chart**: Medium-length yellow bar
#   - Bar extends to ~5.7, slightly past the 5.0 green threshold
#   - Sits in the light yellow "moderate" background zone
#   - Similar length to Floods case
# - **Interpretation**:
#   - At first glance, agreement appears only moderate (similar to Floods)
#   - However, this is **misleading** - the sensitivity analysis and other visualizations
#     reveal that most experts (18 out of 22) have very tight agreement around 25
#   - The moderate δ_max is inflated by a single outlier at 100
#   - This demonstrates a limitation of δ_max: it can't distinguish between:
#     - Genuine bimodal disagreement (Floods case)
#     - Tight core consensus with a single outlier (Pendlers case)
#   - **Lesson**: Always use the gauge in conjunction with other visualizations
#     (especially centroid charts and sensitivity analysis) for full understanding
#   - The Omega (median) value is more representative of the true consensus here
#
# ### Key Insights from This Visualization
#
# 1. **Instant Quality Assessment**: The gauge provides immediate visual feedback on
#    consensus quality without requiring numerical analysis
#
# 2. **Stakeholder Communication**: Non-technical audiences can understand the color-coded
#    zones (green = good, red = bad) without training in fuzzy mathematics
#
# 3. **Decision Confidence**: The gauge position helps decision makers assess how much
#    confidence to place in the recommended consensus value
#
# 4. **Threshold Transparency**: By showing the 5.0 and 15.0 thresholds explicitly, the
#    visualization makes the quality criteria transparent and verifiable
#
# 5. **Dual Presentation**: Having both a speedometer (intuitive) and bar chart (precise)
#    serves different cognitive styles and communication needs
#
# 6. **Comparative Analysis**: When multiple gauges are shown together, it's easy to
#    rank scenarios by consensus quality at a glance
#
# 7. **Limitations Awareness**: The Pendlers case teaches that δ_max alone doesn't tell
#    the full story - always examine the underlying distribution
#
# ### When to Use This Visualization
#
# **Ideal for:**
# - Executive summaries and presentations to senior leadership
# - Public communication about expert consensus results
# - Dashboard displays monitoring multiple consensus studies
# - Quick screening: determining which cases need deeper investigation
# - Building stakeholder confidence in well-agreed recommendations
#
# **Complement with other visualizations when:**
# - δ_max falls in the "moderate" zone (5-15) - investigate why
# - Presenting to technical audiences who want to see the full distribution
# - δ_max seems inconsistent with qualitative expert feedback
# - Making high-stakes decisions requiring maximum transparency
#
# ### Practical Applications
#
# **For Decision Makers:**
# - Use the gauge in executive reports as a "quality seal"
# - Green gauge = "high confidence recommendation"
# - Yellow gauge = "usable recommendation, monitor implementation"
# - Red gauge = "need more expert input before proceeding"
#
# **For Facilitators:**
# - Show participants the gauge before and after deliberation to demonstrate progress
# - Use color zones to set expectations: "Let's try to reach the green zone"
# - Identify when consensus is "good enough" vs. when more discussion is needed
#
# **For Researchers:**
# - Report δ_max with the gauge visualization for intuitive interpretation
# - Use consistent thresholds (5.0, 15.0) across studies for comparability
# - Document cases where δ_max and qualitative assessment diverge
#
# **For Communicators:**
# - Include the gauge in policy briefs and white papers
# - Use the traffic light metaphor (green/yellow/red) in verbal explanations
# - Combine with simple statements: "Experts showed strong agreement on this issue"
#
# ### Understanding the Thresholds
#
# **Why δ_max < 5.0 is "Good":**
# - In most domains, a distance of 5 units between mean and median centroids indicates
#   that outliers are minimal and opinions are relatively symmetric
# - This threshold has been validated across various expert elicitation studies
# - Below 5.0, the Best Compromise is stable and representative
#
# **Why δ_max > 15.0 is "Low":**
# - A distance of 15+ units suggests significant polarization or bimodal distributions
# - Mean and median diverge substantially, indicating outliers or distinct opinion groups
# - Above 15.0, consensus-building efforts may be needed before acting on results
#
# **Adjusting Thresholds:**
# - The default thresholds (5.0, 15.0) work well for many applications
# - For high-stakes decisions, you might want stricter thresholds (e.g., 3.0, 10.0)
# - For exploratory research, more lenient thresholds (e.g., 7.0, 20.0) may be acceptable
# - Always document and justify threshold choices
#
# ### Advantages of the Gauge Visualization
#
# **Cognitive Benefits:**
# - Leverages familiar speedometer metaphor from everyday experience
# - Color coding aligns with universal traffic light conventions
# - Reduces cognitive load compared to interpreting raw numbers
#
# **Communication Benefits:**
# - Transcends language barriers (visual understanding)
# - Suitable for mixed-expertise audiences
# - Creates memorable impression (easier to recall "green gauge" than "δ_max = 2.20")
#
# **Presentation Benefits:**
# - Visually striking and professional-looking
# - Works well in both print and digital formats
# - Can be understood in seconds, even from across a room
#
# ### Limitations and Considerations
#
# **Over-Simplification:**
# - Reduces complex consensus dynamics to a single metric
# - May mask important nuances (e.g., Pendlers case outlier vs. Floods case bimodality)
# - Should always be used alongside other visualizations, not in isolation
#
# **Threshold Arbitrariness:**
# - The 5.0 and 15.0 thresholds are guidelines, not absolute laws
# - Different domains may require different thresholds
# - Context matters: δ_max = 6 might be acceptable for budget estimates but concerning
#   for safety assessments
#
# **Binary Thinking:**
# - Color zones might encourage "pass/fail" thinking
# - Reality is more nuanced: δ_max = 4.9 isn't meaningfully better than 5.1
# - Viewers should focus on trends and relative values, not just zone boundaries
#
# **Cultural Differences:**
# - Color meanings vary across cultures (though green/red is fairly universal)
# - "Good/moderate/low" labels may need translation or cultural adaptation
#
# ### Technical Notes
# - Left plot is a semicircular gauge spanning 0° to 180° (π radians)
# - Zone boundaries are at π/3 and 2π/3 radians for equal visual division
# - Arrow angle is calculated to position δ_max proportionally within its zone
# - For δ_max values exceeding the scale, the visualization extends the x-axis dynamically
# - The speedometer uses a white inner circle to create the gauge "hole" aesthetic
# - Both plots are generated using matplotlib and saved at 300 DPI for publication quality
# - Consistent with other BeCoMe visualizations in color palette and styling
# - The gauge can be exported as PNG for inclusion in documents and presentations


# %%
def plot_accuracy_gauge(result, title, case_name, thresholds=(5.0, 15.0)):
    """
    Accuracy indicator as gauge (speedometer) for delta_max
    """
    delta_max = result.max_error
    agreement = calculate_agreement_level(delta_max, thresholds)

    # Determine color and range
    # Zones: [0, 1/3] = Low, [1/3, 2/3] = Moderate, [2/3, 1] = Good
    if agreement == "good":
        color = "#2ECC71"  # Green
        # Good zone: gauge_value between 2/3 and 1
        # delta_max=0 → gauge_value=1, delta_max=5 → gauge_value=2/3
        gauge_value = 2 / 3 + (1 / 3) * (1 - delta_max / thresholds[0])
        zone = "EXCELLENT AGREEMENT"
    elif agreement == "moderate":
        color = "#F39C12"  # Orange
        # Moderate zone: gauge_value between 1/3 and 2/3
        # delta_max=5 → gauge_value=2/3, delta_max=15 → gauge_value=1/3
        normalized = (delta_max - thresholds[0]) / (thresholds[1] - thresholds[0])
        gauge_value = 2 / 3 - (1 / 3) * normalized
        zone = "MODERATE AGREEMENT"
    else:
        color = "#E74C3C"  # Red
        # Low zone: gauge_value between 0 and 1/3
        # delta_max=15 → gauge_value=1/3, delta_max→∞ → gauge_value=0
        normalized = min((delta_max - thresholds[1]) / thresholds[1], 1.0)
        gauge_value = (1 / 3) * (1 - normalized)
        zone = "LOW AGREEMENT"

    # Create figure with two plots
    fig = plt.figure(figsize=(14, 6))
    gs = GridSpec(1, 2, figure=fig, width_ratios=[1.2, 1])

    # Plot 1: Gauge (semicircle speedometer)
    ax1 = fig.add_subplot(gs[0])

    # Draw semicircle with zones
    # Zones: low (0-pi/3), moderate (pi/3-2pi/3), good (2pi/3-pi)
    zone_ranges = [
        (0, np.pi / 3, "#E74C3C", "Low"),
        (np.pi / 3, 2 * np.pi / 3, "#F39C12", "Moderate"),
        (2 * np.pi / 3, np.pi, "#2ECC71", "Good"),
    ]

    # Draw outer zones
    for start, end, col, _label in zone_ranges:
        theta_zone = np.linspace(start, end, 100)
        x_outer = np.cos(theta_zone)
        y_outer = np.sin(theta_zone)
        x_inner = 0.7 * np.cos(theta_zone)
        y_inner = 0.7 * np.sin(theta_zone)

        # Create polygon for the zone
        vertices = list(zip(x_outer, y_outer, strict=False)) + list(
            zip(x_inner[::-1], y_inner[::-1], strict=False)
        )
        poly = plt.Polygon(vertices, facecolor=col, alpha=0.3, edgecolor=col, linewidth=0)
        ax1.add_patch(poly)

    # Draw white inner circle once
    theta_inner = np.linspace(0, np.pi, 200)
    x_inner_circle = 0.7 * np.cos(theta_inner)
    y_inner_circle = 0.7 * np.sin(theta_inner)
    ax1.fill(
        [*x_inner_circle, x_inner_circle[-1], x_inner_circle[0]],
        [*y_inner_circle, 0, 0],
        color="white",
        zorder=2,
    )

    # Arrow (indicator)
    angle = np.pi * gauge_value
    arrow_length = 0.85
    ax1.arrow(
        0,
        0,
        arrow_length * np.cos(angle),
        arrow_length * np.sin(angle),
        head_width=0.1,
        head_length=0.1,
        fc=color,
        ec=color,
        linewidth=3,
        zorder=5,
    )

    # Central circle
    circle = plt.Circle((0, 0), 0.15, color="black", zorder=10)
    ax1.add_patch(circle)

    # Text with delta_max value
    ax1.text(
        0,
        -0.3,
        f"delta_max = {delta_max:.2f}",
        ha="center",
        va="top",
        fontsize=18,
        fontweight="bold",
        color="black",
    )
    ax1.text(0, -0.45, zone, ha="center", va="top", fontsize=12, fontweight="bold", color="black")

    # Zone labels
    ax1.text(-0.85, 0.5, "High\n(< 5.0)", ha="center", fontsize=9, color="black", fontweight="bold")
    ax1.text(
        0, 1.05, "Moderate\n(5.0-15.0)", ha="center", fontsize=9, color="black", fontweight="bold"
    )
    ax1.text(0.85, 0.5, "Low\n(> 15.0)", ha="center", fontsize=9, color="black", fontweight="bold")

    ax1.set_xlim(-1.2, 1.2)
    ax1.set_ylim(-0.6, 1.3)
    ax1.set_aspect("equal")
    ax1.axis("off")
    ax1.set_title(
        f"{title}\nExpert Agreement Quality Indicator", fontsize=12, fontweight="bold", pad=20
    )

    # Plot 2: Bar chart with thresholds
    ax2 = fig.add_subplot(gs[1])

    ax2.barh(["delta_max"], [delta_max], color=color, height=0.5, edgecolor="black", linewidth=2)

    # Threshold lines
    ax2.axvline(
        x=thresholds[0], color="#2ECC71", linestyle="--", linewidth=2, label="Good Threshold"
    )
    ax2.axvline(
        x=thresholds[1], color="#E74C3C", linestyle="--", linewidth=2, label="Low Threshold"
    )

    # Background zones
    ax2.axvspan(0, thresholds[0], alpha=0.2, color="#2ECC71")
    ax2.axvspan(thresholds[0], thresholds[1], alpha=0.2, color="#F39C12")
    ax2.axvspan(
        thresholds[1], max(delta_max * 1.2, thresholds[1] * 1.2), alpha=0.2, color="#E74C3C"
    )

    ax2.set_xlabel("delta_max Value", fontsize=11, fontweight="bold")
    ax2.set_title("delta_max Relative to Thresholds", fontsize=12, fontweight="bold")
    ax2.legend(fontsize=9)
    ax2.grid(True, alpha=0.3, axis="x")
    ax2.set_xlim(0, max(delta_max * 1.2, thresholds[1] * 1.2))

    # Value annotation
    ax2.text(
        delta_max + 0.5,
        0,
        f"{delta_max:.2f}",
        va="center",
        fontsize=12,
        fontweight="bold",
        color="black",
    )

    plt.tight_layout()
    plt.savefig(
        output_dir / f"{case_name}_accuracy_gauge.png",
        dpi=300,
        bbox_inches="tight",
    )
    plt.show()


# Plot for all three cases
plot_accuracy_gauge(budget_result, "Budget Case: COVID-19 budget", "budget")
plot_accuracy_gauge(floods_result, "Floods Case: Land reduction", "floods")
plot_accuracy_gauge(pendlers_result, "Pendlers Case: Likert scale", "pendlers")

# %% [markdown]
# ## 3. Conclusions and Results Interpretation
#
# This section synthesizes insights from all visualizations (triangular membership functions,
# centroid charts, interactive sensitivity analysis, scenario dashboard, and accuracy gauges)
# to provide comprehensive interpretations for each case study.
#
# ### Budget Case: COVID-19 Budget Estimation (22 experts)
#
# **Overall Assessment: EXCELLENT CONSENSUS - Highly Reliable Results**
#
# **Key Findings from Visualizations:**
#
# 1. **Triangular Membership Functions Analysis:**
#    - Expert opinions show moderate spread but significant overlap in the 45-60 billion CZK range
#    - Most triangular fuzzy numbers cluster tightly around 50-55 billion CZK
#    - Some experts provided wider triangles (greater uncertainty), others narrower (more confidence)
#    - All three aggregates (Gamma, Omega, Best Compromise) are positioned very close together
#    - The yellow Best Compromise triangle sits naturally in the zone of maximum expert overlap
#
# 2. **Centroid Chart Analysis:**
#    - Expert centroids range from ~26 to ~80 billion CZK (approximately 3× spread)
#    - Distribution shows smooth, gradual increase - no major gaps or distinct clusters
#    - Most experts (approximately 75%) concentrated in the 40-55 billion CZK range
#    - **Aggregated values:**
#      - Arithmetic Mean (Γ): 50.23 billion CZK
#      - Median (Ω): 45.83 billion CZK
#      - Best Compromise (ΓΩMean): 48.03 billion CZK
#    - **δ_max = 2.20** - well below the "good" threshold of 5.0
#    - The three horizontal lines (Gamma, Omega, Compromise) are extremely close together
#    - Gamma slightly above Omega indicates a few higher estimates gently pulling the mean up
#
# 3. **Accuracy Gauge Indicator:**
#    - Speedometer arrow points firmly in the **green zone** (far right, ~85-90% position)
#    - Status: **"EXCELLENT AGREEMENT"**
#    - Bar chart shows very short green bar extending only to 2.2 (less than half the good threshold)
#    - Visual confirmation of outstanding consensus quality
#
# 4. **Sensitivity Analysis (Expected Behavior):**
#    - Removing any single expert should cause δ_max to change by less than 0.5
#    - Best Compromise should remain stable in the 46-50 billion CZK range
#    - Method demonstrates high robustness - consensus doesn't depend on any particular expert
#    - Even removing 3-4 experts simultaneously should maintain δ_max < 5.0
#
# 5. **Dashboard Comparison:**
#    - Green "good" cell in agreement column - only scenario achieving this status
#    - Serves as the **gold standard** among the three cases
#    - Demonstrates that BeCoMe can produce highly reliable consensus with proper expert alignment
#
# **Interpretation:**
#
# The Budget Case represents an **exemplary expert consensus scenario**. Despite having 22 experts
# with individual opinions ranging from 26 to 80 billion CZK, the panel demonstrates remarkable
# agreement when viewed through fuzzy aggregation. The δ_max of 2.20 indicates that the distance
# between the arithmetic mean and median centroids is minimal, suggesting:
# - Opinion distribution is relatively symmetric
# - Few outliers are significantly influencing the results
# - The central tendency is well-defined and stable
#
# The Best Compromise value of **48.03 billion CZK** (with fuzzy range [45.93, 48.67, 49.50])
# represents a **highly reliable consensus estimate** that can be confidently used for decision-making.
# The narrow uncertainty range (approximately 3.57 billion, or ~7.7% of the centroid) further
# confirms the precision of the consensus.
#
# **Practical Implications:**
#
# - **For Decision Makers:** This consensus can be acted upon with high confidence. The green
#   gauge indicator provides strong evidence to stakeholders that expert agreement is solid.
#   Budget planning can proceed using the 48 billion CZK estimate with minimal risk of
#   overlooking significant expert dissent.
#
# - **For Methodology:** The Budget Case demonstrates that BeCoMe performs excellently when
#   expert opinions are naturally aligned. Even with a 3× range in individual centroids,
#   the fuzzy aggregation captures the collective wisdom effectively.
#
# - **No Further Action Needed:** Unlike the other cases, no additional expert consultation,
#   deliberation rounds, or sensitivity testing is required. The consensus is stable and reliable.
#
# **Success Factors:**
#
# What made this case successful?
# - Experts likely shared common information sources and analytical frameworks
# - The COVID-19 budget context may have had clear reference points (previous budgets, economic data)
# - 22 experts provided sufficient diversity while maintaining coherent viewpoints
# - The moderate spread (26-80) was wide enough to capture uncertainty but not so wide as to indicate fundamental disagreement
#
# ### Floods Case: Arable Land Reduction for Flood Prevention (13 experts)
#
# **Overall Assessment: MODERATE CONSENSUS - Results Usable with Caution**
#
# **Key Findings from Visualizations:**
#
# 1. **Triangular Membership Functions Analysis:**
#    - **Greatest spread among all three scenarios** - expert opinions range from near 0% to over 40%
#    - Clear separation into **distinct opinion clusters:**
#      - **Pessimistic group** (0-10%): Experts expecting minimal land reduction
#      - **Moderate group** (10-25%): Mid-range estimates
#      - **Optimistic group** (25-40%+): Experts expecting substantial land reduction
#    - The three aggregates (Gamma, Omega, Compromise) are noticeably separated
#    - Arithmetic mean (red) is pulled toward higher values by the high-estimate cluster
#    - Median (teal) is more conservative, reflecting the lower/middle expert groups
#    - Best Compromise (yellow) attempts to bridge the gap between divergent views
#
# 2. **Centroid Chart Analysis:**
#    - Expert centroids range from ~0.5% to ~47% (nearly **100× spread!**)
#    - Clear **bimodal distribution** - two distinct peaks:
#      - **Low cluster:** 5 experts with centroids 0.5-8%
#      - **High cluster:** 5 experts with centroids 37-47%
#      - **Middle zone:** 3 experts around 14-42% attempting to bridge the gap
#    - Large gap between clusters (8-14%) reveals fundamental disagreement
#    - **Aggregated values:**
#      - Arithmetic Mean (Γ): 20.28%
#      - Median (Ω): 8.33%
#      - Best Compromise (ΓΩMean): 14.31%
#    - **δ_max = 5.97** - just above the "good" threshold (5.0), in moderate range
#    - Wide separation between Gamma (20.28%) and Omega (8.33%) shows asymmetric distribution
#    - Gamma is pulled significantly upward by the high-value cluster
#    - Omega stays closer to the lower cluster, being more robust to high outliers
#
# 3. **Accuracy Gauge Indicator:**
#    - Speedometer arrow points in the **yellow zone** (middle-upper area, ~45-50% position)
#    - Status: **"MODERATE AGREEMENT"**
#    - Bar chart shows medium-length yellow/orange bar extending to ~6.0
#    - Bar just crosses the 5.0 "good" threshold line, landing in moderate zone
#    - Visual warning that consensus quality is acceptable but not strong
#
# 4. **Sensitivity Analysis (Expected Behavior):**
#    - **Moderate sensitivity** due to bimodal distribution
#    - Removing experts from low cluster (0.5-8%) should:
#      - Increase Gamma (mean shifts toward high cluster)
#      - Keep Omega relatively stable or shift slightly up
#      - Potentially increase δ_max (less balance between clusters)
#    - Removing experts from high cluster (37-47%) should:
#      - Decrease Gamma significantly
#      - Omega may shift down slightly
#      - δ_max should decrease (removing outliers reduces apparent disagreement)
#    - Removing middle-range experts (14-42%) should:
#      - Increase δ_max (removes the "bridge" between clusters)
#      - Emphasize the bimodal nature more clearly
#
# 5. **Dashboard Comparison:**
#    - Yellow "moderate" cell in agreement column
#    - Despite having fewer experts (13 vs. 22 in Budget/Pendlers), the issue isn't panel size
#    - The problem is **genuine polarization** - experts fundamentally disagree
#    - Bimodal pattern is clearly visible in mini-charts
#
# **Interpretation:**
#
# The Floods Case represents a **challenging consensus scenario** characterized by genuine expert
# disagreement rather than measurement uncertainty. The bimodal distribution reveals that experts
# hold fundamentally different perspectives on flood prevention's impact on arable land:
#
# - **Low-estimate group** (0.5-8%): May believe flood prevention measures can be implemented with
#   minimal agricultural impact through careful planning, alternative technologies, or that
#   flood-prone land is already marginally productive
#
# - **High-estimate group** (37-47%): May assess that effective flood prevention requires
#   substantial land conversion to wetlands, reservoirs, or buffer zones, significantly reducing
#   agricultural area
#
# - **Middle-ground group** (14-42%): Recognize both perspectives and estimate moderate impacts
#
# The δ_max of 5.97, while only slightly above the "good" threshold, is **nearly 3× higher than
# the Budget Case** (2.20), indicating substantially weaker consensus. The Best Compromise of
# **14.31%** (with range [10.00, 14.67, 18.25]) represents a **mathematical balance** rather than
# a true collective agreement.
#
# **Critical Insight:** The moderate δ_max (5.97) might seem acceptable in isolation, but the
# visualizations reveal it stems from **real disagreement** (two distinct expert groups with
# opposing views) rather than natural measurement variability. This is fundamentally different
# from the Pendlers Case, which has similar δ_max (5.68) but from a different cause (outlier).
#
# **Practical Implications:**
#
# - **For Decision Makers:** Use the 14.31% estimate with **caution and context**. The consensus
#   is not false - it represents a genuine middle ground - but decision makers must understand:
#   - Some experts believe impact could be as low as 0.5-8%
#   - Others believe it could be as high as 37-47%
#   - The "compromise" doesn't mean all experts agree on 14%; it means their divergent views average to this
#   - Consider preparing contingency plans for both low-impact and high-impact scenarios
#
# - **Recommended Actions:**
#   1. **Further Investigation:** Why do experts disagree? Different assumptions about:
#      - Flood prevention technologies to be used?
#      - Regional geography and soil quality?
#      - Time horizons (short-term vs. long-term impacts)?
#      - Definition of "arable land" (current vs. potential)?
#
#   2. **Scenario Planning:** Rather than using a single estimate, develop policies for:
#      - **Low-impact scenario** (8%): What if flood measures are efficient?
#      - **Moderate-impact scenario** (14%): The Best Compromise
#      - **High-impact scenario** (40%): What if extensive land conversion is needed?
#
#   3. **Targeted Deliberation:** Bring low-cluster and high-cluster experts together to:
#      - Identify the root causes of disagreement
#      - Clarify assumptions and share information
#      - Potentially reach better alignment through discussion
#
#   4. **Delphi Method:** Consider a second round of expert elicitation where experts see
#      the aggregate results and others' reasoning, then revise their estimates
#
# - **For Methodology:** The Floods Case demonstrates that δ_max in the 5-15 range should
#   trigger deeper investigation. The BeCoMe method correctly identifies moderate agreement,
#   but stakeholders need to understand this means "proceed with caution" not "proceed with confidence."
#
# **Why This Matters:**
#
# If decision makers only looked at the Best Compromise value (14.31%) without examining the
# visualizations, they might implement policies assuming ~14% land reduction, when in reality:
# - The outcome could be much lower (~5%) if the pessimistic group is correct → policies might be over-cautious
# - The outcome could be much higher (~40%) if the optimistic group is correct → policies might be under-prepared
#
# The **value of the BeCoMe visualizations** is precisely in revealing this underlying disagreement
# that a single consensus number would mask.
#
# **Success Factors for Improvement:**
#
# To improve consensus quality in future similar studies:
# - Ensure all experts work from common definitions (what counts as "arable land"?)
# - Provide shared reference data (current land use maps, flood risk assessments)
# - Clarify the scenario (which flood prevention measures are being evaluated?)
# - Consider separate analyses for different sub-scenarios if fundamental assumptions differ
#
# ### Pendlers Case: Cross-Border Worker Travel Assessment via Likert Scale (22 experts)
#
# **Overall Assessment: MISLEADING MODERATE CONSENSUS - Core Agreement is Strong but Outlier Inflates δ_max**
#
# **Key Findings from Visualizations:**
#
# 1. **Triangular Membership Functions Analysis:**
#    - **Extremely tight agreement** - vast majority of triangular opinions are nearly identical
#    - Almost all experts (approximately 18 out of 22) chose similar lower bounds, peaks, and upper bounds
#    - Triangles cluster very tightly around 30-35 on the Likert scale (0-100)
#    - **BUT:** One clear outlier triangle extends to ~100 (maximum Likert value)
#    - Three aggregates show some separation:
#      - Median (Omega, teal): Stays with main cluster around 25-30
#      - Arithmetic Mean (Gamma, red): Pulled upward toward 36 by the outlier
#      - Best Compromise (yellow): Falls in between at ~31
#    - The outlier creates the **illusion** of moderate consensus when viewed only through δ_max
#
# 2. **Centroid Chart Analysis:**
#    - Most expert centroids **tightly clustered** around 24-26 (extremely narrow range!)
#    - 18 out of 22 experts (82%) have centroids in the 24-30 range (**strong main cluster**)
#    - A few experts provided mid-range estimates around 48-50 (moderate deviation)
#    - One clear **outlier at ~100** (maximum Likert value) - dramatically separated from main cluster
#    - **Aggregated values:**
#      - Arithmetic Mean (Γ): 36.36
#      - Median (Ω): 25.00
#      - Best Compromise (ΓΩMean): 30.68
#    - **δ_max = 5.68** - in the moderate range, similar to Floods Case (5.97)
#    - **Critical difference from Floods:** Despite similar δ_max, the underlying pattern is completely different!
#      - Floods: Genuine bimodal disagreement (two large groups with opposing views)
#      - Pendlers: Tight core consensus (18 experts agree) + one outlier
#    - The outlier pulls Gamma (36.36) significantly higher than Omega (25.00)
#    - Omega (25.00) robustly represents the **true majority consensus**, being immune to the outlier
#
# 3. **Accuracy Gauge Indicator:**
#    - Speedometer arrow points in the **yellow zone** (middle area, ~50% position)
#    - Status: **"MODERATE AGREEMENT"**
#    - Bar chart shows medium-length yellow bar extending to ~5.7
#    - Visually similar to Floods Case
#    - **This is misleading!** The gauge correctly reports δ_max but cannot distinguish:
#      - Genuine disagreement (Floods)
#      - Outlier-corrupted consensus (Pendlers)
#
# 4. **Sensitivity Analysis (Expected Behavior):**
#    - **Main cluster is robust; outlier has disproportionate impact**
#    - Removing experts from main cluster (24-30 centroids) should:
#      - Cause minimal changes in δ_max (maybe ±0.5)
#      - Keep Best Compromise around 30-31
#      - Demonstrate stability of core consensus
#    - **Removing the high outlier (~100) should:**
#      - **Decrease δ_max dramatically** (potentially to < 2.0, similar to Budget Case!)
#      - Decrease Gamma significantly (was artificially pulled up)
#      - Keep Omega nearly unchanged (median is robust to outliers by design)
#      - Shift Best Compromise down toward main cluster consensus
#      - Reveal the **true consensus** hidden by the outlier
#    - Removing mid-range experts (48-50) should have moderate impact
#    - **This sensitivity test is crucial** for understanding the Pendlers Case properly
#
# 5. **Dashboard Comparison:**
#    - Yellow "moderate" cell in agreement column - **same color as Floods**
#    - But mini-charts tell a completely different story:
#      - Pendlers centroid chart: Tight main cluster + outlier
#      - Floods centroid chart: Two separated clusters with gap
#    - Pendlers membership functions: Massive overlap around 30-35 + one distant triangle
#    - Floods membership functions: Clearly separated triangle groups
#    - **Key lesson:** Table/gauge alone insufficient; must examine visual distributions
#
# **Interpretation:**
#
# The Pendlers Case presents a **paradoxical situation** where the δ_max metric (5.68) suggests
# moderate agreement (similar to Floods at 5.97), but the underlying reality is **strong core
# consensus corrupted by a single outlier**. This case demonstrates both the **strengths and
# limitations** of the δ_max metric:
#
# **Strengths demonstrated:**
# - δ_max correctly identifies that something requires attention (moderate yellow zone)
# - The metric works as intended: distance between mean and median signals asymmetry
# - Combined with visualizations, the true pattern becomes clear
#
# **Limitations revealed:**
# - δ_max alone cannot distinguish between:
#   - **Type A moderate consensus:** Genuine bimodal disagreement (Floods)
#   - **Type B moderate consensus:** Outlier-inflated disagreement (Pendlers)
# - A single number loses critical distributional information
# - Without centroid charts and membership functions, the strong core agreement would be missed
#
# The **true consensus** in the Pendlers Case is represented by:
# - **Omega (Median): 25.00** - robust to the outlier, reflects the 82% majority view
# - Main cluster: 18 experts tightly aligned around 24-30
# - If the outlier were removed, δ_max would drop to approximately 1.5-2.0 (excellent range)
#
# The **Best Compromise (30.68)** is mathematically correct as the mean of Gamma and Omega,
# but may **over-weight the outlier**, giving it ~25% influence when it represents only ~4.5%
# of the expert panel (1 out of 22).
#
# **Critical Questions About the Outlier:**
#
# Before making decisions, investigate:
# 1. **Data entry error?** Was 100 accidentally entered instead of 10 or 30?
# 2. **Misunderstanding?** Did this expert misinterpret the Likert scale or question?
# 3. **Unique perspective?** Does this expert have access to information others lack?
# 4. **Legitimate minority view?** Does this represent a valid alternative scenario?
#
# **Practical Implications:**
#
# - **For Decision Makers:**
#   - **Primary recommendation:** Use **Omega (25.00)** as the consensus estimate, NOT Best Compromise (30.68)
#   - The Omega value correctly represents the strong majority agreement
#   - Rationale: When 82% of experts tightly agree (24-30) and 1 expert (4.5%) provides an extreme estimate (100),
#     the median-based approach is more appropriate than the compromise
#   - **Secondary analysis:** Investigate the outlier:
#     - If it's an error or misunderstanding → correct it and recalculate (would yield δ_max ~2.0)
#     - If it's a legitimate alternative view → document it as a minority opinion but don't let it
#       dilute the strong core consensus
#
# - **Recommended Actions:**
#   1. **Verify the outlier:** Contact the expert who provided the ~100 estimate to:
#      - Confirm they meant to rate it that high
#      - Understand their reasoning
#      - Check for any misinterpretation of the scale or question
#
#   2. **Sensitivity documentation:** Report results as:
#      - "With all 22 experts: δ_max = 5.68, moderate agreement, Best Compromise = 30.68"
#      - "With outlier removed (21 experts): δ_max ≈ 1.8, excellent agreement, Best Compromise ≈ 25.5"
#      - "Conclusion: 18 out of 22 experts (82%) demonstrate strong consensus around 25-30"
#
#   3. **Use appropriate aggregate:**
#      - If outlier is verified as legitimate: Use **Median (25.00)** for robustness
#      - If outlier is corrected/removed: Recalculate and use revised Best Compromise
#
#   4. **Policy implications:**
#      - Proceed with confidence based on the 25-30 estimate
#      - The strong core agreement suggests the assessment is reliable
#      - No need for further deliberation rounds (unlike Floods Case)
#
# - **For Methodology:** The Pendlers Case teaches crucial lessons:
#   - **Never rely on δ_max alone** - always examine distributions visually
#   - Moderate δ_max (5-15) can have different causes requiring different responses:
#     - Floods (genuine disagreement) → need deliberation and scenario planning
#     - Pendlers (outlier corruption) → need outlier investigation and robust estimator (median)
#   - The **Omega (median) value is especially valuable** when outliers are present
#   - Sensitivity analysis is not optional - it's essential for proper interpretation
#   - Interactive widgets allow stakeholders to discover these insights themselves
#
# **Comparison with Budget Case:**
#
# If the Pendlers outlier were removed or corrected:
# - Pendlers would likely achieve δ_max ≈ 1.5-2.0 (even better than Budget's 2.20!)
# - Both would be green "excellent agreement" scenarios
# - 22 experts with tight alignment (Pendlers) vs. 22 experts with moderate spread but good alignment (Budget)
#
# **Why This Case is Valuable for Demonstration:**
#
# The Pendlers Case is pedagogically important because it:
# - Shows that BeCoMe handles outliers appropriately (median-based aggregation is robust)
# - Demonstrates the critical value of visualizations beyond summary metrics
# - Teaches analysts to investigate moderate δ_max values rather than accepting them at face value
# - Proves that "moderate agreement" can mean very different things in different contexts
# - Highlights the importance of the full BeCoMe toolkit (not just the final numbers)
#
# ### Cross-Case Comparison and General Observations
#
# **Comparative Summary:**
#
# | Aspect | Budget Case | Floods Case | Pendlers Case |
# |--------|-------------|-------------|---------------|
# | **Experts** | 22 | 13 | 22 |
# | **δ_max** | 2.20 | 5.97 | 5.68 |
# | **Status** | Excellent | Moderate | Moderate* |
# | **Pattern** | Smooth distribution | Bimodal clusters | Tight cluster + outlier |
# | **Γ - Ω spread** | 4.40 CZK | 11.95% | 11.36 Likert value |
# | **True consensus** | Very strong | Weak/divided | Strong (hidden) |
# | **Recommended action** | Proceed confidently | Further deliberation | Use median, verify outlier |
# | **Best aggregate** | Best Compromise | Best Compromise (with caution) | **Omega (Median)** |
#
# **Key Methodological Insights:**
#
# 1. **Panel Size ≠ Agreement Quality**
#    - Budget (22 experts): Excellent (δ_max = 2.20)
#    - Floods (13 experts): Moderate (δ_max = 5.97)
#    - Pendlers (22 experts): Moderate* (δ_max = 5.68, but misleading)
#    - **Conclusion:** Quality depends on opinion alignment, not expert quantity
#    - Having more experts doesn't guarantee better consensus
#    - A smaller aligned panel (Budget) outperforms a larger divided panel
#
# 2. **Same δ_max, Different Meanings**
#    - Floods (5.97) and Pendlers (5.68) both show "moderate agreement"
#    - But causes are fundamentally different:
#      - **Floods:** Real bimodal disagreement between two expert groups
#      - **Pendlers:** Strong core consensus masked by single outlier
#    - **Implication:** Always examine visualizations; numbers alone are insufficient
#
# 3. **Gamma vs. Omega: When Does It Matter?**
#    - **Budget:** Γ (50.23) ≈ Ω (45.83), difference = 4.40 → both are reliable
#    - **Floods:** Γ (20.28) vs Ω (8.33), difference = 11.95 → significant asymmetry
#    - **Pendlers:** Γ (36.36) vs Ω (25.00), difference = 11.36 → outlier influence
#    - **Rule of thumb:** When Γ and Ω differ substantially, Ω (median) is more robust
#
# 4. **Visual Patterns Predict Agreement Levels**
#    - **Excellent (green):** Smooth centroid gradients + heavy triangle overlap → Budget
#    - **Moderate from disagreement (yellow):** Clustered centroids with gaps + separated triangles → Floods
#    - **Moderate from outlier (yellow):** Tight main cluster + distant outlier + mostly overlapping triangles → Pendlers
#    - Each pattern requires different interpretation and action
#
# 5. **The Value of Multiple Visualizations**
#    - **Triangular membership functions:** Show full fuzzy structure, reveal overlap/separation
#    - **Centroid charts:** Simplify to 1D, make clusters and outliers obvious
#    - **Accuracy gauges:** Provide instant quality assessment via color coding
#    - **Dashboard:** Enable cross-case comparison and pattern recognition
#    - **Sensitivity analysis:** Reveal robustness and quantify individual expert influence
#    - **Together:** They provide a complete picture that no single visualization can offer
#
# 6. **BeCoMe Method Robustness**
#    - **Handles diverse scenarios:** Different scales (CZK, %, Likert), units, domains
#    - **Robust to outliers:** Median-based aggregation (Omega) provides stability
#    - **Balanced compromise:** GammaOmegaMean combines mean (sensitive) and median (robust)
#    - **Transparent quality metrics:** δ_max provides clear, interpretable quality indicator
#    - **Self-diagnostic:** Visualizations reveal when consensus is strong vs. weak vs. corrupted
#
# 7. **Uncertainty Quantification**
#    - Budget: Range = 3.57 billion (~7.7% of centroid) - **low uncertainty**
#    - Floods: Range = 8.25% (~57.7% of centroid) - **high uncertainty**
#    - Pendlers: Range = 6.21 Likert value (~20.2% of centroid) - **moderate uncertainty** (inflated by outlier)
#    - The fuzzy range [lower, peak, upper] captures collective uncertainty better than confidence intervals
#
# **General Observations About the BeCoMe Method:**
#
# 1. **Method is Robust to Outliers**
#    - Demonstrated clearly in Pendlers Case
#    - Median (Omega) remains stable when outliers are present
#    - Best Compromise balances sensitivity (Gamma) and robustness (Omega)
#    - Sensitivity analysis allows quantification of individual expert influence
#    - Users can test "what if we remove this expert?" scenarios interactively
#
# 2. **Visualizations Enable Informed Decision-Making**
#    - Numbers alone (δ_max, Best Compromise) are necessary but insufficient
#    - Triangular membership functions reveal the full fuzzy structure
#    - Centroid charts make distribution patterns immediately obvious
#    - Accuracy gauges provide instant quality assessment for non-technical stakeholders
#    - Dashboard enables rapid cross-scenario comparison
#    - Together, they transform raw expert opinions into actionable insights
#
# 3. **Interactive Elements Increase Transparency**
#    - Sensitivity analysis widgets allow stakeholders to explore results themselves
#    - Real-time recalculation builds understanding of how aggregation works
#    - Checkboxes for expert inclusion/exclusion democratize the analysis
#    - Seeing δ_max change as experts are removed builds intuition about robustness
#    - Interactive exploration increases stakeholder buy-in and trust in results
#
# 4. **Method Scales Across Contexts**
#    - Successfully handles different domains: budget estimation, environmental impact, social assessment
#    - Works with varying panel sizes: 13 (Floods) to 22 (Budget/Pendlers) experts
#    - Accommodates different scales: billions of CZK, percentages, Likert scales
#    - Produces consistent, interpretable results across all scenarios
#    - Quality metrics (δ_max thresholds) transfer across contexts
#
# 5. **Practical Recommendations for Using BeCoMe:**
#
#    **For Practitioners:**
#    - Always examine all visualizations, not just summary statistics
#    - Use δ_max as a screening tool: < 5 (green) = proceed, 5-15 (yellow) = investigate, > 15 (red) = reconsider
#    - When δ_max is moderate (5-15), determine whether it's from:
#      - Genuine disagreement (like Floods) → need deliberation
#      - Outlier corruption (like Pendlers) → use median, verify outliers
#    - Prefer Omega (median) when Gamma and Omega differ substantially
#    - Document sensitivity analysis results to demonstrate robustness
#    - Present multiple visualizations to stakeholders for comprehensive understanding
#
#    **For Researchers:**
#    - BeCoMe provides a complete framework for fuzzy expert aggregation
#    - δ_max serves as a quantitative quality metric for meta-analysis
#    - Centroid distributions can reveal cognitive biases or information asymmetries
#    - Sensitivity analysis enables systematic robustness testing
#    - The method's transparency aids in peer review and replication
#
#    **For Decision Makers:**
#    - Green gauge (δ_max < 5): High confidence - proceed with consensus estimate
#    - Yellow gauge (δ_max 5-15): Moderate confidence - investigate before proceeding
#    - Red gauge (δ_max > 15): Low confidence - seek additional expert input or scenario planning
#    - Always request visualizations alongside numerical results
#    - Use sensitivity analysis to test "what if" scenarios before finalizing decisions
#
# **Future Directions:**
#
# Based on these three case studies, promising extensions include:
# - Automated outlier detection algorithms to flag cases like Pendlers
# - Adaptive thresholds for δ_max based on domain-specific requirements
# - Clustering algorithms to automatically identify opinion groups (like Floods bimodal pattern)
# - Integration with Delphi method for iterative consensus improvement
# - Machine learning models to predict consensus quality from initial expert opinions
# - Expanded visualizations for larger expert panels (>50 experts)
# - Real-time collaborative platforms where experts can see aggregate results and revise estimates
#
# **Conclusion:**
#
# The three case studies demonstrate that the BeCoMe (Best Compromise Method) provides a **robust,
# transparent, and practical framework** for expert consensus aggregation. The combination of:
# - Fuzzy number representation (captures uncertainty)
# - Dual aggregation (mean + median)
# - Quality metrics (δ_max)
# - Comprehensive visualizations (membership functions, centroids, gauges, dashboards)
# - Interactive sensitivity analysis
#
# ...creates a powerful toolkit that goes beyond simple averaging to provide **deep insights into
# the structure, quality, and reliability of expert consensus**.
#
# The key lesson across all cases: **Numbers provide answers, but visualizations provide understanding.**
# The BeCoMe method's strength lies not just in calculating a "best compromise" value, but in
# revealing the full landscape of expert opinion, enabling informed, confident decision-making
# even in the presence of uncertainty, disagreement, or outliers.
