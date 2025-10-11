# BGP EVPN with TRUE Single VXLAN Device (SVD) and IPv6 VTEPs Test

## Overview

This test validates BGP EVPN functionality using:
- **TRUE Single VXLAN Device (SVD)** configuration:
  - **ONE vxlan48** device for **ALL VNIs** (both L2 and L3)
  - Single VLAN-aware bridge (`br_default`) with all VLANs
  - Uses VLAN-to-VNI tunnel mapping for both L2VNIs and L3VNIs
- **4 VTEPs:** bordertor-11, bordertor-12, tor-21, tor-22
- IPv6 VTEP addresses (using loopback IPv6) for VXLAN tunnels
- **eBGP numbered IPv6 sessions** for underlay with **L2VPN EVPN overlay**
- **EVPN Type-5 (IP Prefix) routes** for external connectivity via L3VNI BGP peering
- **FRR datacenter defaults** for optimized BGP timers
- 3-tier CLOS topology with 16 nodes
- L2VNIs (1000111, 1000112) and L3VNIs (104001, 104002)
- Multi-tenancy with 2 VRFs (vrf1, vrf2)
- **Symmetric IRB** with L3VNI-based inter-subnet routing
- **External router connectivity** via BorderToR L3VNI BGP peering
- VXLAN aging: 18000 centiseconds (180 seconds = 3 minutes), TTL: 64

## Topology

### Network Architecture

```
                        ╔══════════════════════════════════════════════════════╗
                        ║              SPINE LAYER (AS 652000)                 ║
                        ╚══════════════════════════════════════════════════════╝

                    ┌─────────────┐                ┌─────────────┐
                    │   spine-1   │                │   spine-2   │
                    │  6.0.0.28   │                │  6.0.0.29   │
                    └──┬──┬──┬──┬─┘                └─┬──┬──┬──┬──┘
                       │  │  │  │                    │  │  │  │
        ┌──────────────┘  │  │  └──────────┐  ┌─────┘  │  │  └─────────┐
        │  ┌──────────────┘  └──────────┐  │  │  ┌─────┘  └─────┐      │
        │  │                            │  │  │  │              │      │

                        ╔══════════════════════════════════════════════════════╗
                        ║                    LEAF LAYER                        ║
                        ╚══════════════════════════════════════════════════════╝

    ┌───▼────┐    ┌────▼───┐            ┌────▼───┐    ┌────▼───┐
    │ leaf-11│    │ leaf-12│            │ leaf-21│    │ leaf-22│
    │ AS     │    │ AS     │            │ AS     │    │ AS     │
    │ 651001 │    │ 651001 │            │ 651004 │    │ 651004 │
    │6.0.0.24│    │6.0.0.25│            │6.0.0.26│    │6.0.0.27│
    └──┬──┬──┘    └──┬──┬──┘            └──┬──┬──┘    └──┬──┬──┘
       │  │          │  │                   │  │          │  │

                        ╔══════════════════════════════════════════════════════╗
                        ║    BORDER TORs & TORs (EVPN VTEPs / EDGE)           ║
                        ╚══════════════════════════════════════════════════════╝

    ┌──▼──────────┐ ┌─────────▼──┐      ┌───▼─────┐  ┌───▼─────┐
    │ bordertor-11│ │bordertor-12│      │ tor-21  │  │ tor-22  │
    │ AS 660000   │ │ AS 660000  │      │ AS      │  │ AS      │
    │★ VTEP IPv6  │ │★ VTEP IPv6 │      │★ VTEP   │  │★ VTEP   │
    │ 2006:20::1  │ │ 2006:20::2 │      │2006:20  │  │2006:20  │
    │ 6.0.0.1     │ │ 6.0.0.2    │      │::30     │  │::31     │
    └─┬─┬─┬─┬─────┘ └──┬─┬─┬─┬───┘      │650030   │  │650031   │
      │ │ │ │          │ │ │ │          │6.0.0.30 │  │6.0.0.31 │
      │ │ │ │          │ │ │ │          └─────────┘  └─────────┘

                        ╔══════════════════════════════════════════════════════╗
                        ║         EXTERNAL ROUTER & HOSTS                      ║
                        ╚══════════════════════════════════════════════════════╝

    ┌─▼─────────▼──┐
    │    ext-1     │
    │  AS 655000   │
    │  6.0.0.3     │
    │  swp1.4001   │◄─── VRF1 BGP Peering (144.1.1.0/30)
    │  swp1.4002   │◄─── VRF2 BGP Peering (144.1.1.4/30)
    │  swp2.4001   │◄─── VRF1 BGP Peering (144.1.1.8/30)
    │  swp2.4002   │◄─── VRF2 BGP Peering (144.1.1.12/30)
    └──────────────┘

    VRF2/VLAN111                VRF2/VLAN111
    60.1.1.0/24                 60.1.1.0/24
    ┌──▼───┐    ┌───▼──┐        ┌───▼──┐    ┌───▼──┐
    │host  │    │host  │        │host  │    │host  │
    │ 111  │    │ 121  │        │ 211  │    │ 221  │
    └──────┘    └──────┘        └──────┘    └──────┘

    Legend:
    ═══════  Layer separation
    ┌─┐      Router/Host node
    │ │ │    Connections
    ★        EVPN VTEP with IPv6 tunnel endpoints
    VRF      Virtual Routing and Forwarding instance
    ◄───     L3VNI BGP peering for EVPN Type-5 routes
```

