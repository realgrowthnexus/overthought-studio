from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math, random
import os; D=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))+'/'
FD=D+"style/fonts/"; SC=D+"scenes/"; OUT=D+"renders/"
import os; os.makedirs(OUT,exist_ok=True)
BG=(17,17,17); INK=(246,241,230); Y=(255,214,10); DIM=(150,146,136)
def K(s,bold=True): return ImageFont.truetype(FD+("Kalam-Bold.ttf" if bold else "Kalam-Bold.ttf"),s)
def CB(s): return ImageFont.truetype(FD+"CaveatBrush-Regular.ttf",s)
def scene(name,size,tint=None,fill=None):
    im=Image.open(SC+name+".jpg").convert("RGB")
    if tint:  # recolour bright pixels near given points to yellow
        px=im.load()
        for (cx,cy,r) in tint:
            for y in range(max(0,cy-r),min(1024,cy+r)):
                for x in range(max(0,cx-r),min(1024,cx+r)):
                    if (x-cx)**2+(y-cy)**2<r*r:
                        v=sum(px[x,y])/3
                        if v>60: k=v/255; px[x,y]=(int(Y[0]*k),int(Y[1]*k),int(Y[2]*k))
    for p in (fill or []): ImageDraw.floodfill(im,p,Y,thresh=70)
    im=im.resize((size,size),Image.LANCZOS).point(lambda v:int(17+v*238/255))
    m=Image.new("L",(size,size),0); e=int(size*0.065)
    ImageDraw.Draw(m).rectangle((e,e,size-e,size-e),fill=255); m=m.filter(ImageFilter.GaussianBlur(size*0.05))
    return im,m
def wobble_underline(d,x,w,y,th,seed):
    random.seed(seed); pts=[]
    for i in range(15):
        pts.append((x-6+(w+12)*i/14, y+math.sin(i*0.8+seed)*th*0.6+random.uniform(-1.5,1.5)))
    d.line(pts,fill=Y+(235,),width=th,joint="curve")
def text_block(c,cx,y,parts,size,rot=-1.5,seed=1,align="center"):
    """parts: list of (text, kind) kind in 'ink','key','dim'"""
    fonts={"ink":K(size),"key":CB(int(size*1.22)),"dim":K(int(size*0.5))}
    cols={"ink":INK,"key":Y,"dim":DIM}
    tmp=ImageDraw.Draw(Image.new("RGBA",(1,1)))
    tw=sum(tmp.textlength(t,font=fonts[k]) for t,k in parts)
    H=int(size*1.9); L=Image.new("RGBA",(int(tw)+80,H),(0,0,0,0)); d=ImageDraw.Draw(L)
    x=40; base=int(size*1.25)
    for t,k in parts:
        f=fonts[k]; w=d.textlength(t,font=f)
        d.text((x,base),t,font=f,fill=cols[k]+(255,),anchor="ls")
        if k=="key": wobble_underline(d,x,w,base+size*0.22,max(4,size//14),seed)
        x+=w
    L=L.rotate(rot,resample=Image.BICUBIC,expand=True)
    sh=Image.new("RGBA",L.size,(0,0,0,0)); sh.putalpha(L.split()[3].point(lambda a:int(a*0.85))); sh=sh.filter(ImageFilter.GaussianBlur(9))
    px=int(cx-L.width/2) if align=="center" else int(cx-40)
    c.alpha_composite(sh,(px+3,y+6)); c.alpha_composite(L,(px,y))
def margin_note(c,x,y,text,size=34):
    d=ImageDraw.Draw(c); f=K(size)
    # little hand-drawn arrow + note
    random.seed(len(text))
    pts=[(x,y+size*0.6)]+[(x+i*9,y+size*0.6+random.uniform(-2,2)) for i in range(1,6)]
    d.line(pts,fill=Y,width=3); d.line([(x+45,y+size*0.6),(x+33,y+size*0.3)],fill=Y,width=3); d.line([(x+45,y+size*0.6),(x+33,y+size*0.9)],fill=Y,width=3)
    d.text((x+60,y),text,font=f,fill=Y)
def bug(c,x,y,size=40):
    d=ImageDraw.Draw(c); f=K(size)
    d.text((x,y),"overthought",font=f,fill=(200,196,186))
    w=d.textlength("overthought",font=f)
    random.seed(3); cx,cy=x+w+22,y+size*0.62
    pts=[(cx+math.cos(t*0.7)*(8+random.uniform(-3,3)),cy+math.sin(t*0.9)*(7+random.uniform(-3,3))) for t in range(30)]
    d.line(pts,fill=Y,width=3,joint="curve")
def short(scn,top,bottom,note=None,tint=None,extra=None,fill=None):
    c=Image.new("RGBA",(1080,1920),BG+(255,))
    im,m=scene(scn,1080,tint,fill); c.paste(im,(0,430),m)
    if extra: extra(c)
    for i,parts in enumerate(top): text_block(c,540,150+i*115,parts,88,[-1.6,1.0][i%2],i+1)
    text_block(c,540,1440,bottom,104,-2.2,7)
    if note: margin_note(c,540-int(ImageDraw.Draw(c).textlength(note,font=K(42))/2)-30,1680,note,42)
    bug(c,48,44,42)
    return c
def longform(scn,lines,note=None,tint=None,sub=None,extra=None,fill=None):
    c=Image.new("RGBA",(1920,1080),BG+(255,))
    im,m=scene(scn,1080,tint,fill); c.paste(im,(800,0),m)
    if extra: extra(c)
    y=300
    for i,parts in enumerate(lines):
        text_block(c,120,y,parts,92,[-1.8,0.8,-1.0][i%3],i+3,align="left"); y+=135
    if note: margin_note(c,140,y+40,note,36)
    if sub:  # subtitle style for narration
        d=ImageDraw.Draw(c); f=K(46); w=d.textlength(sub,font=f)
        d.text(((1920-w)/2,985),sub,font=f,fill=INK)
    bug(c,60,48,38)
    return c
