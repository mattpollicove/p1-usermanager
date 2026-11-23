import asyncio
import csv
import io
import json
import unittest

import httpx
from ldap3 import Connection, MOCK_SYNC, Server

from api import ldap_groups
from api.group_transfer import (
    Group, Membership, Transfer, apply_import, preflight, read_csv, write_csv,
)
from api.pingone_groups import PingOneGroups


class Directory:
    def __init__(self):
        self.records = [{"id": "p", "name": "Parent"}]
        self.links = {("older", "p")}
        self.members = {("old", "p")}
        self.writes = []
        self.fail_once = False

    async def groups(self):
        return self.records + [{"id": "older", "name": "Older"}]

    async def populations(self):
        return {"pop": "People"}

    async def users(self):
        return [{"id": key, "username": name} for key, name in
                (("old", "Former"), ("new", "Present"))]

    async def parents(self, target):
        return {parent for child, parent in self.links if child == target}

    async def direct_members(self, target):
        return [user for user in await self.users() if (user["id"], target) in self.members]

    async def create_group(self, group):
        self.writes.append(("create", group.key))
        self.records.append({"id": group.key, "name": group.name})
        return group.key

    async def nest_group(self, child, parent):
        self.writes.append(("nest", child, parent))
        self.links.add((child, parent))

    async def add_member(self, user, group):
        self.writes.append(("add", user, group))
        self.members.add((user, group))
        if self.fail_once:
            self.fail_once = False
            raise RuntimeError("timeout after server committed write")

    async def remove_member(self, user, group):
        self.writes.append(("remove", user, group))
        self.members.remove((user, group))


