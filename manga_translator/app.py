from __future__ import annotations
import sys,json,traceback
from pathlib import Path
from PIL import Image
from PySide6.QtCore import Qt,QObject,Signal,QRunnable,QThreadPool
from PySide6.QtGui import QPixmap,QPainter,QPen
from PySide6.QtWidgets import *
from .core import OCR,analyze,process_page,natural_key
EXT={".jpg",".jpeg",".png",".webp",".bmp"}
class Signals(QObject):
    ok=Signal(object);err=Signal(str);progress=Signal(int,str)
class Worker(QRunnable):
    def __init__(self,fn):super().__init__();self.fn=fn;self.s=Signals()
    def run(self):
        try:self.s.ok.emit(self.fn(self.s))
        except Exception:self.s.err.emit(traceback.format_exc())
class Preview(QLabel):
    def __init__(self):
        super().__init__();self.setAlignment(Qt.AlignCenter);self.setMinimumSize(650,700);self.setStyleSheet("background:#202124;color:white");self.src=None;self.boxes=[]
    def show_image(self,path,boxes=None):self.src=QPixmap(str(path));self.boxes=boxes or [];self.refresh()
    def refresh(self):
        if not self.src:return
        pm=self.src.scaled(self.size(),Qt.KeepAspectRatio,Qt.SmoothTransformation)
        if self.boxes:
            sx=pm.width()/self.src.width();sy=pm.height()/self.src.height();q=QPixmap(pm);p=QPainter(q);p.setPen(QPen(Qt.red,2))
            for b in self.boxes:
                x1,y1,x2,y2=b;p.drawRect(int(x1*sx),int(y1*sy),int((x2-x1)*sx),int((y2-y1)*sy))
            p.end();pm=q
        self.setPixmap(pm)
    def resizeEvent(self,e):super().resizeEvent(e);self.refresh()
class Main(QMainWindow):
    def __init__(self):
        super().__init__();self.resize(1450,900);self.setWindowTitle("Manga Translator");self.folder=None;self.pages=[];self.key="";self.model="gpt-5.6";self.ocr=OCR()
        c=QWidget();self.setCentralWidget(c);v=QVBoxLayout(c);bar=QHBoxLayout()
        for t,f in [("加入漫畫資料夾",self.open_folder),("API 設定",self.settings),("分析目前頁",self.analyze_current),("整本批次翻譯",self.batch)]:
            b=QPushButton(t);b.clicked.connect(f);bar.addWidget(b)
        bar.addStretch();v.addLayout(bar);sp=QSplitter();self.list=QListWidget();self.list.currentRowChanged.connect(self.select);sp.addWidget(self.list)
        self.preview=Preview();sp.addWidget(self.preview);side=QWidget();sv=QVBoxLayout(side);self.details=QTextEdit();self.details.setReadOnly(True);sv.addWidget(self.details)
        self.pb=QProgressBar();sv.addWidget(self.pb);sp.addWidget(side);sp.setSizes([250,850,350]);v.addWidget(sp);self.setStatusBar(QStatusBar())
    def open_folder(self):
        f=QFileDialog.getExistingDirectory(self,"選擇漫畫資料夾")
        if not f:return
        self.folder=Path(f);self.pages=sorted([p for p in self.folder.iterdir() if p.suffix.lower() in EXT],key=lambda p:natural_key(p.name))
        self.list.clear();self.list.addItems([p.name for p in self.pages]);self.pb.setRange(0,len(self.pages));self.pb.setValue(0)
        if self.pages:self.list.setCurrentRow(0)
    def select(self,i):
        if 0<=i<len(self.pages):self.preview.show_image(self.pages[i])
    def settings(self):
        k,ok=QInputDialog.getText(self,"OpenAI API","請貼上 API Key（以 sk- 開頭）。不要選擇檔案或貼入檔案路徑。",QLineEdit.Password,self.key)
        if ok:
            k=k.strip().strip('"').strip("'")
            if k.lower().startswith(("file:","http:","https:")) or "/" in k or "\\" in k:
                QMessageBox.warning(self,"API Key 格式錯誤","你輸入的內容看起來是檔案路徑或網址，不是 OpenAI API Key。\n\n請貼上以 sk- 開頭的 API Key。")
                return
            if not k.startswith("sk-"):
                QMessageBox.warning(self,"API Key 格式錯誤","OpenAI API Key 應以 sk- 開頭。請重新貼上正確的 Key。")
                return
            self.key=k
            self.statusBar().showMessage("API Key 已設定（只保存在目前程式記憶體中）")
    def analyze_current(self):
        i=self.list.currentRow()
        if i<0:return
        p=self.pages[i]
        def job(s):return analyze(Image.open(p).convert("RGB"),self.ocr)
        self.statusBar().showMessage("正在偵測與 OCR…");w=Worker(job)
        def done(regs):
            self.preview.show_image(p,[r["box"] for r in regs]);self.details.setPlainText("\n\n".join(f"{n+1}. {r['jp']}" for n,r in enumerate(regs)));self.statusBar().showMessage(f"找到 {len(regs)} 個日文區域")
        w.s.ok.connect(done);w.s.err.connect(self.error);QThreadPool.globalInstance().start(w)
    def batch(self):
        if not self.pages:return
        if not self.key:self.settings()
        if not self.key:return
        pages=list(self.pages);folder=self.folder;key=self.key;model=self.model;outdir=folder/"translated_zh-TW";outdir.mkdir(exist_ok=True);pp=outdir/"progress.json"
        try:state=json.loads(pp.read_text(encoding="utf-8")) if pp.exists() else {}
        except:state={}
        self.pb.setRange(0,len(pages))
        def job(sig):
            previous=""
            for idx,p in enumerate(pages):
                out=outdir/(p.stem+"_zh-TW.png")
                if state.get(p.name)=="done" and out.exists():sig.progress.emit(idx+1,p.name+"（已完成，跳過）");continue
                regs,previous=process_page(p,out,self.ocr,key,model,previous);state[p.name]="done";pp.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding="utf-8");sig.progress.emit(idx+1,f"{p.name} → {len(regs)} 區")
            return str(outdir)
        w=Worker(job);w.s.progress.connect(lambda n,m:(self.pb.setValue(n),self.statusBar().showMessage(m)));w.s.ok.connect(lambda d:QMessageBox.information(self,"整本完成",f"中文版已輸出到：\n{d}"));w.s.err.connect(self.error);QThreadPool.globalInstance().start(w)
    def error(self,t):self.statusBar().showMessage("錯誤");QMessageBox.critical(self,"錯誤",t[-5000:])
def main():
    app=QApplication(sys.argv);app.setStyle("Fusion");w=Main();w.show();sys.exit(app.exec())
