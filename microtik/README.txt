
# 
from librouteros import connect

def get_mikrotik_connection(host, user, password, port=8728, timeout=10):
    try:
        return connect(
            host=host,
            username=user,
            password=password,
            port=port,
            timeout=timeout
        )
    except Exception as e:
        print(f"❌ MikroTik connect failed: {e}")
        return None


def block_ip(ip_address, router):
    api = get_mikrotik_connection(
        router.ip_address,
        router.username,
        router.password,
        getattr(router, "port", 8728)
    )
    if not api:
        return False

    al = api.path("ip", "firewall", "address-list")

    existing = list(al.select(
        where=f'list="blocked_users" and address="{ip_address}"'
    ))

    if not existing:
        al.add(
            list="blocked_users",
            address=ip_address,
            comment="blocked from app"
        )

    print(f"🔒 Blocked {ip_address} on {router.ip_address}")
    return True


def unblock_ip(ip_address, router):
    api = get_mikrotik_connection(
        router.ip_address,
        router.username,
        router.password,
        getattr(router, "port", 8728)
    )
    if not api:
        return False

    al = api.path("ip", "firewall", "address-list")

    for row in al.select(
        where=f'list="blocked_users" and address="{ip_address}"'
    ):
        al.remove(row[".id"])

    print(f"🔓 Unblocked {ip_address} on {router.ip_address}")
    return True