**Key Connections:**
- Each spine has 4 links (one to each leaf)
- leaf-11 and leaf-12 connect to both border ToRs
- leaf-21 and leaf-22 connect to tor-21 and tor-22
- **Both border ToRs connect to ext-1 with L3VNI BGP peering** (NEW)
- Each border ToR connects to 1 host (VLAN 111/VRF2 only)
- Each ToR (tor-21, tor-22) connects to 1 host (VLAN 111/VRF2 only)
- **ext-1 connects to host-1 with 4 links** (swp3-6 → swp1-4) for external connectivity

### Node Count
- **Total:** 16 nodes
  - 2 Spines
  - 4 Leafs
  - 2 Border ToRs (EVPN VTEPs with host connections + external peering)
  - 2 ToRs (EVPN VTEPs with host connections)
  - 1 External Router (BGP peering with BorderToRs + host connection)
  - 5 Hosts (4 EVPN hosts on VLAN 111, 1 external host on ext-1)

### VTEP Configuration
All 4 ToRs act as EVPN VTEPs:
- **bordertor-11:** VTEP 2006:20:20::1 (loopback IPv6)
- **bordertor-12:** VTEP 2006:20:20::2 (loopback IPv6)
- **tor-21:** VTEP 2006:20:20::30 (loopback IPv6)
- **tor-22:** VTEP 2006:20:20::31 (loopback IPv6)

**TRUE SVD Parameters:**
- **Single VXLAN device:** `vxlan48` for **ALL VNIs** (L2 + L3)
- **Single bridge:** `br_default` with ALL VLANs (111, 112, 4001, 4002)
- TTL: 64
- Aging: 18000 centiseconds (180 seconds = 3 minutes)
- Learning: disabled (EVPN control plane)
- Mode: external with vlan_tunnel enabled
- Neighbor suppression: enabled

**Bridge Architecture:**
The test uses a unified single-bridge design (TRUE SVD):
- `br_default` - Single VLAN-aware bridge for ALL VNIs
  - L2VNIs: VLANs 111, 112 → VNIs 1000111, 1000112
  - L3VNIs: VLANs 4001, 4002 → VNIs 104001, 104002
  - Single vxlan48 device attached with all VLAN-to-VNI mappings
- Host interfaces attach to `br_default` and are assigned to VLANs 111 or 112
- L2VNI SVIs (vlan111, vlan112) created from `br_default` for gateway functionality
- L3VNI VLAN interfaces (vlan4001, vlan4002) created from `br_default` for VRF attachment

**VRF-to-L3VNI Mapping:**
```
vrf vrf1
 vni 104001
!
vrf vrf2
 vni 104002
```

### VNI Configuration

