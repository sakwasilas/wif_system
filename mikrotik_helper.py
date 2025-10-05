# # ==================== STANDARD LIBRARY ====================
# import secrets

# # ==================== MIKROTIK API ====================
# # pip install librouteros
# from librouteros import connect

# # ==================== MIKROTIK HELPER ====================

# def get_mikrotik_connection(host, user, password, port=8728):
#     """
#     Establish connection to a specific MikroTik router.
#     Returns the API connection or None on failure.
#     """
#     try:
#         api = connect(username=user, password=password, host=host, port=port)
#         return api
#     except Exception as e:
#         print(f"Error connecting to MikroTik {host}: {e}")
#         return None


# def block_ip(ip_address, router):
#     """
#     Block a static IP on a given router.
#     'router' should be an object or dict with:
#     - router.ip_address (host)
#     - router.username
#     - router.password
#     - router.port (optional, default 8728)
#     """
#     api = get_mikrotik_connection(router.ip_address, router.username, router.password, getattr(router, "port", 8728))
#     if not api:
#         return False
#     try:
#         api(cmd="/ip/firewall/address-list/add", address=ip_address, list="blocked")
#         return True
#     except Exception as e:
#         print(f"Error blocking IP {ip_address} on {router.ip_address}: {e}")
#         return False


# def unblock_ip(ip_address, router):
#     """
#     Unblock a static IP on a given router.
#     """
#     api = get_mikrotik_connection(router.ip_address, router.username, router.password, getattr(router, "port", 8728))
#     if not api:
#         return False
#     try:
#         rules = list(api(cmd="/ip/firewall/address-list/print", query={"address": ip_address, "list": "blocked"}))
#         for r in rules:
#             api(cmd="/ip/firewall/address-list/remove", **{".id": r[".id"]})
#         return True
#     except Exception as e:
#         print(f"Error unblocking IP {ip_address} on {router.ip_address}: {e}")
#         return False

# '''
# # ==================== PASSWORD GENERATOR ====================
# def generate_password(length=8):
#     """Generate a random secure password for customer or router access."""
#     return secrets.token_urlsafe(length)[:length]
# '''
# ==================== STANDARD LIBRARY ====================
import secrets

# ==================== MIKROTIK API ====================
# pip install librouteros
from librouteros import connect

# ==================== MIKROTIK HELPER ====================

def get_mikrotik_connection(host, user, password, port=8728):
    """
    Establish connection to a specific MikroTik router.
    Returns the API connection or None on failure.
    """
    try:
        api = connect(username=user, password=password, host=host, port=port)
        return api
    except Exception as e:
        print(f"Error connecting to MikroTik {host}: {e}")
        return None


def block_ip(ip_address, router):
    """
    Block a static IP on a given router and disconnect Hotspot user if active.
    'router' should be an object or dict with:
    - router.ip_address (host)
    - router.username
    - router.password
    - router.port (optional, default 8728)
    """
    api = get_mikrotik_connection(
        router.ip_address, 
        router.username, 
        router.password, 
        getattr(router, "port", 8728)
    )
    if not api:
        return False
    
    try:
        # 1️⃣ Add IP to address list
        api(cmd="/ip/firewall/address-list/add", address=ip_address, list="blocked")

        # 2️⃣ Ensure a firewall rule exists to drop traffic for this list
        existing_rules = list(api(cmd="/ip/firewall/filter/print", query={
            "chain": "forward",
            "src-address-list": "blocked",
            "action": "drop"
        }))
        if not existing_rules:
            api(cmd="/ip/firewall/filter/add", chain="forward", src_address_list="blocked", action="drop", comment="Auto block list")

        # 3️⃣ Disconnect Hotspot user if active
        active_users = list(api(cmd="/ip/hotspot/active/print", query={"address": ip_address}))
        for user in active_users:
            api(cmd="/ip/hotspot/active/remove", **{".id": user[".id"]})

        return True
    except Exception as e:
        print(f"Error blocking IP {ip_address} on {router.ip_address}: {e}")
        return False


def unblock_ip(ip_address, router):
    """
    Unblock a static IP on a given router.
    Removes from address list and allows traffic again.
    """
    api = get_mikrotik_connection(
        router.ip_address, 
        router.username, 
        router.password, 
        getattr(router, "port", 8728)
    )
    if not api:
        return False
    
    try:
        # 1️⃣ Remove IP from address list
        rules = list(api(cmd="/ip/firewall/address-list/print", query={"address": ip_address, "list": "blocked"}))
        for r in rules:
            api(cmd="/ip/firewall/address-list/remove", **{".id": r[".id"]})

        # 2️⃣ Remove Hotspot active disconnects (optional: they can reconnect)
        active_users = list(api(cmd="/ip/hotspot/active/print", query={"address": ip_address}))
        for user in active_users:
            api(cmd="/ip/hotspot/active/remove", **{".id": user[".id"]})

        return True
    except Exception as e:
        print(f"Error unblocking IP {ip_address} on {router.ip_address}: {e}")
        return False


