# CADMATION Brand Guidelines

> **Document Version:** 1.0  
> **Brand:** CADMation  
> **Last Updated:** April 2026  
> **Template Reference:** Stealth Brand Guidelines  

---

## 1. Brand Identity & Purpose

CADMation is the Intelligent Local Copilot for CATIA V5 sheet metal design — a professional-grade desktop AI companion that works entirely offline, putting engineer-grade precision directly on the engineer's workstation.

Our identity is a commitment to **consistency, visibility, and reliability** within the high-stakes engineering workflow. We provide the technical infrastructure — Deep Specification Tree extraction, Interactive Tagging, and Smart Chat — to transform complex CAD data into actionable design intelligence.

In this ecosystem, **Interactive Tagging** isn't just a feature; it is the visual bridge between human intent and AI execution. Our identity system is engineered for flexibility and instant brand recognition, ensuring that the CADMation presence remains a stable, professional anchor across every touchpoint: the CATIA viewport, technical documentation, the desktop icon, and the welcome screen.

**Brand Promise:** Precision without compromise. Local without limitation. Smart without internet.

**Core Attribute:** Desktop-native AI for CATIA V5 sheet metal professionals — running entirely offline, with zero cloud dependency.

---

## 2. Logo System & Versions

The CADMation logo system provides three primary lockups, each engineered for maximum brand recognition across every conceivable interface — from the CATIA specification tree panel to A3 technical posters.

### 2.1 Horizontal Lockup
*The preferred version.* Use in the majority of applications for maximum visual impact and immediate brand recognition. The symbol and wordmark sit side by side in balanced proportion.

```
[CADMATION SYMBOL]  [CADMATION wordmark]
```

### 2.2 Vertical Lockup
Designed for tall, narrow layouts where horizontal space is constrained — such as vertical banners, sidebar icons, or mobile-first contexts.

```
[CADMATION SYMBOL]
[CADMATION wordmark]
```

### 2.3 Symbol Lockup
Reserved for environments where space is at an absolute premium — favicons, toolbar buttons, app icons, and notification badges.

> **Mandatory Requirement:** When the symbol is used alone (without the wordmark), the brand name "CADMation" must remain visible within the same visual field or primary container to ensure brand attribution. The symbol may never appear in isolation as a sole brand identifier without adjacent wordmark.

### 2.4 Logo File Deliverables
| File | Format | Use Case |
|---|---|---|
| `CADMation-Horizontal-FullColor.svg` | Vector | Primary digital use |
| `CADMation-Horizontal-Monochrome.svg` | Vector | Single-color print |
| `CADMation-Vertical-FullColor.svg` | Vector | Narrow layouts |
| `CADMation-Vertical-Monochrome.svg` | Vector | Single-color print |
| `CADMation-Symbol-FullColor.svg` | Vector | Icon / favicon |
| `CADMation-Symbol-Monochrome.svg` | Vector | Single-color icon |

---

## 3. Clear Space & Minimum Size

Negative space is essential. The minimum clear space around the logo is equal to the **height of the CADMation symbol** on all four sides. This breathing room prevents visual clutter and ensures the logo remains legible against complex engineering data, CAD backgrounds, and dense technical documents.

**Clear Space Rule:** Maintain a clear zone of at least `1×` the symbol height on all sides of every logo lockup.

### Minimum Dimensions

| Lockup Type | Digital Minimum | Print Minimum |
|---|---|---|
| **Horizontal Lockup** | 112px × 34px | 39mm × 12mm |
| **Vertical Lockup** | 88px × 53px | 31mm × 18mm |
| **Symbol (standalone)** | 24px × 24px | 8mm × 8mm |

---

## 4. Logo Misuse

To maintain the technical authority of the CADMation brand, the logo lockups must never be altered, redesigned, or modified in any way. The following actions are **strictly prohibited**:

- ❌ Do not change the logo color outside of the approved palette
- ❌ Do not outline, apply gradients, or use pattern fills on the logo
- ❌ Do not stretch, distort, warp, crop, or rotate the logo
- ❌ Do not add drop shadows or external visual effects
- ❌ Do not position the logo over off-brand colors or busy backgrounds
- ❌ Do not overlay the logo on active CATIA viewports where geometry or specification tree elements obscure brand legibility
- ❌ Do not separate the symbol from the wordmark in the horizontal lockup
- ❌ Do not add extra text, icons, or graphic elements inside the logo boundary
- ❌ Do not use unapproved background colors behind any lockup
- ❌ Do not recreate or redraw the logo from scratch without written approval

**When in doubt:** Default to monochrome (black or white) lockup on any colored background.

