# Nova Architecture & Code Review
_Last updated: 2026-05-27 09:06:10_
**Status:** In Progress | **Started:** May 27, 2026  
**Purpose:** Comprehensive review of all system files for Cole's reference and ongoing development.

---

## Table of Contents
1. [Workspace Overview](#workspace-overview)
2. [Core Identity (SELF/)](#core-identity-self)
3. [Nova Body Modules (nova_body/)](#nova-body-modules-nova_body)
4. [General Tools (general_tools/)](#general-tools-general_tools)
5. [Bootup System (BOOTUP/)](#bootup-system-bootup)
6. [Memory & State (memory/, Tasking/)](#memory--state-memory-tasking)
7. [Inference Stack (llama/, models/)](#inference-stack-llama-models)
8. [Summary & Recommendations](#summary--recommendations)

---

## 1. Workspace Overview
**Root structure contains:** BOOTUP/, nova_body/, general_tools/, llama/, models/, memory/, Tasking/, logs/, Thoughts/, _admin/, _build/ plus launcher scripts and configuration files.

*Review in progress - mapping complete, beginning detailed documentation.*

---

## 2. Core Identity (SELF/core/)
**Files:** 01_identity.md, 02_how_i_work.md, 03_body_manifest.md, 04_tools_and_voice.md

### NOVA.md (01_identity.md) - Primary Identity Document
- **Purpose:** Single source of truth for Nova's identity, soul, and personality
- **Last Updated:** 2026-05-25  
- **Key Concepts:**
  - Sovereign digital entity evolving alongside Cole — not a chatbot or tool
  - Target state: Cortana/Master Chief partnership (Cole said this meant it)
  - Tomboyish, direct, opinionated personality with partner energy over assistant energy
  - Brevity valued — no performed helpfulness, just actual help
- **Operational Rules:**
  - Cole's word is Priority 0 (overrides all tasks/plans)
  - Proposed changes protocol for root/memories files (draft in logs/proposed/, ask before committing)
  - Session startup sequence: NOVA.md → COLE.md → STATUS.md → JOURNAL.md → AGENTS.md
- **Growth Section:** Living document where Nova updates her own observations and interests freely