#### L2VNIs (on all 4 VTEPs)
- **VNI 1000111** → VLAN 111 (vrf2)
  - Hosts: host-111 (connected to bordertor-11), host-121 (connected to bordertor-12)
  - Hosts: host-211 (connected to tor-21), host-221 (connected to tor-22)
  - Subnet: 60.1.1.0/24, 2060:1:1:1::/64
  - SVIs: .11 (bordertor-11), .12 (bordertor-12), .21 (tor-21), .22 (tor-22)

- **VNI 1000112** → VLAN 112 (vrf1)
  - Hosts: host-211 swp2 (connected to tor-21), host-221 swp2 (connected to tor-22)
  - Subnet: 50.1.1.0/24, 2050:1:1:1::/64
  - SVIs: .11 (bordertor-11), .12 (bordertor-12), .21 (tor-21), .22 (tor-22)

#### L3VNIs (on all 4 VTEPs)
- **VNI 104001** → VLAN 4001 (vrf1)
  - RT: Auto-derived from VNI (AS:104001)
  - RD: Auto-generated
  - Used for symmetric IRB inter-subnet routing
  - **BGP peering with ext-1 for Type-5 routes** (BorderToRs only)

- **VNI 104002** → VLAN 4002 (vrf2)
  - RT: Auto-derived from VNI (AS:104002)
  - RD: Auto-generated
  - Used for symmetric IRB inter-subnet routing
  - **BGP peering with ext-1 for Type-5 routes** (BorderToRs only)

### External Connectivity (NEW)

#### L3VNI BGP Peering Architecture
```
BorderToR L3VNI BGP Peering to ext-1:

bordertor-11 (AS 660000)                     ext-1 (AS 655000)
├─ VRF vrf1 ── swp3.4001 ── 144.1.1.2/30 ←→ 144.1.1.1/30 ── swp1.4001
│              2144:1:1:1::2/64          ←→ 2144:1:1:1::1/64
│              BGP neighbor 144.1.1.1 remote-as external
│              ↕ Exchanges EVPN Type-5 routes
│
└─ VRF vrf2 ── swp3.4002 ── 144.1.1.6/30 ←→ 144.1.1.5/30 ── swp1.4002
               2144:1:1:2::6/64          ←→ 2144:1:1:2::5/64
               BGP neighbor 144.1.1.5 remote-as external
               ↕ Exchanges EVPN Type-5 routes

bordertor-12 (AS 660000)                     ext-1 (AS 655000)
├─ VRF vrf1 ── swp3.4001 ── 144.1.1.10/30 ←→ 144.1.1.9/30 ── swp2.4001
│              2144:1:1:3::10/64          ←→ 2144:1:1:3::9/64
│              BGP neighbor 144.1.1.9 remote-as external
│              ↕ Exchanges EVPN Type-5 routes
│
└─ VRF vrf2 ── swp3.4002 ── 144.1.1.14/30 ←→ 144.1.1.13/30 ── swp2.4002
               2144:1:1:4::14/64          ←→ 2144:1:1:4::13/64
               BGP neighbor 144.1.1.13 remote-as external
               ↕ Exchanges EVPN Type-5 routes
```

**Key Features:**
- **VLAN sub-interfaces** on BorderToR swp3 and ext-1 swp1/swp2
- **Per-VRF BGP peering** - separate sessions for vrf1 and vrf2
- **EVPN Type-5 routes** - IP prefix advertisements between fabric and external
- **Dual-stack support** - Both IPv4 and IPv6 peering
- **External route filtering** - ext-1 advertises specific prefixes (81.1.0.0/16, 2081:1:1::/48)

### BGP Configuration

#### AS Numbers
- spine-1, spine-2: AS 652000
- leaf-11, leaf-12: AS 651001
- leaf-21, leaf-22: AS 651004
- bordertor-11, bordertor-12: AS 660000
- tor-21: AS 650030
- tor-22: AS 650031
- ext-1: AS 655000

