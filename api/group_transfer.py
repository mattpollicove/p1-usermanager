"""Portable group records and a read-only PingOne import planner."""

import csv
import json
from collections import defaultdict, deque
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Group:
    key: str
    name: str
    scope: str = ""  # environment, or a target population ID
    description: str = ""
    external_id: str = ""


@dataclass(frozen=True, order=True)
class Membership:
    group: str
    username: str = ""
    user_id: str = ""


@dataclass
class Transfer:
    groups: dict[str, Group] = field(default_factory=dict)
    nesting: set[tuple[str, str]] = field(default_factory=set)  # child, parent
    members: set[Membership] = field(default_factory=set)


FIELDS = ("record_type", "group_key", "name", "scope", "description", "external_id",
          "child_key", "parent_key", "username", "user_id", "members")
ROW_FIELDS = {
    "group": {"group_key", "name", "scope", "description", "external_id", "members"},
    "nesting": {"child_key", "parent_key"},
    "membership": {"group_key", "username", "user_id"},
}


def read_csv(stream, members_column="members", member_delimiter=""):
    """Read typed records; optional mapped cells contain lists of exact usernames."""
    if member_delimiter and (len(member_delimiter) != 1 or member_delimiter in ',\\\"\r\n'):
        raise ValueError("Membership delimiter must be one character other than comma, quote or backslash.")
    data = Transfer()
    reader = csv.DictReader(stream, strict=True)
    headers = reader.fieldnames or []
    if "record_type" not in headers or len(headers) != len(set(headers)):
        raise ValueError("CSV requires a record_type header and unique column names.")
    if members_column != "members" and (members_column not in headers or members_column in FIELDS):
        raise ValueError("Choose a nonstandard CSV header for the mapped membership list.")
    for row in reader:
        try:
            if None in row or None in row.values():
                raise ValueError("Row has a different number of cells than the header.")
            if members_column != "members":
                if row.get("members"):
                    raise ValueError("Both standard and mapped membership cells are populated.")
                row["members"] = row[members_column]
            kind = row["record_type"]
            if kind not in ROW_FIELDS:
                raise ValueError(f"Unknown record type {kind!r}.")
            if any(row.get(col) for col in set(FIELDS) - ROW_FIELDS[kind] - {"record_type"}):
                raise ValueError(f"Unexpected fields in {kind} row.")
            get = lambda key: row.get(key, "")
            if kind == "group":
                key, name = get("group_key"), get("name")
                if not key.strip() or not name.strip() or key in data.groups:
                    raise ValueError("Group needs a unique nonempty key and a name.")
                data.groups[key] = Group(key, name, get("scope"), get("description"), get("external_id"))
                if get("members"):
                    if member_delimiter:
                        values = next(csv.reader([get("members")], delimiter=member_delimiter,
                                                 escapechar="\\", strict=True))
                    else:
                        values = json.loads(get("members"))
                    if not isinstance(values, list) or any(
                        not isinstance(value, str) or not value.strip() for value in values
                    ):
                        raise ValueError("Membership cell must contain a JSON array of usernames.")
                    data.members.update(Membership(key, value) for value in values)
            elif kind == "nesting":
                child, parent = get("child_key"), get("parent_key")
                if not child.strip() or not parent.strip():
                    raise ValueError("Nesting needs child_key and parent_key.")
                data.nesting.add((child, parent))
            else:
                key, username, user_id = get("group_key"), get("username"), get("user_id")
                if not key.strip() or not (username.strip() or user_id.strip()):
                    raise ValueError("Membership needs a group_key and a username or user_id.")
                data.members.add(Membership(key, username, user_id))
        except (ValueError, csv.Error) as exc:
            raise ValueError(f"CSV line {reader.line_num}: {exc}") from exc
    return data


def write_csv(stream, data: Transfer):
    writer = csv.DictWriter(stream, FIELDS)
    writer.writeheader()
    for key, group in sorted(data.groups.items()):
        writer.writerow(dict(record_type="group", group_key=key, name=group.name,
                             scope=group.scope, description=group.description,
                             external_id=group.external_id))
    for child, parent in sorted(data.nesting):
        writer.writerow(dict(record_type="nesting", child_key=child, parent_key=parent))
    for member in sorted(data.members):
        writer.writerow(dict(record_type="membership", group_key=member.group,
                             username=member.username, user_id=member.user_id))


def child_first(nodes, edges):
    dependencies = dict.fromkeys(nodes, 0)
    parents = defaultdict(set)
    for child, parent in set(edges):
        dependencies[parent] += 1
        parents[child].add(parent)
    ready = deque(sorted(node for node, count in dependencies.items() if not count))
    ordered = []
    while ready:
        child = ready.popleft()
        ordered.append(child)
        for parent in sorted(parents[child]):
            dependencies[parent] -= 1
            if not dependencies[parent]:
                ready.append(parent)
    if len(ordered) != len(dependencies):
        raise ValueError("Group nesting contains a cycle or self-link.")
    return ordered


