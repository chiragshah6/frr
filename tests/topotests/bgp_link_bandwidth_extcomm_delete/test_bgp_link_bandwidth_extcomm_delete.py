#!/usr/bin/env python
# SPDX-License-Identifier: ISC

"""
Probe whether deleting outbound link-bandwidth can crash adj-out install.

Topology mirrors the reported production pattern:

  r1/r2 (AS 65001)
      |  eBGP + LB + RT
      v
     r3 (AS 4202100001)
      |  peer-group to_dc_peer + DC_RMAP_UNI_OUT
      |    seq 15: set extended-comm-list stripext delete  (LB:.*:.*)
      v
     r4 (AS 65004)

r3 receives two weighted IPv6 paths with link-bandwidth, then announces to
r4.  The outbound route-map deletes LB while preserving RT.  After the
route-map, subgroup_announce_check() still attempts cumulative LB handling
via ecommunity_replace_linkbw() because BATTR_RMAP_LINK_BW_SET was not set.

On current upstream code that path does:

  bgp_attr_set_ecommunity(attr, ecommunity_replace_linkbw(...));

It does not free the returned ecommunity.  Therefore the
old_ecom == new_ecom use-after-free described in the private-tree crash
cannot occur here even though the functional sequence is the same.

This test validates that sequence: no crash, LB stripped toward r4, RT kept.
"""

import functools
import json
import os
import sys

import pytest

CWD = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(CWD, "../"))

# pylint: disable=C0413
from lib import topotest
from lib.topogen import Topogen, get_topogen
from lib.topolog import logger


pytestmark = [pytest.mark.bgpd]

PREFIX = "2001:db8:100::/48"
R3_TO_R4 = "2001:db8:34::4"
ROUTE_TARGET = "RT:65001:100"


def setup_module(mod):
    topodef = {
        "s13": ("r1", "r3"),
        "s23": ("r2", "r3"),
        "s34": ("r3", "r4"),
    }
    tgen = Topogen(topodef, mod.__name__)
    tgen.start_topology()

    for router in tgen.routers().values():
        router.load_frr_config()

    tgen.start_router()


def teardown_module(mod):
    tgen = get_topogen()
    tgen.stop_topology()


def _path_extcommunity(path):
    return path.get("extendedCommunity", {}).get("string", "")


def _router_alive(router):
    err = router.check_router_running()
    if err:
        return "{} daemons not running: {}".format(router.name, err)
    return None


def _check_sessions():
    r3 = get_topogen().gears["r3"]

    alive = _router_alive(r3)
    if alive:
        return alive

    output = json.loads(r3.vtysh_cmd("show bgp ipv6 unicast summary json"))
    peers = output.get("peers", {})
    expected = {
        "2001:db8:13::1": "Established",
        "2001:db8:23::2": "Established",
        "2001:db8:34::4": "Established",
    }
    for peer, state in expected.items():
        peer_data = peers.get(peer)
        if not peer_data:
            return "r3: peer {} missing from summary".format(peer)
        if peer_data.get("state") != state:
            return "r3: peer {} state {!r}, expected {!r}".format(
                peer, peer_data.get("state"), state
            )
    return None


def _check_weighted_multipath():
    r3 = get_topogen().gears["r3"]

    alive = _router_alive(r3)
    if alive:
        return alive

    output = json.loads(r3.vtysh_cmd("show bgp ipv6 unicast {} json".format(PREFIX)))
    paths = output.get("paths", [])
    if len(paths) != 2:
        return "r3: expected two paths for {}, got {}".format(PREFIX, len(paths))

    for path in paths:
        ecoms = _path_extcommunity(path)
        if "LB:" not in ecoms:
            return "r3: inbound path missing LB: {!r}".format(ecoms)
        if ROUTE_TARGET not in ecoms:
            return "r3: inbound path missing {}: {!r}".format(ROUTE_TARGET, ecoms)

    logger.debug("r3 multipath ready with LB+RT on both paths")
    return None


def _check_export_after_lb_delete():
    tgen = get_topogen()
    r3 = tgen.gears["r3"]
    r4 = tgen.gears["r4"]

    alive = _router_alive(r3)
    if alive:
        return "r3 crashed while building adj-out after LB delete: {}".format(alive)

    # Also confirm advertised-routes on the DUT itself, then receiver RIB.
    adv = json.loads(
        r3.vtysh_cmd(
            "show bgp ipv6 unicast neighbors {} advertised-routes detail json".format(
                R3_TO_R4
            )
        )
    )
    adv_routes = adv.get("advertisedRoutes", {})
    if PREFIX not in adv_routes:
        return "r3: {} missing from advertised-routes to {}".format(PREFIX, R3_TO_R4)

    adv_paths = adv_routes[PREFIX].get("paths", [])
    if not adv_paths:
        return "r3: no advertised paths for {}".format(PREFIX)

    adv_ecoms = _path_extcommunity(adv_paths[0])
    if "LB:" in adv_ecoms:
        return "r3 advertised-routes still contain LB after stripext delete: {!r}".format(
            adv_ecoms
        )
    if ROUTE_TARGET not in adv_ecoms:
        return "r3 advertised-routes lost {}: {!r}".format(ROUTE_TARGET, adv_ecoms)

    rib = json.loads(r4.vtysh_cmd("show bgp ipv6 unicast {} json".format(PREFIX)))
    paths = rib.get("paths", [])
    if not paths:
        return "r4: {} not installed".format(PREFIX)

    ecoms = _path_extcommunity(paths[0])
    if "LB:" in ecoms:
        return "r4 still has LB after stripext delete: {!r}".format(ecoms)
    if ROUTE_TARGET not in ecoms:
        return "r4 lost {}: {!r}".format(ROUTE_TARGET, ecoms)

    logger.debug(
        "export after LB delete ok: r3 alive, advertised/received ecom=%r", ecoms
    )
    return None


def test_delete_link_bandwidth_no_adj_out_crash():
    """
    Run the reported policy sequence and require bgpd to stay up.

    Current upstream cumulative handling does not free the ecommunity returned
    by ecommunity_replace_linkbw(), so this should pass without crashing even
    when replace returns the same object after LB deletion.
    """
    tgen = get_topogen()

    if tgen.routers_have_failure():
        pytest.skip(tgen.errors)

    _, result = topotest.run_and_expect(_check_sessions, None, count=60, wait=1)
    assert result is None, result

    _, result = topotest.run_and_expect(
        _check_weighted_multipath, None, count=30, wait=1
    )
    assert result is None, result

    _, result = topotest.run_and_expect(
        _check_export_after_lb_delete, None, count=30, wait=1
    )
    assert result is None, result

    # Force a second announce cycle after the policy has already been applied.
    r3 = tgen.gears["r3"]
    r3.vtysh_cmd("clear bgp ipv6 unicast * soft out")

    _, result = topotest.run_and_expect(
        _check_export_after_lb_delete, None, count=30, wait=1
    )
    assert result is None, result

    alive = _router_alive(r3)
    assert alive is None, alive


if __name__ == "__main__":
    args = ["-s"] + sys.argv[1:]
    sys.exit(pytest.main(args))
