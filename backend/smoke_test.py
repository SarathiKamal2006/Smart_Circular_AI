import os, sys
os.environ["EMBEDDINGS"]="tfidf"
sys.path.insert(0,".")
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as c:
    r=c.post("/api/circulars/samples/load").json(); print("loaded",r["added"])
    circs=c.get("/api/circulars").json()
    pl=[x for x in circs if "placement" in x["filename"]][0]
    f=pl["facts"]; print("TITLE:",f["title"]); print({k:f[k] for k in ("department","time","venue")}); print("date",f["event_date"]["text"],"deadline",f["deadline"]["text"])
    print("SUMMARY:",pl["summary"])
    sid="t1"
    qs=["When is the placement training?","Where?","Who can attend?","What's the last date for registration?","What should I bring?","Who should I contact?","How do I register?","What time does it end?"]
    for q in qs:
        j=c.post("/api/chat",json={"question":q,"session_id":sid,"circular_id":pl["id"] if q.startswith("When is the pl") else None}).json()
        print(f"\nQ: {q}\n   [{j['intent']['intent']} {j['intent']['confidence']}] conf={j['confidence']} follow={j['followup']} circ={j['circular_title'][:30]}\nA: {j['answer']}")
    print("\n--- cross-circular, no scope")
    for q in ["When is the internal assessment test?","What is the last date to pay the fee?","How much is the hostel fee?","Who can attend the generative AI workshop?","Where is the workshop?","What is the cafeteria menu?"]:
        j=c.post("/api/chat",json={"question":q,"session_id":"t2"}).json()
        print(f"\nQ: {q}\n   [{j['intent']['intent']}] conf={j['confidence']} circ={(j['circular_title'] or '')[:35]}\nA: {j['answer']}")
    print(c.get("/api/stats").json())
    m=c.post("/api/chat",json={"question":"Where?","session_id":"t1"}).json()
    t=c.get(f"/api/tts/{m['message_id']}"); print("tts",t.status_code, t.headers.get("content-type"))
