from flask import Flask,request,jsonify,render_template
from threading import Lock
import os,uuid
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

# Presentation Remote: login + multiple laptops
import time as _time
PPT={}; PPT_LOCK=Lock(); PPT_ONLINE_SECONDS=12

def _ppt_login(v):
 return "".join(ch for ch in str(v or "").strip().lower() if ch.isalnum() or ch in "_-")[:40]
def _ppt_room(login):
 return PPT.setdefault(login,{"seq":0,"command":"","devices":{}})

@app.post("/api/ppt/register")
def ppt_register():
 x=request.json or {}; login=_ppt_login(x.get("login")); dev=str(x.get("device_id",""))[:100]
 if len(login)<2 or not dev:return jsonify(ok=False),400
 with PPT_LOCK:
  room=_ppt_room(login); room["devices"][dev]={"seen":_time.time()}; seq=room["seq"]
 return jsonify(ok=True,seq=seq)

@app.post("/api/ppt/heartbeat")
def ppt_heartbeat():
 x=request.json or {}; login=_ppt_login(x.get("login")); dev=str(x.get("device_id",""))[:100]
 if len(login)<2 or not dev:return jsonify(ok=False),400
 with PPT_LOCK:_ppt_room(login)["devices"].setdefault(dev,{})["seen"]=_time.time()
 return jsonify(ok=True)

@app.get("/api/ppt/poll")
def ppt_poll():
 login=_ppt_login(request.args.get("login")); dev=str(request.args.get("device_id",""))[:100]; last=int(request.args.get("last",0) or 0)
 if len(login)<2 or not dev:return jsonify(ok=False),400
 with PPT_LOCK:
  room=_ppt_room(login); room["devices"].setdefault(dev,{})["seen"]=_time.time(); seq=room["seq"]; cmd=room["command"] if seq>last else ""
 return jsonify(ok=True,seq=seq,command=cmd)

@app.post("/api/ppt/command")
def ppt_command():
 x=request.json or {}; login=_ppt_login(x.get("login")); cmd=str(x.get("command",""))
 if len(login)<2 or cmd not in ("next","prev"):return jsonify(ok=False),400
 with PPT_LOCK:
  room=_ppt_room(login); room["seq"]+=1; room["command"]=cmd; seq=room["seq"]
 return jsonify(ok=True,seq=seq)

@app.get("/api/ppt/status")
def ppt_status():
 login=_ppt_login(request.args.get("login"))
 if len(login)<2:return jsonify(ok=True,online=0)
 now=_time.time()
 with PPT_LOCK:
  online=sum(1 for d in _ppt_room(login)["devices"].values() if now-float(d.get("seen",0))<=PPT_ONLINE_SECONDS)
 return jsonify(ok=True,online=online)

if __name__=="__main__":app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
