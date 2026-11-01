#!/usr/bin/env python3
"""Fail if live OpenClaw config diverges from the canonical role-policy matrix."""
import json, sys, pathlib

CFG = pathlib.Path.home()/".openclaw/openclaw.json"
MATRIX = pathlib.Path(__file__).resolve().parent.parent/"phase-a"/"policy-matrix.json"

def main():
    cfg=json.loads(CFG.read_text()); mx=json.loads(MATRIX.read_text())
    e=cfg["agents"]["entries"]; errs=[]
    for rid,spec in mx["roles"].items():
        if rid not in e: errs.append(f"{rid}: missing agent"); continue
        a=e[rid]; t=a.get("tools",{})
        allow=set((a.get("subagents") or {}).get("allowAgents") or [])
        if set(spec["spawn"])!=allow:
            errs.append(f"{rid}: allowAgents {sorted(allow)} != {sorted(spec['spawn'])}")
        deny=set(t.get("deny") or [])
        if spec["spawn"]==[] and "sessions_spawn" not in deny:
            errs.append(f"{rid}: sessions_spawn not denied for a leaf role")
        ex=spec["exec"]
        if ex=="deny":
            if "exec" not in deny: errs.append(f"{rid}: exec should be denied")
        elif ex=="approval":
            if "exec" in deny: errs.append(f"{rid}: exec denied on a lead (breaks children)")
            elif (t.get("exec") or {}).get("ask")!="always": errs.append(f"{rid}: lead exec must be ask=always")
        elif ex=="sandbox":
            if (a.get("sandbox") or {}).get("mode")!="all": errs.append(f"{rid}: sandbox not enabled")
            if (a.get("sandbox",{}).get("docker") or {}).get("image")!=mx["image"]: errs.append(f"{rid}: sandbox image mismatch")
        if spec["sandbox"] and (a.get("sandbox") or {}).get("mode")!="all":
            errs.append(f"{rid}: sandbox expected")
    if errs:
        print("POLICY DRIFT:"); [print(" -",x) for x in errs]; sys.exit(1)
    print(f"policy OK: {len(mx['roles'])} roles match matrix")

if __name__=="__main__": main()
