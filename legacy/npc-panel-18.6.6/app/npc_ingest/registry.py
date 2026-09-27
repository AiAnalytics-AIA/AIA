from __future__ import annotations
import sqlite3, json, hashlib, time
from pathlib import Path
from typing import Any

SCHEMA="""
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS uploady(
 id INTEGER PRIMARY KEY AUTOINCREMENT, hash TEXT UNIQUE, soubor TEXT, prijato TEXT,
 trat TEXT, popis TEXT, n_radku INTEGER, n_sloupcu INTEGER, skore_pravosti REAL,
 rozhodnuti TEXT, duvod TEXT, verze_panelu TEXT, report TEXT);
CREATE TABLE IF NOT EXISTS verze(
 verze TEXT PRIMARY KEY, vytvoreno TEXT, rodic TEXT, upload_id INTEGER, n_radku INTEGER,
 cesta TEXT, sha256 TEXT, hash_cilu TEXT, changelog TEXT, aktivni INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS benchmarky(
 id TEXT PRIMARY KEY, nazev TEXT, zdroj_hash TEXT, otazka TEXT, kategorie_json TEXT,
 filtr_json TEXT, skutecnost_json TEXT, holdout_ids_json TEXT, vlozeno TEXT);
CREATE TABLE IF NOT EXISTS regrese(
 id INTEGER PRIMARY KEY AUTOINCREMENT, verze TEXT, benchmark TEXT, varianta TEXT,
 tvd REAL, tvd_dolni REAL, tvd_horni REAL, tau_poradi REAL, rozptyl REAL,
 naklad_kc REAL, spusteno TEXT);
CREATE TABLE IF NOT EXISTS slovnik(
 promenna TEXT, varianta_vstup TEXT, kanonicka_hodnota TEXT, potvrzeno_kdy TEXT,
 PRIMARY KEY(promnena,varianta_vstup));
CREATE TABLE IF NOT EXISTS holdout_respondenti(
 source_id TEXT, respondent_hash TEXT, created_at TEXT,
 PRIMARY KEY(source_id,respondent_hash));
CREATE TABLE IF NOT EXISTS overrides(
 id INTEGER PRIMARY KEY AUTOINCREMENT, upload_hash TEXT, actor TEXT, reason TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS otazky(
 id INTEGER PRIMARY KEY AUTOINCREMENT, stable_id TEXT UNIQUE, znene TEXT, tema TEXT,
 platnost_let INTEGER, skala TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS respondenti_banky(
 source_id TEXT, respondent_id TEXT, pohlavi TEXT, vek REAL, vzdelani TEXT,
 kraj TEXT, trida TEXT, PRIMARY KEY(source_id,respondent_id));
CREATE TABLE IF NOT EXISTS odpovedi(
 id INTEGER PRIMARY KEY AUTOINCREMENT, source_id TEXT, respondent_id TEXT, otazka_id INTEGER,
 odpoved_text TEXT, odpoved_kod TEXT, rok INTEGER, v_holdoutu INTEGER DEFAULT 0,
 FOREIGN KEY(otazka_id) REFERENCES otazky(id));
CREATE INDEX IF NOT EXISTS idx_odp_q ON odpovedi(otazka_id);
CREATE INDEX IF NOT EXISTS idx_odp_resp ON odpovedi(source_id,respondent_id);
"""
# fix schema typo from legacy drafts safely at init (SQLite would otherwise fail on PK name)
SCHEMA=SCHEMA.replace("PRIMARY KEY(promnena,varianta_vstup)","PRIMARY KEY(promenna,varianta_vstup)")


def sha256_file(path: str|Path) -> str:
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for ch in iter(lambda:f.read(1024*1024),b""): h.update(ch)
    return h.hexdigest()


