"""Turn reports/delta.txt and reports/e2e.xml into a short report a non-expert can read."""
import re
import sys
import xml.etree.ElementTree as ET

import os
R = os.environ.get("REPORT_DIR", "reports/latest")
GROUPS = {
    "TestInfrastructure": "Is everything built?",
    "TestApi": "Does the API answer correctly?",
    "TestDataFlow": "Do prices flow Lambda -> Redis -> API?",
    "TestDynamoControl": "Does DynamoDB control the API (enable, disable, cache time)?",
    "TestLogs": "Are logs written?",
    "TestResilience": "Does it survive a failure?",
}


def words(name):
    t = name.removeprefix("test_").replace("_", " ")
    t = t.replace("api", "API").replace("alb", "ALB").replace("ecs", "ECS").replace("ecr", "ECR").replace("az", "AZ").replace("lambda", "Lambda").replace("redis", "Redis").replace("dynamodb", "DynamoDB").replace("ttl", "TTL")
    return t[0].upper() + t[1:]


def delta_table():
    """Section D of docs/match-delta.md: the known differences between AWS and Floci."""
    try:
        doc = open("docs/match-delta.md").read()
    except FileNotFoundError:
        return ["(docs/match-delta.md not found)"]
    m = re.search(r"^## D\. Delta.*?\n(.*)\Z", doc, re.S | re.M)
    return m.group(1).strip().splitlines() if m else ["(section D not found in docs/match-delta.md)"]


def delta():
    try:
        lines = open(f"{R}/delta.txt").read().splitlines()
    except FileNotFoundError:
        return ["## C. Match", "", "Delta check did not run."], False
    checks = [(l.strip()[:4].strip(), l.strip()[4:].strip()) for l in lines if re.match(r"\s+(PASS|GAP)\s", l)]
    gaps = [c for c in checks if c[0] == "GAP"]
    summary = next((l for l in lines if l.startswith("Diagram match")), "no result")
    out = ["## C. Match: does Floci have every element of the production diagram (A)?", "", f"**{summary}**", "",
           "| # | Element in diagram A | Result |", "|---|---|---|"]
    out += [f"| {i} | {name} | {res} |" for i, (res, name) in enumerate(checks, 1)]
    out += ["", "A PASS means Floci reports the resource as configured. It does not prove real AWS routing.", "",
            "## D. Delta: what is still different between AWS (A) and Floci (B)", ""]
    if gaps:
        out += ["**Missing right now (found by the check above):**", ""] + [f"- {n}" for _, n in gaps] + [""]
    else:
        out += ["Nothing is missing from the diagram. These are the known differences that remain:", ""]
    out += delta_table()
    return out, not gaps


def e2e():
    try:
        suite = ET.parse(f"{R}/e2e.xml").getroot()
        suite = suite if suite.tag == "testsuite" else suite[0]
    except (FileNotFoundError, ET.ParseError):
        return ["## E. Behaviour", "", "e2e did not produce a result."], False
    groups = {}
    for tc in suite.iter("testcase"):
        cls = tc.get("classname", "").split(".")[-1]
        bad = tc.find("failure") is not None or tc.find("error") is not None
        groups.setdefault(cls, []).append((words(tc.get("name")), not bad, float(tc.get("time", 0)), tc))
    total = sum(len(v) for v in groups.values())
    failed = sum(1 for v in groups.values() for x in v if not x[1])
    out = ["## E. Behaviour: does the system work? (end-to-end tests)", "",
           f"**{total - failed} of {total} tests passed**" + (f", {failed} FAILED" if failed else ""), ""]
    for cls, tests in groups.items():
        out.append(f"**{GROUPS.get(cls, cls)}**")
        for name, ok, secs, tc in tests:
            out.append(f"- {'PASS' if ok else 'FAIL'}  {name} ({secs:.1f}s)")
            if not ok:
                node = tc.find("failure") if tc.find("failure") is not None else tc.find("error")
                out.append(f"    reason: {(node.get('message') or '')[:160]}")
        out.append("")
    return out, failed == 0


d, d_ok = delta()
e, e_ok = e2e()
verdict = "PASS: the environment matches the diagram and works end to end." if d_ok and e_ok else "FAIL: see the rows marked GAP in C, the 'Missing right now' list in D, or the FAIL lines in E."
text = "\n".join(["# Floci run report", ""] + d + [""] + e + ["## Verdict", "", verdict, ""])
open(f"{R}/summary.md", "w").write(text)
print(text)
sys.exit(0 if d_ok and e_ok else 1)
