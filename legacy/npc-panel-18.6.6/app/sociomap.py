"""Auditovatelná preference mapa a segmentace pro modul VÝZKUM.

Primární kontrakt specifikuje row-conditional multidimensional unfolding přes R
`smacof::unfolding`. Runtime proto umí dvě cesty:
- `method="r_smacof"`: použije Rscript + balíček smacof, pokud je dostupný;
- `method="python"`: vlastní weighted unfolding nad pouze pozorovanými buňkami.

Python fallback NENÍ vydáván za implementaci R/smacof. Je to deterministická,
auditovatelná aproximace pro prostředí bez R. Metadata vždy nesou použitou metodu.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
import json, math, shutil, subprocess, tempfile
import numpy as np
import pandas as pd

from study_validation import ipsatize, object_columns


@dataclass
class MapResult:
    method: str
    respondent_xy: np.ndarray
    object_xy: np.ndarray
    object_names: list[str]
    stress_1: float
    iterations: int
    metadata: dict[str, Any]

    def serializable(self) -> dict[str, Any]:
        return {"method": self.method, "respondent_xy": self.respondent_xy.tolist(),
                "object_xy": self.object_xy.tolist(), "object_names": self.object_names,
                "stress_1": self.stress_1, "iterations": self.iterations,
                "metadata": self.metadata}


def _targets_from_ratings(x: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Observed-cell target dissimilarities after ipsatization, no matrix imputation."""
    ip = ipsatize(x, list(x.columns)).to_numpy(float)
    rr, cc = np.where(np.isfinite(ip))
    vals = ip[rr, cc]
    # Per respondent robust range; preferred objects -> smaller dissimilarity.
    lo = np.nanmin(ip, axis=1); hi = np.nanmax(ip, axis=1)
    rng = np.where(np.isfinite(hi - lo) & ((hi - lo) > 1e-9), hi - lo, 1.0)
    d = (hi[rr] - vals) / rng[rr]
    d = .05 + .95 * np.clip(d, 0, 1)
    return rr.astype(int), cc.astype(int), d.astype(float)


def fit_python_unfolding(df: pd.DataFrame, *, seed: int = 20260814,
                         max_iter: int = 350, learning_rate: float = .04) -> MapResult:
    cols = object_columns(df)
    if len(cols) < 3:
        raise ValueError("Pro mapu jsou potřeba alespoň 3 objektové sloupce.")
    x = df[cols].apply(pd.to_numeric, errors="coerce")
    rr, cc, target = _targets_from_ratings(x)
    if len(target) < max(30, 3 * len(cols)):
        raise ValueError("Příliš málo pozorovaných respondent×objekt hodnocení.")
    n, m = len(x), len(cols)
    rng = np.random.default_rng(seed)

    # SVD initialization uses centered missing=0 only for starting coordinates;
    # the objective below uses exclusively observed cells.
    ip = ipsatize(x, cols).to_numpy(float)
    a = np.where(np.isfinite(ip), ip, 0.0)
    a -= a.mean(axis=0, keepdims=True)
    try:
        u, s, vt = np.linalg.svd(a, full_matrices=False)
        U = u[:, :2] * np.maximum(s[:2], 1e-3)
        V = vt[:2, :].T * np.maximum(s[:2], 1e-3)
        scale0 = np.std(np.vstack([U, V])) or 1.0
        U = U / scale0; V = V / scale0
    except Exception:
        U = rng.normal(0, .2, size=(n, 2)); V = rng.normal(0, .5, size=(m, 2))

    # Adam-like full observed-cell optimization.
    mu = np.zeros_like(U); mv = np.zeros_like(V)
    vu = np.zeros_like(U); vv = np.zeros_like(V)
    b1, b2, eps = .9, .999, 1e-8
    last = None; best = (float("inf"), U.copy(), V.copy(), 0)
    deg_u = np.bincount(rr, minlength=n).reshape(-1, 1).clip(min=1)
    deg_v = np.bincount(cc, minlength=m).reshape(-1, 1).clip(min=1)
    denom = float(np.sum(target * target)) or 1.0

    for it in range(1, max_iter + 1):
        diff = U[rr] - V[cc]
        dist = np.sqrt(np.sum(diff * diff, axis=1) + 1e-9)
        # Optimal global distance scale for current coordinates.
        scale = float(np.dot(dist, target) / (np.dot(dist, dist) + 1e-12))
        err = scale * dist - target
        stress = math.sqrt(float(np.sum(err * err)) / denom)
        if stress < best[0]: best = (stress, U.copy(), V.copy(), it)
        if last is not None and abs(last - stress) < 1e-7:
            break
        last = stress
        coef = (2.0 * scale * err / dist)[:, None]
        gu = np.zeros_like(U); gv = np.zeros_like(V)
        np.add.at(gu, rr, coef * diff)
        np.add.at(gv, cc, -coef * diff)
        gu /= deg_u; gv /= deg_v
        mu = b1 * mu + (1-b1) * gu; mv = b1 * mv + (1-b1) * gv
        vu = b2 * vu + (1-b2) * (gu*gu); vv = b2 * vv + (1-b2) * (gv*gv)
        muh = mu/(1-b1**it); mvh = mv/(1-b1**it)
        vuh = vu/(1-b2**it); vvh = vv/(1-b2**it)
        lr = learning_rate * (0.35 + 0.65 * (1 - it/max_iter))
        U -= lr * muh/(np.sqrt(vuh)+eps); V -= lr * mvh/(np.sqrt(vvh)+eps)
        center = np.vstack([U, V]).mean(axis=0)
        U -= center; V -= center

    stress, U, V, bit = best
    return MapResult("python_weighted_unfolding", U, V, cols, float(stress), int(bit),
                     {"missing_policy": "observed_cells_only", "ipsatized": True,
                      "target": "row_relative_dissimilarity", "exact_r_smacof": False})


