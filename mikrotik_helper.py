from librouteros import connect


def get_mikrotik_connection(host, user, password, port=8728, timeout=10):
    """
    Connect to MikroTik RouterOS API.
    Public IP setups need timeouts so the app doesn't hang.
    """
    try:
        api = connect(
            host=host,
            username=user,
            password=password,
            port=port,
            timeout=timeout
        )
        return api
    except Exception as e:
        print(f"❌ MikroTik connect failed [{host}:{port}] -> {e}")
        return None


def block_ip(ip_address, router):
    """
    Block customer by adding IP to address-list 'blocked_users'.
    IMPORTANT: The firewall DROP rule should be created ONCE on MikroTik:
      /ip firewall filter add chain=forward src-address-list=blocked_users action=drop
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
        # ✅ 1) Add IP to blocked_users if not already there
        existing = list(api(
            cmd="/ip/firewall/address-list/print",
            query={"address": ip_address, "list": "blocked_users"}
        ))

        if not existing:
            api(
                cmd="/ip/firewall/address-list/add",
                address=ip_address,
                list="blocked_users",
                comment="Blocked by Flask"
            )

        # ✅ 2) OPTIONAL: Disconnect Hotspot session (only if hotspot exists)
        try:
            active_users = list(api(
                cmd="/ip/hotspot/active/print",
                query={"address": ip_address}
            ))
            for u in active_users:
                api(cmd="/ip/hotspot/active/remove", **{".id": u[".id"]})
        except Exception:
            # Hotspot not used on this router; ignore safely
            pass

        # ✅ 3) OPTIONAL: Remove DHCP lease (only if DHCP server exists)
        try:
            leases = list(api(
                cmd="/ip/dhcp-server/lease/print",
                query={"address": ip_address}
            ))
            for lease in leases:
                api(cmd="/ip/dhcp-server/lease/remove", **{".id": lease[".id"]})
        except Exception:
            # DHCP server not used on this router; ignore safely
            pass

        print(f"🔒 Blocked {ip_address} on router {router.ip_address}")
        return True

    except Exception as e:
        print(f"⚠️ Error blocking {ip_address} on {router.ip_address}: {e}")
        return False


def unblock_ip(ip_address, router):
    """
    Unblock customer by removing IP from address-list 'blocked_users'.
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
        # ✅ 1) Remove from blocked_users address list
        rules = list(api(
            cmd="/ip/firewall/address-list/print",
            query={"address": ip_address, "list": "blocked_users"}
        ))
        for r in rules:
            api(cmd="/ip/firewall/address-list/remove", **{".id": r[".id"]})

        # ✅ 2) OPTIONAL: Disconnect Hotspot session (only if hotspot exists)
        try:
            active_users = list(api(
                cmd="/ip/hotspot/active/print",
                query={"address": ip_address}
            ))
            for u in active_users:
                api(cmd="/ip/hotspot/active/remove", **{".id": u[".id"]})
        except Exception:
            pass

        print(f"✅ Unblocked {ip_address} on router {router.ip_address}")
        return True

    except Exception as e:
        print(f"⚠️ Error unblocking {ip_address} on {router.ip_address}: {e}")
        return False

