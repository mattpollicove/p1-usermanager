"""LDAP group migration, separate from the scalar user mapper."""

import re
import ssl
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass

from ldap3 import ALL, BASE, MODIFY_ADD, SUBTREE, Connection, Server, Tls
from ldap3.core.exceptions import LDAPException
from ldap3.utils.conv import escape_filter_chars
from ldap3.utils.dn import escape_rdn, parse_dn

from api.group_transfer import Group, Membership, Transfer, child_first
from api.ldap_utils import _normalize_host_and_ssl


PROFILES = {
    "Active Directory (member)": ("group", "member"),
    "LDAP groupOfNames (member)": ("groupOfNames", "member"),
    "LDAP groupOfUniqueNames (uniqueMember)": ("groupOfUniqueNames", "uniqueMember"),
    "LDAP posixGroup (memberUid)": ("posixGroup", "memberUid"),
    "Reverse memberOf (import only)": ("", "memberOf"),
}
PAGING = "1.2.840.113556.1.4.319"
ATTR = re.compile(r"[a-zA-Z][a-zA-Z0-9-]*\Z")


@dataclass(frozen=True)
class DirectoryMapping:
    group_base: str
    user_base: str
    group_class: str
    membership: str
    username: str
    user_filter: str
    group_filter: str = ""
    first_gid: int = 0

    def validate(self):
        dn_key(self.group_base)
        dn_key(self.user_base)
        if not ATTR.fullmatch(self.group_class) or not ATTR.fullmatch(self.username):
            raise ValueError("Choose valid LDAP object class and username attribute names.")
        if self.membership not in {"member", "uniqueMember", "memberUid", "memberOf"}:
            raise ValueError("Unsupported LDAP membership attribute.")
        if not self.user_filter.startswith("(") or not self.user_filter.endswith(")"):
            raise ValueError("Enter an LDAP user filter, such as (objectClass=person).")
        if self.group_filter and not (self.group_filter.startswith("(") and self.group_filter.endswith(")")):
            raise ValueError("Enter a parenthesized LDAP group filter.")


def dn_key(dn):
    """Keep RDN boundaries and normalize equivalent escapes and AVA ordering."""
    rdns, rdn = [], []
    try:
        parts = parse_dn(dn)
    except LDAPException as exc:
        raise ValueError(f"Invalid LDAP distinguished name: {dn!r}.") from exc
    for attr, value, separator in parts:
        encoded = value.encode("utf-8")
        decoded = re.sub(rb"\\(?:([a-fA-F0-9]{2})|(.))",
                         lambda m: bytes.fromhex(m[1].decode()) if m[1] else m[2], encoded)
        rdn.append((attr.lower(), decoded.decode("utf-8").casefold()))
        if separator != "+":
            rdns.append(tuple(sorted(rdn)))
            rdn = []
    return tuple(rdns)


def values(entry, attr):
    attrs = entry["attributes"]
    if any(key.lower().startswith(attr.lower() + ";range=") for key in attrs):
        raise ValueError(f"LDAP returned an incomplete {attr} list for {entry['dn']}.")
    value = next((value for key, value in attrs.items() if key.lower() == attr.lower()), [])
    return value if isinstance(value, (tuple, list)) else ([] if value is None else [value])


def single(entry, attr, *, required=False):
    found = values(entry, attr)
    if len(found) > 1 or (required and (not found or not str(found[0]).strip())):
        raise ValueError(f"Expected one {attr} value on {entry['dn']}.")
    return str(found[0]) if found else ""


def member_key(value):
    match = re.search(r"#('[01]+'[bB])$", value)
    if match:
        prefix = value[:match.start()]
        escapes = len(prefix) - len(prefix.rstrip("\\"))
        if not escapes % 2:
            return dn_key(prefix), match[1].upper()
    return dn_key(value), ""


@contextmanager
def connect(config):
    from pathlib import Path
    
    host, use_ssl, uri_port = _normalize_host_and_ssl(config.get("host", ""), config.get("use_ssl", False))
    start_tls = bool(config.get("start_tls")) and not use_ssl
    bind_dn, password = config.get("bind_dn", ""), config.get("password", "")
    if not host or not bind_dn or not password or not (use_ssl or start_tls):
        raise ValueError("Group migration requires a saved bind account and LDAPS or StartTLS.")
    timeout = int(config.get("timeout") or 30)
    port = uri_port or int(config.get("port") or (636 if use_ssl else 389))
    
    # Determine TLS validation: use saved certificate if available, otherwise allow unverified
    tls_config = None
    
    # Try to load certificate from secure storage
    from api.certificate_discovery import load_certificate
    cert_pem = load_certificate(host, port)
    
    if cert_pem:
        # Use certificate loaded from secure storage
        import tempfile
        import ssl
        
        # Create a temporary file with the certificate for ldap3
        with tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False) as f:
            f.write(cert_pem)
            cert_file = f.name
        
        try:
            tls_config = Tls(validate=ssl.CERT_REQUIRED, ca_certs_file=cert_file)
        finally:
            # Clean up temp file after TLS config is created
            import atexit
            atexit.register(lambda: Path(cert_file).unlink(missing_ok=True))
    else:
        # Allow unverified/self-signed certificates (user accepted the cert dialog)
        tls_config = Tls(validate=ssl.CERT_NONE)
    
    server = Server(host, port=port, use_ssl=use_ssl, get_info=ALL, connect_timeout=timeout, tls=tls_config)
    conn = Connection(server, user=bind_dn, password=password, auto_referrals=False,
                      raise_exceptions=True, receive_timeout=timeout)
    try:
        conn.open(read_server_info=False)
        if start_tls and not conn.start_tls(read_server_info=False):
            raise ValueError("Unable to negotiate LDAP StartTLS.")
        if not conn.bind():
            raise ValueError("LDAP bind failed.")
        yield conn
    except LDAPException as exc:
        raise RuntimeError(f"LDAP: {exc}") from exc
    finally:
        if not conn.closed:
            conn.unbind()


