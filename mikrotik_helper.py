# ==================== STANDARD LIBRARY ====================
import secrets

# ==================== MIKROTIK API ====================
# Assuming you use librouteros or any MikroTik API library
# pip install librouteros

from librouteros import connect

# MikroTik connection settings
MIKROTIK_HOST = "192.168.88.1"
MIKROTIK_USER = "admin"
MIKROTIK_PASS = "yourpassword"
MIKROTIK_PORT = 8728  # default API port


def get_mikrotik_connection():
    """Establish connection to MikroTik router."""
    try:
        api = connect(
            username=MIKROTIK_USER,
            password=MIKROTIK_PASS,
            host=MIKROTIK_HOST,
            port=MIKROTIK_PORT
        )
        return api
    except Exception as e:
        print(f"Error connecting to MikroTik: {e}")
        return None


# ==================== IP BLOCK / UNBLOCK ====================

def block_ip(ip_address):
    """Block a static IP via MikroTik firewall."""
    api = get_mikrotik_connection()
    if not api:
        return False
    try:
        api(cmd="/ip/firewall/address-list/add", address=ip_address, list="blocked")
        return True
    except Exception as e:
        print(f"Error blocking IP {ip_address}: {e}")
        return False


def unblock_ip(ip_address):
    """Unblock a static IP via MikroTik firewall."""
    api = get_mikrotik_connection()
    if not api:
        return False
    try:
        rules = list(api(cmd="/ip/firewall/address-list/print", query={"address": ip_address, "list": "blocked"}))
        for r in rules:
            api(cmd="/ip/firewall/address-list/remove", **{".id": r[".id"]})
        return True
    except Exception as e:
        print(f"Error unblocking IP {ip_address}: {e}")
        return False


# ==================== PASSWORD GENERATOR ====================
def generate_password(length=8):
    """Generate a random secure password for customer or router access."""
    return secrets.token_urlsafe(length)[:length]
