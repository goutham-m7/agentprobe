# v0.2 execution plan

REGULAR coding variant: repository has no .rebaseai configuration in its root listing.

Deliver ROADMAP items in numerical order, each as a specific local main commit followed by a roadmap closure commit/next delivery update. Test before implementation at the owning boundary: HTTP transport (fake remote HTTP), runner (real local callables), label CLI (subprocess stdin), calibration (paired data), artifact XML (parser), repeat CLI and packaging (real install/build).

External doubles: httpx transport stands in for paid HTTP service; synthetic callables exercise deterministic/alternating behavior; no internal logic mocks. Not tested: paid endpoint availability/billing, real-human agreement, GitHub writes, arbitrary tool effects. These are explicitly outside the milestone.

Canonical gates: make check, make demo, uv build, then fresh local clone and isolated wheel install. ROADMAP.md carries item status and delivery commit ranges.
