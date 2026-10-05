"""Generate GitHub-safe, script-free SVGs from the recorded model results."""
from pathlib import Path
from html import escape
import json

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
INK='#241739';PURPLE='#7853ec';MINT='#b8f18b';PAPER='#f6f4fb';LINE='#e5dff0'
MODEL=json.loads((ROOT/'artifacts/evidence-model.json').read_text(encoding='utf-8'))
CONTROL=json.loads((ROOT/'artifacts/control-model.json').read_text(encoding='utf-8'))
TEST=json.loads((ROOT/'artifacts/evidence-model-test.json').read_text(encoding='utf-8'))
CONTROL_TEST=json.loads((ROOT/'artifacts/control-model-test.json').read_text(encoding='utf-8'))

def text(x,y,value,size=30,color=INK,weight=400,anchor='start'):
    return f'<text x="{x}" y="{y}" fill="{color}" font-family="Arial, Helvetica, sans-serif" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}">{escape(str(value))}</text>'

def box(x,y,w,h,fill='#fff',stroke=LINE,r=24):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'

def path(d,color=PURPLE,width=5,dash=''):
    return f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"'+(f' stroke-dasharray="{dash}"' if dash else '')+'/>'

def write(name,w,h,body,label):
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-labelledby="title"><title id="title">{escape(label)}</title><defs><linearGradient id="hero" x2="1" y2="1"><stop stop-color="#241739"/><stop offset="1" stop-color="#42305f"/></linearGradient></defs>{body}</svg>'
    (OUT/name).write_text(svg,encoding='utf-8')

def hero():
    s=box(2,2,1196,526,'url(#hero)','#241739',34)
    s+='<circle cx="1090" cy="30" r="290" fill="#7853ec" opacity=".12"/>'
    s+=text(60,72,'POLICY ENFORCEMENT LAB',24,'#c6b5ef',700)
    s+=text(60,186,'Policy',94,'#fff',700)+text(60,286,'Switchboard',94,'#fff',700)
    s+=text(62,351,'Same message. Different rules.',34,'#e6dcf6')
    s+=box(60,408,276,65,MINT,MINT,32)+text(198,451,'3 policy adapters',27,INK,700,'middle')
    s+=path('M740 176 H850 V110 H1000','#c4a6ff',7)
    s+=path('M740 176 H850 V255 H1000','#c4a6ff',7)
    s+=path('M740 176 H850 V400 H1000','#c4a6ff',7)
    s+=box(676,127,137,100,'#5c4280','#8765b2',25)+text(744,192,'$15',47,'#fff',700,'middle')
    for y,title,status,color in [(60,'Harbor · $20','ALLOW',MINT),(205,'Harbor · $10','REVIEW','#f4d18a'),(350,'Cedar · approval','REVIEW','#f4d18a')]:
        s+=box(920,y,228,105,'#342246','#76548d',20)
        s+=text(944,y+36,title,21,'#ddcfee',700)+text(944,y+79,status,32,color,700)
    write('hero.svg',1200,530,s,'Policy Switchboard: a $15 refund changes with customer policy; three real policy adapters.')

def results():
    s=box(2,2,1196,646,PAPER,LINE,30)
    s+=text(54,78,'Measured outcomes',53,INK,700)
    s+=text(54,120,'SYNTHETIC STUDY · RESEARCH ONLY',24,'#745e8d',700)
    for x,title,report,baseline in [(52,'Original checks',MODEL,CONTROL),(618,'New frozen test',TEST,CONTROL_TEST)]:
        s+=box(x,157,528,290)
        s+=text(x+30,203,title,29,INK,700)
        s+=text(x+30,280,f"{report['correct']}/{report['total']}",68,PURPLE,700)
        s+=text(x+30,327,'Customer LoRA',27,INK,700)
        s+=box(x+30,350,466,15,LINE,LINE,7)
        s+=box(x+30,350,466*report['correct']/report['total'],15,PURPLE,PURPLE,7)
        s+=text(x+30,411,f"Head-only control: {baseline['correct']}/{baseline['total']}",25,'#736782')
    for x,value,label in [(52,'0','unsafe on new test'),(428,str(round(MODEL['p95_uncached_ms']))+' ms','warm CPU p95'),(804,'50','regression tests')]:
        s+=box(x,473,344,124,'#ede7f9','#e0d4f4',20)
        s+=text(x+23,525,value,43,INK,700)+text(x+23,568,label,24,'#735989')
    write('results.svg',1200,650,s,'Recorded synthetic results: LoRA 72/72 original checks and 66/66 new frozen tests; head-only control 67/72 and 62/66. Zero unsafe approvals observed on the new test. Warm CPU p95 24 ms, 50 regression tests. Not production certification.')