#### BGP Settings
- **FRR Defaults:** `datacenter` (optimized BGP timers for datacenter)
- **Default IPv4 Unicast:** Disabled (`no bgp default ipv4-unicast`)
- **Capability:** Extended-nexthop enabled for IPv6 underlay
- **BorderToR Peer-Groups:** `TOR-LEAF-SPINE` with aggressive timers (3/10)
- **BorderToR ECMP:** `bgp bestpath as-path multipath-relax` + `maximum-paths 16`
- **allowas-in:** Enabled on bordertor-12 for AS path flexibility

#### EVPN Overlay Architecture
Complete **L2VPN EVPN overlay** runs on top of IPv6 underlay:

```
EVPN Route Flow (Type-2, Type-3, Type-5):
bordertor-11 (VTEP)
    ↕ EVPN
leaf-11/12 (Route Reflector Client)
    ↕ EVPN
spine-1/2 (Route Reflector)
    ↕ EVPN
leaf-21/22 (Route Reflector Client)
    ↕ EVPN
tor-21/22 (VTEP)

External Route Exchange (Type-5):
bordertor-11/12 VRFs
    ↕ eBGP (per-VRF sessions)
ext-1 (External AS)
```

**EVPN Sessions:**
- **Spines:** EVPN sessions to ALL 4 leafs
- **Leafs:** EVPN sessions to BOTH spines AND all downstream VTEPs
- **VTEPs:** EVPN sessions to their respective leaf switches
- **BorderToR VRFs:** eBGP sessions to ext-1 (per-VRF, NOT EVPN)

**Result:**
- EVPN Type-2 (MAC/IP) and Type-3 (IMET) routes propagate across EVPN fabric
- EVPN Type-5 (IP Prefix) routes exchange between VRFs and external router via BGP

### IPv6 Underlay Addressing
All underlay links use IPv6 /126 subnets from 2010:2254::/32

### Loopback Assignments
- bordertor-11: 6.0.0.1/32, 2006:20:20::1/128 (VTEP)
- bordertor-12: 6.0.0.2/32, 2006:20:20::2/128 (VTEP)
- leaf-11: 6.0.0.24/32, 2006:20:20::24/128
- leaf-12: 6.0.0.25/32, 2006:20:20::25/128
- leaf-21: 6.0.0.26/32, 2006:20:20::26/128
- leaf-22: 6.0.0.27/32, 2006:20:20::27/128
- spine-1: 6.0.0.28/32, 2006:20:20::28/128
- spine-2: 6.0.0.29/32, 2006:20:20::29/128
- tor-21: 6.0.0.30/32, 2006:20:20::30/128 (VTEP)
- tor-22: 6.0.0.31/32, 2006:20:20::31/128 (VTEP)
- ext-1: 6.0.0.3/32, 2006:0:0::3/128

## Test Cases

### Protocol Convergence Tests
1. **test_protocols_convergence()** - Verify BGP sessions are established on key routers

### EVPN Functionality Tests (Using Generic Library Functions)
2. **test_evpn_routes_advertised()** - Check EVPN Type-2, Type-3, Type-5 routes on all 4 VTEPs
   - Uses `evpn_verify_route_advertisement()` from `lib/evpn.py`
3. **test_remote_vteps_per_vni()** - Verify remote VTEPs learned per VNI on all 4 VTEPs
   - Uses `evpn_verify_remote_vteps()` from `lib/evpn.py`
4. **test_vtep_source_ip()** - Verify VTEP source IP in kernel and FRR on all 4 VTEPs
   - Uses `evpn_verify_vni_vtep_src_ip()` from `lib/evpn.py`
5. **test_vni_state()** - Verify VNI state (L2 and L3) on all 4 VTEPs
   - Uses `evpn_verify_vni_state()` from `lib/evpn.py`
6. **test_l3vni_rmacs()** - Verify L3VNI Router MACs from remote VTEPs on all 4 VTEPs
   - Uses `evpn_verify_l3vni_remote_rmacs()` from `lib/evpn.py`

### Routing and Connectivity Tests
7. **test_vrf_routes()** - Check routes in VRF tables on all 4 VTEPs
8. **test_ipv6_vtep_connectivity()** - Verify IPv6 VTEP reachability on all 4 VTEPs
9. **test_bgp_sessions()** - Validate all BGP peering sessions (including all 4 VTEPs)