def scope_of(record):
    return (record.get("population") or {}).get("id") or "environment"


@dataclass
class ImportPlan:
    resolved: dict[str, str]
    create: list[Group]
    nest: list[tuple[str, str]]
    add: list[tuple[str, str]]
    remove: list[tuple[str, str]]
    group_labels: dict[str, str]
    user_labels: dict[str, str]

    def operations(self):
        for group in self.create:
            yield "Create group", group.key, group.scope
        for child, parent in self.nest:
            yield "Nest child in parent", child, parent
        for user, group in self.add:
            yield "Add direct member", group, user
        for user, group in self.remove:
            yield "REMOVE direct member", group, user

    def describe(self, operation):
        action, group, value = operation
        label = self.group_labels[group]
        if action == "Nest child in parent":
            value = self.group_labels[value]
        elif action != "Create group":
            value = self.user_labels[value]
        return f"{action}: {label} | {value}"


def resolve_groups(data, groups, populations, default_scope):
    by_id = {group["id"]: group for group in groups}
    external, names = defaultdict(list), defaultdict(list)
    for group in groups:
        if group.get("externalId"):
            external[group["externalId"]].append(group)
        names[group["name"].casefold(), scope_of(group)].append(group)
    resolved, new = {}, {}
    claimed = set()
    occupied_scopes = defaultdict(set)
    for name, scope in names:
        occupied_scopes[name].add(scope)
    claimed_external = set()
    for key, group in sorted(data.groups.items()):
        scope = group.scope or default_scope
        if scope != "environment" and scope not in populations:
            raise ValueError(f"Choose a valid target scope for {group.name!r}.")
        name_key = group.name.casefold(), scope
        if group.external_id and group.external_id in claimed_external:
            raise ValueError(f"Duplicate source external ID {group.external_id!r}.")
        if group.external_id:
            claimed_external.add(group.external_id)
        matches = external.get(group.external_id) or names[name_key]
        if len(matches) > 1:
            raise ValueError(f"Ambiguous target group: {group.name!r}.")
        if matches:
            target = matches[0]
            if scope_of(target) != scope or (
                group.external_id and target.get("externalId") not in (None, "", group.external_id)
            ):
                raise ValueError(f"Target scope or external ID conflicts for {group.name!r}.")
            if target["id"] in claimed:
                raise ValueError(f"Multiple source groups resolve to {group.name!r}.")
            claimed.add(target["id"])
            resolved[key] = target["id"]
        else:
            occupied = occupied_scopes[name_key[0]]
            if scope in occupied or "environment" in occupied or (scope == "environment" and occupied):
                raise ValueError(f"Group name conflicts with another target scope: {group.name!r}.")
            occupied.add(scope)
            new[key] = Group(key, group.name, scope, group.description, group.external_id)
    references = {member.group for member in data.members}
    references.update(key for edge in data.nesting for key in edge)
    for key in sorted(references - data.groups.keys()):
        if key not in by_id:
            raise ValueError(f"Missing group {key!r}; use a group row or an existing PingOne group ID.")
        if key in claimed:
            raise ValueError(f"Group {key!r} is referenced both by target ID and a source key.")
        resolved[key] = key
    return resolved, new


