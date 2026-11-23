# Baixar vídeos YouTube
# Dois cliques para abrir. Na primeira vez ele instala sozinho o que precisa.

import os
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog

# ======================= cores e fontes =======================
BRANCO = "#FFFFFF"
FUNDO = "#EEEDEA"
PAINEL = "#F1F5FD"
TEXTO = "#1A1D23"
TEXTO_2 = "#6B7080"
TEXTO_3 = "#9A9EA8"
BORDA = "#E3E3DF"
AZUL = "#2B63EB"
AZUL_HOVER = "#1F51CC"
AZUL_CLARO = "#EAF0FE"
AZUL_SEL = "#F6F8FF"
AZUL_PROGRESSO = "#5B87F0"
CINZA_BTN = "#EFEFEC"
CINZA_BTN_HOVER = "#E4E4E0"
CINZA_ICONE = "#F1F1EE"
AMARELO = "#F2BE2C"
AMARELO_BORDA = "#C99A17"
ESCURO = "#1F2229"
VERDE = "#16A34A"
VERDE_HOVER = "#12873D"
VERDE_CLARO = "#EAF7EE"
VERMELHO = "#D92D20"
DESLIGADO = "#C3C8D2"

if os.name == "nt":
    F, FB = "Segoe UI", "Segoe UI Semibold"
elif sys.platform == "darwin":
    F, FB = "Helvetica Neue", "Helvetica Neue"
else:
    F, FB = "DejaVu Sans", "DejaVu Sans"

S = 1.0  # escala de tela (ajustada ao abrir)


def px(v):
    return int(round(v * S))


def fonte(tam, negrito=False):
    return (FB if negrito else F, -px(tam), "bold" if (negrito and FB == F) else "normal")


# ======================= dependências e arquivos =======================
DEPENDENCIAS = ["yt-dlp[default]", "imageio-ffmpeg", "deno", "pillow"]
PADRAO_LINK = re.compile(r"(youtube\.com/|youtu\.be/)", re.I)

QUALIDADES_VIDEO = [(1080, "1080p — Alta qualidade"), (720, "720p — Recomendado"),
                    (480, "480p — Econômico"), (360, "360p — Mais leve")]
QUALIDADES_AUDIO = [(192, "MP3 192 kbps — Boa qualidade"), (128, "MP3 128 kbps — Arquivo menor")]


