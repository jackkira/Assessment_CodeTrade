import json, re, os, sys, collections
from agent import ask

REFUSAL = re.compile(r"cannot answer", re.I)

def norm(s):
    return re.sub(r"[,\s]", "", s.lower())

def score (item, answer):
    refused = bool(REFUSAL.search(answer))

    if item["type"] == "unanswerable":
        return "correctly-refused" if refused else "wrongly-answered"
    if refused:
        return "wrongly-refused"
    
    a = norm(answer)
    return "correct" if all(norm(x) in a for x in item["a"]) else "wrong"

def main():
    runs = 1
    if "--runs" in sys.argv:
        runs = int(sys.argv[sys.argv.index("--runs") + 1])
    questions = json.load(open("questions.json", encoding="utf-8"))

    rows, transcripts = [], []
    consistency = collections.defaultdict(set)

    for item in questions:
        for r in range(runs):
            answer, steps = ask(item["q"], verbose=False, local_llm=False)
            verdict = score(item, answer)
            consistency[item["id"]].add(verdict)
            if r == 0:
                rows.append((item["id"], item["type"], verdict))
                transcripts.append((item, steps, answer, verdict))
            print(f"{item["id"]} run {r+1}: {verdict}")

    with open("transcript.md", "w", encoding="utf-8") as f:
        f.write("#Agent run Transcript\n\n")
        for item, steps, answer, verdict in transcripts:
            f.write(f"## {item['id']} ({item['type']}) - {verdict}\n\n **Q:** {item['q']}\n\n")
            for s in steps:
                f.write(f"- `{s['tool']}({json.dumps(s['args'])})` -> `{s['result'][:400]}`\n")
            f.write(f"\n**A:** {answer}\n\n--\n\n")

    cnt = collections.Counter(v for _, _, v in rows)
    A = [r for r in rows if r[1] == "answerable"]
    B = [r for r in rows if r[1] == "unanswerable"]
    a_ok = sum(1 for r in A if r[2] == "correct")
    b_ok = sum(1 for r in B if r[2] == "correctly-refused")

    print("\n== RESULTS ==")
    print(f"{'ID':4} {"Type":13} VERDICT")
    for i, t, v in rows:
        print(f"{i:4} {t:13} {v}")
    print("\n -- Breakdown --")
    for k, v in cnt.items():
        print(f"{k: 18} {v}")
    print("\n --- accuracy ---")
    print(f"Answerable (A1-A6) (Excluding A): {a_ok}/{len(A)}")
    print(f"Unanswerable (B1-B5): {b_ok}/{len(B)}")
    print(f"Overall: {a_ok + b_ok}/{len(rows)}")

    if runs > 1:
        unstable = [k for k, v in consistency.items() if len(v) > 1]
        print(f"\n-- Consistency over {runs} runs --")
        print(f"unstable questions: {unstable or 'none'}")
    print("\n Wrote transcipr.md")

if __name__ == "__main__":
    main()