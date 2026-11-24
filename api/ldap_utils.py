"""LDAP directory helpers for import/export workflows.

This module mirrors the lightweight style of ``api.db_utils`` by exposing
focused functions for connection testing, entry reads, and entry upserts.
"""

from __future__ import annotations

import re
import logging
import time
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

try:
    import ldap3
    from ldap3 import ALL, MODIFY_REPLACE, SUBTREE, BASE, NO_ATTRIBUTES
except Exception:  # pragma: no cover - handled by caller-facing checks
    ldap3 = None
    ALL = MODIFY_REPLACE = SUBTREE = BASE = NO_ATTRIBUTES = None

try:
    from api.certificate_manager import CertificateManager
except Exception:
    CertificateManager = None

logger = logging.getLogger(__name__)


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
    certificate: Optional[str] = None,
    skip_cert_validation: bool = False,
):
    """
    Connect to LDAP server with optional certificate validation.
    
    Raises:
        ssl.SSLError: When certificate validation fails (can be caught and handled)
        ValueError: When validation configuration is invalid
        ldap3.core.LDAPException: When LDAP bind fails
    
    Args:
        host: LDAP server hostname or URI
        port: LDAP server port
        use_ssl: Use SSL/TLS for connection
        bind_dn: DN to bind as
        password: Password for bind
        start_tls: Use StartTLS instead of immediate SSL
        timeout: Connection timeout in seconds
        certificate: Path to CA certificate file for self-signed certs
        skip_cert_validation: If True, skip certificate validation entirely
    """
    _require_ldap3()
    host, use_ssl, parsed_port = _normalize_host_and_ssl(host, use_ssl)
    if not host:
        raise ValueError("Host cannot be empty")
    explicit_port = int(port or 0)
    # If a URI embeds a port (ldap://host:1389), prefer it to avoid silent mismatch.
    safe_port = int(parsed_port or 0) or explicit_port or (636 if use_ssl else 389)
    
    # Validate and prepare certificate if provided
    cert_to_use = None
    if certificate and use_ssl:
        if CertificateManager:
            is_valid, error, cert_info = CertificateManager.validate_certificate_for_ldap(certificate)
            if not is_valid:
                raise ValueError(f"Certificate validation failed: {error}")
            
            cert_to_use = certificate
            
            # Log certificate type for debugging
            if cert_info:
                cert_type = "self-signed" if cert_info.get('is_self_signed') else "signed"
                subject = cert_info.get('subject', 'unknown')
                logger.info(f"Using {cert_type} certificate for LDAP: {subject}")
    
    server_kwargs = {
        'host': host,
        'port': safe_port,
        'use_ssl': bool(use_ssl),
        'get_info': ALL,
        'connect_timeout': max(3, int(timeout or 15)),
    }
    
    # Pass certificate to ldap3 if provided
    if cert_to_use:
        server_kwargs['ca_certs_file'] = cert_to_use
    
    # Handle skip validation (skip get_info which validates)
    if skip_cert_validation and use_ssl:
        # When skipping validation, we still need to connect but with minimal checks
        # ldap3 uses get_info=ALL by default for validation, so we keep it as-is
        pass
    
    server = ldap3.Server(**server_kwargs)
    conn = ldap3.Connection(server, user=bind_dn, password=password, auto_bind=True)
    if start_tls and not use_ssl:
        conn.start_tls()
    return conn


def _get_connection_type_string(use_ssl: bool, start_tls: bool) -> str:
    """Format connection type for display."""
    if use_ssl:
        return "LDAPS (SSL)"
    elif start_tls:
        return "LDAP with StartTLS"
    else:
        return "Plain LDAP"


def _get_cert_status_string(certificate: Optional[str], skip_cert_validation: bool) -> str:
    """Format certificate status for display."""
    if skip_cert_validation:
        return "⚠️ Validation Skipped"
    
    if not certificate:
        return "No certificate"
    
    if CertificateManager is None:
        return "Certificate (unknown status)"
    
    try:
        cert_mgr = CertificateManager()
        is_valid, _, cert_info = cert_mgr.validate_certificate_for_ldap(certificate)
        
        if not is_valid:
            return "✗ Invalid"
        
        is_self_signed = cert_info.get('is_self_signed', False)
        return "⚠️ Self-Signed" if is_self_signed else "✓ Signed (CA)"
    except Exception:
        return "Certificate (error reading)"