async def preflight(api, data: Transfer, default_scope="", replacement=frozenset()):
    groups = await api.groups()
    users = await api.users() if data.members or replacement else []
    populations = await api.populations() if data.groups else {}
    known = {group["id"]: group for group in groups}
    users_by_id = {user["id"]: user for user in users}
    usernames = defaultdict(list)
    for user in users:
        if user.get("username"):
            usernames[user["username"]].append(user)
    resolved, new = resolve_groups(data, groups, populations, default_scope)
    if not replacement <= data.groups.keys():
        raise ValueError("Replacement scope must contain only explicitly selected group records.")
    if replacement & new.keys():
        raise ValueError("Replacement can target only existing groups.")
    affected = replacement | {member.group for member in data.members}
    for key in affected & resolved.keys():
        target = known[resolved[key]]
        if any(target.get(flag) for flag in ("isAdmin", "isExternal", "isProvisioned", "userFilter")):
            raise ValueError(f"Special or dynamic group {target['name']!r} cannot be edited.")
    desired = defaultdict(set)
    for member in sorted(data.members):
        matches = ([users_by_id[member.user_id]] if member.user_id in users_by_id else []) \
            if member.user_id else usernames[member.username]
        if len(matches) != 1:
            raise ValueError(f"Expected one target user for {(member.user_id or member.username)!r}.")
        user = matches[0]
        scope = new[member.group].scope if member.group in new else scope_of(known[resolved[member.group]])
        if scope != "environment" and scope_of(user) != scope:
            raise ValueError(f"User {user['username']!r} is outside the group's population.")
        desired[member.group].add(user["id"])

    def node(key):
        return ("target", resolved[key]) if key in resolved else ("source", key)

    def target_scope(key):
        return new[key].scope if key in new else scope_of(known[resolved[key]])

    nest, current_edges = [], set()
    if data.nesting:
        for target in known:
            for parent in await api.parents(target):
                if parent not in known:
                    raise ValueError(f"Nesting references unreadable PingOne group {parent!r}.")
                current_edges.add((("target", target), ("target", parent)))
        for child, parent in sorted(data.nesting):
            edge = node(child), node(parent)
            if edge not in current_edges:
                if not data.groups:
                    raise ValueError("Membership-only imports require all listed nesting links to exist.")
                if target_scope(parent) not in ("environment", target_scope(child)):
                    raise ValueError("A population-scoped parent requires a child in the same population.")
                if any(any(known[resolved[key]].get(flag) for flag in
                           ("isAdmin", "isExternal", "isProvisioned", "userFilter"))
                       for key in (child, parent) if key in resolved):
                    raise ValueError("Cannot change nesting of a special or dynamic group.")
                nest.append((child, parent))
        proposed_edges = [(node(child), node(parent)) for child, parent in nest]
        child_first({endpoint for edge in current_edges.union(proposed_edges) for endpoint in edge},
                    current_edges.union(proposed_edges))
    add, remove = [], []
    for key in sorted(affected):
        current = set()
        if key in resolved:
            for user in await api.direct_members(resolved[key]):
                current.add(user["id"])
                users_by_id[user["id"]] = user
        add.extend((user, key) for user in sorted(desired[key] - current))
        if key in replacement:
            remove.extend((user, key) for user in sorted(current - desired[key]))
    group_labels = {
        key: f"{known[target]['name']} [{scope_of(known[target])}; {target}]"
        for key, target in resolved.items()
    }
    group_labels.update({key: f"{group.name} [{group.scope}; source: {key}]"
                         for key, group in new.items()})
    return ImportPlan(resolved, list(new.values()), nest, add, remove, group_labels,
                      {key: f"{user.get('username', key)} [{key}]" for key, user in users_by_id.items()})


async def apply_import(api, plan: ImportPlan, progress):
    ids, completed, verified = dict(plan.resolved), [], []
    creates = {group.key: group for group in plan.create}
    operations = list(plan.operations())
    for index, (action, group, value) in enumerate(operations):
        label = plan.describe(operations[index])
        progress(index, len(operations), label)
        try:
            if action == "Create group":
                ids[group] = await api.create_group(creates[group])
            elif action == "Nest child in parent":
                await api.nest_group(ids[group], ids[value])
            elif action == "Add direct member":
                await api.add_member(value, ids[group])
            else:
                await api.remove_member(value, ids[group])
        except (ValueError, KeyError, RuntimeError) as exc:
            return completed, f"{label}\n{exc}\n{len(operations) - index - 1} writes not attempted."
        completed.append(label)
    try:
        if creates:
            by_id = {group["id"]: group for group in await api.groups()}
            for key, group in creates.items():
                if ids[key] not in by_id or scope_of(by_id[ids[key]]) != group.scope:
                    raise ValueError(f"Could not verify group creation: {group.name}.")
        parents = {child: await api.parents(ids[child]) for child in {c for c, _ in plan.nest}}
        if any(ids[parent] not in parents[child] for child, parent in plan.nest):
            raise ValueError("One or more nesting links could not be verified.")
        members = {key: {user["id"] for user in await api.direct_members(ids[key])}
                   for _, key in set(plan.add + plan.remove)}
        if (any(user not in members[key] for user, key in plan.add)
                or any(user in members[key] for user, key in plan.remove)):
            raise ValueError("One or more membership changes could not be verified.")
        verified = completed
    except (ValueError, KeyError, RuntimeError) as exc:
        return completed, f"Writes returned success, but read-back failed: {exc}"
    progress(len(operations), len(operations), "Verified")
    return verified, ""


async def export_pingone(api):
    data = Transfer()
    groups = await api.groups()
    unsupported = ("isAdmin", "isExternal", "isProvisioned", "userFilter")
    for group in groups:
        if not any(group.get(flag) for flag in unsupported):
            key = group["id"]
            data.groups[key] = Group(key, group["name"], scope_of(group),
                                     group.get("description") or "", group.get("externalId") or "")
    for key in data.groups:
        for parent in await api.parents(key):
            if parent not in data.groups:
                raise ValueError(f"An exported group depends on an unsupported or unreadable parent ({parent}).")
            data.nesting.add((key, parent))
        for user in await api.direct_members(key):
            data.members.add(Membership(key, user["username"]))
    # Check the other direction as well so skipped special groups cannot silently lose edges.
    for group in groups:
        if group["id"] not in data.groups and set(await api.parents(group["id"])) & data.groups.keys():
            raise ValueError("An exported group contains an unsupported child group.")
    child_first(data.groups, data.nesting)
    return data
