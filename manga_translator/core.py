from __future__ import annotations
import json,re,cv2,numpy as np
from PIL import Image,ImageDraw,ImageFont
JP_RE=re.compile(r"[\u3040-\u30ff\u3400-\u9fff々〆ヶー]")
def natural_key(s): return [int(x) if x.isdigit() else x.lower() for x in re.split(r"(\d+)",str(s))]
class OCR:
    def __init__(self): self.e=None
    def read(self,img):
        if self.e is None:
            from manga_ocr import MangaOcr
            self.e=MangaOcr()
        return (self.e(img.convert("RGB")) or "").strip()
def merge_boxes(boxes,gap):
    boxes=[list(map(int,b)) for b in boxes]; changed=True
    while changed:
        changed=False; result=[]
        while boxes:
            a=boxes.pop(0); merged=False
            for i,b in enumerate(boxes):
                if not(a[2]+gap<b[0] or b[2]+gap<a[0] or a[3]+gap<b[1] or b[3]+gap<a[1]):
                    boxes.pop(i); boxes.insert(0,[min(a[0],b[0]),min(a[1],b[1]),max(a[2],b[2]),max(a[3],b[3])])
                    changed=merged=True; break
            if not merged: result.append(a)
        boxes=result
    return boxes
def detect(img):
    a=np.array(img.convert("RGB")); g=cv2.cvtColor(a,cv2.COLOR_RGB2GRAY); h,w=g.shape; sc=max(1,max(h,w)/1800)
    bw=cv2.adaptiveThreshold(g,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY_INV,31,13)
    small=max(1,int(1.5*sc)); bw=cv2.morphologyEx(bw,cv2.MORPH_OPEN,np.ones((small,small),np.uint8))
    kv=cv2.getStructuringElement(cv2.MORPH_RECT,(max(3,int(4*sc)),max(10,int(24*sc))))
    kh=cv2.getStructuringElement(cv2.MORPH_RECT,(max(10,int(24*sc)),max(3,int(4*sc))))
    joined=cv2.bitwise_or(cv2.dilate(bw,kv),cv2.dilate(bw,kh))
    n,_,stats,_=cv2.connectedComponentsWithStats(joined,8); out=[]
    for i in range(1,n):
        x,y,ww,hh,area=stats[i]; ba=ww*hh
        if ww<12*sc or hh<12*sc or ba<160*sc*sc or ba>h*w*.09: continue
        if max(ww/hh,hh/ww)>10: continue
        p=int(7*sc); out.append((max(0,x-p),max(0,y-p),min(w,x+ww+p),min(h,y+hh+p)))
    out=merge_boxes(out,int(8*sc)); out.sort(key=lambda b:(b[1]//max(1,int(160*sc)),-b[0],b[1])); return out
def analyze(img,ocr):
    regs=[]
    for b in detect(img):
        t=ocr.read(img.crop(tuple(b)))
        if len(JP_RE.findall(t))>=2 and 1<len(t)<220: regs.append({"box":b,"jp":t})
    return regs
def translate(regions,key,model,previous=""):
    if not regions:return []
    from openai import OpenAI
    c=OpenAI(api_key=key)
    inp="前一頁參考：\n"+previous[-1500:]+"\n\n本頁：\n"+"\n".join(f"[{i}] {r['jp']}" for i,r in enumerate(regions))
    ins='''你是專業日文漫畫翻譯員。將本頁各 OCR 區塊翻成自然的台灣繁體中文。前一頁內容只用來維持人物名稱、稱呼、口癖和上下文，不可把前頁文字加入本頁。保留情緒、敬語、語氣，不增加劇情。只輸出 JSON 陣列：[{"id":0,"zh":"..."},...]，每個本頁 id 必須恰好出現一次。'''
    r=c.responses.create(model=model,instructions=ins,input=inp); s=r.output_text.strip()
    s=re.sub(r"^```(?:json)?\s*|\s*```$","",s,flags=re.S)
    d={int(x["id"]):str(x["zh"]) for x in json.loads(s)}
    return [d.get(i,"") for i in range(len(regions))]
def font(sz):
    for p in [r"C:\Windows\Fonts\msjhbd.ttc",r"C:\Windows\Fonts\msjh.ttc",r"C:\Windows\Fonts\mingliu.ttc"]:
        try:return ImageFont.truetype(p,sz)
        except:pass
    return ImageFont.load_default()
def clean(img,box):
    x1,y1,x2,y2=map(int,box); arr=np.array(img.convert("RGB")); roi=arr[y1:y2,x1:x2]
    if roi.size==0:return img
    gray=cv2.cvtColor(roi,cv2.COLOR_RGB2GRAY)
    if float(np.mean(gray))>225: arr[y1:y2,x1:x2]=255
    else:
        mask=np.where(gray<125,255,0).astype(np.uint8); mask=cv2.dilate(mask,np.ones((3,3),np.uint8),iterations=1)
        fixed=cv2.inpaint(cv2.cvtColor(roi,cv2.COLOR_RGB2BGR),mask,3,cv2.INPAINT_TELEA)
        arr[y1:y2,x1:x2]=cv2.cvtColor(fixed,cv2.COLOR_BGR2RGB)
    return Image.fromarray(arr)
def draw_text(img,box,text):
    x1,y1,x2,y2=map(int,box); d=ImageDraw.Draw(img); w=x2-x1; h=y2-y1; margin=max(3,int(min(w,h)*.06))
    maxw=max(10,w-2*margin); maxh=max(10,h-2*margin); chosen=None
    for sz in range(min(46,max(14,int(h*.3))),9,-1):
        f=font(sz); lines=[]; cur=""
        for ch in text.replace("\n",""):
            test=cur+ch
            if cur and d.textbbox((0,0),test,font=f)[2]>maxw: lines.append(cur);cur=ch
            else:cur=test
        if cur:lines.append(cur)
        lh=int(sz*1.25)
        if len(lines)*lh<=maxh:chosen=(f,lines,lh);break
    if not chosen:f=font(10);lines=list(text);lh=12
    else:f,lines,lh=chosen
    y=y1+max(margin,(h-len(lines)*lh)//2)
    for line in lines:
        tw=d.textbbox((0,0),line,font=f)[2]; d.text((x1+(w-tw)//2,y),line,font=f,fill="black");y+=lh
    return img
def process_page(path,out_path,ocr,key,model,previous=""):
    img=Image.open(path).convert("RGB"); regs=analyze(img,ocr); zhs=translate(regs,key,model,previous); out=img.copy()
    for r,z in zip(regs,zhs): out=clean(out,r["box"]);out=draw_text(out,r["box"],z);r["zh"]=z
    out.save(out_path,"PNG"); return regs,"\n".join(f"{r['jp']} → {r.get('zh','')}" for r in regs)
