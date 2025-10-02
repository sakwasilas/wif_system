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
    Block a static IP on a given router.
    'router' should be an object or dict with:
    - router.ip_address (host)
    - router.username
    - router.password
    - router.port (optional, default 8728)
    """
    api = get_mikrotik_connection(router.ip_address, router.username, router.password, getattr(router, "port", 8728))
    if not api:
        return False
    try:
        api(cmd="/ip/firewall/address-list/add", address=ip_address, list="blocked")
        return True
    except Exception as e:
        print(f"Error blocking IP {ip_address} on {router.ip_address}: {e}")
        return False


def unblock_ip(ip_address, router):
    """
    Unblock a static IP on a given router.
    """
    api = get_mikrotik_connection(router.ip_address, router.username, router.password, getattr(router, "port", 8728))
    if not api:
        return False
    try:
        rules = list(api(cmd="/ip/firewall/address-list/print", query={"address": ip_address, "list": "blocked"}))
        for r in rules:
            api(cmd="/ip/firewall/address-list/remove", **{".id": r[".id"]})
        return True
    except Exception as e:
        print(f"Error unblocking IP {ip_address} on {router.ip_address}: {e}")
        return False

'''
# ==================== PASSWORD GENERATOR ====================
def generate_password(length=8):
    """Generate a random secure password for customer or router access."""
    return secrets.token_urlsafe(length)[:length]
'''
