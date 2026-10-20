import re,sys
s=open(sys.argv[1],encoding='utf-8').read()
s=re.sub(r'<!doctype html>\s*','',s,flags=re.I)
s=re.sub(r'</?html[^>]*>|</?head>|</?body[^>]*>','',s)
s=re.sub(r'<meta charset="utf-8">|<meta name="viewport"[^>]*>','',s)
s=s.replace('<title>AIA PM Status</title>','<title>AIA PM Status</title><meta name="claude:viewport-fit-sides" content="cover">',1)
s=s.replace('</style>','body{padding-left:max(16px,env(safe-area-inset-left,0px))!important;padding-right:max(16px,env(safe-area-inset-right,0px))!important}</style>',1)
open(sys.argv[2],'w',encoding='utf-8').write(s.strip()+"\n")