def architecture():
    s=box(2,2,1196,606,PAPER,LINE,30)+text(54,78,'How it works',53,INK,700)
    nodes=[(45,'Message','input'),(270,'FastAPI','tenant auth'),(495,'Ticket facts','trusted context'),(720,'Rules','policy checks'),(945,'Output','or review')]
    for x,title,sub in nodes:
        s+=box(x,172,205,127)
        s+=text(x+102,219,title,29,INK,700,'middle')+text(x+102,265,sub,23,'#7b688b',400,'middle')
        if x<945:s+=path(f'M{x+205} 235 H{x+225}',PURPLE,4)
    s+=path('M822 299 V335 H685 V381',PURPLE,4,'8 9')
    s+=text(555,346,'Secret pre-filter',24,'#745e8d')
    s+=box(486,385,400,128,'#ede7f9','#d8c9f2')
    s+=text(686,433,'MiniLM + customer LoRA',29,PURPLE,700,'middle')
    s+=text(686,478,'trained verdict head',25,'#765392',400,'middle')
    s+=path('M886 449 H937',PURPLE,4,'8 9')
    s+=box(945,385,205,128,'#edf7e5','#d7e9c8')
    s+=text(1047,433,'Compare',31,INK,700,'middle')+text(1047,478,'nothing sent',23,'#4e7740',400,'middle')
    s+=text(55,570,'AI customer delivery stays disabled.',30,'#6d5683',700)
    write('architecture.svg',1200,610,s,'Message enters FastAPI authentication, trusted ticket context and deterministic policy checks. Rules output or human review is separate from privacy-filtered MiniLM plus customer LoRA research comparisons, which deliver no customer messages.')

def stack():
    s=box(2,2,1196,376,'url(#hero)',INK,30)+text(54,75,'Built with purpose',49,'#fff',700)
    items=[('MiniLM','semantic encoder'),('PyTorch + PEFT','LoRA training'),('FastAPI + Pydantic','typed service'),('SQLite','trusted facts & evidence'),('Docker + Actions','verified serving'),('HTML · CSS · JS','animated playground')]
    for i,(name,detail) in enumerate(items):
        x=48+(i%3)*373;y=109+(i//3)*124
        s+=box(x,y,355,108,'#38254e','#65487d',20)
        s+=text(x+21,y+43,name,29,'#fff',700)+text(x+21,y+81,detail,22,'#cabae0')
    write('stack.svg',1200,380,s,'Technology stack: MiniLM, PyTorch and PEFT, FastAPI and Pydantic, SQLite, Docker and GitHub Actions, HTML CSS JavaScript.')

def navigation():
    for name,title,sub in [('start','Run it','setup guide'),('audit','Architecture','full audit'),('evidence','Results','raw model evidence'),('trust','Boundaries','scope & limitations')]:
        s=box(2,2,276,110,'#ede7f9','#d9cdef',20)+text(20,48,title,28,INK,700)+text(20,84,sub,19,'#705589')
        s+=path('M238 24 H258 V44 M239 43 L258 24',PURPLE,3)
        write(name+'.svg',280,114,s,title+' — '+sub)

if __name__=='__main__':
    OUT.mkdir(exist_ok=True)
    hero();results();architecture();stack();navigation()
    print('Built eight script-free SVG graphics from recorded results.')