---

## 5. Brand Color Palette

The CADMation palette is rooted in **industrial neutrals** with high-contrast functional colors for UI feedback. Every color serves a specific purpose in the CATIA plugin context.

### Primary Colors

| Color | Name | Hex | RGB | CMYK | Use |
|---|---|---|---|---|---|
| ![#2A2B2A](https://via.placeholder.com/24/2A2B2A/2A2B2A?text=) | **Dark Grey** | `#2A2B2A` | 42, 43, 42 | C0 M1 Y1 K84 | Primary backgrounds, text on light |
| ![#191919](https://via.placeholder.com/24/191919/191919?text=) | **Rich Black** | `#191919` | 25, 25, 25 | C0 M0 Y0 K90 | Maximum contrast, headings, dark UI |

### Secondary / Functional Colors

| Color | Name | Hex | RGB | CMYK | Use |
|---|---|---|---|---|---|
| ![#E63F26](https://via.placeholder.com/24/E63F26/E63F26?text=) | **Bright Red-Orange** | `#E63F26` | 230, 63, 38 | C0 M73 Y84 K10 | Critical BOM errors, STL isolation failures, high-priority alerts |
| ![#FFCC33](https://via.placeholder.com/24/FFCC33/FFCC33?text=) | **Signal Yellow** | `#FFCC33` | 255, 204, 51 | C0 M20 Y80 K0 | Warnings, interactive tagging highlights, selection |
| ![#98CBCB](https://via.placeholder.com/24/98CBCB/98CBCB?text=) | **Teal Blue** | `#98CBCB` | 152, 203, 203 | C25 M0 Y0 K20 | Successful PartNumber resolution, confirmed system processes, info states |

### Neutral Scale

| Name | Hex | Use |
|---|---|---|
| **CATIA Grey** | `#F4F4F4` | Light UI backgrounds, inactive panels |
| **Panel Grey** | `#E0E0E0` | Borders, dividers |
| **Text Grey** | `#6B6B6B` | Secondary text, disabled states |

### Color Proportions
- **70%** Rich Black / Dark Grey (dominant — background, UI chrome)
- **15%** White / CATIA Grey (neutral space, text on dark)
- **10%** Functional colors (alerts, highlights, interactive states)
- **5%** Teal Blue (success, confirmation — used sparingly)

---

## 6. Typography: Roboto FLEX

**Roboto FLEX** is the exclusive typeface for CADMation. It provides the variable axis necessary for technical clarity, hierarchy, and precision across all digital and print touchpoints.

> *Why Roboto FLEX?* CADMation operates inside the CATIA V5 environment — a dense, information-rich engineering interface. Roboto FLEX's variable weight axes (wdth, wght, opsz) allow the same font file to serve everything from 9px specification tree labels to 48px section headings, without switching font families.

### Approved Weights

| Weight | Variable Axis | Use |
|---|---|---|
| **Black** | `wght=900` | Hero headings, watermark text |
| **Bold** | `wght=700` | Section headings, UI labels |
| **SemiBold** | `wght=600` | Sub-headings, key values |
| **Medium** | `wght=500` | Interactive elements, buttons |
| **Regular** | `wght=400` | Body text, descriptions |
| **Light** | `wght=300` | Tertiary info, timestamps |

*Italic variants are approved for emphasis within body copy.*

### Typography Hierarchy

| Role | Font | Size | Weight | Line Height |
|---|---|---|---|---|
| Document Title | Roboto FLEX | 32px / 18pt | Bold | 1.2 |
| Section Heading | Roboto FLEX | 20px / 12pt | Bold | 1.3 |
| Sub-Heading | Roboto FLEX | 16px / 10pt | SemiBold | 1.4 |
| Body Copy | Roboto FLEX | 14px / 9pt | Regular | 1.5 |
| Labels & Tags | Roboto FLEX | 12px / 8pt | Medium | 1.4 |
| Caption / Metadata | Roboto FLEX | 10px / 7pt | Light | 1.3 |

### Typography Prohibitions
- 🚫 Use of unauthorized fonts (Raleway, Arial, Helvetica, Open Sans, etc.)
- 🚫 Applying strokes, outlines, or drop shadows to typography
- 🚫 Using font weights not listed in the Approved Weights table
- 🚫 Converting text to outlines in logo lockups
- 🚫 Mixing Roboto FLEX with other typefaces within the same document

---

## 7. Image Style: "Focus on the Important"

Our imagery mirrors the precision of the CADMation plugin itself. Every image follows a **"singular focus" rule** — isolation to guide the viewer's eye directly to the technical subject.

### Core Principles

1. **Singular Focus** — One primary subject per image. Never show the entire CATIA interface; show the *important part* — the specification tree tag, the BOM entry, the part number, the error highlight.
2. **Shallow Depth of Field** — Use selective focus to blur backgrounds and distractions. The technical subject must remain razor-sharp.
3. **Minimal Backgrounds** — Neutral or solid backgrounds only. No assembly clutter, no distracting geometry.
4. **High Contrast** — The subject must pop from the background. Use the color palette to separate subject from context.

### Approved Image Types
- Single sheet metal part isolated on neutral background
- Specification tree nodes with active Interactive Tagging highlights
- BOM list entries with color-coded status (red for error, teal for confirmed, yellow for warning)
- STL isolation view with geometry hidden/visible toggle demonstration
- Rough Stock scraping workflow screenshots
- Close-up UI panels showing Smart Chat interaction

### Image Prohibitions
- 🚫 Full CATIA interface screenshots as hero images (too much noise)
- 🚫 Busy CAD geometry backgrounds without selective blur
- 🚫 Stock photography of unrelated engineering or office scenes
- 🚫 Low-resolution or pixelated screenshots
- 🚫 Multiple competing focal points in a single image

---

## 8. Tone of Voice: Precise & Purposeful

The CADMation voice is defined by the **"Class Utility Simple"** principle. Our language must be as efficient as the code it describes.

**Voice Pillars:**

| Pillar | Definition | Example |
|---|---|---|
| **Precise** | Every word is technically accurate. No fluff, no filler. Engineering-grade precision in every sentence. | "Extracting 247 PartNumbers from active specification tree" — not "Looking at your design data" |
| **Purposeful** | Every word Educates, Entices, or Encourages. Nothing is said just to fill space. | "Interactive Tagging transforms your specification tree into a searchable, filterable BOM" |
| **Simple** | Get to the point quickly. Simple but smart is the way to go. Short sentences. Active voice. No jargon unless it's the right term. | "Done." — not "The operation has been completed successfully." |

### Writing Guidelines
- Use **active voice** exclusively
- Keep sentences under **20 words** for UI copy
- Use **technical terms correctly** — BOM, PartNumber, STL, Specification Tree, Rough Stock
- Never use **corporate filler** ("synergy", "best-in-class", "leveraging", "cutting-edge")
- **Spell out abbreviations** on first use: "Bill of Materials (BOM)"
- Numbers >spell out one through nine; use numerals for 10+

### Messaging Matrix

| Context | Tone | Example |
|---|---|---|
| Error alerts | Firm, clear, helpful | "STL Isolation Failed: Body 'Cut_Revolve_1' has non-manifold topology." |
| Success confirmation | Confident, concise | "PartNumber Resolved: 247 entries matched." |
| Tutorial / documentation | Patient, instructive, thorough | "Interactive Tagging lets you assign custom labels to any specification tree node, creating a searchable BOM layer." |
| Feature announcement | Precise, benefit-focused | "Deep Specification Tree extraction surfaces every PartNumber in your active CATIA document — offline, instantly." |
| Marketing / landing page | Professional, forward-looking | "CADMation: The Intelligent Local Copilot for CATIA V5 Sheet Metal Design." |

---

## 9. Technical Reference

### Product Architecture
- **Product Name:** CADMation
- **Product Type:** Desktop AI Copilot Plugin for CATIA V5
- **Specialization:** Sheet Metal Design Workflow Automation
- **Core Features:** Deep Specification Tree Extraction, Interactive Tagging, Smart Chat, BOM Extraction, STL Isolation, Rough Stock Scraping
- **Operating Mode:** Fully offline (local inference, no cloud dependency)

### Licensing & Distribution
- **License:** MIT License
- **Distribution Model:** Single-file executable, easy deployment within engineering departments
- **Version Range:** v2.0.0 through v2.2.0 (active development)

### Reliability Pillars
The CADMation brand stands on three technical pillars:

1. **WebSocket Architecture** — Real-time, low-latency communication between the CATIA plugin and local AI inference engine
2. **Single-File Distribution** — Zero-config installation for enterprise deployment
3. **SPA Tracking & PartNumber Resolution** — Using reference document names to prevent duplicate naming mismatches, ensuring BOM accuracy

### Brand Contact
- **Website:** cadmation.io *(placeholder)*
- **Support:** support@cadmation.io *(placeholder)*
- **Documentation:** docs.cadmation.io *(placeholder)*

---

*This document is a living brand asset. For updates, approval requests, or brand questions, contact the CADMation brand team.*