def search(conn, base, query, attributes, scope=SUBTREE):
    cookie, seen, entries = None, set(), []
    while True:
        conn.search(base, query, scope, attributes=list(dict.fromkeys(attributes)),
                    paged_size=500 if scope == SUBTREE else None, paged_cookie=cookie)
        result = conn.result
        if result["result"] != 0 or any(item["type"] == "searchResRef" for item in conn.response):
            raise ValueError(f"Incomplete LDAP search under {base}: {result.get('description')}.")
        entries.extend(item for item in conn.response if item["type"] == "searchResEntry")
        cookie = result.get("controls", {}).get(PAGING, {}).get("value", {}).get("cookie")
        if not cookie:
            return entries
        if cookie in seen:
            raise ValueError("Repeated LDAP paging cookie.")
        seen.add(cookie)


def directory_entries(conn, mapping, exporting=False):
    mapping.validate()
    group_filter = f"(objectClass={mapping.group_class})"
    if mapping.group_filter:
        group_filter = f"(&{group_filter}{mapping.group_filter})"
    group_attrs = ["cn", mapping.membership]
    user_attrs = [mapping.username]
    if mapping.membership == "uniqueMember":
        group_attrs.append("uniqueIdentifier")
        user_attrs.append("uniqueIdentifier")
    if not exporting:
        group_attrs.append("description")
        if mapping.membership == "memberOf":
            user_attrs.append("memberOf")
    elif mapping.membership == "memberUid":
        group_attrs.append("gidNumber")
    groups = search(conn, mapping.group_base, group_filter, group_attrs)
    users = search(conn, mapping.user_base, f"(&{mapping.user_filter}(!{group_filter}))", user_attrs)
    return groups, users


def unique_index(entries, key):
    index = {}
    for entry in entries:
        value = key(entry)
        if value in index:
            raise ValueError(f"Ambiguous LDAP records: {entry['dn']} and {index[value]['dn']}.")
        index[value] = entry
    return index


def from_directory(groups, users, mapping):
    data = Transfer()
    by_dn = unique_index([*groups, *users], lambda entry: dn_key(entry["dn"]))
    by_uid = defaultdict(list)
    names = {}
    for entry in users:
        name = single(entry, mapping.username)
        if name:
            names[entry["dn"]] = name
            by_uid[name].append(entry)
    for entry in groups:
        key = entry["dn"]
        descriptions = values(entry, "description")
        data.groups[key] = Group(key, single(entry, "cn", required=True),
                                 description=str(descriptions[0]) if descriptions else "")

    def relate(member, group):
        if member in data.groups:
            data.nesting.add((member, group))
        elif member in names and len(by_uid[names[member]]) == 1:
            data.members.add(Membership(group, names[member]))
        else:
            raise ValueError(f"LDAP member {member!r} has no unambiguous username.")

    if mapping.membership == "memberOf":
        for entry in [*groups, *users]:
            for value in values(entry, "memberOf"):
                parent = by_dn.get(dn_key(str(value)))
                if parent and parent["dn"] in data.groups:
                    relate(entry["dn"], parent["dn"])
                elif entry["dn"] in data.groups:
                    raise ValueError(f"Parent group {value!r} was not included in the LDAP group search.")
    else:
        for entry in groups:
            for value in values(entry, mapping.membership):
                text = str(value)
                if mapping.membership == "memberUid":
                    matches = by_uid[text]
                    target = matches[0] if len(matches) == 1 else None
                elif mapping.membership == "uniqueMember":
                    dn, identifier = member_key(text)
                    target = by_dn.get(dn)
                    if identifier and target and identifier not in {
                        str(item).upper() for item in values(target, "uniqueIdentifier")
                    }:
                        raise ValueError(f"Cannot verify the LDAP uniqueMember identifier for {text!r}.")
                else:
                    target = by_dn.get(dn_key(text))
                if target is None:
                    raise ValueError(f"Group {entry['dn']} has an unresolved LDAP member {text!r}.")
                relate(target["dn"], entry["dn"])
    child_first(data.groups, data.nesting)
    return data


