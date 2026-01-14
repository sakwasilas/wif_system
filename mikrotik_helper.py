
# ==================== STANDARD LIBRARY ====================


# ==================== MIKROTIK API ====================
# pip install librouteros
from librouteros import connect

# ==================== MIKROTIK HELPER ====================

def get_mikrotik_connection(host, user, password, port=8728):
    """
    Establish connection to a MikroTik router.
    Returns the API connection or None on failure.
    """
    try:
        api = connect(username=user, password=password, host=host, port=port)
        return api
    except Exception as e:
        print(f"❌ Error connecting to MikroTik {host}: {e}")
        return None


def block_ip(ip_address, router):
    """
    Block a static IP on a given router and disconnect Hotspot user immediately.
    Moves firewall rule to the top for instant effect.
    """
    api = get_mikrotik_connection(router.ip_address, router.username, router.password, getattr(router, "port", 8728))
    if not api:
        print("❌ Router connection failed while blocking.")
        return False
    
    try:
        # 1️⃣ Add IP to 'blocked_users' address list if not already there
        existing = list(api(cmd="/ip/firewall/address-list/print", query={"address": ip_address, "list": "blocked_users"}))
        if not existing:
            api(cmd="/ip/firewall/address-list/add", address=ip_address, list="blocked_users", comment="Suspended by Flask")

        # 2️⃣ Ensure firewall rule exists (drop traffic for blocked_users)
        rules = list(api(cmd="/ip/firewall/filter/print", query={"chain": "forward", "src-address-list": "blocked_users"}))
        if not rules:
            api(cmd="/ip/firewall/filter/add", chain="forward", src_address_list="blocked_users", action="drop", comment="Auto block list", disabled=False)
        else:
            for r in rules:
                api(cmd="/ip/firewall/filter/move", **{".id": r[".id"]}, position=0)

        # 3️⃣ Disconnect any active Hotspot session
        active_users = list(api(cmd="/ip/hotspot/active/print", query={"address": ip_address}))
        for user in active_users:
            api(cmd="/ip/hotspot/active/remove", **{".id": user[".id"]})

        # 4️⃣ Optional: Remove DHCP lease (forces new request)
        leases = list(api(cmd="/ip/dhcp-server/lease/print", query={"address": ip_address}))
        for lease in leases:
            api(cmd="/ip/dhcp-server/lease/remove", **{".id": lease[".id"]})

        print(f"🔒 Blocked {ip_address}")
        return True
    except Exception as e:
        print(f"⚠️ Error blocking IP {ip_address} on {router.ip_address}: {e}")
        return False


def unblock_ip(ip_address, router):
    """
    Unblock a static IP on a given router.
    Removes from address list and allows traffic again.
    """
    api = get_mikrotik_connection(router.ip_address, router.username, router.password, getattr(router, "port", 8728))
    if not api:
        print("❌ Router connection failed while unblocking.")
        return False
    
    try:
        # 1️⃣ Remove from blocked_users address list
        rules = list(api(cmd="/ip/firewall/address-list/print", query={"address": ip_address, "list": "blocked_users"}))
        for r in rules:
            api(cmd="/ip/firewall/address-list/remove", **{".id": r[".id"]})

        # 2️⃣ Disconnect Hotspot sessions (optional)
        active_users = list(api(cmd="/ip/hotspot/active/print", query={"address": ip_address}))
        for user in active_users:
            api(cmd="/ip/hotspot/active/remove", **{".id": user[".id"]})

        print(f"✅ Unblocked {ip_address}")
        return True
    except Exception as e:
        print(f"⚠️ Error unblocking IP {ip_address} on {router.ip_address}: {e}")
        return False

