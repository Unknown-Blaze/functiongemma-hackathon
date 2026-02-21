import random
import re
from copy import deepcopy

from benchmark import BENCHMARKS, compute_f1, compute_total_score
from main import generate_hybrid


def perturb_text(text, rng):
    variants = [
        lambda s: s,
        lambda s: s.replace("What's", "What is").replace("How's", "How is"),
        lambda s: s.replace("Send a message", "Text").replace("Find", "Look up"),
        lambda s: s.replace(" and ", ", and "),
        lambda s: re.sub(r"\s+", " ", s).strip(),
        lambda s: s.rstrip(".") + " please.",
    ]
    out = rng.choice(variants)(text)
    if rng.random() < 0.25:
        out = "Hey assistant, " + out[0].lower() + out[1:]
    return out


def build_stress_cases(multiplier=4, seed=42):
    rng = random.Random(seed)
    cases = []
    for case in BENCHMARKS:
        for idx in range(multiplier):
            clone = deepcopy(case)
            clone["name"] = f"{case['name']}_stress_{idx+1}"
            for msg in clone["messages"]:
                if msg.get("role") == "user":
                    msg["content"] = perturb_text(msg["content"], rng)
            cases.append(clone)
    return cases


def run_local_stress(multiplier=4, seed=42):
    cases = build_stress_cases(multiplier=multiplier, seed=seed)
    results = []
    print(f"Running stress benchmark on {len(cases)} cases...")
    for i, case in enumerate(cases, 1):
        result = generate_hybrid(case["messages"], case["tools"])
        f1 = compute_f1(result.get("function_calls", []), case["expected_calls"])
        results.append({
            "name": case["name"],
            "difficulty": case["difficulty"],
            "total_time_ms": float(result.get("total_time_ms", 0)),
            "f1": f1,
            "source": result.get("source", "unknown"),
        })
        if i % 20 == 0:
            print(f"  {i}/{len(cases)} done...")

    avg_f1 = sum(r["f1"] for r in results) / len(results)
    avg_time = sum(r["total_time_ms"] for r in results) / len(results)
    on_device = sum(1 for r in results if r["source"] == "on-device")
    score = compute_total_score(results)

    print("\n=== Local Stress Summary ===")
    print(f"Cases         : {len(results)}")
    print(f"Avg F1        : {avg_f1:.4f}")
    print(f"Avg Time (ms) : {avg_time:.2f}")
    print(f"On-device %   : {100.0 * on_device / len(results):.1f}%")
    print(f"Score         : {score:.1f}%")


if __name__ == "__main__":
    run_local_stress()