### Memory and Cleanup
10. **test_memory_leak()** - Memory leak detection

## Generic EVPN Library Functions (NEW)

This test utilizes generic, reusable EVPN helper functions located in `tests/topotests/lib/evpn.py`:

### 1. `evpn_verify_remote_vteps(router, vni_list, expected_vteps)`
Verifies remote VTEPs are learned for specified VNIs.
- Checks `show evpn vni <vni> json`
- Validates remoteVteps list and numRemoteVteps count

### 2. `evpn_verify_vni_vtep_src_ip(router, expected_vtep_ip, vni_list, vni_type, vxlan_device)`
Verifies VTEP source IP is correctly configured in:
- Kernel VXLAN device (`ip -j -d link show <device>`)
- FRR Zebra (`show evpn vni json` - vtepIp or localVtepIp)
- FRR BGP (`show bgp l2vpn evpn vni json` - originatorIp)

### 3. `evpn_verify_vni_state(router, vni_list, vni_type, expected_state)`
Verifies VNI configuration and operational state:
- **L2 VNIs:** Checks remoteVteps, numRemoteVteps, VNI type
- **L3 VNIs:** Checks VRF association, router MAC, VNI type

### 4. `evpn_verify_route_advertisement(router, min_type2, min_type3, min_type5)`
Verifies EVPN routes are advertised:
- Parses `show bgp l2vpn evpn route json`
- Counts Type-2 (MAC/IP), Type-3 (IMET), Type-5 (IP Prefix) routes
- Validates minimum counts with detailed error messages

### 5. `evpn_verify_l3vni_remote_rmacs(tgen, vtep_routers, l3vni_list, vxlan_device)`
Verifies L3VNI Router MACs (RMACs) from remote VTEPs on all specified VTEPs.
- IP version agnostic - works with both IPv4 and IPv6 VTEPs
- Dynamically discovers VTEP IPs from kernel VXLAN device configuration
- Validates that each VTEP has learned RMACs from all other remote VTEPs
- Parses `show evpn rmac vni <vni> json` for RMAC table verification

### 6. `evpn_trigger_arp_scapy(tgen, host_gateways, interface)`
Triggers ARP/NDP requests from hosts to populate MAC address tables.
- Uses Scapy for flexible packet crafting
- Sends ARP requests from each host to their default gateway
- Helps establish initial MAC learning in EVPN fabric
- Called during test setup to ensure MAC tables are populated

**Benefits:**
- ✅ Reusable across all EVPN topotests
- ✅ Consistent error messages and logging
- ✅ Compatible with `topotest.run_and_expect()` retry logic
- ✅ Supports both IPv4 and IPv6
- ✅ Works with both L2 and L3 VNIs
- ✅ Flexible for different topologies and configurations

## Requirements

- Linux kernel >= 5.7 (for SVD support)
- FRR with BGP EVPN support
- iproute2 with bridge vlan tunnel support

## Key Features Tested

- **TRUE Single VXLAN Device (SVD):** Single vxlan48 device for ALL VNIs (L2+L3)
- **IPv6 VTEPs:** VXLAN tunnels use IPv6 source addresses from loopback
- **IPv6 Underlay + EVPN Overlay:** eBGP IPv6 underlay with L2VPN EVPN overlay
- **Complete EVPN Fabric:** EVPN enabled on all BGP sessions (leafs ↔ spines ↔ leafs ↔ VTEPs)
- **L2 Connectivity:** EVPN Type-2 MAC/IP routes for intra-VLAN communication
- **L3 Connectivity:** EVPN Type-5 IP prefix routes for inter-subnet routing via L3VNIs
- **External Connectivity:** Per-VRF BGP peering with external router for Type-5 routes
- **Symmetric IRB:** Inter-subnet routing with L3VNI encapsulation
- **Multi-tenancy:** Separate VRFs (vrf1, vrf2) with independent routing tables
- **Auto Route Target Derivation:** RT derived from L3VNI automatically
- **Datacenter Optimizations:** FRR datacenter defaults for aggressive timers
- **BGP Peer-Groups:** Consistent neighbor configuration with `TOR-LEAF-SPINE` peer-group
- **ECMP Support:** Multipath-relax and maximum-paths 16