def fit_r_smacof(df: pd.DataFrame, *, seed: int = 20260814) -> MapResult:
    if not shutil.which("Rscript"):
        raise RuntimeError("Rscript není dostupný.")
    cols = object_columns(df)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        inp, out = td/"ratings.csv", td/"out.json"
        df[cols].to_csv(inp, index=False)
        script = td/"run.R"
        script.write_text(r'''
args <- commandArgs(trailingOnly=TRUE)
suppressPackageStartupMessages(library(smacof))
suppressPackageStartupMessages(library(jsonlite))
x <- as.matrix(read.csv(args[1], check.names=FALSE))
# Ipsatization; NAs stay NA.
rmn <- rowMeans(x, na.rm=TRUE)
x <- x - rmn
# smacof unfolding expects proximities; high preference -> low dissimilarity.
rng <- apply(x, 1, function(z) max(z,na.rm=TRUE)-min(z,na.rm=TRUE))
rng[!is.finite(rng) | rng==0] <- 1
mx <- apply(x, 1, max, na.rm=TRUE)
d <- (mx - x) / rng
set.seed(as.integer(args[3]))
fit <- unfolding(d, ndim=2, conditionality="row", itmax=1000)
obj <- list(stress=fit$stress, conf.row=unname(fit$conf.row),
            conf.col=unname(fit$conf.col), iter=fit$it)
write(toJSON(obj, digits=10, auto_unbox=TRUE), args[2])
''', encoding="utf-8")
        p = subprocess.run(["Rscript", str(script), str(inp), str(out), str(seed)],
                           capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError("R smacof selhal: " + (p.stderr or p.stdout)[-1200:])
        obj = json.loads(out.read_text(encoding="utf-8"))
        return MapResult("r_smacof_unfolding_row", np.asarray(obj["conf.row"], float),
                         np.asarray(obj["conf.col"], float), cols, float(obj["stress"]),
                         int(obj.get("iter") or 0), {"exact_r_smacof": True, "ipsatized": True})


def fit_unfolding(df: pd.DataFrame, *, method: str = "auto", seed: int = 20260814) -> MapResult:
    if method in {"auto", "r_smacof"} and shutil.which("Rscript"):
        try:
            return fit_r_smacof(df, seed=seed)
        except Exception:
            if method == "r_smacof": raise
    return fit_python_unfolding(df, seed=seed)


def fit_segments(df: pd.DataFrame, *, seed: int = 20260814, k_min: int = 2,
                 k_max: int = 8, bootstrap: int = 20) -> dict[str, Any]:
    from sklearn.mixture import GaussianMixture
    from sklearn.metrics import adjusted_rand_score
    cols = object_columns(df)
    xdf = ipsatize(df, cols)
    X = np.where(np.isfinite(xdf.to_numpy(float)), xdf.to_numpy(float), 0.0)
    if len(X) < 30:
        raise ValueError("Segmentace potřebuje alespoň 30 respondentů.")
    k_max = min(k_max, max(k_min, len(X)//20), len(cols))
    fits = []
    for k in range(k_min, k_max+1):
        g = GaussianMixture(k, covariance_type="full", random_state=seed, reg_covar=1e-5, n_init=3)
        g.fit(X); fits.append((g.bic(X), g))
    bic, model = min(fits, key=lambda z: z[0])
    labels = model.predict(X); probs = model.predict_proba(X)
    if model.n_components > 1:
        h = -np.sum(np.clip(probs, 1e-12, 1) * np.log(np.clip(probs, 1e-12, 1)), axis=1)
        entropy = float(1.0 - np.mean(h)/np.log(model.n_components))
    else: entropy = 0.0
    rng = np.random.default_rng(seed + 11)
    aris = []
    for b in range(max(0, bootstrap)):
        ix = rng.integers(0, len(X), len(X))
        gm = GaussianMixture(model.n_components, covariance_type="full", random_state=seed+b+1,
                             reg_covar=1e-5, n_init=1)
        try:
            gm.fit(X[ix]); pred = gm.predict(X); aris.append(adjusted_rand_score(labels, pred))
        except Exception:
            continue
    return {"labels": labels, "probabilities": probs, "k": model.n_components,
            "bic": float(bic), "entropy": round(entropy, 4),
            "bootstrap_ari": round(float(np.median(aris)), 4) if aris else None,
            "bootstrap_ari_values": aris}


def profile_segments(df: pd.DataFrame, labels: np.ndarray, *, top_n: int = 12) -> dict[str, Any]:
    chars = [c for c in df if c.startswith(("dem_", "att_", "beh_", "bin_"))]
    out: dict[str, Any] = {}
    for seg in sorted(set(map(int, labels))):
        mask = labels == seg; prof = []
        for c in chars:
            s = pd.to_numeric(df[c], errors="coerce")
            a, b = s[mask].dropna(), s[~mask].dropna()
            if len(a) < 5 or len(b) < 5: continue
            sd = float(s.std()) or 1.0
            diff = (float(a.mean()) - float(b.mean())) / sd
            prof.append({"variable": c, "segment_mean": float(a.mean()),
                         "rest_mean": float(b.mean()), "standardized_diff": diff})
        prof.sort(key=lambda z: -abs(z["standardized_diff"]))
        out[str(seg+1)] = {"n": int(mask.sum()), "share": float(mask.mean()), "top": prof[:top_n]}
    return out


def whitespace_opportunities(map_result: MapResult, *, top_n: int = 5) -> list[dict[str, float]]:
    """Heuristic: dense respondent zones relatively far from all objects."""
    U, V = map_result.respondent_xy, map_result.object_xy
    if not len(U): return []
    xmin, ymin = U.min(axis=0); xmax, ymax = U.max(axis=0)
    gx = np.linspace(xmin, xmax, 35); gy = np.linspace(ymin, ymax, 35)
    bw = max(np.std(U[:,0]), np.std(U[:,1]), .1) * .25
    cand=[]
    for x in gx:
        for y in gy:
            d2 = np.sum((U-np.array([x,y]))**2, axis=1)
            dens = float(np.exp(-d2/(2*bw*bw)).sum())
            objdist = float(np.sqrt(np.sum((V-np.array([x,y]))**2, axis=1)).min())
            cand.append((dens*objdist, dens, objdist, x, y))
    cand.sort(reverse=True)
    chosen=[]
    for score,dens,od,x,y in cand:
        if all((x-z["x"])**2+(y-z["y"])**2 > (bw*.8)**2 for z in chosen):
            chosen.append({"x":float(x),"y":float(y),"score":float(score),
                           "density":float(dens),"nearest_object_distance":float(od)})
        if len(chosen)>=top_n: break
    return chosen


def export_map_html(path: str | Path, map_result: MapResult, df: pd.DataFrame,
                    segment_result: dict[str, Any], profiles: dict[str, Any]) -> Path:
    """Standalone preference map with auditable drill-down and respondent KDE.

    Objects and respondents share the unfolding space. Profiling variables are never
    used to fit that space; they are attached only after the solution for drill-down.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    U, V = map_result.respondent_xy, map_result.object_xy
    labels = np.asarray(segment_result["labels"], int)
    chars = [c for c in df.columns if c.startswith(("dem_", "att_", "beh_", "bin_"))]

    def _safe(v):
        if pd.isna(v):
            return None
        if isinstance(v, np.integer):
            return int(v)
        if isinstance(v, np.floating):
            return float(v)
        return v.item() if hasattr(v, "item") else v

    obj_stats = []
    for j, c in enumerate(map_result.object_names):
        ss = pd.to_numeric(df[c], errors="coerce")
        fam = c.replace("obj_", "fam_", 1)
        prof = []
        valid = ss.notna()
        if valid.sum() >= 20:
            cut = ss[valid].quantile(.75)
            hi, lo = valid & (ss >= cut), valid & (ss < cut)
            for ch in chars:
                z = pd.to_numeric(df[ch], errors="coerce")
                zh, zl = z[hi].dropna(), z[lo].dropna()
                if len(zh) >= 5 and len(zl) >= 5:
                    sd = float(z[valid].std()) or 1.0
                    diff = (float(zh.mean()) - float(zl.mean())) / sd
                    prof.append({"variable": ch, "standardized_diff": float(diff),
                                 "top_mean": float(zh.mean()), "rest_mean": float(zl.mean())})
            prof.sort(key=lambda x: -abs(x["standardized_diff"]))
        d = np.sqrt(np.sum((V - V[j]) ** 2, axis=1))
        order = np.argsort(d)
        nearest = [map_result.object_names[int(k)] for k in order if int(k) != j][:3]
        farthest = [map_result.object_names[int(k)] for k in order[::-1] if int(k) != j][:3]
        obj_stats.append({
            "name": c, "x": float(V[j, 0]), "y": float(V[j, 1]),
            "mean": float(ss.mean()) if ss.notna().any() else None,
            "familiarity": float(pd.to_numeric(df[fam], errors="coerce").mean()) if fam in df else None,
            "top_profile": prof[:8], "nearest": nearest, "farthest": farthest,
        })

    respondents = []
    for i in range(len(U)):
        row = df.iloc[i]
        respondents.append({
            "x": float(U[i, 0]), "y": float(U[i, 1]), "segment": int(labels[i]) + 1,
            "id": int(row["respondent_id"]) if "respondent_id" in df and pd.notna(row["respondent_id"]) else i + 1,
            "profile": {c: _safe(row[c]) for c in chars if c in row.index},
            "ratings": {c: _safe(row[c]) for c in map_result.object_names if c in row.index},
        })

    # Display-only KDE over respondent coordinates. It never feeds back into fitting.
    density = []
    if len(U) >= 10 and np.ptp(U[:, 0]) > 0 and np.ptp(U[:, 1]) > 0:
        try:
            from scipy.stats import gaussian_kde
            xmin, ymin = U.min(axis=0)
            xmax, ymax = U.max(axis=0)
            gx, gy = np.linspace(xmin, xmax, 30), np.linspace(ymin, ymax, 30)
            xx, yy = np.meshgrid(gx, gy)
            grid = np.vstack([xx.ravel(), yy.ravel()])
            zz = gaussian_kde(U.T)(grid)
            mx = float(zz.max() or 1.0)
            density = [{"x": float(x), "y": float(y), "z": float(z / mx)}
                       for x, y, z in zip(grid[0], grid[1], zz)]
        except Exception:
            density = []

    payload = {
        "points": respondents, "objects": obj_stats, "profiles": profiles,
        "stress": map_result.stress_1, "method": map_result.method,
        "opportunities": whitespace_opportunities(map_result), "density": density,
        "segments": sorted(set(int(x) + 1 for x in labels)),
    }
    html = r'''<!doctype html><meta charset="utf-8"><title>NPC Panel — preference map</title>
<style>
body{font-family:system-ui;margin:0;background:#f7f7f8;color:#111}.wrap{display:grid;grid-template-columns:1fr 360px;height:100vh}
#map{width:100%;height:100%;background:white}.side{padding:18px;overflow:auto;border-left:1px solid #ddd}h1{font-size:18px}.muted{color:#666;font-size:12px}.card{background:white;border:1px solid #ddd;border-radius:10px;padding:12px;margin:10px 0}
button{margin:3px;padding:5px 8px}.kv{display:grid;grid-template-columns:1fr 1fr;gap:3px 8px;font-size:12px}.scroll{max-height:300px;overflow:auto}
</style>
<div class="wrap"><svg id="map"></svg><div class="side"><h1>Preference map</h1><div id="meta" class="muted"></div>
<div class="card"><b>Segmenty</b><div id="segments"></div></div><div id="detail" class="card">Klikni na objekt, respondenta nebo segment.</div>
<div class="card"><b>White-space candidates</b><div id="opp"></div></div></div></div>
<script>
const D=__DATA__, svg=document.getElementById('map'), NS='http://www.w3.org/2000/svg';
function el(n,a){let e=document.createElementNS(NS,n);for(const k in a)e.setAttribute(k,a[k]);return e}
function esc(x){return String(x??'—').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))}
function rows(obj){return '<div class="kv">'+Object.entries(obj||{}).map(([k,v])=>`<div>${esc(k)}</div><div>${esc(v)}</div>`).join('')+'</div>'}
function showSeg(s){const p=D.profiles[String(s)];document.getElementById('detail').innerHTML=`<b>Segment ${s}</b><br>n=${p?.n??'—'}; ${(100*(p?.share??0)).toFixed(1)} %<hr>`+(p?.top??[]).map(x=>`${esc(x.variable)}: Δ=${x.standardized_diff.toFixed(2)}`).join('<br>')}
function showResp(p){document.getElementById('detail').innerHTML=`<b>Respondent ${p.id}</b> · segment ${p.segment}<hr><b>Charakteristiky</b><div class="scroll">${rows(p.profile)}</div><hr><b>Hodnocení objektů</b><div class="scroll">${rows(p.ratings)}</div>`}
function showObj(o){const top=(o.top_profile||[]).map(x=>`${esc(x.variable)}: Δ=${x.standardized_diff.toFixed(2)}`).join('<br>')||'—';document.getElementById('detail').innerHTML=`<b>${esc(o.name)}</b><br>průměr: ${o.mean==null?'—':o.mean.toFixed(2)}<br>familiarita: ${o.familiarity==null?'—':(100*o.familiarity).toFixed(1)+' %'}<hr><b>Profil top hodnotitelů</b><br>${top}<hr><b>Nejbližší objekty</b><br>${(o.nearest||[]).map(esc).join(', ')}<hr><b>Nejvzdálenější objekty</b><br>${(o.farthest||[]).map(esc).join(', ')}`}
function draw(){const W=svg.clientWidth,H=svg.clientHeight,pad=45;const xs=D.points.map(p=>p.x).concat(D.objects.map(o=>o.x)),ys=D.points.map(p=>p.y).concat(D.objects.map(o=>o.y));const mnx=Math.min(...xs),mxx=Math.max(...xs),mny=Math.min(...ys),mxy=Math.max(...ys);const X=x=>pad+(x-mnx)/(mxx-mnx||1)*(W-2*pad),Y=y=>H-pad-(y-mny)/(mxy-mny||1)*(H-2*pad);svg.innerHTML='';
D.density.forEach(p=>{let r=el('rect',{x:X(p.x)-(W/30)/2,y:Y(p.y)-(H/30)/2,width:Math.max(4,W/30+1),height:Math.max(4,H/30+1),fill:'#2563eb',opacity:(.02+.16*p.z).toFixed(3)});svg.appendChild(r)});
D.points.forEach(p=>{let c=el('circle',{cx:X(p.x),cy:Y(p.y),r:2.5,fill:`hsl(${(p.segment*67)%360} 58% 46%)`,opacity:.35});c.style.cursor='pointer';c.onclick=()=>showResp(p);svg.appendChild(c)});
D.opportunities.forEach((p,i)=>{let c=el('circle',{cx:X(p.x),cy:Y(p.y),r:10,fill:'none',stroke:'#555','stroke-dasharray':'3 3'});c.style.cursor='pointer';c.onclick=()=>document.getElementById('detail').innerHTML=`<b>White-space #${i+1}</b><br>density×distance=${p.score.toFixed(3)}<br>density=${p.density.toFixed(3)}<br>nearest object distance=${p.nearest_object_distance.toFixed(3)}`;svg.appendChild(c)});
D.objects.forEach(o=>{let g=el('g',{}),c=el('circle',{cx:X(o.x),cy:Y(o.y),r:9,fill:'#111'}),t=el('text',{x:X(o.x)+12,y:Y(o.y)+4,'font-size':12,'font-weight':'700'});t.textContent=o.name.replace('obj_','');g.append(c,t);g.style.cursor='pointer';g.onclick=()=>showObj(o);svg.appendChild(g)});}
document.getElementById('segments').innerHTML=D.segments.map(s=>`<button onclick="showSeg(${s})">${s}</button>`).join('');
document.getElementById('meta').textContent=`${D.method}; stress-1=${D.stress.toFixed(3)}. KDE je pouze vizuální vrstva nad hotovým unfolding řešením.`;
document.getElementById('opp').innerHTML=D.opportunities.map((x,i)=>`#${i+1}: ${x.score.toFixed(2)}`).join('<br>');window.onresize=draw;draw();
</script>'''.replace('__DATA__', json.dumps(payload, ensure_ascii=False, default=str))
    path.write_text(html, encoding="utf-8")
    return path

# ---------------------------------------------------------------------------
# 17.3 relational landscape: object×object matrix + score height
# ---------------------------------------------------------------------------

@dataclass
class RelationalMapResult:
    object_names: list[str]
    relation_matrix: np.ndarray
    target_distance_matrix: np.ndarray
    object_xy: np.ndarray
    object_scores: np.ndarray
    object_height: np.ndarray
    stress_1: float
    iterations: int
    relation_source: str
    metadata: dict[str, Any]

    def serializable(self)->dict[str,Any]:
        return {'object_names':self.object_names,'relation_matrix':self.relation_matrix.tolist(),
                'target_distance_matrix':self.target_distance_matrix.tolist(),'object_xy':self.object_xy.tolist(),
                'object_scores':self.object_scores.tolist(),'object_height':self.object_height.tolist(),
                'stress_1':self.stress_1,'iterations':self.iterations,'relation_source':self.relation_source,
                'metadata':self.metadata}


def _weighted_mean(x:np.ndarray,w:np.ndarray)->float:
    ok=np.isfinite(x)&np.isfinite(w)&(w>0)
    return float(np.average(x[ok],weights=w[ok])) if ok.any() else float('nan')


def derive_relation_matrix(data:pd.DataFrame, object_names:list[str], *, weights_col:str='vaha')->tuple[np.ndarray,np.ndarray]:
    """Derive object×object relations from common respondent ratings.

    Contract used by the client-facing sociomap:
    * every included object is related to every other included object;
    * diagonal is exactly 0 (an object has no relation to itself);
    * off-diagonal values are on 1–10;
    * this *derived* path is symmetric because ordinary correlation is symmetric;
    * an explicitly measured/user-supplied directional matrix may be asymmetric and
      its two directions are preserved by :func:`fit_relational_landscape`.

    The 1–10 transformation is a signed-correlation relationship scale:
      corr=-1 -> 1, corr=0 -> 5.5, corr=+1 -> 10.
    Thus stronger positive co-movement means closer spatial position. Negative
    association becomes a low relation score rather than being converted to
    absolute correlation.
    """
    X=data[object_names].apply(pd.to_numeric,errors='coerce').to_numpy(float)
    w=pd.to_numeric(data.get(weights_col,pd.Series(1.0,index=data.index)),errors='coerce').fillna(1.0).to_numpy(float)
    m=len(object_names); R=np.zeros((m,m),float); scores=np.full(m,np.nan,float)
    for i in range(m): scores[i]=_weighted_mean(X[:,i],w)
    for i in range(m):
        for j in range(i+1,m):
            a,b=X[:,i],X[:,j];ok=np.isfinite(a)&np.isfinite(b)&np.isfinite(w)&(w>0)
            if ok.sum()<5:
                rel=5.5
            else:
                ww=w[ok];aa=a[ok];bb=b[ok];sw=float(ww.sum()) or 1.0
                ma=float(np.sum(ww*aa)/sw);mb=float(np.sum(ww*bb)/sw)
                va=float(np.sum(ww*(aa-ma)**2)/sw);vb=float(np.sum(ww*(bb-mb)**2)/sw)
                cov=float(np.sum(ww*(aa-ma)*(bb-mb))/sw)
                corr=cov/max((va*vb)**0.5,1e-12);corr=max(-1.0,min(1.0,corr))
                rel=1.0+9.0*((corr+1.0)/2.0)
            R[i,j]=R[j,i]=float(np.clip(rel,1.0,10.0))
    np.fill_diagonal(R,0.0)
    return R,scores


def _coerce_relation_scale_1_10(matrix:np.ndarray)->np.ndarray:
    """Preserve direction while coercing legacy matrices to the 1–10 contract."""
    R=np.asarray(matrix,float).copy()
    if R.ndim!=2 or R.shape[0]!=R.shape[1]: raise ValueError('Relační matice musí být čtvercová.')
    if R.shape[0]<3: raise ValueError('Relační mapa potřebuje alespoň 3 objekty.')
    R=np.nan_to_num(R,nan=5.5,posinf=10.0,neginf=1.0)
    mask=~np.eye(len(R),dtype=bool); off=R[mask]
    if off.size:
        lo=float(np.nanmin(off)); hi=float(np.nanmax(off))
        if lo>=0.0 and hi<=1.000001:              # legacy similarity 0..1
            R[mask]=1.0+9.0*R[mask]
        elif lo>=-1.000001 and hi<=1.000001:      # signed correlations -1..1
            R[mask]=1.0+9.0*((R[mask]+1.0)/2.0)
        else:
            R[mask]=np.clip(R[mask],1.0,10.0)
    np.fill_diagonal(R,0.0)
    return R


def _mutual_relation_for_position(matrix_1_10:np.ndarray)->np.ndarray:
    """A single 2D distance needs one mutual value per pair.

    Directionality remains visible in the matrix. Position uses the arithmetic mean
    of i→j and j→i, the simplest auditable projection rule.
    """
    raw=_coerce_relation_scale_1_10(matrix_1_10)
    mutual=(raw+raw.T)/2.0
    N=np.zeros_like(mutual,float)
    mask=~np.eye(len(raw),dtype=bool)
    N[mask]=np.clip((mutual[mask]-1.0)/9.0,0.0,1.0)
    np.fill_diagonal(N,0.0)
    return N


def fit_relational_landscape(relation_matrix:np.ndarray, object_names:list[str], scores:np.ndarray|list[float], *, seed:int=20260820,max_iter:int=900)->RelationalMapResult:
    """Fit fixed 2D positions from the complete relation matrix.

    The matrix itself may be asymmetric. Because one map distance cannot encode two
    directed values simultaneously, the layout uses mean(i→j, j→i); the exported
    matrix preserves each direction separately. Higher mutual relation -> shorter
    target distance. The map itself is 2D and static; score is represented only by
    bubble size/color for primary objects in the HTML UI.
    """
    raw=_coerce_relation_scale_1_10(np.asarray(relation_matrix,float))
    asym=float(np.nanmean(np.abs(raw-raw.T))) if raw.shape[0]>1 else 0.0
    Rpos=_mutual_relation_for_position(raw);m=len(Rpos)
    if len(object_names)!=m: raise ValueError('Počet názvů objektů neodpovídá matici.')
    D=0.12+0.88*(1.0-Rpos);np.fill_diagonal(D,0.0)
    J=np.eye(m)-np.ones((m,m))/m;B=-0.5*J@(D*D)@J
    vals,vecs=np.linalg.eigh(B);ix=np.argsort(vals)[::-1][:2];vals=np.maximum(vals[ix],1e-8);X=vecs[:,ix]*np.sqrt(vals)
    if X.shape[1]<2:X=np.pad(X,((0,0),(0,2-X.shape[1])))
    rng=np.random.default_rng(seed);X=X+rng.normal(0,1e-4,X.shape)
    pairs=[(i,j) for i in range(m) for j in range(i+1,m)];den=sum(D[i,j]**2 for i,j in pairs) or 1.0
    lr=.04;last=None;best=(1e9,X.copy(),0)
    for it in range(1,max_iter+1):
        g=np.zeros_like(X);num=0.0
        for i,j in pairs:
            diff=X[i]-X[j];dist=float(np.linalg.norm(diff)+1e-9);err=dist-D[i,j];num+=err*err
            grad=2*err*diff/dist;g[i]+=grad;g[j]-=grad
        stress=(num/den)**.5
        if stress<best[0]:best=(stress,X.copy(),it)
        if last is not None and abs(last-stress)<1e-9:break
        last=stress;X-=lr*g/max(1,len(pairs));X-=X.mean(axis=0,keepdims=True);lr*=0.997
    stress,X,it=best
    map_dist=[];target_dist=[];rel_values=[]
    for i,j in pairs:
        map_dist.append(float(np.linalg.norm(X[i]-X[j])));target_dist.append(float(D[i,j]));rel_values.append(float((raw[i,j]+raw[j,i])/2.0))
    try:
        from scipy.stats import spearmanr
        rho_target=float(spearmanr(map_dist,target_dist).statistic);rho_relation=float(spearmanr(map_dist,rel_values).statistic)
    except Exception:
        rho_target=float('nan');rho_relation=float('nan')
    sc=np.asarray(scores,float);finite=sc[np.isfinite(sc)]
    if not finite.size:H=np.full(m,.5)
    else:
        lo=float(np.min(finite));hi=float(np.max(finite));H=np.array([.5 if not np.isfinite(v) else (.25+.75*((v-lo)/(hi-lo) if hi>lo else .5)) for v in sc])
    return RelationalMapResult(list(object_names),raw,D,X,sc,H,float(stress),int(it),'EXPLICIT_RELATION_MATRIX',
        {'diagonal_contract':'zero','relation_scale':'1-10','distance_rule':'higher_mutual_relation_closer','visual_score_rule':'bubble_size_and_color','all_pairs_simultaneous':True,
         'input_asymmetry_mean_abs':round(asym,6),'asymmetry_fit_rule':'position uses mean(i→j,j→i); matrix preserves both directions',
         'spearman_map_vs_target_distance':None if not np.isfinite(rho_target) else round(rho_target,6),
         'spearman_map_distance_vs_relation':None if not np.isfinite(rho_relation) else round(rho_relation,6),
         'algorithm':'NPC complete all-pairs stress layout; Bahbouh-inspired relation-map semantics, not claimed as proprietary QED implementation'})

def relation_map_from_battery(data:pd.DataFrame,spec:StudySpec,*,explicit_matrix:Any=None)->RelationalMapResult:
    cols=[f'obj_{o.slug}' for o in spec.objects if f'obj_{o.slug}' in data]
    labels=[o.label for o in spec.objects if f'obj_{o.slug}' in data]
    if explicit_matrix is not None:
        R=np.asarray(explicit_matrix,float);w=pd.to_numeric(data.get('vaha',pd.Series(1.0,index=data.index)),errors='coerce').fillna(1.0).to_numpy(float)
        scores=np.array([_weighted_mean(pd.to_numeric(data[c],errors='coerce').to_numpy(float),w) for c in cols])
        res=fit_relational_landscape(R,labels,scores,seed=spec.seed);res.relation_source='MEASURED_OR_USER_SUPPLIED_RELATION_MATRIX';return res
    R,scores=derive_relation_matrix(data,cols);res=fit_relational_landscape(R,labels,scores,seed=spec.seed);res.relation_source='DERIVED_FROM_COMMON_RESPONDENT_RATINGS';return res


def relational_nearest_pairs(res:RelationalMapResult,top_n:int=10)->list[tuple[str,str,float]]:
    """Return closest mutual pairs using the mean of both directed relations."""
    pairs=[]
    for i in range(len(res.object_names)):
        for j in range(i+1,len(res.object_names)):
            mutual=float((res.relation_matrix[i,j]+res.relation_matrix[j,i])/2.0)
            pairs.append((res.object_names[i],res.object_names[j],mutual))
    return sorted(pairs,key=lambda x:-x[2])[:top_n]


def export_relational_png(path:str|Path,res:RelationalMapResult)->Path:
    """Static 2D client preview: position=relations, bubble size/color=score."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    x,y=res.object_xy[:,0],res.object_xy[:,1]
    sc=np.asarray(res.object_scores,float); finite=sc[np.isfinite(sc)]
    if finite.size:
        lo=float(np.min(finite)); hi=float(np.max(finite)); norm=np.array([.5 if not np.isfinite(v) else ((v-lo)/(hi-lo) if hi>lo else .5) for v in sc])
    else: norm=np.full(len(sc),.5)
    fig,ax=plt.subplots(figsize=(10,7))
    sizes=120+500*np.clip(norm,0,1)
    pts=ax.scatter(x,y,s=sizes,c=np.clip(norm,0,1),cmap='turbo',alpha=.84,edgecolors='white',linewidths=1.5)
    for i,name in enumerate(res.object_names): ax.text(x[i],y[i],str(name),fontsize=9,ha='center',va='bottom')
    ax.set_title('Vizualizace vztahů · pozice = vztahy · velikost/barva = skóre')
    ax.set_xlabel('relační osa 1');ax.set_ylabel('relační osa 2');ax.grid(alpha=.12)
    cb=fig.colorbar(pts,ax=ax,fraction=.04,pad=.02);cb.set_label('relativní score')
    fig.tight_layout();fig.savefig(p,dpi=170,bbox_inches='tight');plt.close(fig);return p


def export_relational_html(path:str|Path,res:RelationalMapResult)->Path:
    """Offline interactive 3D relationship terrain. Matrix is audit detail only."""
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    data=res.serializable();data['nearest_pairs']=relational_nearest_pairs(res,12)
    html=r'''<!doctype html><html lang="cs"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Vizualizace vztahů</title><style>
*{box-sizing:border-box}body{margin:0;background:#070a10;color:#f8fafc;font-family:Inter,system-ui}.shell{padding:14px}.head{display:flex;gap:12px;justify-content:space-between;align-items:center;flex-wrap:wrap}.head h2{margin:0}.mut{color:#aab5c7;font-size:12px}.tools{display:flex;gap:7px;flex-wrap:wrap}.tools button,.tools select{background:#111827;border:1px solid #354156;color:white;border-radius:9px;padding:8px 9px}.stage{position:relative;margin-top:10px;border:1px solid #303b50;border-radius:18px;overflow:hidden;background:#000}.stage canvas{width:100%;height:min(72vh,720px);min-height:520px;display:block;touch-action:none}.legend{position:absolute;left:14px;bottom:13px;background:rgba(5,9,15,.82);border:1px solid #354156;border-radius:11px;padding:9px 11px;min-width:240px}.ramp{height:8px;border-radius:99px;background:linear-gradient(90deg,#081a74,#1557d6,#00a9de,#18c86f,#f5df28,#ff8b18,#e52421);margin:6px 0}details{margin-top:10px;background:white;color:#172033;border-radius:12px;overflow:hidden}summary{padding:12px 14px;font-weight:800;cursor:pointer}.matrix{overflow:auto;max-height:420px;padding:8px}.matrix table{border-collapse:collapse;min-width:max-content;font-size:10px}.matrix th,.matrix td{border:1px solid #e5e9f2;padding:5px 7px;text-align:center}.matrix th{background:#f7f9fc;position:sticky;top:0}.info{margin-top:8px;color:#cbd5e1;font-size:12px}.selected{position:absolute;right:14px;bottom:13px;max-width:340px;background:rgba(5,9,15,.82);border:1px solid #354156;border-radius:11px;padding:10px}
</style></head><body><div class="shell"><div class="head"><div><h2>Vizualizace vztahů</h2><div class="mut">Výška = skóre objektu · vzdálenost = oboustranná síla vztahu · oranžová ven / fialová dovnitř</div></div><div class="tools"><select id="mode"><option value="classic">Klasické skóre</option><option value="norm">Normativní skóre · průměr 50, směrodatná odchylka 10</option></select><button id="left">↶</button><button id="right">↷</button><button id="top">Pohled shora</button><button id="labels">Popisky</button><button id="auto">Automatická rotace</button><button id="center">Vycentrovat</button></div></div><div class="stage"><canvas id="cv"></canvas><div class="legend"><b id="legendTitle">Klasické skóre</b><div class="ramp"></div><div class="mut" id="range"></div></div><div class="selected" id="sel">Klikněte na objekt.</div></div><details><summary>Nastavení objektů: s výškou / bez výšky</summary><div class="matrix" id="types"></div></details><details><summary>Rozbalit vztahovou matici</summary><div class="matrix" id="matrix"></div></details><div class="info" id="meta"></div></div><script>
const D=__DATA__,names=D.object_names||[],R=(D.relation_matrix||[]).map(r=>r.map(Number)),n=names.length,cv=document.getElementById('cv'),ctx=cv.getContext('2d');
const classic=names.map((_,i)=>R[i].reduce((a,b)=>a+Number(b||0),0)+R.reduce((a,r)=>a+Number(r[i]||0),0));const avg=classic.reduce((a,b)=>a+b,0)/Math.max(1,n),sd=Math.sqrt(classic.reduce((s,v)=>s+(v-avg)*(v-avg),0)/Math.max(1,n-1))||1,norm=classic.map(v=>50+10*(v-avg)/sd);const noHeight=new Set();let mode='classic',yaw=-.62,pitch=.72,zoom=1,labels=true,auto=false,selected=-1,drag=null,W=0,H=0,dpr=1;
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));function esc(x){return String(x??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))}function S(){return mode==='norm'?norm:classic}function tscore(v){let a=S();if(mode==='norm')return clamp((v-20)/60,0,1);let lo=Math.min(...a),hi=Math.max(...a);return hi>lo?(v-lo)/(hi-lo):.5}function color(t){t=clamp(t,0,1);let s=[[8,26,116],[21,87,214],[0,169,222],[24,200,111],[245,223,40],[255,139,24],[229,36,33]],x=t*(s.length-1),i=Math.min(s.length-2,Math.floor(x)),f=x-i;return`rgb(${s[i].map((v,k)=>Math.round(v+(s[i+1][k]-v)*f)).join(',')})`}
function layout(){if(!n)return[];let p=Array.from({length:n},(_,i)=>[Math.cos(2*Math.PI*i/n)*28,Math.sin(2*Math.PI*i/n)*28]),mx=1;for(let i=0;i<n;i++)for(let j=0;j<n;j++)mx=Math.max(mx,(R[i][j]+R[j][i])/2);for(let it=0;it<800;it++){let step=.1*(1-it/1000),d=Array.from({length:n},()=>[0,0]);for(let i=0;i<n;i++)for(let j=i+1;j<n;j++){let m=(R[i][j]+R[j][i])/2,target=14+46*(1-m/mx),dx=p[j][0]-p[i][0],dy=p[j][1]-p[i][1],dist=Math.hypot(dx,dy)||.001,f=(dist-target)*step*.02;d[i][0]+=f*dx/dist;d[i][1]+=f*dy/dist;d[j][0]-=f*dx/dist;d[j][1]-=f*dy/dist}for(let i=0;i<n;i++){p[i][0]+=d[i][0];p[i][1]+=d[i][1]}}let cx=p.reduce((a,q)=>a+q[0],0)/n,cy=p.reduce((a,q)=>a+q[1],0)/n;p=p.map(q=>[q[0]-cx,q[1]-cy]);let rr=Math.max(1,...p.map(q=>Math.hypot(...q)));return p.map(q=>[q[0]*38/rr,q[1]*38/rr])}const XY=layout();function peaks(){let a=S(),lo=Math.min(...a),hi=Math.max(...a);return XY.map((p,i)=>{let q=mode==='norm'?clamp((a[i]-20)/60,0,1):(hi>lo?(a[i]-lo)/(hi-lo):.5);return{x:p[0],y:p[1],z:noHeight.has(i)?0:4+22*q,s:a[i],i}})}function terrain(x,y,P){let sg=clamp(120/Math.pow(Math.max(n,1),.34),2.6,20),z=0;for(const p of P){let dx=x-p.x,dy=y-p.y;z+=p.z*Math.exp(-(dx*dx+dy*dy)/(2*sg*sg))}return z}function proj(x,y,z){let cy=Math.cos(yaw),sy=Math.sin(yaw),cp=Math.cos(pitch),sp=Math.sin(pitch),rx=x*cy-y*sy,ry=x*sy+y*cy,py=ry*cp-z*sp,pz=ry*sp+z*cp,sc=Math.min(W,H)*.0092*zoom;return[W/2+rx*sc,H*.60+py*sc,pz]}function resize(){let r=cv.getBoundingClientRect();dpr=Math.min(2,devicePixelRatio||1);W=r.width;H=r.height;cv.width=W*dpr;cv.height=H*dpr;ctx.setTransform(dpr,0,0,dpr,0,0)}
function draw(){ctx.fillStyle='#000';ctx.fillRect(0,0,W,H);let P=peaks(),N=32,span=58,g=[],mz=0;for(let y=0;y<=N;y++){g[y]=[];for(let x=0;x<=N;x++){let xx=-span+2*span*x/N,yy=-span+2*span*y/N,z=terrain(xx,yy,P);mz=Math.max(mz,z);g[y][x]={x:xx,y:yy,z}}}let zs=mz?26/mz:1,tr=[];for(let y=0;y<N;y++)for(let x=0;x<N;x++){let a=g[y][x],b=g[y][x+1],c=g[y+1][x+1],d=g[y+1][x];for(const q of[a,b,c,d])q.zz=q.z*zs;let A=proj(a.x,a.y,a.zz),B=proj(b.x,b.y,b.zz),C=proj(c.x,c.y,c.zz),D=proj(d.x,d.y,d.zz);tr.push({p:[A,B,C],z:(A[2]+B[2]+C[2])/3,h:(a.zz+b.zz+c.zz)/78},{p:[A,C,D],z:(A[2]+C[2]+D[2])/3,h:(a.zz+c.zz+d.zz)/78})}tr.sort((a,b)=>a.z-b.z);for(const t of tr){ctx.beginPath();ctx.moveTo(t.p[0][0],t.p[0][1]);ctx.lineTo(t.p[1][0],t.p[1][1]);ctx.lineTo(t.p[2][0],t.p[2][1]);ctx.closePath();ctx.fillStyle=color(t.h);ctx.globalAlpha=.84;ctx.fill();ctx.globalAlpha=1}if(selected>=0){for(let j=0;j<n;j++)if(j!==selected){arrow(selected,j,'#EB652A',R[selected][j],P,1);arrow(j,selected,'#907CFF',R[j][selected],P,-1)}}let nodes=P.map(p=>{let q=proj(p.x,p.y,terrain(p.x,p.y,P)*zs+1);return{...p,q}}).sort((a,b)=>a.q[2]-b.q[2]);for(const p of nodes){let rr=noHeight.has(p.i)?7:6,fill=noHeight.has(p.i)?'#B9A9FF':color(tscore(p.s));ctx.beginPath();ctx.arc(p.q[0],p.q[1],rr+2,0,Math.PI*2);ctx.fillStyle='white';ctx.fill();ctx.beginPath();ctx.arc(p.q[0],p.q[1],rr,0,Math.PI*2);ctx.fillStyle=fill;ctx.fill();if(labels){ctx.font='700 11px system-ui';ctx.textAlign='center';ctx.fillStyle='white';ctx.shadowColor='#000';ctx.shadowBlur=4;ctx.fillText(names[p.i],p.q[0],p.q[1]-11);ctx.shadowBlur=0}}let a=S();document.getElementById('legendTitle').textContent=mode==='norm'?'Normativní skóre':'Klasické skóre';document.getElementById('range').textContent=mode==='norm'?`norma 20–80 · aktuální ${Math.min(...a).toFixed(1)}–${Math.max(...a).toFixed(1)}`:`rozsah ${Math.min(...a).toFixed(1)}–${Math.max(...a).toFixed(1)}`;if(auto){yaw+=.0011;requestAnimationFrame(draw)}}function arrow(i,j,col,val,P,side){if(val<2)return;let a=P[i],b=P[j],A=proj(a.x,a.y,terrain(a.x,a.y,P)+3),B=proj(b.x,b.y,terrain(b.x,b.y,P)+3),mx=(A[0]+B[0])/2+side*10,my=(A[1]+B[1])/2-18;ctx.beginPath();ctx.moveTo(A[0],A[1]);ctx.quadraticCurveTo(mx,my,B[0],B[1]);ctx.strokeStyle=col;ctx.globalAlpha=.25+.07*val;ctx.lineWidth=1+.18*val;ctx.stroke();ctx.globalAlpha=1}
function pick(x,y){let P=peaks(),best=-1,bd=18;for(const p of P){let q=proj(p.x,p.y,terrain(p.x,p.y,P)+1),d=Math.hypot(q[0]-x,q[1]-y);if(d<bd){bd=d;best=p.i}}return best}cv.onpointerdown=e=>{let r=cv.getBoundingClientRect();drag={x:e.clientX,y:e.clientY,m:false,sx:e.clientX-r.left,sy:e.clientY-r.top};cv.setPointerCapture(e.pointerId)};cv.onpointermove=e=>{if(!drag)return;let dx=e.clientX-drag.x,dy=e.clientY-drag.y;if(Math.abs(dx)+Math.abs(dy)>2)drag.m=true;yaw+=dx*.008;pitch=clamp(pitch+dy*.006,.08,1.52);drag.x=e.clientX;drag.y=e.clientY;draw()};cv.onpointerup=()=>{if(drag&&!drag.m){let i=pick(drag.sx,drag.sy);if(i>=0){selected=i;document.getElementById('sel').innerHTML=`<b>${esc(names[i])}</b><div class="mut">${mode==='norm'?'Normativní':'Klasické'} skóre: ${S()[i].toFixed(1)} · vysílá ${R[i].reduce((a,b)=>a+b,0).toFixed(1)} · přijímá ${R.reduce((a,r)=>a+r[i],0).toFixed(1)}</div>`;draw()}}drag=null};cv.onwheel=e=>{e.preventDefault();zoom=clamp(zoom*Math.exp(-e.deltaY*.001),.45,2.8);draw()};document.getElementById('mode').onchange=e=>{mode=e.target.value;draw()};document.getElementById('left').onclick=()=>{yaw-=.35;draw()};document.getElementById('right').onclick=()=>{yaw+=.35;draw()};document.getElementById('top').onclick=()=>{pitch=.08;draw()};document.getElementById('labels').onclick=()=>{labels=!labels;draw()};document.getElementById('auto').onclick=()=>{auto=!auto;draw()};document.getElementById('center').onclick=()=>{yaw=-.62;pitch=.72;zoom=1;draw()};window.onresize=()=>{resize();draw()};
document.getElementById('types').innerHTML=names.map((nm,i)=>`<label style="display:inline-flex;gap:5px;margin:5px 10px"><input type="checkbox" onchange="this.checked?noHeight.add(${i}):noHeight.delete(${i});draw()"> ${esc(nm)} bez výšky</label>`).join('');document.getElementById('matrix').innerHTML=`<table><tr><th>Objekt</th>${names.map(x=>`<th>${esc(x)}</th>`).join('')}</tr>${names.map((nm,i)=>`<tr><td><b>${esc(nm)}</b></td>${names.map((_,j)=>`<td>${i===j?'0':Number(R[i][j]||0).toFixed(1)}</td>`).join('')}</tr>`).join('')}</table>`;document.getElementById('meta').textContent=`Zdroj vztahů: ${D.relation_source||'neuveden'} · stres mapy ${Number(D.stress_1||0).toFixed(3)}`;resize();draw();
</script></body></html>'''.replace('__DATA__',json.dumps(data,ensure_ascii=False,default=str))
    p.write_text(html,encoding='utf-8');return p