def instalar_dependencias():
    flags = 0x08000000 if os.name == "nt" else 0  # sem janela preta no Windows
    base = [sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check"]
    try:
        subprocess.run(base + ["--upgrade"] + DEPENDENCIAS, check=True, creationflags=flags)
    except Exception:
        subprocess.run(base + DEPENDENCIAS, check=True, creationflags=flags)


def recurso(nome):
    """Arquivo que vem junto com o programa (dentro do .exe ou ao lado do .pyw)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    caminho = os.path.join(base, nome)
    return caminho if os.path.exists(caminho) else None


def caminho_deno():
    """Motor de JavaScript que o yt-dlp precisa para o YouTube."""
    p = recurso("deno.exe" if os.name == "nt" else "deno")
    if p:
        return p
    try:
        import deno
        return deno.find_deno_bin()
    except Exception:
        import shutil
        return shutil.which("deno")


def pasta_padrao():
    downloads = os.path.join(os.path.expanduser("~"), "Downloads")
    return downloads if os.path.isdir(downloads) else os.path.expanduser("~")


def abrir(caminho):
    try:
        if os.name == "nt":
            os.startfile(caminho)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", caminho])
        else:
            subprocess.Popen(["xdg-open", caminho])
    except Exception:
        pass


def erro_amigavel(e):
    msg = str(e).lower()
    if "private video" in msg:
        return "Esse vídeo é privado. Só quem é dono pode ver."
    if "confirm your age" in msg or "age-restricted" in msg or "inappropriate for some users" in msg:
        return "Esse vídeo tem restrição de idade e pede login. Não dá para baixar."
    if "not a bot" in msg or "confirm you" in msg:
        return "O YouTube pediu uma verificação. Espere alguns minutos e tente de novo."
    if "video unavailable" in msg or "has been removed" in msg or "no longer available" in msg:
        return "Esse vídeo não está disponível. Ele pode ter sido apagado."
    if "members-only" in msg or "join this channel" in msg:
        return "Esse vídeo é só para membros do canal. Não dá para baixar."
    if "live event" in msg or "is live" in msg or "premieres in" in msg:
        return "Esse vídeo é uma transmissão ao vivo que ainda não terminou. Tente depois."
    if "unsupported url" in msg or "is not a valid url" in msg:
        return "Esse link não parece ser de um vídeo do YouTube. Confira e tente de novo."
    if any(p in msg for p in ("getaddrinfo", "connection", "timed out", "network", "resolve")):
        return "Parece que a internet caiu. Verifique a conexão e tente de novo."
    return "Não foi possível baixar este vídeo. Feche o programa, abra de novo e tente mais uma vez."


def opcoes_base():
    import imageio_ffmpeg
    o = {
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "windowsfilenames": True,
        "ffmpeg_location": imageio_ffmpeg.get_ffmpeg_exe(),
    }
    deno = caminho_deno()
    if deno:
        o["js_runtimes"] = {"deno": {"path": deno}}
    return o


def formato_video(h):
    return (f"bv*[vcodec^=avc1][height<={h}]+ba[ext=m4a]/bv*[height<={h}][ext=mp4]+ba[ext=m4a]/"
            f"b[height<={h}][ext=mp4]/bv*[height<={h}]+ba/b[height<={h}]/b")


def tamanho_estimado(info, tipo, q):
    """Tamanho aproximado do arquivo, em texto (ex.: '84 MB')."""
    if not info:
        return "—"
    dur = info.get("duration") or 0
    if tipo == "audio":
        b = q * 1000 / 8 * dur
    else:
        fmts = info.get("formats") or []
        vids = [f for f in fmts if f.get("vcodec") not in (None, "none") and f.get("height")
                and f["height"] <= q and (f.get("filesize") or f.get("filesize_approx"))]
        if not vids:
            return "—"
        vids.sort(key=lambda f: (f["height"], (f.get("vcodec") or "").startswith("avc1"),
                                 f.get("tbr") or 0))
        v = vids[-1]
        b = v.get("filesize") or v.get("filesize_approx")
        if v.get("acodec") in (None, "none"):
            auds = [f for f in fmts if f.get("vcodec") in (None, "none") and f.get("acodec") not in (None, "none")
                    and (f.get("filesize") or f.get("filesize_approx"))]
            auds.sort(key=lambda f: (f.get("ext") == "m4a", f.get("abr") or 0))
            if auds:
                b += auds[-1].get("filesize") or auds[-1].get("filesize_approx")
    if not b:
        return "—"
    mb = b / 1024 / 1024
    return f"{mb / 1024:.1f} GB".replace(".", ",") if mb >= 1024 else f"{max(1, round(mb))} MB"


def duracao_txt(seg):
    if not seg:
        return ""
    seg = int(seg)
    h, m, s = seg // 3600, seg % 3600 // 60, seg % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


# ======================= imagens (Pillow) =======================
def imagem_placeholder(w, h):
    from PIL import Image, ImageDraw, ImageFilter
    im = Image.new("RGB", (w, h), (34, 42, 56))
    d = ImageDraw.Draw(im)
    d.ellipse([-w * 0.15, h * 0.05, w * 0.55, h * 1.1], fill=(44, 78, 150))
    d.ellipse([w * 0.55, h * 0.35, w * 1.15, h * 1.3], fill=(150, 138, 66))
    return im.filter(ImageFilter.GaussianBlur(w / 9))


def compor_miniatura(img, w, h, r):
    """Recorta a imagem para caber (w x h) e arredonda os cantos de cima."""
    from PIL import Image, ImageDraw, ImageTk
    if img is None:
        img = imagem_placeholder(w, h)
    img = img.convert("RGB")
    iw, ih = img.size
    esc = max(w / iw, h / ih)
    img = img.resize((max(w, int(iw * esc + 0.5)), max(h, int(ih * esc + 0.5))), Image.LANCZOS)
    iw, ih = img.size
    img = img.crop(((iw - w) // 2, (ih - h) // 2, (iw - w) // 2 + w, (ih - h) // 2 + h)).convert("RGBA")
    k = 4  # suaviza a borda arredondada
    mask = Image.new("L", (w * k, h * k), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w * k, (h + r) * k], radius=r * k, fill=255)
    img.putalpha(mask.resize((w, h), Image.LANCZOS))
    return ImageTk.PhotoImage(img)


def baixar_miniatura(url):
    import io
    import urllib.request
    from PIL import Image
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return Image.open(io.BytesIO(r.read()))


def logo(tam):
    from PIL import Image, ImageTk
    p = recurso("logo_cliente_download.png") or recurso("logo_cliente.png") or recurso("icone.png")
    if not p:
        return None
    return ImageTk.PhotoImage(Image.open(p).resize((tam, tam), Image.LANCZOS))


# ======================= componentes desenhados =======================
def rrect(c, x1, y1, x2, y2, r, **kw):
    """Retângulo com cantos realmente redondos (curva exata, sem achatar)."""
    import math
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    pts = []
    passos = max(4, int(r / 1.5))
    for cx, cy, a0 in ((x2 - r, y1 + r, -90), (x2 - r, y2 - r, 0), (x1 + r, y2 - r, 90), (x1 + r, y1 + r, 180)):
        for i in range(passos + 1):
            a = math.radians(a0 + 90 * i / passos)
            pts += [cx + r * math.cos(a), cy + r * math.sin(a)]
    return c.create_polygon(pts, **kw)


def forma_lisa(w, h, r, cor, borda=None, esp=0, pct=None, cor_pct=None):
    """Imagem de um retângulo arredondado com bordas suaves (antisserrilhado)."""
    from PIL import Image, ImageDraw, ImageTk
    k = 4
    W, H = max(1, w * k), max(1, h * k)
    R = min(r * k, W // 2, H // 2)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if borda and esp:
        e = int(esp * k)
        d.rounded_rectangle([0, 0, W - 1, H - 1], R, fill=borda)
        d.rounded_rectangle([e, e, W - 1 - e, H - 1 - e], max(0, R - e), fill=cor)
    else:
        d.rounded_rectangle([0, 0, W - 1, H - 1], R, fill=cor)
    if pct:
        cam = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(cam).rounded_rectangle([0, 0, W - 1, H - 1], R, fill=cor_pct)
        xk = max(1, int(W * min(pct, 100) / 100))
        im.alpha_composite(cam.crop((0, 0, xk, H)), (0, 0))
    return ImageTk.PhotoImage(im.resize((w, h), Image.LANCZOS))


def descendentes(w):
    for f in w.winfo_children():
        yield f
        yield from descendentes(f)


class Cartao(tk.Canvas):
    """Caixa com cantos arredondados; o conteúdo vai em .dentro"""

    def __init__(self, pai, fundo, cor=BRANCO, borda=BORDA, raio=12, pad=14, espessura=1):
        super().__init__(pai, bg=fundo, highlightthickness=0, bd=0)
        self.cor, self.borda, self.raio, self.esp = cor, borda, px(raio), espessura
        p = pad if isinstance(pad, tuple) else (pad,) * 4
        self.pl, self.pt, self.pr, self.pb = (px(v) for v in p)
        self.dentro = tk.Frame(self, bg=cor)
        self.janela = self.create_window(self.pl, self.pt, window=self.dentro, anchor="nw")
        self.dentro.bind("<Configure>", lambda e: self._ajustar())
        self.bind("<Configure>", lambda e: self._desenhar())

    def _ajustar(self):
        self.config(height=self.dentro.winfo_reqheight() + self.pt + self.pb)
        if not self.winfo_ismapped() or self.winfo_width() <= 1:
            self.config(width=self.dentro.winfo_reqwidth() + self.pl + self.pr)

    def _desenhar(self):
        w, h = self.winfo_width(), self.winfo_height()
        self.delete("fundo")
        if w <= 2 or h <= 2:
            return
        self._img = forma_lisa(w, h, self.raio, self.cor, self.borda, self.esp)
        self.create_image(0, 0, image=self._img, anchor="nw", tags="fundo")
        self.tag_lower("fundo")
        self.itemconfig(self.janela, width=max(1, w - self.pl - self.pr))

    def colorir(self, cor=None, borda=None, espessura=None):
        antiga = self.cor
        if cor:
            self.cor = cor
            for w in [self.dentro, *descendentes(self.dentro)]:
                try:
                    if w.cget("bg") == antiga:
                        w.config(bg=cor)
                except tk.TclError:
                    pass
        if borda:
            self.borda = borda
        if espessura is not None:
            self.esp = espessura
        self._desenhar()

    def ao_clicar(self, func):
        for w in [self, self.dentro, *descendentes(self.dentro)]:
            w.bind("<Button-1>", lambda e: func())
            w.config(cursor="hand2")


class Botao(tk.Canvas):
    """Botão arredondado, com ícone opcional e barra de progresso."""

    def __init__(self, pai, fundo, texto, comando, cor=AZUL, hover=AZUL_HOVER, cor_texto=BRANCO,
                 altura=48, largura=None, raio=10, tam=15, icone=None):
        super().__init__(pai, bg=fundo, highlightthickness=0, bd=0, height=px(altura),
                         width=px(largura) if largura else 10, cursor="hand2")
        self.texto, self.comando, self.cor, self.hover = texto, comando, cor, hover
        self.cor_texto, self.raio, self.tam, self.icone = cor_texto, px(raio), tam, icone
        self.ativo, self.sobre, self.pct = True, False, None
        self.bind("<Configure>", lambda e: self.desenhar())
        self.bind("<Enter>", lambda e: self._hover(True))
        self.bind("<Leave>", lambda e: self._hover(False))
        self.bind("<Button-1>", lambda e: self.ativo and self.comando())

    def _hover(self, s):
        self.sobre = s
        self.desenhar()

    def desenhar(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 2:
            return
        base = (self.hover if self.sobre else self.cor) if self.ativo else DESLIGADO
        if self.pct is not None:
            base = AZUL_PROGRESSO
        self._img = forma_lisa(w, h, self.raio, base, pct=self.pct if self.pct else None, cor_pct=self.cor)
        self.create_image(0, 0, image=self._img, anchor="nw")
        cor_t = self.cor_texto if (self.ativo or self.pct is not None) else BRANCO
        t = self.create_text(0, h / 2, text=self.texto, fill=cor_t, font=fonte(self.tam, True), anchor="w")
        x1, _, x2, _ = self.bbox(t)
        tw = x2 - x1
        gap = px(10) if self.icone else 0
        iw = px(self.tam) if self.icone else 0
        x0 = (w - tw - iw - gap) / 2
        if self.icone:
            self.icone(self, x0 + iw / 2, h / 2, iw, cor_t)
        self.coords(t, x0 + iw + gap, h / 2)

    def mudar(self, texto=None, ativo=None, pct="manter"):
        if texto is not None:
            self.texto = texto
        if ativo is not None:
            self.ativo = ativo
            self.config(cursor="hand2" if ativo else "arrow")
        if pct != "manter":
            self.pct = pct
        self.desenhar()


# ---- ícones desenhados (não dependem de fontes do sistema) ----
def ic_download(c, x, y, s, cor):
    lw = max(2, int(s / 9))
    c.create_line(x, y - s * .45, x, y + s * .15, fill=cor, width=lw, capstyle="round")
    c.create_line(x - s * .3, y - s * .12, x, y + s * .18, x + s * .3, y - s * .12, fill=cor, width=lw,
                  capstyle="round", joinstyle="round")
    c.create_line(x - s * .45, y + s * .45, x + s * .45, y + s * .45, fill=cor, width=lw, capstyle="round")


def ic_colar(c, x, y, s, cor):
    lw = max(1, int(s / 11))
    rrect(c, x - s * .35, y - s * .35, x + s * .35, y + s * .5, s * .12, fill="", outline=cor, width=lw)
    rrect(c, x - s * .18, y - s * .5, x + s * .18, y - s * .25, s * .06, fill="", outline=cor, width=lw)


def ic_play(c, x, y, s, cor, cheio=False):
    pts = [x - s * .3, y - s * .4, x + s * .4, y, x - s * .3, y + s * .4]
    c.create_polygon(pts, fill=cor if cheio else "", outline=cor, width=max(1.5, s / 9), joinstyle="round")


def ic_musica(c, x, y, s, cor):
    lw = max(1.5, s / 9)
    c.create_line(x - s * .2, y + s * .3, x - s * .2, y - s * .4, x + s * .35, y - s * .5, x + s * .35, y + s * .2,
                  fill=cor, width=lw, joinstyle="round")
    c.create_oval(x - s * .45, y + s * .15, x - s * .15, y + s * .45, outline=cor, width=lw)
    c.create_oval(x + s * .1, y + s * .05, x + s * .4, y + s * .35, outline=cor, width=lw)


def ic_pasta(c, x, y, s, cor):
    lw = max(1, s / 10)
    c.create_line(x - s * .5, y + s * .35, x - s * .5, y - s * .35, x - s * .1, y - s * .35, x, y - s * .22,
                  x + s * .5, y - s * .22, x + s * .5, y + s * .35, x - s * .5, y + s * .35, fill=cor, width=lw,
                  joinstyle="round")


def ic_escudo(c, x, y, s, cor):
    lw = max(1.5, s / 10)
    c.create_line(x, y - s * .5, x + s * .42, y - s * .32, x + s * .38, y + s * .1, x, y + s * .5,
                  x - s * .38, y + s * .1, x - s * .42, y - s * .32, x, y - s * .5, fill=cor, width=lw,
                  joinstyle="round", smooth=False)
    c.create_line(x - s * .17, y, x - s * .03, y + s * .14, x + s * .2, y - s * .14, fill=cor, width=lw,
                  capstyle="round", joinstyle="round")


def icone_canvas(pai, fundo, desenho, tam=18, cor=TEXTO_2, caixa=None, cor_caixa=None):
    """Pequeno canvas com um ícone; opcionalmente dentro de um quadrado arredondado."""
    lado = px(caixa or tam + 4)
    c = tk.Canvas(pai, width=lado, height=lado, bg=fundo, highlightthickness=0, bd=0)
    if caixa:
        rrect(c, 0, 0, lado - 1, lado - 1, px(12), fill=cor_caixa, outline=cor_caixa)
    desenho(c, lado / 2, lado / 2, px(tam), cor)
    return c


def passo(pai, numero, texto, fundo=BRANCO):
    linha = tk.Frame(pai, bg=fundo)
    d = px(26)
    c = tk.Canvas(linha, width=d, height=d, bg=fundo, highlightthickness=0)
    c.create_oval(1, 1, d - 1, d - 1, fill=ESCURO, outline=ESCURO)
    c.create_text(d / 2, d / 2, text=str(numero), fill=BRANCO, font=fonte(12, True))
    c.pack(side="left")
    tk.Label(linha, text=texto, font=fonte(16, True), bg=fundo, fg=TEXTO).pack(side="left", padx=(px(12), 0))
    return linha


# ======================= tela principal =======================
class App:
    def __init__(self, root):
        self.root = root
        self.fila = queue.Queue()
        self.baixando = False
        self.tipo = "video"
        self.qualidade = 720
        self.pasta = pasta_padrao()
        self.info = None
        self.miniatura_pil = None
        self.pedido_previa = 0
        self.agendado = None
        self.ultimo_arquivo = None
        self.detalhes = ""
        self.imagens = {}

        root.title("Baixar vídeos Youtube")
        root.configure(bg=FUNDO)
        root.resizable(False, False)

        janela = tk.Frame(root, bg=BRANCO)
        janela.pack(fill="both", expand=True)

        # ---------- cabeçalho ----------
        cab = tk.Frame(janela, bg=BRANCO, padx=px(32), pady=px(12))
        cab.pack(fill="x")
        self.imagens["logo"] = logo(px(52))
        if self.imagens["logo"]:
            tk.Label(cab, image=self.imagens["logo"], bg=BRANCO).pack(side="left")
        tk.Label(cab, text="Baixar vídeos Youtube", font=fonte(16, True), bg=BRANCO, fg=TEXTO).pack(
            side="left", padx=(px(12), 0))
        tk.Frame(janela, bg=BORDA, height=1).pack(fill="x")

        corpo = tk.Frame(janela, bg=BRANCO)
        corpo.pack(fill="both", expand=True)

        # ---------- coluna da esquerda ----------
        esq = tk.Frame(corpo, bg=BRANCO, padx=px(44), pady=px(36), width=px(626))
        esq.pack(side="left", fill="y")
        esq.pack_propagate(False)
        tk.Frame(corpo, bg=BORDA, width=1).pack(side="left", fill="y")
        dir_ = tk.Frame(corpo, bg=PAINEL, padx=px(40), pady=px(36), width=px(490))
        dir_.pack(side="left", fill="both", expand=True)
        dir_.pack_propagate(False)

        tk.Label(esq, text="Seus vídeos favoritos,\nprontos para baixar.", font=fonte(38, True), bg=BRANCO,
                 fg=TEXTO, justify="left").pack(anchor="w")
        tk.Label(esq, text="Cole o link, escolha o formato e pronto. Sem menus complicados.", font=fonte(15),
                 bg=BRANCO, fg=TEXTO_2).pack(anchor="w", pady=(px(10), px(28)))

        # passo 1
        l1 = tk.Frame(esq, bg=BRANCO)
        l1.pack(fill="x")
        passo(l1, 1, "Cole o link do vídeo").pack(side="left")
        self.aviso_link = tk.Label(l1, text="", font=fonte(13, True), bg=BRANCO, fg=AZUL)
        self.aviso_link.pack(side="right")

        self.caixa_link = Cartao(esq, BRANCO, borda=BORDA, raio=20, pad=7)
        self.caixa_link.pack(fill="x", pady=(px(12), px(26)))
        d = self.caixa_link.dentro
        icone_canvas(d, BRANCO, ic_play, tam=11, cor=TEXTO_3).pack(side="left", padx=(px(12), px(6)))
        self.entrada = tk.Entry(d, font=fonte(15), relief="flat", bd=0, bg=BRANCO, fg=TEXTO,
                                insertbackground=TEXTO, highlightthickness=0)
        self.entrada.pack(side="left", fill="x", expand=True, ipady=px(9))
        Botao(d, BRANCO, "Colar", self.colar, cor=CINZA_BTN, hover=CINZA_BTN_HOVER, cor_texto=TEXTO,
              altura=40, largura=94, raio=16, tam=14, icone=ic_colar).pack(side="right")
        self.entrada.bind("<KeyRelease>", lambda e: self.validar_link())
        self.entrada.bind("<FocusIn>", lambda e: self.caixa_link.colorir(borda=AZUL))
        self.entrada.bind("<FocusOut>", lambda e: self.validar_link())

        # passo 2
        passo(esq, 2, "Escolha o formato").pack(anchor="w")
        grade = tk.Frame(esq, bg=BRANCO)
        grade.pack(fill="x", pady=(px(12), px(26)))
        grade.columnconfigure(0, weight=1, uniform="f")
        grade.columnconfigure(1, weight=1, uniform="f")
        self.op_video = self.opcao(grade, ic_play, "Vídeo", "Imagem + áudio", "video")
        self.op_audio = self.opcao(grade, ic_musica, "Só áudio", "Arquivo MP3", "audio")
        self.op_video.grid(row=0, column=0, sticky="we", padx=(0, px(6)))
        self.op_audio.grid(row=0, column=1, sticky="we", padx=(px(6), 0))

        # passo 3
        passo(esq, 3, "Selecione a qualidade").pack(anchor="w")
        l3 = tk.Frame(esq, bg=BRANCO)
        l3.pack(fill="x", pady=(px(12), px(14)))
        l3.columnconfigure(0, weight=1)
        self.seletor = Cartao(l3, BRANCO, raio=20, pad=6)
        self.seletor.grid(row=0, column=0, sticky="we", padx=(0, px(12)))
        sd = self.seletor.dentro
        self.rot_qual = tk.Label(sd, text="", font=fonte(15, True), bg=BRANCO, fg=TEXTO, anchor="w")
        self.rot_qual.pack(side="left", fill="x", expand=True, padx=(px(11), 0), pady=px(9))
        seta = tk.Canvas(sd, width=px(20), height=px(20), bg=BRANCO, highlightthickness=0)
        seta.create_line(px(5), px(8), px(10), px(13), px(15), px(8), fill=TEXTO_2, width=max(1.5, px(1.6)),
                         capstyle="round", joinstyle="round")
        seta.pack(side="right", padx=px(11))
        self.seletor.ao_clicar(self.abrir_qualidades)
        self.botao = Botao(l3, BRANCO, "Baixar agora", self.iniciar, altura=52, largura=190, raio=20,
                           tam=15, icone=ic_download)
        self.botao.grid(row=0, column=1, sticky="nse")

        linha_pasta = tk.Frame(esq, bg=BRANCO)
        linha_pasta.pack(fill="x")
        icone_canvas(linha_pasta, BRANCO, ic_pasta, tam=13, cor=TEXTO_3).pack(side="left")
        self.rot_pasta = tk.Label(linha_pasta, text="", font=fonte(13), bg=BRANCO, fg=TEXTO_2)
        self.rot_pasta.pack(side="left", padx=(px(6), px(8)))
        alterar = tk.Label(linha_pasta, text="Alterar", font=fonte(13, True) + ("underline",), bg=BRANCO,
                           fg=TEXTO, cursor="hand2")
        alterar.pack(side="left")
        alterar.bind("<Button-1>", lambda e: self.trocar_pasta())

        self.status = tk.Label(esq, text="", font=fonte(13), bg=BRANCO, fg=TEXTO_2, wraplength=px(530),
                               justify="left")
        self.status.pack(anchor="w", pady=(px(12), 0))
        self.link_detalhes = tk.Label(esq, text="copiar detalhes do erro", font=fonte(12) + ("underline",),
                                      bg=BRANCO, fg=AZUL, cursor="hand2")
        self.link_detalhes.bind("<Button-1>", lambda e: self.copiar_detalhes())

        # ---------- coluna da direita: prévia ----------
        tk.Label(dir_, text="P R É V I A   D O   A R Q U I V O", font=fonte(11, True), bg=PAINEL,
                 fg=TEXTO_3).pack(anchor="w", pady=(px(4), px(16)))
        self.card = Cartao(dir_, PAINEL, raio=22, pad=(1, 0, 1, 16), borda=BORDA)
        self.card.pack(fill="x")
        cd = self.card.dentro
        self.mini_w, self.mini_h = px(408), px(230)
        self.mini = tk.Canvas(cd, width=self.mini_w, height=self.mini_h, bg=PAINEL, highlightthickness=0)
        self.mini.pack(fill="x")
        info = tk.Frame(cd, bg=BRANCO, padx=px(19), pady=px(18))
        info.pack(fill="x")
        self.rot_titulo = tk.Label(info, text="", font=fonte(16, True), bg=BRANCO, fg=TEXTO, anchor="w",
                                   justify="left", wraplength=px(360))
        self.rot_titulo.pack(anchor="w")
        self.rot_site = tk.Label(info, text="", font=fonte(13), bg=BRANCO, fg=TEXTO_3)
        self.rot_site.pack(anchor="w", pady=(px(2), px(14)))
        tk.Frame(info, bg=BORDA, height=1).pack(fill="x", pady=(0, px(14)))
        dados = tk.Frame(info, bg=BRANCO)
        dados.pack(fill="x")
        self.valores = {}
        for i, nome in enumerate(("Formato", "Qualidade", "Tamanho")):
            dados.columnconfigure(i, weight=1, uniform="d")
            col = tk.Frame(dados, bg=BRANCO)
            col.grid(row=0, column=i, sticky="w")
            tk.Label(col, text=nome, font=fonte(13), bg=BRANCO, fg=TEXTO_2).pack(anchor="w")
            self.valores[nome] = tk.Label(col, text="—", font=fonte(14, True), bg=BRANCO, fg=TEXTO)
            self.valores[nome].pack(anchor="w", pady=(px(2), 0))

        # resultado (aparece quando termina)
        self.res = Cartao(dir_, PAINEL, cor=VERDE_CLARO, borda="#BFE5CB", raio=20, pad=16)
        self.res_txt = tk.Label(self.res.dentro, text="", font=fonte(14, True), bg=VERDE_CLARO, fg="#14532D",
                                anchor="w")
        self.res_txt.pack(anchor="w")
        bts = tk.Frame(self.res.dentro, bg=VERDE_CLARO)
        bts.pack(fill="x", pady=(px(10), 0))
        Botao(bts, VERDE_CLARO, "Abrir o arquivo", lambda: abrir(self.ultimo_arquivo or self.pasta), cor=VERDE,
              hover=VERDE_HOVER, altura=38, largura=136, raio=16, tam=13).pack(side="left")
        Botao(bts, VERDE_CLARO, "Abrir a pasta", lambda: abrir(self.pasta), cor=BRANCO, hover="#F3F3F0",
              cor_texto=TEXTO, altura=38, largura=116, raio=16, tam=13).pack(side="left", padx=px(6))
        Botao(bts, VERDE_CLARO, "Baixar outro", self.novo, cor=BRANCO, hover="#F3F3F0", cor_texto=TEXTO,
              altura=38, largura=106, raio=16, tam=13).pack(side="left")

        self.seguro = Cartao(dir_, PAINEL, cor="#F9FBFF", raio=20, pad=16)
        self.seguro.pack(fill="x", pady=(px(18), 0))
        sg = self.seguro.dentro
        icone_canvas(sg, "#F9FBFF", ic_escudo, tam=16, cor=AZUL, caixa=34, cor_caixa=AZUL_CLARO).pack(
            side="left", padx=(0, px(12)))
        txt = tk.Frame(sg, bg="#F9FBFF")
        txt.pack(side="left")
        tk.Label(txt, text="Download seguro", font=fonte(13, True), bg="#F9FBFF", fg=TEXTO).pack(anchor="w")
        tk.Label(txt, text="Nenhum histórico ou dado pessoal é armazenado.", font=fonte(12), bg="#F9FBFF",
                 fg=TEXTO_2).pack(anchor="w")

        # ---------- rodapé ----------
        rod = tk.Frame(root, bg=FUNDO, padx=px(16), pady=px(8))
        rod.pack(fill="x")
        tk.Label(rod, text="Baixe apenas conteúdos que você tem permissão para usar.", font=fonte(11),
                 bg=FUNDO, fg=TEXTO_2).pack(side="left")
        tk.Label(rod, text="© Ana Pinheiro. Todos os direitos reservados.", font=fonte(11), bg=FUNDO,
                 fg=TEXTO_2).pack(side="right")

        # estado inicial
        root.geometry(f"{px(1118)}x{px(744)}")
        self.escolher("video")
        self.atualizar_pasta()
        self.mostrar_previa()
        root.bind("<FocusIn>", lambda e: self.colar_automatico())
        root.bind("<Return>", lambda e: self.iniciar())
        root.after(100, self.ler_fila)
        root.after(300, self.colar_automatico)
        self.centralizar()

    # ---------- partes da tela ----------
    def opcao(self, pai, desenho, titulo, sub, tipo):
        c = Cartao(pai, BRANCO, raio=20, pad=14)
        d = c.dentro
        c.icone_box = tk.Canvas(d, width=px(44), height=px(44), bg=BRANCO, highlightthickness=0)
        c.icone_box.pack(side="left")
        c.desenho = desenho
        t = tk.Frame(d, bg=BRANCO)
        t.pack(side="left", padx=(px(12), 0), pady=px(4))
        tk.Label(t, text=titulo, font=fonte(15, True), bg=BRANCO, fg=TEXTO).pack(anchor="w")
        tk.Label(t, text=sub, font=fonte(13), bg=BRANCO, fg=TEXTO_2).pack(anchor="w")
        c.radio = tk.Canvas(d, width=px(20), height=px(20), bg=BRANCO, highlightthickness=0)
        c.radio.pack(side="right", anchor="n")
        c.ao_clicar(lambda: self.escolher(tipo))
        return c

    def desenhar_opcao(self, c, sel):
        c.colorir(cor=AZUL_SEL if sel else BRANCO, borda=AZUL if sel else BORDA, espessura=1)
        b = c.icone_box
        b.delete("all")
        lado = px(44)
        fundo = AZUL_CLARO if sel else CINZA_ICONE
        rrect(b, 0, 0, lado - 1, lado - 1, px(14), fill=fundo, outline=fundo)
        c.desenho(b, lado / 2, lado / 2, px(16), AZUL if sel else TEXTO_2)
        r = c.radio
        r.delete("all")
        n = px(20)
        if sel:
            r.create_oval(1, 1, n - 2, n - 2, outline=AMARELO_BORDA, width=max(1, px(1.5)), fill=AZUL_SEL)
            r.create_oval(px(5), px(5), n - px(6), n - px(6), fill=AMARELO, outline=AMARELO)
        else:
            r.create_oval(1, 1, n - 2, n - 2, outline="#B9BCC4", width=max(1, px(1.2)))

    def mostrar_previa(self, carregando=False):
        c = self.mini
        c.delete("all")
        w, h = self.mini_w, self.mini_h
        self.imagens["mini"] = compor_miniatura(self.miniatura_pil, w, h, px(22))
        c.create_image(0, 0, image=self.imagens["mini"], anchor="nw")
        r = px(28)
        c.create_oval(w / 2 - r, h / 2 - r, w / 2 + r, h / 2 + r, fill=BRANCO, outline=BRANCO)
        ic_play(c, w / 2 + px(2), h / 2, px(20), AZUL)
        info = self.info
        dur = duracao_txt(info.get("duration")) if info else ""
        if dur:
            t = c.create_text(0, 0, text=dur, font=fonte(12, True), fill=BRANCO, anchor="se")
            x1, y1, x2, y2 = c.bbox(t)
            bw, bh = x2 - x1 + px(14), y2 - y1 + px(8)
            rrect(c, w - px(12) - bw, h - px(12) - bh, w - px(12), h - px(12), px(9), fill="#1C1C1C",
                  outline="#1C1C1C")
            c.coords(t, w - px(12) - px(7), h - px(12) - px(4))
            c.tag_raise(t)
        if carregando:
            self.rot_titulo.config(text="Carregando a prévia…", fg=TEXTO_2)
            self.rot_site.config(text="")
        elif info:
            self.rot_titulo.config(text=info.get("title") or "Vídeo", fg=TEXTO)
            self.rot_site.config(text=info.get("uploader") or "youtube.com")
        else:
            self.rot_titulo.config(text="Cole um link para ver a prévia", fg=TEXTO_2)
            self.rot_site.config(text="O título e o tamanho aparecem aqui")
        self.atualizar_dados()

    def atualizar_dados(self):
        lista = QUALIDADES_VIDEO if self.tipo == "video" else QUALIDADES_AUDIO
        self.valores["Formato"].config(text="MP4" if self.tipo == "video" else "MP3")
        self.valores["Qualidade"].config(text=f"{self.qualidade}p" if self.tipo == "video"
                                         else f"{self.qualidade} kbps")
        self.valores["Tamanho"].config(text=tamanho_estimado(self.info, self.tipo, self.qualidade))
        rotulo = dict(lista).get(self.qualidade, str(self.qualidade))
        self.rot_qual.config(text=rotulo)

    # ---------- utilidades ----------
    def centralizar(self):
        self.root.update_idletasks()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        x = max(0, (self.root.winfo_screenwidth() - w) // 2)
        y = max(0, (self.root.winfo_screenheight() - h) // 3)
        self.root.geometry(f"+{x}+{y}")

    def atualizar_pasta(self):
        if self.pasta == pasta_padrao():
            self.rot_pasta.config(text="Será salvo na sua pasta de Downloads")
        else:
            p = self.pasta if len(self.pasta) < 45 else "…" + self.pasta[-44:]
            self.rot_pasta.config(text=f"Será salvo em {p}")

    def mostrar_status(self, texto, cor=TEXTO_2):
        self.status.config(text=texto, fg=cor)

    def copiar_detalhes(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.detalhes)
        self.link_detalhes.config(text="✓ copiado — cole numa mensagem para quem te ajuda")

    # ---------- passo 1 ----------
    def colar(self):
        try:
            texto = self.root.clipboard_get().strip()
        except tk.TclError:
            texto = ""
        if not texto:
            self.aviso_link.config(text="Copie o link no YouTube primeiro", fg=VERMELHO)
            return
        self.entrada.delete(0, "end")
        self.entrada.insert(0, texto)
        self.validar_link()

    def colar_automatico(self):
        if self.entrada.get().strip() or self.baixando:
            return
        try:
            texto = self.root.clipboard_get().strip()
        except tk.TclError:
            return
        if PADRAO_LINK.search(texto) and " " not in texto:
            self.entrada.insert(0, texto)
            self.validar_link()

    def validar_link(self):
        texto = self.entrada.get().strip()
        if not texto:
            self.aviso_link.config(text="")
            self.caixa_link.colorir(borda=BORDA)
            return False
        if PADRAO_LINK.search(texto):
            self.aviso_link.config(text="✓  Link válido", fg=AZUL)
            self.caixa_link.colorir(borda=AZUL)
            self.agendar_previa(texto)
            return True
        self.aviso_link.config(text="✗  Não é um link do YouTube", fg=VERMELHO)
        self.caixa_link.colorir(borda=VERMELHO)
        return False

    # ---------- prévia ----------
    def agendar_previa(self, url):
        if self.info and self.info.get("_link") == url:
            return
        if self.agendado:
            self.root.after_cancel(self.agendado)
        self.agendado = self.root.after(600, lambda: self.buscar_previa(url))

    def buscar_previa(self, url):
        self.agendado = None
        self.pedido_previa += 1
        n = self.pedido_previa
        self.info, self.miniatura_pil = None, None
        self.mostrar_previa(carregando=True)
        threading.Thread(target=self._previa, args=(url, n), daemon=True).start()

    def _previa(self, url, n):
        try:
            import yt_dlp
            with yt_dlp.YoutubeDL(opcoes_base()) as ydl:
                info = ydl.extract_info(url, download=False)
            info["_link"] = url
            img = None
            if info.get("thumbnail"):
                try:
                    img = baixar_miniatura(info["thumbnail"])
                except Exception:
                    img = None
            self.fila.put(("previa", (n, info, img)))
        except Exception as e:
            self.fila.put(("previa_erro", (n, e)))

    # ---------- passos 2 e 3 ----------
    def escolher(self, tipo):
        self.tipo = tipo
        self.desenhar_opcao(self.op_video, tipo == "video")
        self.desenhar_opcao(self.op_audio, tipo == "audio")
        lista = self.qualidades_disponiveis()
        valores = [q for q, _ in lista]
        if self.qualidade not in valores:
            self.qualidade = 720 if (tipo == "video" and 720 in valores) else valores[0]
        self.atualizar_dados()

    def qualidades_disponiveis(self):
        if self.tipo == "audio":
            return QUALIDADES_AUDIO
        if not self.info:
            return QUALIDADES_VIDEO
        alturas = [f.get("height") for f in self.info.get("formats") or []
                   if f.get("vcodec") not in (None, "none") and f.get("height")]
        maior = max(alturas) if alturas else 1080
        lista = [(q, r) for q, r in QUALIDADES_VIDEO if q <= maior]
        return lista or [(maior, f"{maior}p — Melhor disponível")]

    def abrir_qualidades(self):
        m = tk.Menu(self.root, tearoff=0, font=fonte(14), bg=BRANCO, fg=TEXTO, activebackground=AZUL_CLARO,
                    activeforeground=TEXTO, bd=0)
        for q, rotulo in self.qualidades_disponiveis():
            m.add_command(label=("✓  " if q == self.qualidade else "     ") + rotulo,
                          command=lambda q=q: self.mudar_qualidade(q))
        x = self.seletor.winfo_rootx()
        y = self.seletor.winfo_rooty() + self.seletor.winfo_height() + px(4)
        try:
            m.tk_popup(x, y)
        finally:
            m.grab_release()

    def mudar_qualidade(self, q):
        self.qualidade = q
        self.atualizar_dados()

    def trocar_pasta(self):
        p = filedialog.askdirectory(initialdir=self.pasta)
        if p:
            self.pasta = p
            self.atualizar_pasta()

    def iniciar(self):
        if self.baixando:
            return
        if not self.validar_link():
            if not self.entrada.get().strip():
                self.aviso_link.config(text="Cole o link primeiro", fg=VERMELHO)
                self.caixa_link.colorir(borda=VERMELHO)
            return
        self.baixando = True
        self.res.pack_forget()
        self.seguro.pack(fill="x", pady=(px(18), 0))
        self.link_detalhes.pack_forget()
        self.mostrar_status("")
        self.botao.mudar(texto="Procurando…", ativo=False, pct=0)
        os.makedirs(self.pasta, exist_ok=True)
        threading.Thread(target=self.baixar, daemon=True,
                         args=(self.entrada.get().strip(), self.tipo, self.qualidade, self.pasta)).start()

    def novo(self):
        self.res.pack_forget()
        self.seguro.pack(fill="x", pady=(px(18), 0))
        self.entrada.delete(0, "end")
        self.info, self.miniatura_pil = None, None
        self.validar_link()
        self.mostrar_previa()
        self.mostrar_status("Pronto para o próximo. Copie outro link no YouTube.")
        self.entrada.focus()

    def baixar(self, url, tipo, q, pasta):
        import yt_dlp

        def gancho(d):
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                if total:
                    self.fila.put(("progresso", min(99, d.get("downloaded_bytes", 0) * 100 / total)))
            elif d["status"] == "finished":
                self.fila.put(("finalizando", None))

        opcoes = opcoes_base()
        opcoes.update({"outtmpl": os.path.join(pasta, "%(title)s.%(ext)s"), "progress_hooks": [gancho]})
        if tipo == "video":
            opcoes.update({"format": formato_video(q), "merge_output_format": "mp4"})
        else:
            opcoes.update({"format": "ba/b", "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": str(q)}]})
        try:
            with yt_dlp.YoutubeDL(opcoes) as ydl:
                info = ydl.extract_info(url, download=True)
            arquivo = None
            baixados = info.get("requested_downloads") or []
            if baixados:
                arquivo = baixados[0].get("filepath")
            if arquivo and tipo == "audio" and not arquivo.lower().endswith(".mp3"):
                arquivo = os.path.splitext(arquivo)[0] + ".mp3"
            if arquivo and not os.path.exists(arquivo):
                arquivo = None
            self.fila.put(("sucesso", (info.get("title") or "Seu vídeo", arquivo)))
        except Exception as e:
            self.fila.put(("erro", (erro_amigavel(e), str(e))))

    # ---------- mensagens do segundo plano ----------
    def ler_fila(self):
        try:
            while True:
                tipo, valor = self.fila.get_nowait()
                if tipo == "progresso":
                    self.botao.mudar(texto=f"Baixando… {valor:.0f}%", pct=valor)
                elif tipo == "finalizando":
                    self.botao.mudar(texto="Finalizando…", pct=99)
                elif tipo == "previa":
                    n, info, img = valor
                    if n == self.pedido_previa:
                        self.info, self.miniatura_pil = info, img
                        self.escolher(self.tipo)
                        self.mostrar_previa()
                elif tipo == "previa_erro":
                    n, e = valor
                    if n == self.pedido_previa:
                        self.info = None
                        self.mostrar_previa()
                        self.rot_titulo.config(text="Não deu para carregar a prévia", fg=TEXTO_2)
                        self.rot_site.config(text=erro_amigavel(e))
                elif tipo == "sucesso":
                    titulo, arquivo = valor
                    self.ultimo_arquivo = arquivo
                    oque = "Vídeo baixado" if self.tipo == "video" else "Áudio baixado"
                    self.res_txt.config(text=f"✓  {oque} com sucesso!")
                    self.seguro.pack_forget()
                    self.res.pack(fill="x", pady=(px(18), 0))
                    self.fim()
                elif tipo == "erro":
                    amigavel, tecnico = valor
                    self.mostrar_status("✗  " + amigavel, VERMELHO)
                    self.detalhes = tecnico
                    self.link_detalhes.config(text="copiar detalhes do erro")
                    self.link_detalhes.pack(anchor="w", pady=(px(2), 0))
                    self.fim()
        except queue.Empty:
            pass
        self.root.after(100, self.ler_fila)

    def fim(self):
        self.baixando = False
        self.botao.mudar(texto="Baixar agora", ativo=True, pct=None)


# ======================= abertura =======================
def iniciar_app(raiz):
    for w in raiz.winfo_children():
        w.destroy()
    App(raiz)


def main():
    global S
    if os.name == "nt":
        try:  # texto nítido em telas de alta resolução
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    raiz = tk.Tk()
    S = max(1.0, raiz.winfo_fpixels("1i") / 96)
    raiz.title("Baixar vídeos Youtube")
    ico = recurso("icone.ico")
    if ico and os.name == "nt":
        try:
            raiz.iconbitmap(default=ico)
        except Exception:
            pass
    elif recurso("icone.png"):
        try:
            raiz.iconphoto(True, tk.PhotoImage(file=recurso("icone.png")))
        except Exception:
            pass

    if getattr(sys, "frozen", False):  # .exe já vem com tudo dentro
        iniciar_app(raiz)
    else:
        # tela de espera enquanto instala/atualiza os componentes
        raiz.configure(bg=BRANCO)
        raiz.geometry(f"{px(420)}x{px(160)}")
        tk.Label(raiz, text="Preparando o programa…", font=fonte(18, True), bg=BRANCO, fg=TEXTO).pack(
            pady=(px(40), px(6)))
        aviso = tk.Label(raiz, text="Na primeira vez pode levar 1 ou 2 minutos.", font=fonte(13), bg=BRANCO,
                         fg=TEXTO_2)
        aviso.pack()
        resultado = {}

        def trabalhar():
            try:
                instalar_dependencias()
                resultado["ok"] = True
            except Exception:
                resultado["ok"] = False

        t = threading.Thread(target=trabalhar, daemon=True)
        t.start()

        def esperar():
            if t.is_alive():
                raiz.after(200, esperar)
                return
            try:
                import PIL  # noqa: F401
                import yt_dlp  # noqa: F401
                iniciar_app(raiz)
            except ImportError:
                aviso.config(text="Não consegui preparar. Verifique a internet e abra de novo.", fg=VERMELHO)

        esperar()
    raiz.mainloop()


if __name__ == "__main__":
    main()
