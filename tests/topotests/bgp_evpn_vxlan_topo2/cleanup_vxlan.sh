#!/bin/bash
# Cleanup script for BGP EVPN VXLAN topology test
# Run this to clean up stale interfaces from previous test runs

echo "=== Cleaning up BGP EVPN VXLAN test environment ==="

# List of VTEPs to clean
VTEPS="bordertor-11 bordertor-12 tor-21 tor-22"

# Function to cleanup a specific router namespace
cleanup_router() {
    local router=$1
    echo "Cleaning up $router..."

    # Find the namespace PID
    local ns_pid=$(pgrep -f "mininet:$router" | head -1)

    if [ -z "$ns_pid" ]; then
        echo "  No running namespace found for $router"
        return
    fi

    echo "  Found namespace PID: $ns_pid"

    # Execute cleanup commands in the namespace
    nsenter --mount=/proc/$ns_pid/ns/mnt --net=/proc/$ns_pid/ns/net --uts=/proc/$ns_pid/ns/uts -F /bin/bash -c '
        # Bring interfaces down
        ip link set dev vlan111 down 2>/dev/null || true
        ip link set dev vlan112 down 2>/dev/null || true
        ip link set dev vlan4001 down 2>/dev/null || true
        ip link set dev vlan4002 down 2>/dev/null || true
        ip link set dev vxlan48 down 2>/dev/null || true
        ip link set dev vxlan99 down 2>/dev/null || true
        ip link set dev br_default down 2>/dev/null || true
        ip link set dev br_l3vni down 2>/dev/null || true

        # Delete interfaces in dependency order
        ip link del vlan111 2>/dev/null || true
        ip link del vlan112 2>/dev/null || true
        ip link del vlan4001 2>/dev/null || true
        ip link del vlan4002 2>/dev/null || true
        ip link del vxlan48 2>/dev/null || true
        ip link del vxlan99 2>/dev/null || true
        ip link del br_default 2>/dev/null || true
        ip link del br_l3vni 2>/dev/null || true
        ip link del vrf1 2>/dev/null || true
        ip link del vrf2 2>/dev/null || true

        echo "  Cleaned up interfaces in $1"
    ' -- "$router"
}

# Clean up each VTEP
for vtep in $VTEPS; do
    cleanup_router $vtep
done

echo ""
echo "=== Cleanup complete ==="
echo "You can now run the test again:"
echo "  sudo pytest test_bgp_evpn_svd_v6_vtep.py -v -s"