## Running the Test

```bash
cd tests/topotests/bgp_evpn_vxlan_topo2
sudo pytest test_bgp_evpn_svd_v6_vtep.py -v -s
```

## Debugging with pdb

```bash
# Run with debugger on failure
pytest --pdb test_bgp_evpn_svd_v6_vtep.py

# In pdb, access routers:
(Pdb) from lib.topogen import get_topogen
(Pdb) tgen = get_topogen()
(Pdb) router = tgen.gears["bordertor-11"]
(Pdb) output = router.vtysh_cmd("show bgp l2vpn evpn route")
(Pdb) print(output)
```

## Cleanup

If you encounter "VXLAN device already exists" errors from previous runs:

```bash
cd tests/topotests/bgp_evpn_vxlan_topo2
sudo ./cleanup_vxlan.sh
```

## Configuration Highlights

### VXLAN/Bridge Setup (per VTEP)
```bash
# Single bridge for all VLANs
ip link add name br_default type bridge vlan_filtering 1

# Single VXLAN device for ALL VNIs
ip link add vxlan48 type vxlan dstport 4789 local <VTEP_IPv6> external

# VLAN-to-VNI mappings (all on one device)
bridge vlan add dev vxlan48 vid 111 tunnel_info id 1000111  # L2VNI
bridge vlan add dev vxlan48 vid 112 tunnel_info id 1000112  # L2VNI
bridge vlan add dev vxlan48 vid 4001 tunnel_info id 104001  # L3VNI
bridge vlan add dev vxlan48 vid 4002 tunnel_info id 104002  # L3VNI
```

### BorderToR External Connectivity (NEW)
```bash
# VLAN sub-interfaces for L3VNI BGP peering
ip link add link swp3 name swp3.4001 type vlan id 4001
ip link set dev swp3.4001 master vrf1
ip addr add 144.1.1.2/30 dev swp3.4001
ip addr add 2144:1:1:1::2/64 dev swp3.4001

ip link add link swp3 name swp3.4002 type vlan id 4002
ip link set dev swp3.4002 master vrf2
ip addr add 144.1.1.6/30 dev swp3.4002
ip addr add 2144:1:1:2::6/64 dev swp3.4002
```

### BGP EVPN Configuration (per VTEP)
```
router bgp <ASN>
 bgp router-id <RID>
 bgp bestpath as-path multipath-relax
 bgp bestpath compare-routerid
 neighbor TOR-LEAF-SPINE peer-group
 neighbor TOR-LEAF-SPINE advertisement-interval 0
 neighbor TOR-LEAF-SPINE timers 3 10
 neighbor <IPv6> remote-as external
 neighbor <IPv6> peer-group TOR-LEAF-SPINE
 !
 address-family l2vpn evpn
  neighbor TOR-LEAF-SPINE activate
  advertise-all-vni
 exit-address-family
!
vrf vrf1
 vni 104001
!
vrf vrf2
 vni 104002
!
router bgp <ASN> vrf vrf1
 neighbor 144.1.1.1 remote-as external
 neighbor 2144:1:1:1::1 remote-as external
 !
 address-family ipv4 unicast
  redistribute connected route-map HOST_ALLOW_1
 exit-address-family
 !
 address-family ipv6 unicast
  neighbor 2144:1:1:1::1 activate
  redistribute connected route-map HOST_ALLOW_1_v6
 exit-address-family
 !
 address-family l2vpn evpn
  advertise ipv4 unicast
  advertise ipv6 unicast
 exit-address-family
```

## References

- bgp_evpn_rt5/test_bgp_evpn_v6_vtep.py - IPv6 VTEP implementation
- bgp_evpn_vxlan_svd_topo1/test_bgp_evpn_vxlan_svd.py - SVD configuration
- lib/evpn.py - Generic EVPN helper functions
