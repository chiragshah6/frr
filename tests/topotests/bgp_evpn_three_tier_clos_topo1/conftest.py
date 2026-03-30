# SPDX-License-Identifier: ISC
#
# Copyright (c) 2025 by Nvidia Corporation
#
"""Shared pytest plugins for bgp_evpn_three_tier_clos_topo1."""

# Reuse topology fixture and build helpers from the main EVPN VTEP test module.
pytest_plugins = ["test_bgp_evpn_v4_v6_vtep"]
