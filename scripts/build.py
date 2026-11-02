#!/usr/bin/env python3
"""Build JEETube's 80-chapter IIT-JEE Main & Advanced YouTube index (data/videos.json).

Pure Python 3 standard library. Run from anywhere:

    python3 scripts/build.py --self-test
    python3 scripts/build.py
    python3 scripts/build.py --fresh

Queries YouTube's public web search endpoint across all 80 canonical IIT-JEE Main &
Advanced chapters (Mathematics: 29, Physics: 25, Chemistry: 26) using clean, focused
YouTube queries across both YouTube's native Playlist filter (sp=EgIQAw==) and
Long-Form Lecture filter (sp=EgIYAg==), plus 36 educator-specific playlist sweeps.
Enforces a strict Verified JEE Educator/Institute Channel allowlist, chapter-matching,
cross-subject guards, and NEET/regional/clickbait rejection.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import ssl
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "data" / "cache"
OUT_PATH = ROOT / "data" / "videos.json"

INNERTUBE_SEARCH = "https://www.youtube.com/youtubei/v1/search"
SP_PLAYLIST_ONLY = "EgIQAw=="  # YouTube native Type: Playlist protobuf filter
SP_LONG_VIDEOS = "EgIYAg=="    # YouTube native Duration: >20 minutes protobuf filter

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def _ssl_context() -> ssl.SSLContext:
    for cafile in ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt"):
        if os.path.exists(cafile):
            return ssl.create_default_context(cafile=cafile)
    return ssl.create_default_context()


SSL_CTX = _ssl_context()
_lock = threading.Lock()
STATS = {"requests": 0, "cached": 0}

# ---------------------------------------------------------------------------
# Complete 80-Chapter IIT-JEE Main & Advanced Syllabus Taxonomy (PCM)
# Tuple:
#   (ch_no, subject, unit, class_level, weightage, syllabus_scope, chapter_name,
#    match_regex, core_search_phrase, alt_search_phrase)
# Each chapter runs 4 clean queries (no mutually-exclusive teacher stuffing):
#   1. "{core_search_phrase} IIT JEE"              [Playlists Only]
#   2. "{alt_search_phrase} JEE Advanced"          [Playlists Only]
#   3. "{core_search_phrase} JEE one shot"         [Long Videos >20m]
#   4. "{alt_search_phrase} JEE PYQ revision"      [Long Videos >20m]
# ---------------------------------------------------------------------------
SYLLABUS: list[tuple[int, str, str, str, str, str, str, str, str, str]] = [
    # ======================= MATHEMATICS (29 Chapters) =======================
    (
        1, "Mathematics", "Algebra", "Class 11", "High", "Main + Adv",
        "Basic Mathematics, Sets, Modulus & Logarithms",
        r"\b(basic math\w*|sets?\b|inequalit\w*|wavy curve|modulus|logarithm\w*|\blog\b)",
        "Basic Mathematics Logarithm Sets",
        "Sets Inequalities Logarithm Maths",
    ),
    (
        2, "Mathematics", "Algebra", "Class 11", "High", "Main + Adv",
        "Relations & Functions",
        r"\b(relations?\s*(?:and|&)\s*functions?|\bfunctions?\b|domain|range|bijective|composite)",
        "Relations and Functions Class 12 Maths",
        "Functions IIT JEE Mathematics",
    ),
    (
        3, "Mathematics", "Algebra", "Class 11", "High", "Main + Adv",
        "Quadratic Equations & Location of Roots",
        r"\b(quadratic|location of roots|theory of equations)",
        "Quadratic Equations",
        "Quadratic Equation Location of Roots",
    ),
    (
        4, "Mathematics", "Algebra", "Class 11", "High", "Main + Adv",
        "Complex Numbers",
        r"\b(complex numbers?|argand|de moivre|roots of unity|cube roots)",
        "Complex Numbers",
        "Complex Number Geometry",
    ),
    (
        5, "Mathematics", "Algebra", "Class 11", "High", "Main + Adv",
        "Sequences & Series",
        r"\b(sequences?\s*(?:and|&)?\s*series|progression\w*|\ba\.?p\.?\b|\bg\.?p\.?\b|am[- ]gm)",
        "Sequence and Series",
        "Progression and Series Maths",
    ),
    (
        6, "Mathematics", "Algebra", "Class 11", "High", "Main + Adv",
        "Permutations & Combinations (P&C)",
        r"\b(permutations?|combinations?|p\s*&\s*c|\bpnc\b|combinatorics)",
        "Permutations and Combinations",
        "Permutation Combination PnC",
    ),
    (
        7, "Mathematics", "Algebra", "Class 11", "High", "Main + Adv",
        "Binomial Theorem",
        r"\b(binomial theorem|binomial expansion|multinomial|binomial\b)",
        "Binomial Theorem",
        "Binomial Theorem Maths",
    ),
    (
        8, "Mathematics", "Algebra", "Class 12", "Very High", "Main + Adv",
        "Matrices & Determinants",
        r"\b(matri(?:x|ces)|determinants?|cayley|adjoint|system of linear)",
        "Matrices and Determinants",
        "Matrices Class 12 Maths",
    ),
    (
        9, "Mathematics", "Algebra", "Class 12", "Very High", "Main + Adv",
        "Probability",
        r"\b(probability|bayes|conditional probability|random variable|binomial distribution)",
        "Probability Class 12 Maths",
        "Probability IIT JEE Mathematics",
    ),
    (
        10, "Mathematics", "Trigonometry", "Class 11", "Medium", "Main + Adv",
        "Trigonometric Ratios, Identities & Equations",
        r"\b(trigonometr(?:y|ic)|compound angles|trig\s*equations)",
        "Trigonometric Functions and Equations",
        "Trigonometry Class 11 Maths",
    ),
    (
        11, "Mathematics", "Trigonometry", "Class 12", "Medium", "Main + Adv",
        "Inverse Trigonometric Functions (ITF)",
        r"\b(inverse trigonometr\w*|\bitf\b)",
        "Inverse Trigonometric Functions",
        "Inverse Trigonometry ITF",
    ),
    (
        12, "Mathematics", "Trigonometry", "Class 11", "Medium", "JEE Adv Focus",
        "Solution of Triangles (SOT)",
        r"\b(solutions? of triangles?|properties of triangles?|\bsot\b|sine rule|cosine rule)",
        "Solution of Triangle",
        "Properties of Triangle SOT",
    ),
    (
        13, "Mathematics", "Coordinate Geometry", "Class 11", "High", "Main + Adv",
        "Straight Lines & Pair of Straight Lines",
        r"\b(straight lines?|pair of (?:straight )?lines|locus\b)",
        "Straight Lines Class 11",
        "Straight Line Pair of Lines",
    ),
    (
        14, "Mathematics", "Coordinate Geometry", "Class 11", "High", "Main + Adv",
        "Circles",
        r"\b(circles?\b|radical axis|orthogonal circles|family of circles)",
        "Circles Coordinate Geometry",
        "Circle Class 11 Maths",
    ),
    (
        15, "Mathematics", "Coordinate Geometry", "Class 11", "High", "Main + Adv",
        "Parabola",
        r"\b(parabola|focal chord)",
        "Parabola Conic Sections",
        "Parabola Class 11 Maths",
    ),
    (
        16, "Mathematics", "Coordinate Geometry", "Class 11", "High", "Main + Adv",
        "Ellipse",
        r"\b(ellipse|auxiliary circle|eccentric angle)",
        "Ellipse Conic Sections",
        "Ellipse Class 11 Maths",
    ),
    (
        17, "Mathematics", "Coordinate Geometry", "Class 11", "High", "Main + Adv",
        "Hyperbola",
        r"\b(hyperbola|rectangular hyperbola|asymptotes)",
        "Hyperbola",
        "Hyperbola Conic Sections",
    ),
    (
        18, "Mathematics", "Calculus", "Class 12", "High", "Main + Adv",
        "Limits",
        r"\b(limits?\b|l'?hospital|indeterminate|sandwich theorem)",
        "Limits Calculus Maths",
        "Limits Class 12 Maths",
    ),
    (
        19, "Mathematics", "Calculus", "Class 12", "High", "Main + Adv",
        "Continuity & Differentiability",
        r"\b(continuity|differentiability|\blcd\b)",
        "Continuity and Differentiability",
        "Continuity Differentiability Maths",
    ),
    (
        20, "Mathematics", "Calculus", "Class 12", "Medium", "Main + Adv",
        "Methods of Differentiation (MOD)",
        r"\b(methods of differentiation|\bmod\b|differentiation|derivatives?\b)",
        "Methods of Differentiation",
        "Differentiation Class 12 Maths",
    ),
    (
        21, "Mathematics", "Calculus", "Class 12", "Very High", "Main + Adv",
        "Application of Derivatives (AOD)",
        r"\b(applications? of derivatives?|\baod\b|monotonicity|maxima|minima|tangent|normal)",
        "Application of Derivatives",
        "Monotonicity Maxima Minima AOD",
    ),
    (
        22, "Mathematics", "Calculus", "Class 12", "High", "Main + Adv",
        "Indefinite Integration",
        r"\b(indefinite integration|indefinite integrals?)",
        "Indefinite Integration",
        "Indefinite Integration Class 12",
    ),
    (
        23, "Mathematics", "Calculus", "Class 12", "Very High", "Main + Adv",
        "Definite Integration",
        r"\b(definite integration|definite integrals?|leibnitz|walli|limit of sum)",
        "Definite Integration",
        "Definite Integration Class 12",
    ),
    (
        24, "Mathematics", "Calculus", "Class 12", "High", "Main + Adv",
        "Area Under Curves",
        r"\b(area under|application of integrals?|\bauc\b|quadrature)",
        "Area Under Curve",
        "Application of Integrals Area Under Curves",
    ),
    (
        25, "Mathematics", "Calculus", "Class 12", "Very High", "Main + Adv",
        "Differential Equations",
        r"\b(differential equations?|linear differential|exact differential)",
        "Differential Equations Class 12",
        "Differential Equation Maths",
    ),
    (
        26, "Mathematics", "Calculus", "Class 12", "High", "JEE Adv Focus",
        "GIF, Fractional Part & Functional Equations",
        r"\b(greatest integer|fractional part|\bgif\b|functional equations?|floor function|graphs?\s*(?:and|&)\s*transformations?)",
        "Functional Equations",
        "Greatest Integer Function Graphs Transformations",
    ),
    (
        27, "Mathematics", "Vectors, 3D & Statistics", "Class 12", "Very High", "Main + Adv",
        "Vector Algebra",
        r"\b(vectors?\b|vector algebra|scalar triple|vector triple|dot product|cross product)",
        "Vector Algebra Class 12",
        "Vectors Mathematics",
    ),
    (
        28, "Mathematics", "Vectors, 3D & Statistics", "Class 12", "Very High", "Main + Adv",
        "3D Coordinate Geometry",
        r"\b(3d|three dimensional|skew lines|planes?\b|direction cosines)",
        "3D Geometry Class 12",
        "Three Dimensional Geometry Maths",
    ),
    (
        29, "Mathematics", "Vectors, 3D & Statistics", "Class 11", "Medium", "Main + Adv",
        "Statistics",
        r"\b(statistics|variance|standard deviation|mean deviation)",
        "Statistics Maths",
        "Statistics Class 11 JEE Main",
    ),

    # ========================= PHYSICS (25 Chapters) =========================
    (
        30, "Physics", "Mechanics", "Class 11", "Medium", "Main + Adv",
        "Units, Dimensions, Errors & Basic Vectors",
        r"\b(units?\s*(?:and|&)?\s*dimensions?|dimensional|error analysis|significant figures|mathematical tools|vectors?\b)",
        "Units and Dimensions Physics",
        "Units Dimensions Error Analysis",
    ),
    (
        31, "Physics", "Mechanics", "Class 11", "High", "Main + Adv",
        "Kinematics (1D, Projectile & Relative Motion)",
        r"\b(kinematics|rectilinear|projectile|relative motion|motion in a (?:straight|plane)|1d|2d)",
        "Kinematics Physics",
        "Motion in a Straight Line Projectile",
    ),
    (
        32, "Physics", "Mechanics", "Class 11", "High", "Main + Adv",
        "Newton's Laws of Motion & Friction (NLM)",
        r"\b(newton'?s laws?|\bnlm\b|laws of motion|friction|constraint|pseudo force)",
        "Laws of Motion Physics",
        "Newton Laws of Motion Friction NLM",
    ),
    (
        33, "Physics", "Mechanics", "Class 11", "High", "Main + Adv",
        "Work, Power, Energy & Circular Motion",
        r"\b(work[, ]+power|work[, ]+energy|\bwpe\b|circular motion|vertical circle)",
        "Work Power and Energy",
        "Circular Motion Work Energy Physics",
    ),
    (
        34, "Physics", "Mechanics", "Class 11", "High", "Main + Adv",
        "Centre of Mass, Momentum & Collisions",
        r"\b(cent(?:re|er) of mass|\bcom\b|momentum|collisions?|impulse|variable mass)",
        "Centre of Mass Physics",
        "Center of Mass Collisions Momentum",
    ),
    (
        35, "Physics", "Mechanics", "Class 11", "Very High", "Main + Adv",
        "Rotational Mechanics (Rigid Body Dynamics)",
        r"\b(rotational|rigid body|\brbd\b|moment of inertia|torque|angular momentum|rolling)",
        "Rotational Motion Physics",
        "Rigid Body Dynamics Rotational",
    ),
    (
        36, "Physics", "Mechanics", "Class 11", "High", "Main + Adv",
        "Gravitation",
        r"\b(gravitation\w*|kepler|orbital velocity|escape velocity|satellites?)",
        "Gravitation Class 11 Physics",
        "Gravitation Physics",
    ),
    (
        37, "Physics", "Mechanics", "Class 11", "High", "Main + Adv",
        "Fluid Mechanics, Surface Tension & Viscosity",
        r"\b(fluid\w*|hydrostatics|bernoulli|surface tension|viscosity|mechanical properties of fluids)",
        "Fluid Mechanics Physics",
        "Mechanical Properties of Fluids Surface Tension",
    ),
    (
        38, "Physics", "Mechanics", "Class 11", "Medium", "Main + Adv",
        "Elasticity & Mechanical Properties of Solids",
        r"\b(elasticity|mechanical properties of (?:solids|matter)|young'?s modulus|stress|strain)",
        "Mechanical Properties of Solids",
        "Elasticity Physics Class 11",
    ),
    (
        39, "Physics", "Waves & Thermodynamics", "Class 11", "High", "Main + Adv",
        "Simple Harmonic Motion (SHM)",
        r"\b(simple harmonic|\bshm\b|oscillations?|pendulum)",
        "Simple Harmonic Motion SHM",
        "Oscillations Class 11 Physics",
    ),
    (
        40, "Physics", "Waves & Thermodynamics", "Class 11", "High", "Main + Adv",
        "Mechanical Waves & Sound Waves",
        r"\b(waves on string|string waves|sound waves|standing waves|organ pipe|doppler|beats|wave motion|waves\b)",
        "Waves Class 11 Physics",
        "Sound Waves String Waves Doppler",
    ),
    (
        41, "Physics", "Waves & Thermodynamics", "Class 11", "High", "Main + Adv",
        "Thermal Expansion, Calorimetry & Heat Transfer",
        r"\b(calorimetry|thermal expansion|thermal properties|heat transfer|conduction|radiation)",
        "Thermal Properties of Matter",
        "Heat Transfer Calorimetry Physics",
    ),
    (
        42, "Physics", "Waves & Thermodynamics", "Class 11", "Very High", "Main + Adv",
        "Kinetic Theory of Gases & Thermodynamics (KTG)",
        r"\b(kinetic theory|\bktg\b|thermodynamics|carnot|polytropic)",
        "KTG and Thermodynamics Physics",
        "Kinetic Theory of Gases Thermodynamics Physics",
    ),
    (
        43, "Physics", "Electrodynamics", "Class 12", "Very High", "Main + Adv",
        "Electrostatics & Gauss's Law",
        r"\b(electrostatics?|electric charges|electric field|gauss|electric potential|dipole)",
        "Electrostatics Class 12 Physics",
        "Electric Charges and Fields Potential",
    ),
    (
        44, "Physics", "Electrodynamics", "Class 12", "High", "Main + Adv",
        "Capacitors & Dielectrics",
        r"\b(capacitors?|capacitance|dielectrics?)",
        "Capacitor Class 12 Physics",
        "Capacitance Capacitors Physics",
    ),
    (
        45, "Physics", "Electrodynamics", "Class 12", "Very High", "Main + Adv",
        "Current Electricity",
        r"\b(current electricity|kirchhoff|wheatstone|potentiometer|meter bridge)",
        "Current Electricity Class 12",
        "Current Electricity Physics",
    ),
    (
        46, "Physics", "Electrodynamics", "Class 12", "Very High", "Main + Adv",
        "Moving Charges & Magnetism",
        r"\b(moving charges|magnetic effects? of current|biot[- ]savart|ampere|lorentz|cyclotron)",
        "Moving Charges and Magnetism",
        "Magnetic Effects of Current Physics",
    ),
    (
        47, "Physics", "Electrodynamics", "Class 12", "Medium", "Main + Adv",
        "Magnetism & Matter",
        r"\b(magnetism\s*(?:and|&)\s*matter|earth'?s magnetism|bar magnet|magnetic properties|magnetism\b)",
        "Magnetism and Matter Class 12",
        "Magnetism and Matter Physics",
    ),
    (
        48, "Physics", "Electrodynamics", "Class 12", "Very High", "Main + Adv",
        "Electromagnetic Induction (EMI)",
        r"\b(electromagnetic induction|\bemi\b|faraday|lenz|inductance|motional emf)",
        "Electromagnetic Induction Class 12",
        "EMI Electromagnetic Induction Physics",
    ),
    (
        49, "Physics", "Electrodynamics", "Class 12", "High", "Main + Adv",
        "Alternating Current (AC) & EM Waves",
        r"\b(alternating current|\bac\b|lcr|electromagnetic waves|\bem waves\b)",
        "Alternating Current Class 12",
        "Electromagnetic Waves Alternating Current",
    ),
    (
        50, "Physics", "Optics", "Class 12", "Very High", "Main + Adv",
        "Geometrical (Ray) Optics & Optical Instruments",
        r"\b(geometrical optics|ray optics|refraction|prism|lens|mirror|optical instruments)",
        "Ray Optics Class 12 Physics",
        "Geometrical Optics Optical Instruments",
    ),
    (
        51, "Physics", "Optics", "Class 12", "High", "Main + Adv",
        "Wave Optics (YDSE, Interference & Diffraction)",
        r"\b(wave optics|ydse|young'?s double|interference|diffraction|polarization)",
        "Wave Optics Class 12 Physics",
        "Wave Optics YDSE Interference",
    ),
    (
        52, "Physics", "Modern & Experimental", "Class 12", "Very High", "Main + Adv",
        "Modern Physics (Photoelectric, Atoms & X-Rays)",
        r"\b(modern physics|photoelectric|dual nature|bohr|atomic physics|atoms\b|de broglie|x[- ]?rays?)",
        "Modern Physics Class 12",
        "Dual Nature Atoms Photoelectric Physics",
    ),
    (
        53, "Physics", "Modern & Experimental", "Class 12", "High", "Main + Adv",
        "Nuclear Physics & Radioactivity",
        r"\b(nuclear physics|nuclei\b|radioactivity|binding energy|fission|fusion)",
        "Nuclei Class 12 Physics",
        "Nuclear Physics Radioactivity",
    ),
    (
        54, "Physics", "Modern & Experimental", "Class 12", "High", "JEE Main Focus",
        "Semiconductors, Logic Gates & Experimental Physics",
        r"\b(semiconductors?|diodes?|logic gates|zener|vernier|screw gauge|experimental physics)",
        "Semiconductor Class 12 Physics",
        "Experimental Physics Vernier Logic Gates",
    ),

    # ======================== CHEMISTRY (26 Chapters) ========================
    (
        55, "Chemistry", "Physical Chemistry", "Class 11", "High", "Main + Adv",
        "Mole Concept & Stoichiometry",
        r"\b(mole concept|stoichiometry|basic concepts of chemistry|limiting reagent|concentration terms)",
        "Mole Concept Chemistry",
        "Some Basic Concepts of Chemistry Class 11",
    ),
    (
        56, "Chemistry", "Physical Chemistry", "Class 11", "Medium", "Main + Adv",
        "Redox Reactions & Equivalent Concept",
        r"\b(redox|equivalent concept|oxidation number|titration|volumetric|n[- ]factor)",
        "Redox Reactions Class 11",
        "Redox Equivalent Concept Volumetric",
    ),
    (
        57, "Chemistry", "Physical Chemistry", "Class 11", "High", "Main + Adv",
        "Atomic Structure",
        r"\b(atomic structure|atomic sructure|structure of atom|quantum numbers|schrodinger|bohr)",
        "Atomic Structure Chemistry",
        "Structure of Atom Class 11 Chemistry",
    ),
    (
        58, "Chemistry", "Physical Chemistry", "Class 11", "Medium", "JEE Adv Focus",
        "States of Matter (Gaseous State & Real Gases)",
        r"\b(gaseous state|states of matter|real gas\w*|van der waals|compressibility)",
        "States of Matter Gaseous State",
        "Gaseous State Real Gases Chemistry",
    ),
    (
        59, "Chemistry", "Physical Chemistry", "Class 11", "Very High", "Main + Adv",
        "Chemical Thermodynamics & Thermochemistry",
        r"\b(thermodynamics|thermochemistry|enthalpy|entropy|gibbs|hess)",
        "Chemical Thermodynamics Chemistry",
        "Thermochemistry Thermodynamics Class 11",
    ),
    (
        60, "Chemistry", "Physical Chemistry", "Class 11", "High", "Main + Adv",
        "Chemical Equilibrium",
        r"\b(chemical equilibrium|\bkp\b|\bkc\b|le chatelier)",
        "Chemical Equilibrium Class 11",
        "Chemical Equilibrium Chemistry",
    ),
    (
        61, "Chemistry", "Physical Chemistry", "Class 11", "Very High", "Main + Adv",
        "Ionic Equilibrium",
        r"\b(ionic equilibrium|buffer|solubility product|\bph\b|salt hydrolysis)",
        "Ionic Equilibrium Class 11",
        "Ionic Equilibrium Chemistry",
    ),
    (
        62, "Chemistry", "Physical Chemistry", "Class 12", "High", "Main + Adv",
        "Liquid Solutions & Colligative Properties",
        r"\b(liquid solutions?|solutions?\b|colligative|raoult|van'?t hoff)",
        "Solutions Class 12 Chemistry",
        "Liquid Solutions Colligative Properties",
    ),
    (
        63, "Chemistry", "Physical Chemistry", "Class 12", "Very High", "Main + Adv",
        "Electrochemistry",
        r"\b(electrochemistry|nernst|galvanic|conductance|electrolytic|kohlrausch)",
        "Electrochemistry Class 12",
        "Electrochemistry Chemistry",
    ),
    (
        64, "Chemistry", "Physical Chemistry", "Class 12", "Very High", "Main + Adv",
        "Chemical Kinetics",
        r"\b(chemical kinetics|kinetics|rate law|arrhenius|first order)",
        "Chemical Kinetics Class 12",
        "Chemical Kinetics Chemistry",
    ),
    (
        65, "Chemistry", "Physical Chemistry", "Class 12", "Medium", "JEE Adv Focus",
        "Solid State & Surface Chemistry",
        r"\b(solid state|surface chemistry|crystal lattice|packing efficiency|adsorption|colloids)",
        "Solid State Chemistry Class 12",
        "Surface Chemistry Solid State",
    ),
    (
        66, "Chemistry", "Inorganic Chemistry", "Class 11", "High", "Main + Adv",
        "Periodic Table & Periodicity",
        r"\b(periodic table|periodic classification|periodicity|periodic properties|ionization)",
        "Periodic Table Class 11 Chemistry",
        "Periodic Classification Periodicity",
    ),
    (
        67, "Chemistry", "Inorganic Chemistry", "Class 11", "Very High", "Main + Adv",
        "Chemical Bonding & Molecular Structure",
        r"\b(chemical bonding|vsepr|hybridization|molecular orbital|\bmot\b|fajan)",
        "Chemical Bonding Class 11",
        "Chemical Bonding Molecular Structure",
    ),
    (
        68, "Chemistry", "Inorganic Chemistry", "Class 12", "Very High", "Main + Adv",
        "Coordination Compounds",
        r"\b(coordination compounds?|crystal field|\bcft\b|werner|ligands?)",
        "Coordination Compounds Class 12",
        "Coordination Chemistry CFT",
    ),
    (
        69, "Chemistry", "Inorganic Chemistry", "Class 12", "High", "Main + Adv",
        "p-Block Elements (Groups 13 to 18)",
        r"\b(p[- ]?block|boron family|carbon family|nitrogen family|oxygen family|halogens|noble gases)",
        "p Block Elements Chemistry",
        "p Block Class 11 12 Inorganic",
    ),
    (
        70, "Chemistry", "Inorganic Chemistry", "Class 12", "High", "Main + Adv",
        "d- & f-Block Elements & Metallurgy",
        r"\b(d\s*(?:and|&)\s*f\s*block|d[- ]block|transition elements|metallurgy|isolation of elements)",
        "d and f Block Elements Class 12",
        "Metallurgy d and f Block Chemistry",
    ),
    (
        71, "Chemistry", "Inorganic Chemistry", "Class 12", "High", "JEE Adv Focus",
        "Salt Analysis (Qualitative Analysis) & s-Block",
        r"\b(salt analysis|qualitative analysis|cation|anion|s[- ]block)",
        "Salt Analysis Chemistry",
        "Qualitative Analysis s Block Inorganic",
    ),
    (
        72, "Chemistry", "Organic Chemistry", "Class 11", "High", "Main + Adv",
        "IUPAC Nomenclature",
        r"\b(iupac|nomenclature)",
        "IUPAC Nomenclature Organic Chemistry",
        "IUPAC Naming Class 11",
    ),
    (
        73, "Chemistry", "Organic Chemistry", "Class 11", "Very High", "Main + Adv",
        "Structural & Stereoisomerism (Optical & Geometrical)",
        r"\b(isomerism|stereoisomerism|optical isomerism|geometrical isomerism|conformational|chirality)",
        "Isomerism Organic Chemistry",
        "Stereoisomerism Optical Isomerism",
    ),
    (
        74, "Chemistry", "Organic Chemistry", "Class 11", "Very High", "Main + Adv",
        "General Organic Chemistry (GOC)",
        r"\b(general organic chemistry|\bgoc\b|inductive|resonance|mesomeric|hyperconjugation|aromaticity)",
        "General Organic Chemistry GOC",
        "GOC Class 11 Organic Chemistry",
    ),
    (
        75, "Chemistry", "Organic Chemistry", "Class 11", "Very High", "Main + Adv",
        "Reaction Mechanisms & Hydrocarbons",
        r"\b(reaction mechanisms?|\borm\b|hydrocarbons?|alkanes?|alkenes?|alkynes?|electrophilic|sn1|sn2)",
        "Hydrocarbons Class 11 Chemistry",
        "Organic Reaction Mechanism ORM",
    ),
    (
        76, "Chemistry", "Organic Chemistry", "Class 12", "High", "Main + Adv",
        "Haloalkanes, Haloarenes & Grignard Reagent",
        r"\b(haloalkanes?|haloarenes?|alkyl halides?|aryl halides?|grignard|girgnard)",
        "Haloalkanes and Haloarenes Class 12",
        "Alkyl Halide Grignard Reagent",
    ),
    (
        77, "Chemistry", "Organic Chemistry", "Class 12", "High", "Main + Adv",
        "Alcohols, Phenols & Ethers",
        r"\b(alcohols?|phenols?|ethers?|epoxides?)",
        "Alcohol Phenol and Ether Class 12",
        "Alcohols Phenols and Ethers",
    ),
    (
        78, "Chemistry", "Organic Chemistry", "Class 12", "Very High", "Main + Adv",
        "Aldehydes, Ketones & Carboxylic Acids",
        r"\b(aldehydes?|ketones?|carboxylic|carbonyl|aldol|cannizzaro)",
        "Aldehydes Ketones and Carboxylic Acids",
        "Carbonyl Compounds Aldehyde Ketone",
    ),
    (
        79, "Chemistry", "Organic Chemistry", "Class 12", "High", "Main + Adv",
        "Amines & Diazonium Salts",
        r"\b(amines?\b|diazonium|nitrogen containing)",
        "Amines Class 12 Chemistry",
        "Amines Organic Chemistry",
    ),
    (
        80, "Chemistry", "Organic Chemistry", "Class 12", "High", "Main + Adv",
        "Biomolecules, Polymers & Practical Organic Chemistry",
        r"\b(biomolecules?|carbohydrates?|amino acids|polymers?|practical organic|\bpoc\b)",
        "Biomolecules Class 12 Chemistry",
        "Polymers Practical Organic Chemistry POC",
    ),
]

TEACHER_PLAYLIST_SWEEPS: list[tuple[str, str]] = [
    ("Mathematics", "Mohit Tyagi IIT JEE Mathematics"),
    ("Mathematics", "Mathsmerizing Full Course"),
    ("Mathematics", "Mathsmerizing Symposium Compendium"),
    ("Mathematics", "Maths Unplugged JEE"),
    ("Mathematics", "Nishant Vora Vora Classes Maths"),
    ("Mathematics", "MathonGo Complete Chapter JEE Mathematics"),
    ("Mathematics", "Arvind Kalia JEE Nexus Maths"),
    ("Mathematics", "Sameer Chincholikar Unacademy JEE"),
    ("Mathematics", "Manzil JEE Wallah Maths"),
    ("Mathematics", "JEE Challengers PW Mathematics"),
    ("Mathematics", "Neha Agrawal Mathematically Inclined JEE"),
    ("Mathematics", "BHANNAT MATHS JEE"),
    ("Physics", "ABJ sir Physics Mohit Tyagi"),
    ("Physics", "Physics Galaxy Concept Videos"),
    ("Physics", "Physics Galaxy Revision Checklist"),
    ("Physics", "Physics Galaxy Advanced Illustrations"),
    ("Physics", "Eduniti Mohit Goenka Physics"),
    ("Physics", "Physics by Rohit Mishra JEE"),
    ("Physics", "Physics Sir JEE Janardhan"),
    ("Physics", "Vinay Uppal JEE Physics"),
    ("Physics", "Indian School of Physics Nitin Sachan"),
    ("Physics", "Invisible Mechanics JEE Physics"),
    ("Physics", "Physics Wallah Alakh Pandey Class 11 12 Physics"),
    ("Physics", "Jayant Nagda Unacademy JEE Physics"),
    ("Chemistry", "ALK sir Physical Chemistry Mohit Tyagi"),
    ("Chemistry", "ALK sir Inorganic Chemistry Mohit Tyagi"),
    ("Chemistry", "NS sir Organic Chemistry Mohit Tyagi"),
    ("Chemistry", "SKM sir Organic Chemistry"),
    ("Chemistry", "AKK sir Physical Chemistry"),
    ("Chemistry", "PMS sir VJ sir Inorganic Chemistry"),
    ("Chemistry", "Sachin Rana IITB Organic Chemistry"),
    ("Chemistry", "IITian Explains MKA sir Chemistry"),
    ("Chemistry", "DexterChem Chaitanya Rastogi"),
    ("Chemistry", "Sakshi Vora Vora Classes Chemistry"),
    ("Chemistry", "Pankaj Sir Chemistry JEE"),
    ("Chemistry", "Canvas Classes Pahul sir Chemistry"),
]

# Strict Curated Allowlist of Legitimate IIT-JEE Educators & Official Institute Channels
# Guarantees ZERO spam/profane/random personal accounts or non-JEE teaching channels.
VERIFIED_CHANNEL_PATTERNS = (
    "mohit tyagi",
    "competishun",
    "physics galaxy",
    "mathsmerizing",
    "maths unplugged",
    "eduniti",
    "vora classes",
    "jee wallah",
    "physics wallah",
    "lakshya jee",
    "arjuna jee",
    "jee challengers",
    "pw jee",
    "unacademy jee",
    "unacademy atoms",
    "jee nexus",
    "jeefinity",
    "unacademy accelerate",
    "let's crack iit jee",
    "jee 24x7",
    "jee legends",
    "jee alchemy",
    "mathongo",
    "jeeongo",
    "dexterchem",
    "sachin rana",
    "iitian explains",
    "rohit mishra",
    "physics sir jee",
    "indian school of physics",
    "vinay uppal",
    "invisible mechanics",
    "pankaj sir chemistry",
    "canvas classes",
    "vedantu jee",
    "allen jee",
    "motion jee",
    "atp star",
    "esaral",
    "apni kaksha",
    "mathematically inclined",
    "neha agrawal",
    "bhannat maths",
    "acadza",
    "chemiit",
    "pms sir",
    "vishal joshi",
    "vj sir",
    "skm sir",
    "akk sir",
    "iit school",
    "careerwill",
    "ms chouhan",
    "sameer bansal",
    "physics heist",
    "khan academy india - english",
    "simply concise",
    "jee simplified",
    "mr. exponent",
)

ADVANCED_FACULTY_CHANNELS = (
    "mohit tyagi",
    "competishun",
    "mathsmerizing",
    "maths unplugged",
    "indian school of physics",
    "physics sir jee",
    "vinay uppal",
    "iitian explains",
    "sachin rana",
    "jee challengers",
    "invisible mechanics",
    "rohit mishra",
    "sameer bansal",
    "ms chouhan",
    "chemiit",
)

ENGLISH_MEDIUM_CUES = (
    "vedantu jee english",
    "unacademy jee english",
    "khan academy india - english",
    "physics galaxy",
    "mathsmerizing",
    "vinay uppal",
    "physics sir jee",
    "indian school of physics",
)

# Strict Rejections: NEET-only, Class 8/9/10, Regional-only non-English/Hindi, Non-academic noise
HARD_REJECT_RE = re.compile(
    r"\b(neet\s+only|only\s+for\s+neet|neet\s+biology|botany|zoology|mbbs|aiims\s+biology|"
    r"neet\s+ug|complete\s+neet|mission\s+neet|yakeen|aarambh\s+neet|neet\s+202\d|"
    r"class\s*(?:6|7|8|9|10|ix|x)\b|icse|ssc\s+cgl|upsc|tgt|pgt|dsssb|kvs|cuet\s+only|kcet|mht\s*cet|"
    r"vaathi|tamil|telugu|malayalam|kannada|bangla|bengali|marathi|gujarati|odia|"
    r"vlog|prank|controversy|exposed|roast|reaction\s+video|cutoff|marks\s+vs\s+percentile|"
    r"college\s+review|hostel\s+tour|josaa|counselling|time\s*table|how\s+to\s+crack|"
    r"strategy\s+to\s+score|best\s+books\s+for|motivation|motivational|shorts|#shorts)\b",
    re.I,
)


def parse_views(text: str) -> int:
    if not text:
        return 0
    cleaned = text.lower().replace(",", "").strip()
    m = re.search(r"([\d.]+)\s*([kmb]|lakh|cr)?", cleaned)
    if not m:
        return 0
    val = float(m.group(1))
    mult = m.group(2) or ""
    if mult == "k":
        val *= 1_000
    elif mult == "m":
        val *= 1_000_000
    elif mult == "b":
        val *= 1_000_000_000
    elif mult == "lakh":
        val *= 100_000
    elif mult == "cr":
        val *= 10_000_000
    return int(val)


def parse_duration_seconds(text: str) -> int:
    if not text:
        return 0
    parts = [int(p) for p in re.findall(r"\d+", text)]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    if len(parts) == 1:
        return parts[0]
    return 0


def parse_lesson_count(text: str) -> int:
    if not text:
        return 0
    m = re.search(r"(\d+)", text.replace(",", ""))
    return int(m.group(1)) if m else 0


def search_youtube(query: str, params: str = "", use_cache: bool = True) -> dict:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_id = f"{query}::sp={params}" if params else query
    key = hashlib.sha1(cache_id.encode("utf-8")).hexdigest()
    cpath = CACHE_DIR / f"{key}.json"
    if use_cache and cpath.exists():
        with _lock:
            STATS["cached"] += 1
        return json.loads(cpath.read_text(encoding="utf-8"))

    body: dict = {
        "context": {
            "client": {
                "clientName": "WEB",
                "clientVersion": "2.20250101.00.00",
                "hl": "en",
                "gl": "IN",
            }
        },
        "query": query,
    }
    if params:
        body["params"] = params
    payload = json.dumps(body).encode("utf-8")

    last_err = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(
                INNERTUBE_SEARCH,
                data=payload,
                headers={"User-Agent": UA, "Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=15, context=SSL_CTX) as resp:
                data = json.load(resp)
            with _lock:
                STATS["requests"] += 1
            cpath.write_text(json.dumps(data), encoding="utf-8")
            return data
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(0.7 * (attempt + 1))
    print(f"WARN: search failed for {query!r}: {last_err}", flush=True)
    return {}


def extract_candidates(payload: dict) -> list[dict]:
    items = []
    try:
        sections = (
            payload["contents"]["twoColumnSearchResultsRenderer"]["primaryContents"]
            ["sectionListRenderer"]["contents"]
        )
    except (KeyError, TypeError):
        return items

    for sec in sections:
        contents = sec.get("itemSectionRenderer", {}).get("contents", [])
        for entry in contents:
            if "lockupViewModel" in entry:
                parsed = _parse_lockup(entry["lockupViewModel"])
                if parsed:
                    items.append(parsed)
            elif "playlistRenderer" in entry:
                parsed = _parse_legacy_playlist(entry["playlistRenderer"])
                if parsed:
                    items.append(parsed)
            elif "videoRenderer" in entry:
                parsed = _parse_video(entry["videoRenderer"])
                if parsed:
                    items.append(parsed)
    return items


def _parse_lockup(lv: dict) -> dict | None:
    cid = (lv.get("contentId") or "").strip()
    ctype = lv.get("contentType") or ""
    if not cid or ("PLAYLIST" not in ctype and "COURSE" not in ctype and not cid.startswith("PL")):
        return None
    if cid.startswith("RD"):
        return None

    meta_vm = lv.get("metadata", {}).get("lockupMetadataViewModel", {})
    title = (meta_vm.get("title", {}).get("content") or "").strip()
    if not title:
        return None

    rows = (
        meta_vm.get("metadata", {})
        .get("contentMetadataViewModel", {})
        .get("metadataRows", [])
    )
    channel = ""
    channel_url = ""
    sample_lectures: list[dict] = []

    for row in rows:
        parts = row.get("metadataParts") or []
        for part in parts:
            txt_obj = part.get("text") or {}
            content = (txt_obj.get("content") or "").strip()
            if not content or content.lower() in {"playlist", "course", "view full playlist", "view full course", "podcast"}:
                continue
            cmd_runs = txt_obj.get("commandRuns") or []
            web_url = ""
            watch_vid = ""
            if cmd_runs:
                icmd = cmd_runs[0].get("onTap", {}).get("innertubeCommand", {})
                web_url = icmd.get("commandMetadata", {}).get("webCommandMetadata", {}).get("url") or ""
                watch_vid = icmd.get("watchEndpoint", {}).get("videoId") or ""

            if not channel and (web_url.startswith("/@") or web_url.startswith("/channel/") or web_url.startswith("/c/")):
                channel = content
                channel_url = f"https://www.youtube.com{web_url}"
            elif watch_vid and len(sample_lectures) < 4:
                sample_lectures.append(
                    {
                        "video_id": watch_vid,
                        "title": content,
                        "url": f"https://www.youtube.com/watch?v={watch_vid}&list={cid}",
                    }
                )

    if not channel and rows:
        first_parts = rows[0].get("metadataParts") or []
        if first_parts:
            channel = (first_parts[0].get("text", {}).get("content") or "").strip()

    thumb_vm = (
        lv.get("contentImage", {})
        .get("collectionThumbnailViewModel", {})
        .get("primaryThumbnail", {})
        .get("thumbnailViewModel", {})
    )
    sources = thumb_vm.get("image", {}).get("sources") or []
    thumbnail = sources[-1]["url"] if sources else ""

    lesson_count = 0
    for ov in thumb_vm.get("overlays") or []:
        badges = ov.get("thumbnailOverlayBadgeViewModel", {}).get("thumbnailBadges") or []
        for b in badges:
            btxt = b.get("thumbnailBadgeViewModel", {}).get("text") or ""
            cnt = parse_lesson_count(btxt)
            if cnt:
                lesson_count = cnt
                break

    embed_vid = sample_lectures[0]["video_id"] if sample_lectures else ""
    if not embed_vid and thumbnail:
        m = re.search(r"/vi/([A-Za-z0-9_-]{11})/", thumbnail)
        if m:
            embed_vid = m.group(1)

    return {
        "provider": "playlist",
        "video_id": cid,
        "embed_video_id": embed_vid,
        "url": f"https://www.youtube.com/playlist?list={cid}",
        "title": title,
        "channel": channel or "IIT-JEE Faculty",
        "channel_url": channel_url,
        "thumbnail": thumbnail,
        "lesson_count": lesson_count,
        "duration": "",
        "duration_sec": 0,
        "views_text": "",
        "view_count": 0,
        "published": "",
        "sample_lectures": sample_lectures,
    }


def _parse_legacy_playlist(pr: dict) -> dict | None:
    cid = (pr.get("playlistId") or "").strip()
    title = (pr.get("title", {}).get("simpleText") or "").strip()
    if not cid or not title or cid.startswith("RD"):
        return None
    runs = pr.get("shortBylineText", {}).get("runs") or pr.get("longBylineText", {}).get("runs") or []
    channel = (runs[0].get("text") if runs else "").strip() or "IIT-JEE Faculty"
    thumbs = pr.get("thumbnails", [{}])[0].get("thumbnails") or []
    thumbnail = thumbs[-1].get("url", "") if thumbs else ""
    embed_vid = ""
    if thumbnail:
        m = re.search(r"/vi/([A-Za-z0-9_-]{11})/", thumbnail)
        if m:
            embed_vid = m.group(1)
    lesson_count = parse_lesson_count(pr.get("videoCount") or "")
    return {
        "provider": "playlist",
        "video_id": cid,
        "embed_video_id": embed_vid,
        "url": f"https://www.youtube.com/playlist?list={cid}",
        "title": title,
        "channel": channel,
        "channel_url": "",
        "thumbnail": thumbnail,
        "lesson_count": lesson_count,
        "duration": "",
        "duration_sec": 0,
        "views_text": "",
        "view_count": 0,
        "published": "",
        "sample_lectures": [],
    }


def _parse_video(vr: dict) -> dict | None:
    vid = (vr.get("videoId") or "").strip()
    runs = vr.get("title", {}).get("runs") or []
    title = "".join(r.get("text", "") for r in runs).strip()
    if not vid or not title or len(vid) != 11:
        return None

    owner_runs = vr.get("ownerText", {}).get("runs") or vr.get("longBylineText", {}).get("runs") or []
    channel = (owner_runs[0].get("text") if owner_runs else "").strip() or "IIT-JEE Faculty"
    channel_url = ""
    if owner_runs:
        wurl = (
            owner_runs[0]
            .get("navigationEndpoint", {})
            .get("commandMetadata", {})
            .get("webCommandMetadata", {})
            .get("url")
            or ""
        )
        if wurl:
            channel_url = f"https://www.youtube.com{wurl}"

    length_text = (vr.get("lengthText", {}).get("simpleText") or "").strip()
    dur_sec = parse_duration_seconds(length_text)

    views_text = (vr.get("viewCountText", {}).get("simpleText") or "").strip()
    view_count = parse_views(views_text)
    published = (vr.get("publishedTimeText", {}).get("simpleText") or "").strip()

    thumbs = vr.get("thumbnail", {}).get("thumbnails") or []
    thumbnail = thumbs[-1].get("url", "") if thumbs else f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"

    return {
        "provider": "youtube",
        "video_id": vid,
        "embed_video_id": vid,
        "url": f"https://www.youtube.com/watch?v={vid}",
        "title": title,
        "channel": channel,
        "channel_url": channel_url,
        "thumbnail": thumbnail,
        "lesson_count": 0,
        "duration": length_text,
        "duration_sec": dur_sec,
        "views_text": views_text,
        "view_count": view_count,
        "published": published,
        "sample_lectures": [],
    }


def is_verified_jee_channel(channel: str) -> bool:
    low = channel.casefold()
    return any(p in low for p in VERIFIED_CHANNEL_PATTERNS)


def is_advanced_channel(channel: str) -> bool:
    low = channel.casefold()
    return any(t in low for t in ADVANCED_FACULTY_CHANNELS)


def resolve_educator(cand: dict, subject: str, unit: str) -> str:
    blob = f"{cand['title']} {cand['channel']}".lower()
    ch_low = cand["channel"].lower()

    if "mohit tyagi" in ch_low or "competishun" in ch_low:
        if subject == "Mathematics":
            return "MT Sir (Mohit Tyagi)"
        if subject == "Physics":
            return "ABJ Sir (Mohit Tyagi)"
        if unit == "Organic Chemistry" or re.search(r"\bns\s*sir\b|\bneeraj saini\b", blob):
            return "NS Sir (Mohit Tyagi)"
        return "ALK Sir (Mohit Tyagi)"

    teacher_rules = [
        (r"\bnishant vora\b|\bnv\s*sir\b", "Nishant Vora (NV Sir)"),
        (r"\bsakshi vora\b|\bsv\s*ma'?am\b", "Sakshi Vora (SV Ma'am)"),
        (r"vora classes", "Nishant Vora (NV Sir)" if subject == "Mathematics" else "Sakshi Vora (SV Ma'am)"),
        (r"physics galaxy|\bashish arora\b", "Ashish Arora (Physics Galaxy)"),
        (r"eduniti|\bmohit goenka\b", "Mohit Goenka (Eduniti)"),
        (r"mathsmerizing", "Mathsmerizing"),
        (r"maths unplugged", "Sandal Sir (Maths Unplugged)"),
        (r"\brohit mishra\b", "Rohit Mishra Sir"),
        (r"\bsachin rana\b", "Sachin Rana (IITB)"),
        (r"dexterchem|\bchaitanya rastogi\b", "Chaitanya Rastogi (DexterChem)"),
        (r"mathongo|jeeongo|\banup gupta\b|\bprince sir\b", "MathonGo (Anup Sir)"),
        (r"iitian explains|\bmka\s*sir\b|\bkashif alam\b", "MKA Sir (IITian Explains)"),
        (r"\bskm\s*sir\b|\bsurendra kumar mishra\b", "SKM Sir (Kota Organic)"),
        (r"\bakk\s*sir\b|\bakhilesh kanther\b", "AKK Sir (Kota Physical)"),
        (r"\bpms\s*sir\b|\bpiyush maheshwari\b", "PMS Sir (Inorganic)"),
        (r"\bvj\s*sir\b|\bvishal joshi\b", "VJ Sir (Inorganic)"),
        (r"\brohit agarwal\b|\bra\s*sir\b", "Rohit Agarwal (RA Sir)"),
        (r"\bsaleem\s*(?:ahmed)?\s*sir\b", "Saleem Ahmed Sir"),
        (r"\brajwant\s*sir\b|\brj\s*sir\b", "Rajwant Singh (RJ Sir)"),
        (r"\bfaisal\s*sir\b", "Faisal Razaq Sir"),
        (r"\bom pandey\b", "Om Pandey Sir"),
        (r"\btarun khandelwal\b|\btk\s*sir\b", "Tarun Khandelwal (TK Sir)"),
        (r"\bashish agarwal\b", "Ashish Agarwal Sir"),
        (r"\bsachin jakhar\b", "Sachin Jakhar Sir"),
        (r"\bmanoj chauhan\b|\bmc\s*sir\b", "Manoj Chauhan (MC Sir)"),
        (r"\bgb\s*sir\b|\bgavesh bhardwaj\b", "GB Sir (Gavesh Bhardwaj)"),
        (r"\bsameer chincholikar\b|\bsameer sir\b", "Sameer Chincholikar Sir"),
        (r"\bsameer bansal\b", "Sameer Bansal Sir"),
        (r"\barvind kalia\b", "Arvind Kalia Sir"),
        (r"\bjayant nagda\b", "Jayant Nagda Sir"),
        (r"\banupam gupta\b", "Anupam Gupta Sir"),
        (r"\bpaaras thakur\b|\bparas thakur\b", "Paaras Thakur Sir"),
        (r"\bvinay uppal\b", "Vinay Uppal Sir"),
        (r"physics sir jee|\bjanardhan\b", "Janardhan Sir (Physics Sir JEE)"),
        (r"indian school of physics|\bnitin sachan\b|\binsp\b", "Nitin Sachan (INSP)"),
        (r"invisible mechanics", "Invisible Mechanics"),
        (r"pankaj sir", "Pankaj Sijairya Sir"),
        (r"canvas classes|\bpahul\s*sir\b", "Pahul Sir (Canvas Classes)"),
        (r"alakh pandey|physics wallah - alakh pandey", "Alakh Pandey Sir"),
        (r"mathematically inclined|\bneha agrawal\b", "Neha Agrawal Ma'am"),
        (r"bhannat maths|\baman malik\b", "Aman Malik (Bhannat Maths)"),
        (r"acadza|\banshul\s*sir\b", "Anshul Singhal (Acadza)"),
        (r"ms chouhan", "M.S. Chouhan Sir"),
        (r"jee challengers", "JEE Challengers (PW)"),
    ]
    for pat, label in teacher_rules:
        if re.search(pat, blob):
            return label

    return cand["channel"]


def resolve_language(cand: dict) -> str:
    blob = f"{cand['title']} {cand['channel']}".lower()
    if any(cue in blob for cue in ENGLISH_MEDIUM_CUES) or re.search(r"\bin english\b|\benglish medium\b", blob):
        if not re.search(r"\bhindi\b|\bmanzil\b|\bprayas\b|\barjuna\b|\blakshya\b", blob):
            return "English"
    return "Hinglish"


def classify_exam_and_format(cand: dict) -> tuple[str, str]:
    title_low = cand["title"].lower()
    ch_low = cand["channel"].lower()

    if cand["provider"] == "playlist":
        fmt = "Full Course"
        if re.search(r"\b(pyq\w*|previous year|checklist|revision|formula|speed solution|top\s+\d+|mind\s*map)\b", title_low):
            fmt = "Revision & PYQs"
        elif re.search(
            r"\b(advanced illustrations?|symposium|compendium|rank booster|olympiad|irodov|pathfinder|black book|tough)\b",
            title_low,
        ):
            fmt = "Adv Problems"
    else:
        if re.search(
            r"\b(advanced illustrations?|symposium|compendium|rank booster|olympiad|tough|challenger|pathfinder|irodov|black book)\b",
            title_low,
        ) or (is_advanced_channel(ch_low) and cand["duration_sec"] < 7200 and "one shot" not in title_low):
            fmt = "Adv Problems"
        elif (
            re.search(r"\b(pyq\w*|previous year|checklist|revision|formula|mind\s*map|top\s+\d+)\b", title_low)
            and cand["duration_sec"] < 14400
        ):
            fmt = "Revision & PYQs"
        else:
            fmt = "One-Shot"

    has_adv = bool(re.search(r"\b(jee\s*adv\w*|advanced|olympiad|irodov|pathfinder|black\s*book|sbt)\b", title_low))
    has_iit = bool(re.search(r"\biit[\s-]*jee\b", title_low))
    has_main = bool(re.search(r"\b(jee\s*mains?|mains?\s*202\d|manzil|bounce\s*back|jee\s*brief|checklist|ncert)\b", title_low))

    if fmt == "Adv Problems" or any(
        c in ch_low
        for c in (
            "mathsmerizing",
            "maths unplugged",
            "sachin rana",
            "invisible mechanics",
            "indian school of physics",
            "physics sir jee",
            "vinay uppal",
            "iitian explains",
            "sameer bansal",
        )
    ):
        exam = "JEE Advanced" if not has_main else "JEE Main + Advanced"
    elif has_adv and not has_main:
        exam = "JEE Advanced"
    elif has_iit and not has_main and is_advanced_channel(ch_low):
        exam = "JEE Advanced"
    elif (has_main and not has_adv) or any(c in ch_low for c in ("eduniti", "mathongo", "jeeongo")):
        exam = "JEE Main" if not has_adv else "JEE Main + Advanced"
    else:
        exam = "JEE Main + Advanced"

    return exam, fmt


def is_valid_chapter_candidate(cand: dict, ch_no: int, subject: str, chapter_re: re.Pattern[str]) -> bool:
    title = cand["title"]
    channel = cand["channel"]
    sample_titles = " ".join(s["title"] for s in cand.get("sample_lectures", []))

    # 1. Must belong to our Verified IIT-JEE Educator / Official Institute Channel allowlist
    if not is_verified_jee_channel(channel):
        return False

    # 2. Reject NEET-only, Class 8/9/10, Regional non-English/Hindi, and clickbait
    if HARD_REJECT_RE.search(f"{title} {channel}") or re.search(r"\bneet\b", channel, re.I):
        return False
    if re.search(r"\bneet\b", title, re.I) and not re.search(r"\b(jee|iit)\b", title, re.I):
        return False

    # 3. Prevent cross-chapter collisions on shared umbrella terms
    if ch_no == 2 and re.search(r"\b(functional equations?|greatest integer|inverse trigonometr\w*|\bitf\b)\b", title, re.I):
        return False
    if ch_no == 13 and re.search(r"\b(3\s*-?\s*d|three\s+dimension)", title, re.I):
        return False
    if ch_no == 43 and re.search(r"\bcapacit", title, re.I) and not re.search(r"\b(charges|coulomb|gauss)", title, re.I):
        return False
    # Prevent Ch 46 (Moving Charges) from consuming pure "Magnetism and Matter"
    if ch_no == 46 and re.search(r"\bmagnetism\s*(?:and|&)\s*matter\b", title, re.I):
        return False
    if ch_no == 47 and re.search(r"\bmoving charges\b", title, re.I) and not re.search(r"\bmatter\b", title, re.I):
        return False
    # Prevent Ch 22/23 disambiguation
    if ch_no == 22 and re.search(r"\bdefinite integration\b", title, re.I) and not re.search(r"\bindefinite\b", title, re.I):
        return False
    if ch_no == 23 and re.search(r"\bindefinite integration\b", title, re.I) and not re.search(r"\bdefinite\b", title, re.I):
        return False

    # 4. Reject full-subject megacompilations ("all chapters", "in order") unless chapter title matches
    if cand["provider"] == "playlist" and re.search(r"\bin order\b|\ball chapters\b|\bcomplete (?:physics|chemistry|maths)\b", title, re.I):
        return False

    # 5. Avoid isolated mid-series short lecture fragments ("Part 26", "#27", "Lec 14") for single videos
    if cand["provider"] == "youtube" and 0 < cand["duration_sec"] < 3600:
        if re.search(r"(?:^|\b)(?:part|lec(?:ture)?|ep(?:isode)?|l)\s*[-#.]?\s*(?:[2-9]|\d{2,})\b|^#\d+\b", title, re.I):
            if not re.search(r"\b(checklist|pyq|illustrations?|symphony|olympiad|booster|one\s*shot)\b", title, re.I):
                return False

    # 6. Strict Chapter-Title Keyword Match (prevents sample-lecture leakage across chapters)
    if not chapter_re.search(title):
        return False

    # 7. Cross-Subject Guards (checks title & teacher cues without blocking "Physics Wallah" channel on Maths/Chem!)
    blob_tc = f"{title} {channel}"
    if subject == "Mathematics":
        if re.search(
            r"\b(abj sir|physics galaxy|eduniti|rohit mishra|saleem sir|rajwant sir|alk sir|ns sir|sakshi|dexterchem|kinematics|electrostatics|mole concept|organic chemistry)\b",
            blob_tc,
            re.I,
        ) or re.search(r"\b(jee\s+physics|class\s*1[12]\s*physics|jee\s+chemistry)\b", title, re.I):
            return False
    elif subject == "Physics":
        if re.search(
            r"\b(alk sir|ns sir|akk sir|skm sir|sakshi|pankaj sir|faisal|dexterchem|om pandey|sachin rana|mathsmerizing|mathongo|nishant vora|mole concept|enthalpy|gibbs|chemical thermodynamics|chemical kinetics|gaseous state)\b",
            blob_tc,
            re.I,
        ) or re.search(r"\b(chemistry|class\s*1[12]\s*maths|jee\s+mathematics)\b", title, re.I):
            return False
    elif subject == "Chemistry":
        if re.search(
            r"\b(abj sir|physics galaxy|saleem sir|rajwant|eduniti|rohit mishra|vinay uppal|mathsmerizing|nishant vora|mathongo|kinematics|rotational|carnot|photoelectric|x[- ]?rays|modern physics|nuclear physics)\b",
            blob_tc,
            re.I,
        ) or re.search(r"\b(jee\s+physics|class\s*1[12]\s*physics|jee\s+maths)\b", title, re.I):
            return False

    # 8. Duration & Lesson Count Floor
    if cand["provider"] == "playlist":
        if cand["lesson_count"] == 1:
            return False
    else:
        min_sec = 600 if is_advanced_channel(channel) else 900
        if 0 < cand["duration_sec"] < min_sec:
            return False

    return True


def authority_score(cand: dict, fmt: str) -> float:
    score = 45.0
    if is_advanced_channel(cand["channel"]):
        score += 16.0
    if cand["provider"] == "playlist":
        score += 36.0 + min(cand["lesson_count"], 60) * 0.48
    else:
        views = max(cand["view_count"], 1)
        score += min(math.log10(views) * 7.5, 48.0)
        if cand["duration_sec"] >= 14400:
            score += 16.0
        elif cand["duration_sec"] >= 5400:
            score += 10.0
    if fmt == "Full Course":
        score += 10.0
    return round(score, 2)


def build_pedagogy_note(cand: dict, educator: str, exam: str, fmt: str, chapter_name: str) -> str:
    if cand["provider"] == "playlist":
        lessons = f"{cand['lesson_count']}-lecture " if cand["lesson_count"] else "Complete "
        return f"{lessons}YouTube playlist by {educator} · {exam} ({chapter_name})."
    parts = []
    if cand["duration"]:
        parts.append(f"{cand['duration']} {fmt.lower()}")
    else:
        parts.append(fmt)
    parts.append(f"by {educator}")
    if cand["views_text"]:
        parts.append(f"· {cand['views_text']}")
    return " ".join(parts)


def build_corpus(use_cache: bool = True) -> dict:
    compiled_chapters = []
    chapter_tasks = []
    for row in SYLLABUS:
        ch_no, subject, unit, class_lvl, weightage, scope, ch_name, pat, core_q, alt_q = row
        cre = re.compile(pat, re.I)
        compiled_chapters.append((ch_no, subject, unit, class_lvl, weightage, scope, ch_name, cre))
        chapter_tasks.append(("chapter", ch_no, subject, cre, f"{core_q} IIT JEE", SP_PLAYLIST_ONLY))
        chapter_tasks.append(("chapter", ch_no, subject, cre, f"{alt_q} JEE", SP_PLAYLIST_ONLY))
        chapter_tasks.append(("chapter", ch_no, subject, cre, f"{core_q} JEE one shot", SP_LONG_VIDEOS))
        chapter_tasks.append(("chapter", ch_no, subject, cre, f"{alt_q} JEE PYQ revision", SP_LONG_VIDEOS))

    for subj, tq in TEACHER_PLAYLIST_SWEEPS:
        chapter_tasks.append(("sweep", 0, subj, None, tq, SP_PLAYLIST_ONLY))

    print(
        f"Executing {len(chapter_tasks)} YouTube InnerTube queries across {len(SYLLABUS)} JEE chapters...",
        flush=True,
    )

    raw_results: dict[int, list[dict]] = {row[0]: [] for row in SYLLABUS}
    sweep_candidates: list[tuple[str, dict]] = []

    def worker(task):
        kind, ch_no, subject, cre, query, sp = task
        payload = search_youtube(query, params=sp, use_cache=use_cache)
        cands = extract_candidates(payload)
        if kind == "chapter":
            kept = [c for c in cands if is_valid_chapter_candidate(c, ch_no, subject, cre)]
            return kind, ch_no, subject, kept
        return kind, 0, subject, cands

    with ThreadPoolExecutor(max_workers=16) as pool:
        futures = [pool.submit(worker, t) for t in chapter_tasks]
        for fut in as_completed(futures):
            kind, ch_no, subject, items = fut.result()
            if kind == "chapter":
                raw_results[ch_no].extend(items)
            else:
                for c in items:
                    sweep_candidates.append((subject, c))

    # Route teacher-sweep playlists into matching chapters (check specialized chapters first so Ch 26 beats Ch 02)
    priority_chapters = sorted(
        compiled_chapters,
        key=lambda c: (0 if c[0] in {26, 11, 12, 28, 44, 47, 56, 61, 73} else 1, c[0]),
    )
    for subj, cand in sweep_candidates:
        for ch_no, c_subj, _, _, _, _, _, cre in priority_chapters:
            if c_subj == subj and is_valid_chapter_candidate(cand, ch_no, c_subj, cre):
                raw_results[ch_no].append(cand)
                break

    # Process specialized chapters first when claiming global deduplication keys so Ch 02 never steals Ch 26's playlist
    processing_order = sorted(
        compiled_chapters,
        key=lambda c: (0 if c[0] in {26, 11, 12, 22, 23, 24, 28, 44, 47, 56, 60, 61, 72, 73} else 1, c[0]),
    )

    seen_global: set[tuple[str, str]] = set()
    chapter_records_map: dict[int, list[dict]] = {}
    chapter_meta_map: dict[int, dict] = {}

    for ch_no, subject, unit, class_lvl, weightage, scope, ch_name, _ in processing_order:
        candidates = raw_results[ch_no]

        enriched = []
        seen_local: set[tuple[str, str]] = set()
        for cand in candidates:
            gkey = (cand["provider"], cand["video_id"])
            if gkey in seen_global or gkey in seen_local:
                continue
            seen_local.add(gkey)
            exam, fmt = classify_exam_and_format(cand)
            sc = authority_score(cand, fmt)
            enriched.append((sc, exam, fmt, cand))

        playlists_pool = sorted([x for x in enriched if x[3]["provider"] == "playlist"], key=lambda x: -x[0])
        videos_pool = sorted([x for x in enriched if x[3]["provider"] == "youtube"], key=lambda x: -x[0])

        unique_ch: list[dict] = []
        edu_cap: dict[str, int] = {}

        def _try_take(pool_items: list, limit_count: int, per_edu_max: int) -> None:
            for sc, exam, fmt, cand in pool_items:
                if len(unique_ch) >= limit_count:
                    break
                gkey = (cand["provider"], cand["video_id"])
                if gkey in seen_global:
                    continue
                educator = resolve_educator(cand, subject, unit)
                ekey = f"{educator.casefold()}::{cand['provider']}"
                if edu_cap.get(ekey, 0) >= per_edu_max:
                    continue
                seen_global.add(gkey)
                edu_cap[ekey] = edu_cap.get(ekey, 0) + 1
                lang = resolve_language(cand)

                unique_ch.append(
                    {
                        "provider": cand["provider"],
                        "video_id": cand["video_id"],
                        "embed_video_id": cand["embed_video_id"],
                        "url": cand["url"],
                        "title": cand["title"],
                        "channel": cand["channel"],
                        "channel_url": cand["channel_url"],
                        "educator": educator,
                        "language": lang,
                        "thumbnail": cand["thumbnail"],
                        "subject": subject,
                        "unit": unit,
                        "chapter_no": ch_no,
                        "chapter": ch_name,
                        "class_level": class_lvl,
                        "weightage": weightage,
                        "syllabus_scope": scope,
                        "target_exam": exam,
                        "format": fmt,
                        "lesson_count": cand["lesson_count"],
                        "duration": cand["duration"],
                        "duration_sec": cand["duration_sec"],
                        "views_text": cand["views_text"],
                        "view_count": cand["view_count"],
                        "published": cand["published"],
                        "score": sc,
                        "note": build_pedagogy_note(cand, educator, exam, fmt, ch_name),
                        "sample_lectures": cand.get("sample_lectures") or [],
                    }
                )

        # Balanced selection: up to 10 diverse Full Playlists + up to 8 diverse Long-Form Lectures = up to 18/chapter
        _try_take(playlists_pool, 10, 2)
        _try_take(videos_pool, len(unique_ch) + 8, 2)
        if len(unique_ch) < 16:
            _try_take(playlists_pool + videos_pool, 16, 3)

        unique_ch.sort(key=lambda r: (-r["score"], -r["lesson_count"], -r["view_count"]))
        pl_cnt = sum(1 for r in unique_ch if r["provider"] == "playlist")

        yt_pl_q = urllib.parse.quote_plus(f"{ch_name} IIT JEE")
        yt_os_q = urllib.parse.quote_plus(f"{ch_name} JEE one shot")

        chapter_records_map[ch_no] = unique_ch
        chapter_meta_map[ch_no] = {
            "chapter_no": ch_no,
            "subject": subject,
            "unit": unit,
            "class_level": class_lvl,
            "weightage": weightage,
            "syllabus_scope": scope,
            "chapter": ch_name,
            "count": len(unique_ch),
            "playlist_count": pl_cnt,
            "video_count": len(unique_ch) - pl_cnt,
            "yt_playlists_url": f"https://www.youtube.com/results?search_query={yt_pl_q}&sp=EgIQAw%253D%253D",
            "yt_oneshots_url": f"https://www.youtube.com/results?search_query={yt_os_q}&sp=EgIYAg%253D%253D",
        }

    # Assemble in canonical syllabus order 1..80
    syllabus_out = [chapter_meta_map[n] for n in range(1, len(SYLLABUS) + 1)]
    all_entries: list[dict] = []
    for n in range(1, len(SYLLABUS) + 1):
        all_entries.extend(chapter_records_map[n])

    by_score = sorted(all_entries, key=lambda x: (-x["score"], -x["view_count"], x["chapter_no"]))
    for idx, rec in enumerate(by_score, 1):
        rec["global_rank"] = idx

    edu_buckets: dict[str, dict] = {}
    for rec in all_entries:
        edu = rec["educator"]
        if edu not in edu_buckets:
            edu_buckets[edu] = {
                "educator": edu,
                "subjects": Counter(),
                "total": 0,
                "playlists": 0,
                "videos": 0,
                "chapters": set(),
            }
        b = edu_buckets[edu]
        b["subjects"][rec["subject"]] += 1
        b["total"] += 1
        b["chapters"].add(rec["chapter_no"])
        if rec["provider"] == "playlist":
            b["playlists"] += 1
        else:
            b["videos"] += 1

    educators_out = []
    for edu, b in edu_buckets.items():
        primary_subject = b["subjects"].most_common(1)[0][0]
        educators_out.append(
            {
                "educator": edu,
                "subject": primary_subject,
                "total": b["total"],
                "playlists": b["playlists"],
                "videos": b["videos"],
                "chapter_coverage": len(b["chapters"]),
            }
        )
    educators_out.sort(key=lambda e: (-e["total"], -e["playlists"], e["educator"]))

    playlists_total = sum(1 for x in all_entries if x["provider"] == "playlist")
    chapters_with_pl = sum(1 for c in syllabus_out if c["playlist_count"] > 0)

    output = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "chapters_total": len(SYLLABUS),
            "chapters_populated": sum(1 for c in syllabus_out if c["count"] > 0),
            "chapters_with_playlists": chapters_with_pl,
            "entries_published": len(all_entries),
            "playlists_published": playlists_total,
            "videos_published": len(all_entries) - playlists_total,
            "distinct_educators": len(educators_out),
            "distinct_channels": len({x["channel"].casefold() for x in all_entries}),
            "queries_executed": len(chapter_tasks),
            "live_requests": STATS["requests"],
            "cached_requests": STATS["cached"],
        },
        "educators": educators_out,
        "syllabus": syllabus_out,
        "videos": all_entries,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def self_test() -> None:
    assert len(SYLLABUS) == 80, f"Expected 80 canonical JEE chapters, got {len(SYLLABUS)}"
    nums = [r[0] for r in SYLLABUS]
    assert nums == list(range(1, 81)), "Chapter numbers must be contiguous 1..80"

    math_chs = [r for r in SYLLABUS if r[1] == "Mathematics"]
    phys_chs = [r for r in SYLLABUS if r[1] == "Physics"]
    chem_chs = [r for r in SYLLABUS if r[1] == "Chemistry"]
    assert (len(math_chs), len(phys_chs), len(chem_chs)) == (29, 25, 26)

    assert parse_views("1.8M views") == 1_800_000
    assert parse_views("425K views") == 425_000
    assert parse_duration_seconds("7:42:15") == 27735
    assert parse_duration_seconds("45:10") == 2710

    cre_rot = re.compile(r"\b(rotational|rigid body|\brbd\b|moment of inertia)\b", re.I)
    good_pl = {
        "provider": "playlist",
        "video_id": "PL_A4M5IAkMacVaetkKqlCBstwK7TdjOa9",
        "title": "Rotational dynamics | Rigid Body Dynamics | RBD",
        "channel": "Mohit Tyagi",
        "lesson_count": 23,
        "duration_sec": 0,
        "view_count": 0,
        "sample_lectures": [],
    }
    assert is_valid_chapter_candidate(good_pl, 35, "Physics", cre_rot)
    assert resolve_educator(good_pl, "Physics", "Mechanics") == "ABJ Sir (Mohit Tyagi)"
    exam, fmt = classify_exam_and_format(good_pl)
    assert fmt == "Full Course" and exam == "JEE Main + Advanced"

    # Unverified random user playlist must be strictly rejected
    bad_spam_channel = {
        "provider": "playlist",
        "video_id": "PL_random1234567890",
        "title": "Rotational Motion IIT JEE Mohit Tyagi",
        "channel": "Random User Playlist",
        "lesson_count": 20,
        "duration_sec": 0,
        "view_count": 0,
        "sample_lectures": [],
    }
    assert not is_valid_chapter_candidate(bad_spam_channel, 35, "Physics", cre_rot)

    bad_tamil = {
        "provider": "youtube",
        "video_id": "zzzzzzzzzzz",
        "title": "Rotational Motion JEE Tamil One Shot",
        "channel": "Vedantu JEE Vaathi",
        "lesson_count": 0,
        "duration_sec": 7200,
        "view_count": 90000,
        "sample_lectures": [],
    }
    assert not is_valid_chapter_candidate(bad_tamil, 35, "Physics", cre_rot)

    print("self-test ok (80 canonical IIT-JEE chapters & verified-channel guard validated)", flush=True)


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        self_test()
        return 0
    self_test()
    use_cache = "--fresh" not in argv
    out = build_corpus(use_cache=use_cache)
    m = out["meta"]
    print(
        f"\n=== JEETUBE 80-CHAPTER CORPUS REPORT ===\n"
        f"Chapters populated      : {m['chapters_populated']} / {m['chapters_total']}\n"
        f"Chapters with playlists : {m['chapters_with_playlists']} / {m['chapters_total']}\n"
        f"Total JEE resources     : {m['entries_published']} ({m['playlists_published']} playlists, {m['videos_published']} lectures)\n"
        f"Distinct JEE educators  : {m['distinct_educators']} ({m['distinct_channels']} verified channels)\n"
        f"Output written to       : {OUT_PATH}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
