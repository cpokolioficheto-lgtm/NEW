import sys
from PIL import Image, ImageDraw, ImageFont
S=sys.argv[1]; logo=Image.open(sys.argv[2]).convert('RGBA')
rd=Image.open(sys.argv[3]).convert('RGBA'); rd=rd.crop(rd.getbbox())
def whiten(l):
    w=Image.new('RGBA',l.size,(255,255,255,0)); w.putalpha(l.getchannel('A')); return w
DARK=(19,116,118); LIGHT=(28,181,181); W,H=1920,1080
F='/usr/share/fonts/opentype/inter/Inter-%s.otf'
def font(w,s): return ImageFont.truetype(F%w,s)
def ctext(d,y,t,f,fill):
    w=d.textlength(t,font=f); d.text(((W-w)/2,y),t,font=f,fill=fill)
def place(img,lg,cx,cy,h):
    l=lg.resize((int(lg.width*h/lg.height),h),Image.LANCZOS); img.alpha_composite(l,(int(cx-l.width/2),int(cy-l.height/2)))
# intro: white, logo + placeholder for Rodendom logo
im=Image.new('RGBA',(W,H),'white'); d=ImageDraw.Draw(im)
place(im,logo,750,H*0.42,260)
d.line((1149,H*0.42-120,1149,H*0.42+120),fill=LIGHT,width=4)
place(im,rd,1359,H*0.42,260)
d.rectangle((0,H-14,W,H),fill=LIGHT)
ctext(d,H*0.75,'Мокри помещения — критични ситуации',font('Bold',64),DARK)
im.convert('RGB').save(f'{S}/intro.png')
# end card: dark teal background
im=Image.new('RGBA',(W,H),DARK); d=ImageDraw.Draw(im)
white=whiten(logo)
place(im,white,810,H*0.26,180)
d.line((1091,H*0.26-80,1091,H*0.26+80),fill=LIGHT,width=4)
place(im,whiten(rd),1241,H*0.26,180)
ctext(d,H*0.50,'smr-academy',font('Bold',110),'white')
d.rounded_rectangle((W/2-380,H*0.70,W/2+380,H*0.70+120),60,fill=LIGHT)
ctext(d,H*0.70+18,'0893 370 404',font('Bold',72),'white')
im.convert('RGB').save(f'{S}/end.png')
# subtitle sample on gray frame
im=Image.new('RGBA',(W,H),(110,110,110)); ov=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(ov)
f=font('SemiBold',54); t='Ако хидроизолацията не е положена правилно...'
tw=d.textlength(t,font=f); d.rounded_rectangle(((W-tw)/2-30,H-200,(W+tw)/2+30,H-110),16,fill=(0,0,0,150))
d.text(((W-tw)/2,H-190),t,font=f,fill='white'); im.alpha_composite(ov)
place(im,white,W-170,90,80)
d=ImageDraw.Draw(im); ctext(d,H*0.4,'[кадър от видеото]',font('Medium',50),(200,200,200))
im.convert('RGB').save(f'{S}/subs.png')
