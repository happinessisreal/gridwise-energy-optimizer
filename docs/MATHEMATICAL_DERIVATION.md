# Mathematical Derivation & Proof of Global Optimality

**GridWise Smart Campus Energy Optimizer**  
*BUP CSE Fest 2026 Hackathon · Technical Reference Document*

---

This document presents the formal mathematical derivation of the GridWise microgrid optimization formulation and provides the analytical proof establishing why this algorithm deduces the **provably global minimum cost**.

---

## 1. Discrete-Time Microgrid Dynamic System

Consider a 24-hour dispatch horizon discretized into hourly intervals $h \in \mathcal{H} = \{0, 1, \dots, 23\}$. At each interval $h$:
- $D[h] \ge 0$: Campus electrical demand ($\text{kWh}$)
- $S[h] \ge 0$: Rooftop solar PV generation forecast ($\text{kWh}$)
- $T[h] > 0$: Time-of-Use grid import tariff ($\text{BDT/kWh}$)
- $E[h] \ge 0$: State of energy in the battery storage system at the start of hour $h$ ($\text{kWh}$)

### Battery State Evolution
The battery energy evolution is governed by the discrete difference equation:
$$E[h+1] = E[h] + c[h] - d[h], \quad E[0] = E_0$$
where $c[h] \ge 0$ is the charging energy and $d[h] \ge 0$ is the discharging energy in hour $h$. Unrolling this recurrence for any hour $h \in \{0, \dots, 23\}$ yields:
$$E[h] = E_0 + \sum_{i=0}^{h-1} (c[i] - d[i])$$

---

## 2. Decision Space & Linear Program (LP) Formulation

We define a 96-dimensional decision vector $\mathbf{x} \in \mathbb{R}^{96}$ decomposed into 24 block vectors $\mathbf{x}_h = \big[ g[h], s[h], c[h], d[h] \big]^T \in \mathbb{R}^4$:
$$\mathbf{x} = \big[ g[0], s[0], c[0], d[0], \; g[1], s[1], c[1], d[1], \; \dots, \; g[23], s[23], c[23], d[23] \big]^T$$

### 2.1. Objective Function Formulation
The operational goal is to minimize total energy purchase cost in BDT while prioritizing zero-marginal-cost renewable energy and preventing battery degradation from simultaneous charging and discharging:
$$\min_{\mathbf{x}} f(\mathbf{x}) = \sum_{h=0}^{23} \Big[ T[h] \cdot g[h] - 10^{-6} \cdot s[h] + 10^{-7} \cdot (c[h] + d[h]) \Big] = \mathbf{c}^T \mathbf{x}$$
where $\mathbf{c} \in \mathbb{R}^{96}$ is the cost vector:
$$\mathbf{c}_{4h : 4h+3} = \Big[ T[h], \; -10^{-6}, \; 10^{-7}, \; 10^{-7} \Big]^T$$

### 2.2. Equality Constraints ($A_{\text{eq}} \mathbf{x} = \mathbf{b}_{\text{eq}} \in \mathbb{R}^{25}$)
- **Campus Power Balance (24 constraints)**: Kirchhoff's current conservation at the central campus AC bus:
  $$g[h] + s[h] + d[h] - c[h] = D[h], \quad \forall h \in \mathcal{H}$$
- **End-of-Day Battery Neutrality (1 constraint)**: Ensures the microgrid does not deplete stored reserves overnight, preserving long-term cycle sustainability:
  $$E[24] = E_0 \iff \sum_{h=0}^{23} (c[h] - d[h]) = 0$$

### 2.3. Inequality Constraints ($A_{\text{ub}} \mathbf{x} \le \mathbf{b}_{\text{ub}} \in \mathbb{R}^{48}$)
Substituting the unrolled battery energy recurrence $E[h+1] = E_0 + \sum_{i=0}^h (c[i] - d[i])$ into physical operational limits:
- **Maximum Storage Capacity**: $E[h+1] \le C_{\text{battery}}$
  $$\sum_{i=0}^h (c[i] - d[i]) \le C_{\text{battery}} - E_0, \quad \forall h \in \mathcal{H}$$
- **Dynamic Emergency Reserve Floor**: $E[h+1] \ge \max\big(R_{\text{base}}, R_{\text{directive}}[h]\big)$
  $$-\sum_{i=0}^h (c[i] - d[i]) \le E_0 - \max\big(R_{\text{base}}, R_{\text{directive}}[h]\big), \quad \forall h \in \mathcal{H}$$

### 2.4. Continuous Box Bounds ($\mathbf{l} \le \mathbf{x} \le \mathbf{u}$)
- **Grid Power Import**: $0 \le g[h] \le G_{\max}[h]$ (where $G_{\max}[h]$ is capped during `max_grid_window` directives, otherwise $+\infty$). Zero export allowed ($g[h] \ge 0$).
- **Solar Curtailment**: $0 \le s[h] \le S_{\text{eff}}[h] = S[h] \times \text{factor}[h]$ (governed by `solar_reduction`).
- **Inverter Limits**: $0 \le c[h] \le C_{\max}[h]$ (with $C_{\max}[h] = 0$ during `no_charge_window`), $0 \le d[h] \le D_{\max}[h]$ (with $D_{\max}[h] = 0$ during `no_discharge_window`).

