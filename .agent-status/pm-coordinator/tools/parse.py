import re, json
lines=open('decisions.md').read().split('\n')
items=[]; parts={}; part=None; cur=None; field=None; last=None; partE=False
KEY={'Question':'question','Example':'example','Recommendation':'rec','Sources':'sources'}
def flush():
    global cur
    if cur: items.append(cur)
    cur=None
for l in lines:
    m=re.match(r'^## Part ([A-E])\. (.*)',l)
    if m:
        flush(); part=m.group(1); parts[part]=m.group(2); partE=(part=='E'); continue
    if l.startswith('## '):
        flush(); part=None; partE=False; continue
    m=re.match(r'^### (D-\d+)\. (.*)',l)
    if m:
        flush(); cur={'id':m.group(1),'title':m.group(2),'part':part,'question':'','example':'','options':[],'changes':[],'rec':'','sources':''}; field=None; last=None; continue
    if partE and l.startswith('| D-'):
        c=[x.strip() for x in l.strip().strip('|').split('|')]
        items.append({'id':c[0],'title':c[1],'part':'E','question':c[1],'example':c[2],'ifin':c[3],'rec':c[4],'sources':c[5],
          'options':[{'key':'in','text':'**In.** Adds: '+c[3]},{'key':'out','text':"**Out.** Written into the baseline's out list."}],'changes':[]})
        continue
    if not cur: continue
    m=re.match(r'^- \*\*(Question|Example|Options|Recommendation|Sources)\.\*\*\s*(.*)',l)
    if m:
        field=m.group(1); last=None
        if field in KEY: cur[KEY[field]]=m.group(2)
        elif field=='Options': cur['_inline']=m.group(2)
        continue
    m=re.match(r'^  - (?:\(([a-z])\)\s*)?(.*)',l)
    if m and field=='Options':
        if m.group(1): cur['options'].append({'key':m.group(1),'text':m.group(2)}); last='o'
        else: cur['changes'].append(m.group(2)); last='c'
        continue
    if l.startswith('  ') and l.strip() and field:
        t=l.strip()
        if field=='Options':
            if last=='c': cur['changes'][-1]+=' '+t
            elif last=='o': cur['options'][-1]['text']+=' '+t
            elif cur.get('_inline') is not None: cur['_inline']+=' '+t
        elif field in KEY: cur[KEY[field]]+=' '+t
flush()
for x in items:
    inl=(x.pop('_inline',None) or '').strip()
    if inl and not x['options']:
        ch=re.search(r'\s(Changes|Either changes|Both change)\b.*$',inl)
        if ch: x['changes'].append(inl[ch.start()+1:]); inl=inl[:ch.start()].strip()
        parts_=re.split(r'\(([a-z])\)\s*',inl)
        pre=parts_[0].strip(' ;')
        if pre: x['preface']=pre
        for k,v in zip(parts_[1::2],parts_[2::2]): x['options'].append({'key':k,'text':v.strip().rstrip(';').strip()})
assert len(items)==48, len(items)
bad=[x['id'] for x in items if not x['options'] or not x['rec'] or not x['question']]
print('no-options/rec/question:',bad)
json.dump({'parts':parts,'items':items,'source':'c7d5bbe'},open('decisions.json','w'),ensure_ascii=False)
for x in [items[0],items[1]]: print(json.dumps(x,ensure_ascii=False)[:1200]); print()
