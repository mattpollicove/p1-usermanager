"""LDAP directory helpers for import/export workflows.

This module mirrors the lightweight style of ``api.db_utils`` by exposing
focused functions for connection testing, entry reads, and entry upserts.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

try:
    import ldap3
    from ldap3 import ALL, MODIFY_REPLACE, SUBTREE, BASE, NO_ATTRIBUTES
except Exception:  # pragma: no cover - handled by caller-facing checks
    ldap3 = None
    ALL = MODIFY_REPLACE = SUBTREE = BASE = NO_ATTRIBUTES = None


def _require_ldap3():
    if ldap3 is None:
        raise ModuleNotFoundError("ldap3 is not installed")


def _normalize_host_and_ssl(host: str, use_ssl: bool) -> Tuple[str, bool, Optional[int]]:
    """Normalize LDAP host values and infer SSL/port from URI scheme when present."""
    raw = str(host or "").strip()
    ssl_flag = bool(use_ssl)
    parsed_port: Optional[int] = None
    if not raw:
        return "", ssl_flag, parsed_port

    if raw.lower().startswith("ldap://") or raw.lower().startswith("ldaps://"):
        parsed = urlparse(raw)
        normalized_host = parsed.hostname or ""
        parsed_port = parsed.port
        if parsed.scheme.lower() == "ldaps":
            ssl_flag = True
        return normalized_host, ssl_flag, parsed_port

    # Accept accidental trailing slash from copied URLs.
    return raw.rstrip('/'), ssl_flag, parsed_port


def _connect(
    host: str,
    port: int,
    use_ssl: bool,
    bind_dn: str,
    password: str,
    start_tls: bool = False,
    timeout: int = 15,
):
    _require_ldap3()
    host, use_ssl, parsed_port = _normalize_host_and_ssl(host, use_ssl)
    if not host:
        raise ValueError("Host cannot be empty")
    explicit_port = int(port or 0)
    # If a URI embeds a port (ldap://host:1389), prefer it to avoid silent mismatch.
    safe_port = int(parsed_port or 0) or explicit_port or (636 if use_ssl else 389)
    server = ldap3.Server(
        host=host,
        port=safe_port,
        use_ssl=bool(use_ssl),
        get_info=ALL,
        connect_timeout=max(3, int(timeout or 15)),
    )
    conn = ldap3.Connection(server, user=bind_dn, password=password, auto_bind=True)
    if start_tls and not use_ssl:
        conn.start_tls()
    return conn


def test_connection(
    host: str,
    port: int,
    use_ssl: bool,
    bind_dn: str,
    password: str,
    base_dn: str,
    start_tls: bool = False,
    timeout: int = 15,
) -> Tuple[bool, Optional[str]]:
    """Attempt bind and a base DN read; return ``(success, error)``."""
    if not host or not host.strip():
        return False, "Host cannot be empty"
    if not bind_dn or not bind_dn.strip():
        return False, "Bind DN cannot be empty"
    if not base_dn or not base_dn.strip():
        return False, "Base DN cannot be empty"
    try:
        conn = _connect(host, int(port), bool(use_ssl), bind_dn, password, bool(start_tls), timeout=timeout)

        def _suffix_hint() -> str:
            """Return a helpful namingContexts hint from Root DSE when available."""
            try:
                ok_root = conn.search(
                    search_base="",
                    search_filter="(objectClass=*)",
                    search_scope=BASE,
                    attributes=["namingContexts", "defaultNamingContext"],
                )
                if not ok_root or not conn.entries:
                    return ""
                root_attrs = conn.entries[0].entry_attributes_as_dict
                suffixes = []
                for key in ("namingContexts", "defaultNamingContext"):
                    vals = root_attrs.get(key) or []
                    if not isinstance(vals, list):
                        vals = [vals]
                    for v in vals:
                        s = str(v or "").strip()
                        if s and s not in suffixes:
                            suffixes.append(s)
                if not suffixes:
                    return ""
                return "\nAvailable directory suffixes: " + ", ".join(suffixes)
            except Exception:
                return ""

        # DN is not a regular attribute on many LDAP servers; request no attributes.
        ok = conn.search(
            search_base=base_dn,
            search_filter="(objectClass=*)",
            search_scope=BASE,
            attributes=NO_ATTRIBUTES,
        )
        if not ok:
            result = getattr(conn, "result", {}) or {}
            desc = result.get("description") or "searchFailed"
            msg = result.get("message") or "Base DN search failed"
            hint = _suffix_hint() if str(desc).lower() == "nosuchobject" else ""
            conn.unbind()
            return False, f"Base DN validation failed ({desc}): {msg}{hint}"
        conn.unbind()
        return True, None
    except Exception as exc:
        msg = str(exc)
        low = msg.lower()
        if "timed out" in low or "timeout" in low:
            hint = (
                "Connection timed out. Verify host/port reachability, firewall rules, VPN access, "
                "and whether SSL/StartTLS settings match the LDAP server."
            )
            return False, f"{msg}\n\n{hint}"
        return False, msg


def _normalize_attr_value(value):
    if isinstance(value, list):
        if not value:
            return ""
        if len(value) == 1:
            v = value[0]
            if isinstance(v, bytes):
                try:
                    return v.decode('utf-8')
                except Exception:
                    return str(v)
            return v if isinstance(v, str) else str(v)
        return "; ".join(str(v) for v in value)
    if isinstance(value, bytes):
        try:
            return value.decode('utf-8')
        except Exception:
            return str(value)
    return value


def _canonical_ldap_attr_name(name: str) -> str:
    """Map common aliases to LDAP canonical attribute names.

    This protects exports when mappings contain user-friendly names like
    `email` that many LDAP servers reject as invalid attribute types.
    """
    raw = str(name or "").strip()
    if not raw:
        return ""
    alias_map = {
        "email": "mail",
        "username": "cn",
        "lastname": "sn",
        "firstname": "givenName",
        "displayname": "displayName",
        "population.name": "ou",
        "population.id": "employeeNumber",
    }
    return alias_map.get(raw.lower(), raw)


def _is_valid_ldap_attr_name(name: str) -> bool:
    """Return True when name looks like a valid LDAP attribute type token."""
    return bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9-]*", str(name or "")))


def _split_rdn(dn: str) -> Tuple[str, str]:
    """Split `attr=value,...` into `(attr, value)` for the left-most RDN."""
    left = str(dn or "").split(',', 1)[0].strip()
    if '=' not in left:
        return "", ""
    attr, value = left.split('=', 1)
    return attr.strip(), value.strip()


def _entry_exists(conn, dn: str) -> bool:
    """Return True when the DN exists."""
    try:
        ok = conn.search(search_base=dn, search_filter="(objectClass=*)", search_scope=BASE, attributes=NO_ATTRIBUTES)
        return bool(ok and conn.entries)
    except Exception:
        return False


def _ensure_parent_dn(conn, dn: str, errors: List[str]) -> bool:
    """Ensure the target DN exists by recursively creating missing OU/DC containers.

    This allows exporting user entries below a missing container such as
    `ou=people,dc=example,dc=com` when the suffix exists but the OU does not.
    """
    target = str(dn or "").strip()
    if not target:
        return False
    if _entry_exists(conn, target):
        return True

    parent = target.split(',', 1)[1].strip() if ',' in target else ''
    if parent:
        if not _ensure_parent_dn(conn, parent, errors):
            return False

    rdn_attr, rdn_value = _split_rdn(target)
    if not rdn_attr or not rdn_value:
        errors.append(f"Cannot auto-create parent DN '{target}': invalid RDN format")
        return False

    rdn_attr_l = rdn_attr.lower()
    if rdn_attr_l == 'ou':
        attrs = {'objectClass': ['top', 'organizationalUnit'], 'ou': rdn_value}
    elif rdn_attr_l == 'dc':
        attrs = {'objectClass': ['top', 'domain'], 'dc': rdn_value}
    else:
        errors.append(
            f"Cannot auto-create missing parent DN '{target}': unsupported container RDN '{rdn_attr}'"
        )
        return False

    try:
        ok = conn.add(target, attributes=attrs)
        if ok:
            return True
        result = getattr(conn, 'result', {}) or {}
        desc = result.get('description') or 'addFailed'
        msg = result.get('message') or str(result)
        # If another client created it first, treat as success.
        if str(desc).lower() == 'entryalreadyexists':
            return True
        errors.append(f"Failed to auto-create parent DN '{target}' ({desc}): {msg}")
        return False
    except Exception as exc:
        errors.append(f"Failed to auto-create parent DN '{target}': {exc}")
        return False


def get_entry_sample(
    host: str,
    port: int,
    use_ssl: bool,
    bind_dn: str,
    password: str,
    base_dn: str,
    search_filter: str = "(objectClass=person)",
    start_tls: bool = False,
    timeout: int = 15,
) -> Optional[Dict[str, str]]:
    """Return one entry as a flat dict with ``dn`` and scalarized attributes."""
    rows = get_entries(
        host,
        port,
        use_ssl,
        bind_dn,
        password,
        base_dn,
        search_filter=search_filter,
        attributes=None,
        limit=1,
        start_tls=start_tls,
        timeout=timeout,
    )
    return rows[0] if rows else None


def get_entries(
    host: str,
    port: int,
    use_ssl: bool,
    bind_dn: str,
    password: str,
    base_dn: str,
    search_filter: str = "(objectClass=person)",
    attributes: Optional[List[str]] = None,
    limit: Optional[int] = None,
    start_tls: bool = False,
    timeout: int = 15,
) -> List[Dict[str, str]]:
    """Read LDAP entries under base DN and return flat row dicts."""
    conn = _connect(host, int(port), bool(use_ssl), bind_dn, password, bool(start_tls), timeout=timeout)
    attrs = attributes if attributes else ldap3.ALL_ATTRIBUTES
    conn.search(
        search_base=base_dn,
        search_filter=search_filter or "(objectClass=person)",
        search_scope=SUBTREE,
        attributes=attrs,
        size_limit=int(limit or 0),
    )
    rows: List[Dict[str, str]] = []
    for entry in conn.entries:
        item: Dict[str, str] = {"dn": str(entry.entry_dn)}
        try:
            payload = entry.entry_attributes_as_dict
        except Exception:
            payload = {}
        for key, val in payload.items():
            item[str(key)] = _normalize_attr_value(val)
        rows.append(item)
    conn.unbind()
    return rows


def upsert_entries(
    host: str,
    port: int,
    use_ssl: bool,
    bind_dn: str,
    password: str,
    entries: List[Dict[str, object]],
    start_tls: bool = False,
    timeout: int = 15,
    auto_create_parents: bool = True,
) -> Dict[str, object]:
    """Create or update LDAP entries.

    ``entries`` format:
    - ``dn``: target distinguished name
    - ``attributes``: dict of LDAP attributes to values
    - ``object_classes``: optional list used for create path
    """
    conn = _connect(host, int(port), bool(use_ssl), bind_dn, password, bool(start_tls), timeout=timeout)
    created = 0
    updated = 0
    errors: List[str] = []

    for item in entries:
        dn = str(item.get("dn") or "").strip()
        attrs = dict(item.get("attributes") or {})
        object_classes = list(item.get("object_classes") or ["top", "person", "organizationalPerson", "inetOrgPerson"])
        if not dn:
            errors.append("Missing dn for one entry")
            continue
        try:
            # DN is derived from the entry itself; querying NO_ATTRIBUTES avoids invalid-attr errors.
            exists = conn.search(search_base=dn, search_filter="(objectClass=*)", search_scope=BASE, attributes=NO_ATTRIBUTES)
            if exists and conn.entries:
                mod = {}
                for key, value in attrs.items():
                    if value is None:
                        continue
                    safe_key = _canonical_ldap_attr_name(str(key))
                    if not safe_key:
                        continue
                    if not _is_valid_ldap_attr_name(safe_key):
                        errors.append(f"Skipped invalid LDAP attribute '{key}' for {dn}")
                        continue
                    mod[safe_key] = [(MODIFY_REPLACE, [value] if not isinstance(value, list) else value)]
                ok = conn.modify(dn, mod)
                if ok:
                    updated += 1
                else:
                    errors.append(f"Update failed for {dn}: {conn.result}")
            else:
                parent_dn = dn.split(',', 1)[1] if ',' in dn else ''
                if parent_dn:
                    parent_exists = conn.search(
                        search_base=parent_dn,
                        search_filter="(objectClass=*)",
                        search_scope=BASE,
                        attributes=NO_ATTRIBUTES,
                    )
                    if not parent_exists:
                        if auto_create_parents and not _ensure_parent_dn(conn, parent_dn, errors):
                            result = getattr(conn, "result", {}) or {}
                            desc = result.get("description") or "noSuchObject"
                            msg = result.get("message") or "Parent DN does not exist"
                            errors.append(
                                f"Create failed for {dn}: parent DN '{parent_dn}' is not available ({desc}). {msg}"
                            )
                            continue
                        if not auto_create_parents:
                            result = getattr(conn, "result", {}) or {}
                            desc = result.get("description") or "noSuchObject"
                            msg = result.get("message") or "Parent DN does not exist"
                            errors.append(
                                f"Create failed for {dn}: parent DN '{parent_dn}' is not available ({desc}). {msg}"
                            )
                            continue
                add_attrs = {}
                for key, value in attrs.items():
                    safe_key = _canonical_ldap_attr_name(str(key))
                    if safe_key:
                        if not _is_valid_ldap_attr_name(safe_key):
                            errors.append(f"Skipped invalid LDAP attribute '{key}' for {dn}")
                            continue
                        add_attrs[safe_key] = value
                add_attrs["objectClass"] = object_classes
                ok = conn.add(dn, attributes=add_attrs)
                if ok:
                    created += 1
                else:
                    errors.append(f"Create failed for {dn}: {conn.result}")
        except Exception as exc:
            errors.append(f"{dn}: {exc}")

    conn.unbind()
    return {
        "created": created,
        "updated": updated,
        "total": len(entries),
        "errors": errors,
    }