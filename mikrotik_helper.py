from routeros_api import RouterOsApiPool

# MikroTik connection settings (change to match your router)
MIKROTIK_HOST = "192.168.88.1"
MIKROTIK_USERNAME = "admin"
MIKROTIK_PASSWORD = "admin123"
MIKROTIK_PORT = 8728  # default API port

def get_api():
    """Connect to MikroTik router and return API object."""
    api_pool = RouterOsApiPool(
        MIKROTIK_HOST,
        username=MIKROTIK_USERNAME,
        password=MIKROTIK_PASSWORD,
        port=MIKROTIK_PORT,
        plaintext_login=True
    )
    return api_pool.get_api()

def add_pppoe_user(username, password, profile="default"):
    """Add PPPoE user in MikroTik."""
    api = get_api()
    ppp_secret = api.get_resource("/ppp/secret")
    ppp_secret.add(name=username, password=password, service="pppoe", profile=profile)
    print(f"[+] PPPoE user created: {username}")

def remove_pppoe_user(username):
    """Remove PPPoE user."""
    api = get_api()
    ppp_secret = api.get_resource("/ppp/secret")
    users = ppp_secret.get(name=username)
    for u in users:
        ppp_secret.remove(id=u["id"])
    print(f"[-] PPPoE user removed: {username}")

def disable_pppoe_user(username):
    """Disable PPPoE user (suspend)."""
    api = get_api()
    ppp_secret = api.get_resource("/ppp/secret")
    users = ppp_secret.get(name=username)
    for u in users:
        ppp_secret.set(id=u["id"], disabled="yes")
    print(f"[!] PPPoE user disabled: {username}")

def enable_pppoe_user(username):
    """Enable PPPoE user (reactivate)."""
    api = get_api()
    ppp_secret = api.get_resource("/ppp/secret")
    users = ppp_secret.get(name=username)
    for u in users:
        ppp_secret.set(id=u["id"], disabled="no")
    print(f"[✓] PPPoE user enabled: {username}")

def list_active_sessions():
    """List currently active PPPoE sessions."""
    api = get_api()
    active = api.get_resource("/ppp/active")
    return active.get()