@dataclass(frozen=True)
class LDAPWrite:
    dn: str
    create: bool
    members: tuple[str, ...]
    attributes: dict

    def label(self):
        return f"{'Create group' if self.create else 'Add memberships'}: {self.dn}"

    def describe(self):
        heading = self.label()
        if "gidNumber" in self.attributes:
            heading += f" [gidNumber: {self.attributes['gidNumber']}]"
        return "\n".join([heading, *(f"  {member}" for member in self.members)])


def export_plan(conn, data, mapping):
    if mapping.membership == "memberOf":
        raise ValueError("memberOf is read-only.")
    if mapping.membership == "memberUid" and data.nesting:
        raise ValueError("posixGroup/memberUid cannot represent nested groups. No writes were made.")
    existing, users = directory_entries(conn, mapping, exporting=True)
    names = unique_index(existing, lambda entry: single(entry, "cn", required=True).casefold())
    wanted_names = set()
    dns, required = {}, defaultdict(set)
    user_index = defaultdict(list)
    for entry in users:
        user_index[single(entry, mapping.username)].append(entry)
    for key, group in data.groups.items():
        name = group.name.casefold()
        if name in wanted_names:
            raise ValueError(f"LDAP has no PingOne population scopes: duplicate group name {group.name!r}.")
        wanted_names.add(name)
        dns[key] = names[name]["dn"] if name in names else f"cn={escape_rdn(group.name)},{mapping.group_base}"
    for member in data.members:
        matches = user_index[member.username]
        if not member.username or len(matches) != 1:
            raise ValueError(f"Expected one LDAP entry for username {member.username!r}.")
        required[member.group].add(member.username if mapping.membership == "memberUid" else matches[0]["dn"])
    for child, parent in data.nesting:
        required[parent].add(dns[child])
    operations = []
    gid = mapping.first_gid
    used_gids = {
        int(value) for entry in
        (search(conn, mapping.group_base, "(gidNumber=*)", ["gidNumber"])
         if mapping.membership == "memberUid" else [])
        for value in values(entry, "gidNumber")
    }
    key_for = {"member": dn_key, "uniqueMember": member_key, "memberUid": str}[mapping.membership]
    entries_by_dn = (unique_index([*existing, *users], lambda entry: dn_key(entry["dn"]))
                     if mapping.membership == "uniqueMember" else {})
    for key in child_first(data.groups, data.nesting):
        group = data.groups[key]
        old = names.get(group.name.casefold())
        current = {key_for(str(value)) for value in values(old, mapping.membership)} if old else set()
        if mapping.membership == "uniqueMember":
            for dn, identifier in list(current):
                entry = entries_by_dn.get(dn)
                if identifier and entry and identifier in {str(value).upper()
                                                           for value in values(entry, "uniqueIdentifier")}:
                    current.add((dn, ""))
        added = tuple(sorted(value for value in required[key] if key_for(value) not in current))
        if old:
            if added:
                operations.append(LDAPWrite(dns[key], False, added, {}))
            continue
        attrs = {"objectClass": ["top", mapping.group_class], "cn": group.name}
        if group.description:
            attrs["description"] = group.description
        if added:
            attrs[mapping.membership] = list(added)
        if mapping.group_class.lower() in {"groupofnames", "groupofuniquenames"} and not added:
            raise ValueError(f"LDAP schema requires a member when creating {group.name!r}.")
        if mapping.group_class.lower() == "group":
            attrs.update(sAMAccountName=group.name, groupType=2)  # Global distribution, not security.
            if search(conn, mapping.group_base, f"(sAMAccountName={escape_filter_chars(group.name)})",
                      ["sAMAccountName"]):
                raise ValueError(f"LDAP sAMAccountName already exists: {group.name!r}.")
        if mapping.membership == "memberUid":
            if not gid:
                raise ValueError("Specify a starting gidNumber to create POSIX groups.")
            while gid in used_gids:
                gid += 1
            if not 0 < gid <= 2**31 - 1:
                raise ValueError(f"No available LDAP gidNumber starting at {mapping.first_gid}.")
            attrs["gidNumber"] = gid
            gid += 1
        operations.append(LDAPWrite(dns[key], True, added, attrs))
    return operations


def apply_export(conn, operations, mapping, progress):
    completed = []
    key_for = {"member": dn_key, "uniqueMember": member_key, "memberUid": str}[mapping.membership]
    for index, write in enumerate(operations):
        label = write.label()
        progress(index, len(operations), label)
        try:
            if write.create:
                ok = conn.add(write.dn, attributes=write.attributes)
            else:
                ok = conn.modify(write.dn, {mapping.membership: [(MODIFY_ADD, list(write.members))]})
            if not ok:
                raise ValueError(str(conn.result))
            read_back = search(conn, write.dn, "(objectClass=*)", [mapping.membership], BASE)
            if len(read_back) != 1 or not {key_for(value) for value in write.members} <= {
                key_for(str(value)) for value in values(read_back[0], mapping.membership)
            }:
                raise ValueError("Write succeeded but LDAP read-back did not confirm the changes.")
        except (ValueError, LDAPException) as exc:
            return completed, f"{label}\n{exc}\n{len(operations) - index - 1} writes not attempted."
        completed.append(label)
    progress(len(operations), len(operations), "Verified")
    return completed, ""
