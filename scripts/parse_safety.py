#!/usr/bin/env python3
"""Parse `safety check --output json` output (which may be wrapped in a banner)."""
import json
import sys

data = sys.stdin.read()
start = data.find("{")
end = data.rfind("}")
if start == -1 or end == -1:
    print("NO JSON FOUND")
    sys.exit(0)
d = json.loads(data[start : end + 1])
vulns = d.get("vulnerabilities", [])
print(f"vulnerabilities: {len(vulns)}")
for v in vulns:
    print(
        v.get("package_name"),
        v.get("vulnerability_id"),
        v.get("severity"),
        str(v.get("advisory", ""))[:100],
    )