---

## 3. Analytical Proof of Global Optimality

Why does the GridWise solver guarantee the **absolute global minimum cost** rather than a sub-optimal heuristic solution?

### Theorem 1 (Convexity of the Feasible Domain)
The feasible search space $\mathcal{F} \subset \mathbb{R}^{96}$ is defined by:
$$\mathcal{F} = \Big\{ \mathbf{x} \in \mathbb{R}^{96} \;\Big|\; A_{\text{eq}}\mathbf{x} = \mathbf{b}_{\text{eq}}, \; A_{\text{ub}}\mathbf{x} \le \mathbf{b}_{\text{ub}}, \; \mathbf{l} \le \mathbf{x} \le \mathbf{u} \Big\}$$
**Proof**:
1. Every equality constraint $A_{\text{eq}, k} \mathbf{x} = b_{\text{eq}, k}$ defines an affine hyperplane $\mathcal{H}_k$, which is a convex set.
2. Every inequality constraint $A_{\text{ub}, j} \mathbf{x} \le b_{\text{ub}, j}$ and coordinate bound $l_i \le x_i \le u_i$ defines a closed half-space $\mathcal{S}_j$, which is a convex set.
3. The intersection of finitely many hyperplanes and closed half-spaces:
   $$\mathcal{F} = \bigcap_{k=1}^{25} \mathcal{H}_k \;\cap\; \bigcap_{j=1}^{48} \mathcal{S}_j \;\cap\; \prod_{i=1}^{96} [l_i, u_i]$$
   is by definition a **convex polyhedron (polytope)**. Because lower and upper bounds are finite on $s, c, d$ and demand is finite, $\mathcal{F}$ is non-empty and compact. $\blacksquare$

### Theorem 2 (Absence of Local Optima)
For any convex optimization problem $\min_{\mathbf{x} \in \mathcal{F}} f(\mathbf{x})$ where $f(\mathbf{x}) = \mathbf{c}^T \mathbf{x}$ is linear:
**Proof**:
Suppose $\mathbf{x}^* \in \mathcal{F}$ is a local minimum, but there exists $\mathbf{y} \in \mathcal{F}$ such that $f(\mathbf{y}) < f(\mathbf{x}^*)$. By convexity of $\mathcal{F}$, for every $\lambda \in (0, 1]$, the convex combination $\mathbf{z}_\lambda = (1 - \lambda)\mathbf{x}^* + \lambda \mathbf{y} \in \mathcal{F}$.
By linearity of $f$:
$$f(\mathbf{z}_\lambda) = (1 - \lambda) f(\mathbf{x}^*) + \lambda f(\mathbf{y}) < (1 - \lambda) f(\mathbf{x}^*) + \lambda f(\mathbf{x}^*) = f(\mathbf{x}^*)$$
As $\lambda \to 0^+$, $\|\mathbf{z}_\lambda - \mathbf{x}^*\| \to 0$, contradicting the assumption that $\mathbf{x}^*$ is a local minimum in any open $\varepsilon$-ball $B_\varepsilon(\mathbf{x}^*)$. Therefore, **every local minimum is strictly a global minimum**. $\blacksquare$

### Theorem 3 (Simplex Exactness & Duality Certificate)
By the **Fundamental Theorem of Linear Programming**, if a linear program has an optimal solution, at least one optimal solution occurs at an **extreme point (vertex)** of the polytope $\mathcal{F}$.
SciPy's **HiGHS dual revised simplex solver** traverses basic feasible solutions along edges of $\mathcal{F}$. Upon termination, it satisfies the **Karush-Kuhn-Tucker (KKT) conditions** and strong duality:
$$\mathbf{c}^T \mathbf{x}^* = \mathbf{b}_{\text{eq}}^T \mathbf{y}^* + \mathbf{b}_{\text{ub}}^T \mathbf{w}^*$$
with zero duality gap ($\text{Gap} = 0$). This provides an indisputable mathematical certificate that no energy schedule exists with a lower electricity cost in BDT.

### Theorem 4 (Elimination of Simultaneous Churn / Anti-Degeneracy)
In physical microgrids, simultaneous charging ($c[h] > 0$) and discharging ($d[h] > 0$) at the same hour would cause false battery wear without net power flow.
**Proof**:
Let $c[h] = \Delta + \delta_c$ and $d[h] = \Delta + \delta_d$ where $\Delta = \min(c[h], d[h]) > 0$.
The net battery contribution to campus energy balance is $d[h] - c[h] = \delta_d - \delta_c$, which is invariant to $\Delta$.
However, the objective function includes $+10^{-7} (c[h] + d[h]) = 10^{-7} (\delta_c + \delta_d + 2\Delta)$.
Because $10^{-7} > 0$, any candidate solution with $\Delta > 0$ strictly increases cost by $2 \cdot 10^{-7} \Delta > 0$.
Therefore, the HiGHS simplex optimizer strictly drives $\Delta = 0$, guaranteeing:
$$c[h] \cdot d[h] = 0, \quad \forall h \in \mathcal{H}$$
Eliminating battery churn unconditionally without needing non-linear integer variables. $\blacksquare$
