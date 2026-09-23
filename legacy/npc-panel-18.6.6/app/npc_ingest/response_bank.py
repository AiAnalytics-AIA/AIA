from __future__ import annotations
import hashlib, json, math, time
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from .registry import Registry

DEFAULT_VALIDITY={"politika":2,"volby":2,"spotreba":4,"nakup":4,"znacka":4,"hodnoty":8,"spokojenost":8,"zdravi":5,"finance":4,"default":4}

def stable_question_id(text:str,topic:str="")->str:
    norm=" ".join(str(text).lower().split())
    return hashlib.sha256(f"{topic}|{norm}".encode()).hexdigest()[:24]


def _age_group(v:Any)->int:
    try:return int(float(v)//10*10)
    except:return -1


def _profile_distance(persona:dict[str,Any], row:dict[str,Any])->float:
    d=0.0
    if persona.get("pohlavi") and row.get("pohlavi") and str(persona["pohlavi"])!=str(row["pohlavi"]): d+=1.0
    try:d+=min(abs(float(persona.get("vek",50))-float(row.get("vek",50)))/20,2)
    except:pass
    for k,w in (("vzdelani",1.0),("kraj",.8),("trida",.8)):
        if persona.get(k) and row.get(k) and str(persona[k])!=str(row[k]): d+=w
    return d

class ResponseBank:
    def __init__(self,registry_path:str|Path="data/ingest_registry.sqlite"):
        self.registry=Registry(registry_path); self.cx=self.registry.cx
    def close(self):self.registry.close()
    def __enter__(self):return self
    def __exit__(self,*_):self.close()

    def upsert_question(self,text:str,*,topic:str="default",validity_years:int|None=None,scale:str="")->int:
        sid=stable_question_id(text,topic); validity=validity_years or DEFAULT_VALIDITY.get(topic,DEFAULT_VALIDITY["default"])
        self.cx.execute("INSERT OR IGNORE INTO otazky(stable_id,znene,tema,platnost_let,skala,created_at) VALUES(?,?,?,?,?,?)",
                        (sid,text,topic,int(validity),scale,time.strftime("%Y-%m-%dT%H:%M:%S")))
        self.cx.commit(); return int(self.cx.execute("SELECT id FROM otazky WHERE stable_id=?",(sid,)).fetchone()[0])

    def add_responses(self,df:pd.DataFrame,*,source_id:str,question_text:str,answer_text_col:str,
                      answer_code_col:str|None=None,respondent_id_col:str="respondent_id",year:int,
                      topic:str="default",validity_years:int|None=None,holdout_col:str|None=None)->int:
        qid=self.upsert_question(question_text,topic=topic,validity_years=validity_years)
        n=0
        for ix,r in df.iterrows():
            rid=str(r.get(respondent_id_col,ix))
            self.cx.execute("INSERT OR REPLACE INTO respondenti_banky(source_id,respondent_id,pohlavi,vek,vzdelani,kraj,trida) VALUES(?,?,?,?,?,?,?)",
                            (source_id,rid,r.get("pohlavi"),r.get("vek"),r.get("vzdelani"),r.get("kraj"),r.get("trida_spolecenska") or r.get("trida")))
            txt=r.get(answer_text_col)
            if pd.isna(txt):continue
            code=None if not answer_code_col or pd.isna(r.get(answer_code_col)) else str(r.get(answer_code_col))
            hold=int(bool(r.get(holdout_col))) if holdout_col else 0
            self.cx.execute("INSERT INTO odpovedi(source_id,respondent_id,otazka_id,odpoved_text,odpoved_kod,rok,v_holdoutu) VALUES(?,?,?,?,?,?,?)",
                            (source_id,rid,qid,str(txt),code,int(year),hold)); n+=1
        self.cx.commit(); return n

    def _similar_questions(self,text:str,topic:str|None,min_similarity:float,current_year:int)->list[tuple[int,float,dict[str,Any]]]:
        rows=[dict(r) for r in self.cx.execute("SELECT * FROM otazky")]
        if not rows:return []
        corpus=[text]+[r["znene"] for r in rows]
        X=TfidfVectorizer(analyzer="char_wb",ngram_range=(3,5),min_df=1).fit_transform(corpus)
        sims=cosine_similarity(X[0],X[1:]).ravel()
        out=[]
        for r,s in zip(rows,sims):
            if s<min_similarity:continue
            if topic and r["tema"] not in {topic,"default"} and s<max(.45,min_similarity):continue
            out.append((r["id"],float(s),r))
        return sorted(out,key=lambda z:-z[1])

    def find_anchors(self,persona:dict[str,Any],question_text:str,*,k:int=8,topic:str|None=None,
                     current_year:int=2026,min_similarity:float=.18)->list[dict[str,Any]]:
        qs=self._similar_questions(question_text,topic,min_similarity,current_year)
        cand=[]
        for qid,sim,q in qs[:8]:
            rows=self.cx.execute("""SELECT a.*,r.pohlavi,r.vek,r.vzdelani,r.kraj,r.trida
                FROM odpovedi a JOIN respondenti_banky r ON a.source_id=r.source_id AND a.respondent_id=r.respondent_id
                WHERE a.otazka_id=? AND a.v_holdoutu=0 AND a.rok + ? >= ?""",
                (qid,int(q["platnost_let"]),int(current_year))).fetchall()
            for rr in rows:
                z=dict(rr); dist=_profile_distance(persona,z)
                score=sim/(1.0+dist)
                cand.append((score,sim,dist,q,z))
        cand.sort(key=lambda x:-x[0]); picked=[]; seen=set()
        for score,sim,dist,q,z in cand:
            key=(z["source_id"],z["respondent_id"],z["odpoved_text"])
            if key in seen:continue
            seen.add(key)
            picked.append({"source_id":z["source_id"],"year":z["rok"],"question":q["znene"],
                           "question_similarity":round(sim,4),"profile_distance":round(dist,3),
                           "answer_text":z["odpoved_text"],"answer_code":z["odpoved_kod"],
                           "profile":{"pohlavi":z["pohlavi"],"vek":z["vek"],"vzdelani":z["vzdelani"],"kraj":z["kraj"],"trida":z["trida"]}})
            if len(picked)>=k:break
        return picked


def format_anchor_block(anchors:list[dict[str,Any]])->str:
    if not anchors:return ""
    lines=["KONTEXT Z REÁLNÝCH ODPOVĚDÍ PODOBNÝCH LIDÍ:",
           "Níže jsou cizí historické odpovědi. Nekopíruj je. Odpověz sám za sebe; používej je pouze jako jazykovou a zkušenostní kotvu."]
    for a in anchors:
        p=a.get("profile",{})
        prof=", ".join(str(x) for x in [p.get("pohlavi"),p.get("vek"),p.get("vzdelani"),p.get("kraj")] if x not in (None,""))
        lines.append(f"— [{a.get('source_id')}, {a.get('year')}] {prof}: na otázku „{a.get('question')}“ odpověděl(a): „{a.get('answer_text')}“")
    return "\n".join(lines)