class GroupTransferTests(unittest.IsolatedAsyncioTestCase):
    async def test_preview_then_partial_write_and_fresh_rerun(self):
        api = Directory()
        data = Transfer({"child": Group("child", "Child", "environment"),
                         "parent": Group("parent", "Parent", "environment")},
                        {("child", "parent")},
                        {Membership("parent", "Present")})
        plan = await preflight(api, data, replacement={"parent"})
        self.assertEqual(api.writes, [])
        self.assertEqual(plan.remove, [("old", "parent")])
        api.fail_once = True
        completed, error = await apply_import(api, plan, lambda *_: None)
        self.assertEqual(len(completed), 2)
        self.assertIn("1 writes not attempted", error)
        self.assertIn(("old", "p"), api.members)
        rerun = await preflight(api, data, replacement={"parent"})
        self.assertEqual(list(rerun.operations()), [("REMOVE direct member", "parent", "old")])
        self.assertFalse((await apply_import(api, rerun, lambda *_: None))[1])
        self.assertEqual(api.writes, [("create", "child"), ("nest", "child", "p"),
                                      ("add", "new", "p"), ("remove", "old", "p")])
        self.assertIn(("older", "p"), api.links)

    async def test_preflight_rejects_bad_target_before_writes(self):
        api = Directory()
        parent = Group("parent", "Parent", "environment")
        for data, error in (
            (Transfer({"parent": parent}, {("parent", "older")}), "cycle"),
            (Transfer(members={Membership("missing", "Present")}), "Missing group"),
            (Transfer(groups={"parent": parent},
                      members={Membership("parent", "Present", "stale")}), "target user"),
            (Transfer(groups={"unscoped": Group("unscoped", "New")}), "target scope"),
            (Transfer(nesting={("p", "older")}), "require all listed"),
        ):
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                await preflight(api, data)
        api.records.append({"id": "p2", "name": "Parent"})
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            await preflight(api, Transfer({"parent": parent}))
        self.assertEqual(api.writes, [])

    async def test_pingone_api_payload_direction_and_direct_only(self):
        calls = []

        class Client:
            base_url = "https://api.pingone.example/v1/environments/test"

            async def get_token(self):
                return "test"

            def _get_auth_headers(self, token):
                return {"Authorization": f"Bearer {token}"}

        def responder(request):
            calls.append(request)
            if request.method == "POST":
                return httpx.Response(200, json={"id": "parent"})
            if request.url.path.endswith("/users"):
                return httpx.Response(200, json={"_embedded": {"users": [{"id": "user"}]}})
            return httpx.Response(200, json={"_embedded": {"groupMemberships": [
                {"id": "parent", "type": "DIRECT"}, {"id": "grandparent", "type": "INDIRECT"},
            ]}})

        async with httpx.AsyncClient(transport=httpx.MockTransport(responder)) as client:
            api = PingOneGroups(Client(), client)
            await api.nest_group("child", "parent")
            self.assertEqual(await api.parents("child"), {"parent"})
            self.assertEqual(await api.direct_members("parent"), [{"id": "user"}])
        self.assertTrue(calls[0].url.path.endswith("/groups/child/memberOfGroups"))
        self.assertEqual(json.loads(calls[0].content), {"id": "parent"})
        self.assertEqual(calls[-1].url.params["filter"], 'memberOfGroups[id eq "parent" and type eq "DIRECT"]')

    def test_typed_csv_round_trip_and_cell_validation(self):
        data = Transfer({"team": Group("team", 'Team, "A"', "environment"),
                         "parent": Group("parent", "Parent", "environment")},
                        {("team", "parent")}, {Membership("team", "a,b; c")})
        stream = io.StringIO(newline="")
        write_csv(stream, data)
        self.assertEqual(read_csv(io.StringIO(stream.getvalue())), data)
        for cell, delimiter in ((json.dumps(["a;b", "c"]), ""), (r"a\;b;c", ";")):
            stream = io.StringIO(newline="")
            csv.writer(stream).writerows([("record_type", "group_key", "name", "users"),
                                          ("group", "g", "Group", cell)])
            self.assertEqual(read_csv(io.StringIO(stream.getvalue()), "users", delimiter).members,
                             {Membership("g", "a;b"), Membership("g", "c")})
        with self.assertRaisesRegex(ValueError, "CSV line 2"):
            read_csv(io.StringIO("record_type,group_key,name,members\ngroup,g,Group,{}\n"))

    def test_ldap_dialects_and_ranged_values(self):
        user = {"dn": r"cn=Smith\, Alex,ou=users,dc=test", "attributes": {
            "uid": ["alex"], "uniqueIdentifier": ["'0101'B"], "memberOf": ["cn=G,ou=groups,dc=test"]}}
        for attr, reference in (
            ("member", r"CN=Smith\2C Alex,OU=users,DC=test"),
            ("uniqueMember", r"cn=Smith\, Alex,ou=users,dc=test#'0101'B"),
            ("memberUid", "alex"),
            ("memberOf", None),
        ):
            mapping = ldap_groups.DirectoryMapping("ou=groups,dc=test", "ou=users,dc=test",
                                                   "group", attr, "uid", "(objectClass=person)")
            group = {"dn": "cn=G,ou=groups,dc=test", "attributes":
                     {"cn": ["G"], attr: [] if reference is None else [reference]}}
            self.assertEqual(ldap_groups.from_directory([group], [user], mapping).members,
                             {Membership(group["dn"], "alex")})
        with self.assertRaisesRegex(ValueError, "incomplete"):
            ldap_groups.values({"dn": "cn=G", "attributes": {"member;range=0-5": []}}, "member")

    def test_ldap_export_round_trip_and_unsupported_nesting_blocks(self):
        conn = Connection(Server("mock-directory"), client_strategy=MOCK_SYNC)
        conn.bind()
        for dn, classes in (("dc=test", ["domain"]), ("ou=groups,dc=test", ["organizationalUnit"]),
                            ("ou=users,dc=test", ["organizationalUnit"])):
            conn.strategy.add_entry(dn, {"objectClass": classes})
        conn.strategy.add_entry(r"cn=Smith\, Alex,ou=users,dc=test",
                                {"objectClass": ["person"], "uid": "alex"})
        data = Transfer({"child": Group("child", "Child"), "parent": Group("parent", "Parent")},
                        {("child", "parent")}, {Membership("child", "alex")})
        for cls, attr in (("posixGroup", "memberUid"), ("groupOfNames", "member")):
            mapping = ldap_groups.DirectoryMapping("ou=groups,dc=test", "ou=users,dc=test",
                                                   cls, attr, "uid", "(objectClass=person)")
            if attr == "memberUid":
                with self.assertRaisesRegex(ValueError, "cannot represent nested groups"):
                    ldap_groups.export_plan(conn, data, mapping)
                self.assertEqual(ldap_groups.directory_entries(conn, mapping)[0], [])
            else:
                writes = ldap_groups.export_plan(conn, data, mapping)
                self.assertEqual([op.dn.split(",")[0] for op in writes], ["cn=Child", "cn=Parent"])
                self.assertFalse(ldap_groups.apply_export(conn, writes, mapping, lambda *_: None)[1])
                self.assertEqual(ldap_groups.export_plan(conn, data, mapping), [])
                out = ldap_groups.from_directory(*ldap_groups.directory_entries(conn, mapping), mapping)
                self.assertEqual(out.nesting, {("cn=Child,ou=groups,dc=test", "cn=Parent,ou=groups,dc=test")})
                self.assertEqual(out.members, {Membership("cn=Child,ou=groups,dc=test", "alex")})


if __name__ == "__main__":
    unittest.main()