class Registry:
    def __init__(self, path: str|Path="data/ingest_registry.sqlite"):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        self.cx=sqlite3.connect(self.path)
        self.cx.row_factory=sqlite3.Row
        self.cx.executescript(SCHEMA); self.cx.commit()

    def close(self): self.cx.close()
    def __enter__(self): return self
    def __exit__(self,*_): self.close()

    def record_upload(self, **kw) -> int:
        cols=["hash","soubor","prijato","trat","popis","n_radku","n_sloupcu","skore_pravosti","rozhodnuti","duvod","verze_panelu","report"]
        vals=[kw.get(c) for c in cols]; vals[2]=vals[2] or time.strftime("%Y-%m-%dT%H:%M:%S")
        q=f"INSERT OR REPLACE INTO uploady({','.join(cols)}) VALUES({','.join('?' for _ in cols)})"
        cur=self.cx.execute(q,vals); self.cx.commit(); return int(cur.lastrowid or 0)

    def register_version(self, verze:str,cesta:str|Path,*,rodic=None,upload_id=None,hash_cilu="",changelog="",activate=True,n_radku=None):
        p=Path(cesta); sha=sha256_file(p)
        if activate: self.cx.execute("UPDATE verze SET aktivni=0")
        self.cx.execute("INSERT OR REPLACE INTO verze(verze,vytvoreno,rodic,upload_id,n_radku,cesta,sha256,hash_cilu,changelog,aktivni) VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (verze,time.strftime("%Y-%m-%dT%H:%M:%S"),rodic,upload_id,n_radku,str(p.resolve()),sha,hash_cilu,changelog,1 if activate else 0))
        self.cx.commit(); return sha

    def active_version(self) -> dict[str,Any]|None:
        r=self.cx.execute("SELECT * FROM verze WHERE aktivni=1 ORDER BY vytvoreno DESC LIMIT 1").fetchone()
        return dict(r) if r else None

    def version_for_path(self, path: str|Path) -> dict[str,Any]|None:
        """Return registry metadata for an exact immutable panel snapshot path."""
        try:
            target=str(Path(path).resolve())
        except Exception:
            target=str(path)
        rows=self.cx.execute("SELECT * FROM verze ORDER BY vytvoreno DESC").fetchall()
        for row in rows:
            d=dict(row)
            try:
                candidate=str(Path(d["cesta"]).resolve())
            except Exception:
                candidate=str(d["cesta"])
            if candidate==target:
                return d
        return None

    def activate(self,verze:str):
        if not self.cx.execute("SELECT 1 FROM verze WHERE verze=?",(verze,)).fetchone(): raise KeyError(verze)
        self.cx.execute("UPDATE verze SET aktivni=0"); self.cx.execute("UPDATE verze SET aktivni=1 WHERE verze=?",(verze,)); self.cx.commit()


    def record_regression(self, *, verze:str, benchmark:str, varianta:str, tvd:float|None=None,
                          tvd_dolni:float|None=None, tvd_horni:float|None=None,
                          tau_poradi:float|None=None, rozptyl:float|None=None, naklad_kc:float|None=None):
        self.cx.execute("INSERT INTO regrese(verze,benchmark,varianta,tvd,tvd_dolni,tvd_horni,tau_poradi,rozptyl,naklad_kc,spusteno) VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (verze,benchmark,varianta,tvd,tvd_dolni,tvd_horni,tau_poradi,rozptyl,naklad_kc,time.strftime("%Y-%m-%dT%H:%M:%S")))
        self.cx.commit()

    def regression_history(self, limit:int=200)->list[dict[str,Any]]:
        rows=self.cx.execute("SELECT * FROM regrese ORDER BY id DESC LIMIT ?",(int(limit),)).fetchall()
        return [dict(r) for r in rows]

    def register_holdout_hashes(self, source_id:str, hashes:list[str]):
        now=time.strftime("%Y-%m-%dT%H:%M:%S")
        self.cx.executemany("INSERT OR IGNORE INTO holdout_respondenti(source_id,respondent_hash,created_at) VALUES(?,?,?)",[(source_id,h,now) for h in hashes]); self.cx.commit()

    def holdout_hashes(self,source_id:str|None=None)->set[str]:
        if source_id: rows=self.cx.execute("SELECT respondent_hash FROM holdout_respondenti WHERE source_id=?",(source_id,))
        else: rows=self.cx.execute("SELECT respondent_hash FROM holdout_respondenti")
        return {r[0] for r in rows}

    def override(self,upload_hash:str,actor:str,reason:str):
        self.cx.execute("INSERT INTO overrides(upload_hash,actor,reason,created_at) VALUES(?,?,?,?)",(upload_hash,actor,reason,time.strftime("%Y-%m-%dT%H:%M:%S"))); self.cx.commit()
