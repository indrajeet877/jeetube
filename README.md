# JEETube — Complete 80-Chapter IIT-JEE Main & Advanced YouTube Directory

**Live Web App:** [https://indrajeet877.github.io/jeetube/](https://indrajeet877.github.io/jeetube/)

A fast, zero-dependency static syllabus directory of **1,372 verified IIT-JEE Main and JEE Advanced YouTube playlists, marathon one-shots, PYQ revision checklists, and advanced problem-solving sessions** across all **80 canonical chapters** of Mathematics, Physics, and Chemistry.

## Verified Corpus Snapshot

| Metric | Value |
| :--- | :--- |
| **Canonical JEE Chapters** | **80 / 80** (`100%` populated · `80 / 80` chapters with `3–10` Full Playlists each) |
| **Subject Breakdown** | **Mathematics**: 489 (29 ch) · **Physics**: 432 (25 ch) · **Chemistry**: 451 (26 ch — Physical 11, Inorganic 6, Organic 9) |
| **YouTube Structure** | **688 Full Playlists / Courses** · **684 Long-Form Lectures (>20 min)** |
| **Study Formats** | **Full Course**: 680 · **One-Shot**: 586 · **Revision & PYQs**: 78 · **Adv Problems**: 28 |
| **Exam Tiers** | **JEE Main + Advanced**: 1,024 · **JEE Main**: 210 · **JEE Advanced**: 138 |
| **Teaching Mediums** | **Hinglish / Hindi**: 1,207 · **English**: 165 |
| **Verified JEE Faculty** | **53 Educators** across **49 Verified JEE Channels** (MT Sir, ABJ Sir, ALK Sir, NS Sir, Nishant Vora, Sakshi Vora, Ashish Arora / Physics Galaxy, Mohit Goenka / Eduniti, Rohit Mishra, Mathsmerizing, Maths Unplugged!, SKM Sir, AKK Sir, VJ Sir, Sachin Rana, DexterChem, MathonGo, Vinay Uppal, Physics Sir JEE, INSP, M.S. Chouhan, etc.) |

## Architecture & Reproduce

Pure Python 3 standard library builder + vanilla HTML/CSS/JS static frontend (GitHub Pages ready).

```bash
python3 scripts/build.py --self-test
python3 scripts/build.py
python3 -m http.server 8000
```

Open `http://127.0.0.1:8000/`.

## Student-First Features

1. **80-Chapter YouTube-Aligned Syllabus**: Splits commonly conflated chapters (*Permutations & Combinations* vs *Binomial Theorem*, *Ellipse* vs *Hyperbola*, *ITF* vs *SOT*, *Chemical* vs *Ionic Equilibrium*, *Gravitation* vs *Fluid Mechanics* vs *Elasticity*, *IUPAC* vs *Isomerism*) to match 1-to-1 how JEE educators publish playlists on YouTube, with syllabus scope tags (`JEE Adv Focus` / `JEE Main Focus`) where NTA JEE Main and JEE Advanced diverge.
2. **Multi-Dimensional Filtering & 7-Way Sorting**:
   - Separate Subjects (`All PCM`, `Mathematics`, `Physics`, `Chemistry`) + 13 Sub-Branch Unit chips (`Physical`, `Inorganic`, `Organic Chemistry`, `Algebra`, `Calculus`, `Mechanics`, `Electrodynamics`, etc.).
   - Study-Goal Modes (`Full Playlists`, `One-Shot Marathons`, `Quick Revision & PYQs`, `JEE Advanced Rank Boosters`), Teacher Explorer chips + 53-Faculty selector, YouTube Type (`Playlists` vs `Videos`), Exam Tier, Class (`11` / `12`), and Language (`Hinglish` / `English`).
   - 7 Sort Modes: *Syllabus Order*, *Best Relevance*, *Most Viewed on YouTube*, *Deepest Playlists (Lectures ↓)*, *Longest Marathon (Duration ↓)*, *Quickest Revision (Duration ↑)*, and *Highest JEE Weightage First*.
3. **Frictionless Direct YouTube Landing + Inline Player**:
   - Every card provides a primary **`Open Playlist on YouTube ↗`** / **`Watch on YouTube ↗`** CTA alongside an inline distraction-free `youtube-nocookie` `<dialog closedby="any">` preview player, `★ Save` personal study deck, and `✓ Completed` 80-chapter progress tracker (`localStorage`).
