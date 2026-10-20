# Cahier des charges — MecaStruct_RdM_Pro (fourni par l'utilisateur)

> Texte du « Master Prompt » fourni par l'utilisateur. L'architecture effective (fichiers, signatures,
> conventions) est fixée par `ARCHITECTURE.md`, qui prime en cas de divergence de forme. Le fond
> (formules, méthodes, données, tracés) ci-dessous doit être intégralement couvert.

## Organisation et méthodes (synthèse)

| Module | Rôle et base de données | Méthode 1 : analytique / approchée | Méthode 2 : intégrale / exacte (`syms`, `integral`) | Méthode 3 : énergétique / tabulée / matricielle |
| --- | --- | --- | --- | --- |
| DataManager | Matériaux (E, G, ν, Re, Rm, α, P_adm), profilés (IPN, IPE, HEA, HEB, UPN, UAP), fiches de formules LaTeX | Lecture des caractéristiques tabulées (Iz, Iy, S, rz, ry) et calcul de G = E/(2(1+ν)) | — | Table des intégrales de Mohr ∫ Mf^i Mf^j ds et abaques Kt |
| GeometryEngine | Sections standard (rectangle, disque, couronne) ou quelconques | Formules fermées (Iz = bh³/12, Iz = πD⁴/64(1−m⁴), m = d/D), Huygens I_O1z1 = I_Gz + S d_y² | Intégration surfacique (dS = dy dz ou r dr dθ) : zG, yG, I_Gz = ∬ y² dS, I_Gy = ∬ z² dS, Ix = ∬ r² dS | Rayons de giration, facteurs de forme k, sections réduites k_y S |
| BeamSolver | Liaisons 2D/3D, PFS, treillis, torseur de cohésion | Coupures analytiques par morceaux (somme des torseurs à droite ou à gauche) | Intégration des équations d'équilibre : T_y(s) = ∫ q ds, M_fz(s) = −∫ T_y ds | Méthode des nœuds matricielle ; Ménabréa ∂U/∂Y_C = 0 |
| Stress/Displacement | σxx, τxy, τθx, P_matage ; ΔL, φ(s), v(s), α(s) | τ_moy = T/S, τ_max = k T/S ; méthode des aires et moment des aires | Jourawski σyx(y) = T_y/(I_z b(y)) ∫ y dS ; E I v'' = M_fz | U = ∫ dU/ds ds, Clapeyron, Castigliano, forces unités, intégrales de Mohr |
| Buckling | Instabilité suivant min(Iz, Iy) | Rankine (20 ≤ λ < λlim) : P_R = σe S/(1 + (λ/λlim)²) | v'' + k² v = N_B/(E Iz), k² = Pc/(E Iz) → P_E = π² E I/L'² | Arbre de décision λ = L'/r, λlim = π√(E/σe) |
| LocalTensorMohr | Analyse locale, Mohr, critères, extensométrie | σ(θ), τ(θ), centre δ et rayon ρ | det(σ − σi I) = 0 : σi³ − I1 σi² + I2 σi − I3 = 0 | Tresca (σI − σIII ≤ σe/s), Von Mises, Hooke 3D {ε} = [S]{σ}, rosettes |

## Module 1 — Base de données et formulaire