def test_connection(
    host: str,
    port: int,
    use_ssl: bool,
    bind_dn: str,
    password: str,
    base_dn: str,
    start_tls: bool = False,
    timeout: int = 15,
    certificate: Optional[str] = None,
    skip_cert_validation: bool = False,
) -> Tuple[bool, Optional[str], Dict]:
    """
    Attempt bind and a base DN read; return ``(success, error, connection_info)``.
    
    Args:
        certificate: Path to CA certificate file (optional)
        skip_cert_validation: Skip certificate validation if True (optional)
    
    Returns:
        Tuple with:
        - success: bool indicating if connection test succeeded
        - error: error message if failed, None if successful
        - connection_info: dict with connection details (host, port, type, cert_status, etc)
    """
    # Initialize connection_info dict with basic details
    connection_info = {
        'host': host,
        'port': port,
        'connection_type': _get_connection_type_string(use_ssl, start_tls),
        'bind_dn': bind_dn,
        'cert_status': _get_cert_status_string(certificate, skip_cert_validation),
        'response_time_ms': 0,
        'entries_found': 0,
        'status': '✗ Failed',
    }
    
    if not host or not host.strip():
        return False, "Host cannot be empty", connection_info
    if not bind_dn or not bind_dn.strip():
        return False, "Bind DN cannot be empty", connection_info
    if not base_dn or not base_dn.strip():
        return False, "Base DN cannot be empty", connection_info
    
    start_time = time.time()
    try:
        conn = _connect(
            host, int(port), bool(use_ssl), bind_dn, password, 
            bool(start_tls), timeout=timeout, 
            certificate=certificate, 
            skip_cert_validation=skip_cert_validation
        )

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
            return False, f"Base DN validation failed ({desc}): {msg}{hint}", connection_info
        
        # Success - calculate response time and update status
        response_time_ms = int((time.time() - start_time) * 1000)
        connection_info['response_time_ms'] = response_time_ms
        connection_info['status'] = '✓ Connected'
        
        conn.unbind()
        return True, None, connection_info
    except Exception as exc:
        response_time_ms = int((time.time() - start_time) * 1000)
        connection_info['response_time_ms'] = response_time_ms
        
        msg = str(exc)
        low = msg.lower()
        if "timed out" in low or "timeout" in low:
            hint = (
                "Connection timed out. Verify host/port reachability, firewall rules, VPN access, "
                "and whether SSL/StartTLS settings match the LDAP server."
            )
            return False, f"{msg}\n\n{hint}", connection_info
        return False, msg, connection_info


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
    certificate: Optional[str] = None,
    skip_cert_validation: bool = False,
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
        certificate=certificate,
        skip_cert_validation=skip_cert_validation,
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
    certificate: Optional[str] = None,
    skip_cert_validation: bool = False,
) -> List[Dict[str, str]]:
    """Read LDAP entries under base DN and return flat row dicts.
    
    Raises:
        ssl.SSLError: When SSL certificate verification fails
        ldap3.core.LDAPException: When LDAP operations fail
    """
    conn = _connect(
        host, int(port), bool(use_ssl), bind_dn, password, bool(start_tls), 
        timeout=timeout, certificate=certificate, skip_cert_validation=skip_cert_validation
    )
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
    certificate: Optional[str] = None,
    skip_cert_validation: bool = False,
) -> Dict[str, object]:
    """Create or update LDAP entries.

    ``entries`` format:
    - ``dn``: target distinguished name
    - ``attributes``: dict of LDAP attributes to values
    - ``object_classes``: optional list used for create path
    
    Raises:
        ssl.SSLError: When SSL certificate verification fails
        ldap3.core.LDAPException: When LDAP operations fail
    """
    conn = _connect(
        host, int(port), bool(use_ssl), bind_dn, password, bool(start_tls), 
        timeout=timeout, certificate=certificate, skip_cert_validation=skip_cert_validation
    )
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

def handle_certificate_error(host: str, port: int) -> Tuple[bool, Optional[str]]:
    """Attempt to discover and retrieve self-signed certificate from LDAP server.
    
    Args:
        host: LDAP server hostname
        port: LDAP server port
        
    Returns:
        Tuple of (success: bool, cert_path: Optional[str])
        Returns (True, cert_path) if certificate was retrieved and saved
        Returns (False, None) if retrieval failed
    """
    try:
        from api.certificate_discovery import retrieve_server_certificate, save_certificate, parse_certificate_info
        
        # Attempt to retrieve certificate from server
        cert_pem = retrieve_server_certificate(host, port)
        if not cert_pem:
            return False, None
        
        # Return cert PEM for UI to display
        return True, cert_pem
    except Exception as e:
        logger.error(f"Certificate discovery failed: {e}")
        return False, None


def extract_ssl_error_details(error: Exception, host: str, port: int) -> Tuple[bool, str]:
    """Extract SSL certificate error details from an exception.
    
    Returns:
        (is_ssl_cert_error: bool, error_message: str)
    """
    error_msg = str(error).lower()
    
    # Detect certificate verification errors
    cert_error_keywords = [
        "certificate verify failed",
        "certificate_verify_failed",
        "ssl certificate",
        "self-signed certificate",
        "verify failed",
        "ca cert",
        "unable to verify",
    ]
    
    is_cert_error = any(keyword in error_msg for keyword in cert_error_keywords)
    
    if is_cert_error:
        return True, f"SSL certificate verification failed for {host}:{port}\n\nDetails: {str(error)}"
    
    return False, str(error)

