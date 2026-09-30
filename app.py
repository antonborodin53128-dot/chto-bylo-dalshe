from flask import Flask,request,jsonify,render_template
from threading import Lock
import os,uuid,json,urllib.request,urllib.parse
app=Flask(__name__); lock=Lock()
Q=[
("ЧТО СДЕЛАЕТ БЫК?",["Развернётся и спокойно уйдёт","Пробежит мимо контейнера","Запрыгнет внутрь к мужчине","Начнёт бодать контейнер"],2),
("С КАКОЙ ПОПЫТКИ МУЖЧИНА ПОПАДЁТ ПО ГУБКЕ?",["Со второго раза","С третьего","С четвёртого","Вообще не попадёт"],2),
("ЧТО ОН ПЕЧАТАЛ?",["Культуру","Деньги","Кроссворды","Газету «Коммерсант»"],0),
("ЧТО СДЕЛАЕТ ДАЛЬШЕ ИНДИЙСКИЙ СУПЕРГЕРОЙ?",["Спасёт пассажиров от террористов","Заберётся на крыло и починит лопасть","Сцепит всех пассажиров и вытащит","Опустит колесо, чтобы самолёт сел"],3),
("ЧТО СЛУЧИТСЯ С ГИМНАСТОМ?",["Станет добычей крокодила","Выполнит акробатический трюк","Сломает ветку","Зацепится футболкой за ветку"],0),
("КТО ЖЕ ПОЁТ ЗА ШИРМОЙ?",["Ургант","Басков","Билан","Сын Градского"],2),
("КАКАЯ КРЫШКА ЗАЙМЁТ 1-Е МЕСТО?",["Синяя","Белая","Голубая","Золотая"],3)]
S={"r":0,"open":False,"session":str(uuid.uuid4()),"players":{},"votes":{}}
@app.get("/")
def home(): return render_template("index.html")
@app.get("/admin")
def admin(): return render_template("admin.html")


@app.get("/remote")
def remote_page(): return render_template("remote.html")

@app.get("/results")
def results(): return render_template("results.html")

@app.get("/qr")
def qr_page(): return render_template("qr.html")
@app.get("/api/state")
def state():
 d=request.args.get("device",""); r=S["r"]; key=f'{S["session"]}:{r}:{d}'
 return jsonify(round=r+1,open=S["open"],question=Q[r][0],answers=Q[r][1],voted=key in S["votes"],session=S["session"],registered=d in S["players"])
@app.post("/api/join")
def join():
 x=request.json or {}; d=str(x.get("device",""))[:100]; n=str(x.get("name","")).strip()[:40]
 if not d or not n:return jsonify(ok=False),400
 with lock:S["players"][d]=n
 return jsonify(ok=True,session=S["session"])
@app.post("/api/vote")
def vote():
 x=request.json or {}; d=str(x.get("device","")); c=int(x.get("choice",-1))
 with lock:
  if not S["open"]:return jsonify(ok=False,error="Голосование закрыто"),409
  if d not in S["players"]:return jsonify(ok=False,error="Введите имя"),403
  r=S["r"]; k=f'{S["session"]}:{r}:{d}'
  if k in S["votes"]:return jsonify(ok=False,error="Вы уже проголосовали"),409
  if c not in range(4):return jsonify(ok=False),400
  S["votes"][k]=c
 return jsonify(ok=True)
@app.get("/api/admin")
def ast():
 r=S["r"]; counts=[0]*4; scores={d:0 for d in S["players"]}
 for k,c in S["votes"].items():
  p=k.split(":"); rr=int(p[1]); dev=":".join(p[2:])
  if p[0]!=S["session"]:continue
  if rr==r:counts[c]+=1
  if dev in scores and c==Q[rr][2]:scores[dev]+=1
 leaders=sorted([{"name":S["players"][d],"score":v} for d,v in scores.items()],key=lambda x:(-x["score"],x["name"]))
 return jsonify(round=r+1,open=S["open"],question=Q[r][0],answers=Q[r][1],counts=counts,players=len(S["players"]),voted=sum(counts),leaders=leaders)
@app.post("/api/admin/action")
def action():
 x=request.json or {}; a=x.get("action")
 with lock:
  if a=="toggle":S["open"]=not S["open"]
  elif a=="round":S["r"]=max(0,min(6,int(x["round"])-1));S["open"]=False
  elif a=="reset":S.update(r=0,open=False,session=str(uuid.uuid4()),players={},votes={})
  else:return jsonify(ok=False),400
 return jsonify(ok=True)

# Presentation Remote proxy: the contest stays independent, while commands go
# to the standalone realtime Presentation Remote service.
PRESENTATION_REMOTE_URL=os.environ.get("PRESENTATION_REMOTE_URL","https://presentation-remote-yy6x.onrender.com").rstrip("/")

def _remote_json(path, method="GET", payload=None):
 data=None
 headers={}
 if payload is not None:
  data=json.dumps(payload).encode("utf-8"); headers["Content-Type"]="application/json"
 req=urllib.request.Request(PRESENTATION_REMOTE_URL+path,data=data,headers=headers,method=method)
 with urllib.request.urlopen(req,timeout=8) as r:
  return json.loads(r.read().decode("utf-8"))

def _clean_remote_login(v):
 return "".join(ch for ch in str(v or "").strip().lower() if ch.isalnum() or ch in "_-")[:40]

@app.post("/api/presentation/command")
def presentation_command():
 x=request.json or {}; login=_clean_remote_login(x.get("login")); cmd=str(x.get("command",""))
 if len(login)<2 or cmd not in ("next","prev"):return jsonify(ok=False),400
 try:return jsonify(_remote_json("/api/command","POST",{"login":login,"command":cmd}))
 except Exception as e:return jsonify(ok=False,error="Presentation Remote unavailable"),502

@app.get("/api/presentation/status")
def presentation_status():
 login=_clean_remote_login(request.args.get("login"))
 if len(login)<2:return jsonify(ok=True,online=0)
 try:return jsonify(_remote_json("/api/status?login="+urllib.parse.quote(login)))
 except Exception:return jsonify(ok=False,online=0),502

@app.post("/api/presentation/remote-heartbeat")
def presentation_remote_heartbeat():
 x=request.json or {}; login=_clean_remote_login(x.get("login")); rid=str(x.get("remote_id",""))[:100]
 if len(login)<2 or not rid:return jsonify(ok=False),400
 try:return jsonify(_remote_json("/api/remote-heartbeat","POST",{"login":login,"remote_id":rid}))
 except Exception:return jsonify(ok=False),502

if __name__=="__main__":app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