- **Matériaux** : aciers d'usage général (E = 190 GPa, Re = 185 à 355 MPa, Rm = 290 à 490 MPa) ; aciers de
  construction mécanique XC 38, XC 42, XC 48 (E = 210 GPa, G = 80 GPa, ν = 0,3, α = 10 à 12,5·10⁻⁶ °C⁻¹) ;
  alliages d'aluminium 2017 et 5356 (E = 90 GPa, G = 32 GPa, Re = 200 à 220 MPa, Rm = 300 à 320 MPa,
  α = 22,5 à 24·10⁻⁶) ; titane TA6V (E = 116 GPa, Re = 100 à 120 MPa, Rm = 300 à 350 MPa,
  α = 8,5 à 9,5·10⁻⁶) ; fontes FGL/FGS (G = 40 GPa), laiton (G = 34 GPa), Plexiglas (G = 11 GPa, voir note
  d'ARCHITECTURE.md).
- Constante manquante des matériaux isotropes : G = E/(2(1+ν)).
- Table des pressions admissibles de matage P_adm de 0,5 MPa à 150 MPa selon la liaison (clavette, arbre
  cannelé glissant sous charge ou sans charge, fixe) et les conditions de fonctionnement (médiocres,
  moyennes, très bonnes).
- Catalogue de profilés : h, b, a, e, S, Iz, Iy, rz, ry pour IPN (80 à 300), IPE, HEA, HEB, UPN, UAP ; ajout
  utilisateur de matériaux et profilés dans un `.mat`.
- Formulaire rapide : à la sélection d'un module, fiche de toutes les formules en LaTeX avec définition des
  variables et unités SI (Pa, m, N, rad).

## Module 2 — Géométrie des sections droites

- **Méthode A (analytique + Huygens)** : rectangle (S = bh, Iz = bh³/12, Iy = hb³/12) ; disque
  (S = πD²/4, Iz = Iy = πD⁴/64, Ix = πD⁴/32) ; couronne (m = d/D : S = πD²/4 (1−m²), Iz = Iy = πD⁴/64 (1−m⁴),
  Ix = πD⁴/32 (1−m⁴)) ; sections composées I, T, U, L : barycentre par moments statiques
  zG = M_O1y1/S, yG = M_O1z1/S, puis Huygens I_Gz = Σ (I_Giz_i + S_i d_yi²), I_Gy = Σ (I_Giy_i + S_i d_zi²).
- **Méthode B (intégration exacte symbolique/numérique)** : bornes y(z) ou r(θ), dS = dy dz ou r dr dθ :
  S = ∬ dS ; M_O1z1 = ∬ y1 dS ; M_O1y1 = ∬ z1 dS ; I_Gz = ∬ y² dS ; I_Gy = ∬ z² dS ; Ix = ∬ r² dS = I_Gz + I_Gy.
- Rayons de giration rz = √(I_Gz/S), ry = √(I_Gy/S) ; facteur de forme k (3/2 rectangle, 4/3 disque,
  4/3 (1 + rR/(r²+R²)) tube, S/S_âme poutre en I) ; coefficient de section réduite k_y (5/6 rectangle,
  6/7 disque, 1/2 tube mince, S_âme/S poutre en I).

## Module 3 — Équilibre, treillis, efforts intérieurs

- **Treillis 2D/3D** : barres bi-articulées (traction/compression N_i), charges nodales ; méthode des nœuds
  (Σ F = 0 sur i et j à chaque nœud) sous forme [A]{N} = {F} ; tableau : N_x, nature (N > 0 traction,
  N < 0 compression), σxx, ΔL.
- **Poutres** : liaisons (appui simple/ponctuel, rotule/articulation, pivot, pivot glissant, encastrement) ;
  forces ponctuelles F_i, couples M_i, charges réparties q(s) (uniformes ou polynomiales).
- Degré d'hyperstatisme h ; h = 0 : PFS en A (Σ F = 0, Σ M_A = 0, transport M_A = M_B + AB ∧ R_B) ;
  h ≥ 1 : Ménabréa (∂U/∂R_i = 0).
- Torseur des actions intérieures {T_int D/G}_M = {T_ext DROITE}_M = −{T_ext GAUCHE}_M,
  S_M = [N_x, T_y, T_z]ᵀ, M_M = [M_tx, M_fy, M_fz]ᵀ, par :
  1. coupures (zones, discontinuités avant/après effort ponctuel, avant/dans/après charge répartie,
     équations symboliques par morceaux en s) ;
  2. relations différentielles et intégrales : q_y = dT_y/ds ⇒ T_y = ∫ q_y ds ; T_y = −dM_fz/ds ⇒
     M_fz = −∫ T_y ds ; T_z = dM_fy/ds ⇒ M_fy = ∫ T_z ds ; intégration sur [s, L] des charges réparties :
     S_M = ∫_s^L −q(x) dx j, M_M = ∫_s^L MG ∧ (−q(x) dx j).

## Module 4 — Dimensionnement multi-méthodes

1. **Traction/compression (+ thermique)** : σxx = N/S0 ; Kt = σmax/σnom ⇒ σmax = Kt N/S0 ≤ σe/s ;
   εxx = σxx/E + αΔT ; εyy = εzz = −ν σxx/E + αΔT ; ΔV/V0 = (1 − 2ν) ΔL/L0 ; ΔL ≤ ΔLmax par 3 méthodes :
   analytique ΔL = L0 N/(E S0) + αΔT L0, raideur K = E S0/L0 ; intégrale ΔL = ∫_0^L0 (N(x)/(E S(x)) + αΔT(x)) dx ;
   énergétique U = ∫ ½ N²/(E S) ds puis Castigliano ΔL = ∂U/∂F.
2. **Cisaillement et matage** : τ_moy = T/S_cis ; τ_max = k T/S ≤ τe/s (τe = σe/2 Tresca ou σe/√3 Von Mises) ;
   γ = Δy/Δx = τ/G ; Jourawski σyx(y) = T/(Iz b(y)) ∫_S(y) y dS (rectangle : 6T/(bh³) (h²/4 − y²) =
   3/2 T/S [1 − (2y/h)²]) ; matage P = F/S_matée ≤ P_adm ; clavette P = 4C/(D b L) ≤ P_adm et
   τ = 2C/(a L D) ≤ τe ; rivet/goupille P = 2F/(d e) ≤ P_adm et τ = 4F/(π d²) ≤ τe.
3. **Torsion** : θ = dφ/ds = M_t/(G Ix) ≤ θ̄ ; K = G Ix/L ; φ(L) analytique (M_t L/(G Ix)), intégrale
   (∫ M_t/(G Ix) ds), énergétique (U = ∫ ½ M_t²/(G Ix) ds ⇒ φ = ∂U/∂C) ; τ(r) = M_t r/Ix, max en D/2 ;
   τmax = Kt M_t/Ix D/2 ≤ τe/s.
4. **Flexion** : σxx = N/S − Mfz y/I_Gz + Mfy z/I_Gy ; |σmax| = Kt |σnom| ≤ σe/s. Flèche f = |v_max| ≤ f̄ et
   rotations α = dv/ds par 4 méthodes :
   1. différentielle : E I v_k'' = M_fz,k, double intégration par tronçon, 2n constantes via conditions aux
      limites (v = 0 ou v' = 0) et continuité (v_k = v_k+1, v_k' = v_k+1') ;
   2. aires et moment des aires : α_Q − α_P = (1/EI) ∫_P^Q M ds ; f = (1/EI) |∫_0^L (L − s) M ds| = aire × bras de levier ;
   3. énergétique (Castigliano, charge fictive, forces unités) : U = ∫ (½N²/(ES) + ½T_y²/(k_y G S) +
      ½T_z²/(k_z G S) + ½M_t²/(G Ix) + ½M_fy²/(E Iy) + ½M_fz²/(E Iz)) ds ;
      q_i = (∂U/∂Φ)_Φ=0 = ∫ M^P M̄¹/(E Iz) ds + ∫ T^P T̄¹/(k_y G S) ds ; Maxwell-Betti s_ij = s_ji ;
   4. tabulée (intégrales de Mohr) : ∫ M_i M_j ds par formes élémentaires (rectangle, triangle, trapèze,
      parabole), ex. ⅓ M1 M3 l, M3/6 (2M1 + M2) l.
5. **Flambage** : I_min = min(Iz, Iy), r_min = √(I_min/S) ; L' : encastrée-libre 2L, articulée-articulée L,
   encastrée-articulée L/√2, encastrée-encastrée L/2 ; λ = L'/r_min, λlim = π√(E/σe) ; compression
   (λ < 20) P_C = σe S ; Euler (λ ≥ λlim) v'' + Pc/(E I_min) v = 0, v = B sin(π s/L'),
   P_E = π² E I_min/L'², σ_E = π² E/λ² ; Rankine (20 ≤ λ < λlim) 1/P_R = 1/P_E + 1/P_C,
   P_R = σe S/(1 + (λ/λlim)²).

## Module 5 — Analyse locale, Mohr, critères

- Tenseur σ (saisie ou import du point le plus sollicité) ; facette n : C_n = σ·n, σ = C_n·n, τ = C_n·t ;
  2D : σ(θ) = (σxx+σyy)/2 + (σxx−σyy)/2 cos 2θ + σxy sin 2θ, τ(θ) = −(σxx−σyy)/2 sin 2θ + σxy cos 2θ.
- Invariants I1 = tr σ, I2 = (σxxσyy − σxy²) + (σxxσzz − σxz²) + (σzzσyy − σyz²), I3 = det σ ;
  σi³ − I1 σi² + I2 σi − I3 = 0 ; σI ≥ σII ≥ σIII ; directions (σ − σi I) n_i = 0 ; τmax = (σI − σIII)/2.
- Critères : contrainte normale max (fragiles) max|σi| ≤ σR ; Tresca σI − σIII ≤ σe/s ; Von Mises
  σeq = 1/√2 √((σI−σII)² + (σII−σIII)² + (σIII−σI)²) ≤ σe/s (plan : √(σI² − σIσII + σII²)).
- Hooke généralisée : [S], [C] en 3D isotrope, contraintes planes, déformations planes
  (εzz = 0 ⇒ σzz = ν(σxx+σyy)), orthotrope (9 constantes).
- Extensométrie : ΔR/R = K ε ; pont de Wheatstone (quart, demi, complet) ; rosette à 45° (εxx = ε1,
  εyy = ε2, εxy = ½γxy = ε3 − (ε1+ε2)/2).

## Exigences graphiques

Graphiques interactifs (datacursor, grilles, légendes LaTeX, export PNG/PDF) :
1. schéma de la poutre/treillis (appuis, forces, charges réparties, réactions) ;
2. diagrammes N, Ty, Tz, Mt, Mfy, Mfz alignés verticalement sur s ∈ [0, L], extrema marqués ;
3. rotation α(s) et déformée v(s) : courbe exacte, courbe avec effort tranchant (Castigliano), poutre non
   déformée ;
4. cartographie de la section : géométrie, G, axes principaux, σxx(y) linéaire, σyx(y) parabolique ;
5. courbe de flambage σcr(λ), λ ∈ [0, 300] : palier σe, hyperbole d'Euler, Rankine, point de fonctionnement ;
6. tricercle de Mohr (contraintes et déformations ; δ, ρ, A(σxx, σyx), B(σyy, −σxy), 2θ) et lieu de
   plasticité 2D (σI, σII) : hexagone de Tresca, ellipse de Von Mises, point représentatif.

## Consignes

Code MATLAB 100 % complet (aucun TODO), équations de l'interface en LaTeX natif MATLAB, interface en pur
code (`uifigure`, `uigridlayout`, `uitabgroup`), pas de `.mlapp`.
