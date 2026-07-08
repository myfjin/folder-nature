"""folder-nature *mark* layer (v-next) — attribution, not prevention.

This subpackage adds the commercial-distribution layer on top of the core
semantic-identity tool:

    config      Configurable trademark + tier (NO default name — set explicitly)
    payload     The canonical watermark payload + CRC (what gets embedded)
    watermark   Redundant-channel stamp / extract / verify on real source files
    copy        Cooperative, tiered copy-limiter (honest customers)
    sale        Sale-time per-customer stamp + license-acceptance registry
    leak        Leak detection: find the mark in content -> trace buyer -> claim
    signing     Signed sha256 manifest + verify (authenticity + integrity)

LOAD-BEARING HONESTY (stated everywhere, never contradicted):

  * You CANNOT prevent copying of files on a customer's own disk. Nothing here
    tries to. This layer is ATTRIBUTION — it makes a copy traceable to the
    buyer, and makes the origin cryptographically checkable.
  * The watermark answers WHO bought this copy.
  * The signature answers whether the files are GENUINELY ours and UNALTERED.
    They are distinct and ship together; neither is a prevention mechanism.
  * The copy-limiter is a COOPERATIVE tool for honest customers, not anti-piracy.
"""

from __future__ import annotations

__mark_layer_version__ = "0.2.0-dev"
