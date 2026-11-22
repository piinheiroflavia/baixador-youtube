# Baixador de vídeos do YouTube — versão simples e amigável
# Dois cliques para abrir. Na primeira vez ele instala sozinho o que precisa.

import os
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog

# ---------------- aparência ----------------
FUNDO = "#F3F5F9"
CARTAO = "#FFFFFF"
BORDA = "#E2E6EE"
TEXTO = "#1F2430"
TEXTO_2 = "#5B6475"
AZUL = "#2563EB"
AZUL_HOVER = "#1D4ED8"
AZUL_CLARO = "#E8EFFE"
VERDE = "#16A34A"
VERDE_HOVER = "#15803D"
VERDE_CLARO = "#E7F6EC"
VERMELHO = "#DC2626"
VERMELHO_CLARO = "#FDECEC"
CINZA_BOTAO = "#C5CBD6"

FONTE = "Segoe UI" if os.name == "nt" else ("Helvetica" if sys.platform == "darwin" else "DejaVu Sans")

DEPENDENCIAS = ["yt-dlp", "imageio-ffmpeg"]
PADRAO_LINK = re.compile(r"(youtube\.com/|youtu\.be/)", re.I)

FORMATO_VIDEO = {
    # prefere H.264 em MP4, que abre em qualquer computador/celular
    "format": "bv*[vcodec^=avc1][height<=1080]+ba[ext=m4a]/bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b",
    "merge_output_format": "mp4",
}
FORMATO_AUDIO = {
    "format": "ba/b",
    "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
}


def instalar_dependencias():
    if getattr(sys, "frozen", False):  # versão .exe já vem com tudo dentro
        return
    flags = 0x08000000 if os.name == "nt" else 0  # sem janela preta no Windows
    base = [sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check"]
    try:
        subprocess.run(base + ["--upgrade"] + DEPENDENCIAS, check=True, creationflags=flags)
    except Exception:
        subprocess.run(base + DEPENDENCIAS, check=True, creationflags=flags)


def pasta_padrao():
    downloads = os.path.join(os.path.expanduser("~"), "Downloads")
    if not os.path.isdir(downloads):
        downloads = os.path.expanduser("~")
    return os.path.join(downloads, "Vídeos do YouTube")


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
    if "private" in msg:
        return "Esse vídeo é privado. Só quem é dono pode ver."
    if "unavailable" in msg or "not available" in msg or "removed" in msg:
        return "Esse vídeo não está disponível. Ele pode ter sido apagado."
    if "sign in" in msg or "age" in msg:
        return "Esse vídeo pede login (por exemplo, por ter restrição de idade). Não dá para baixar."
    if "unsupported url" in msg or "is not a valid url" in msg:
        return "Esse link não parece ser de um vídeo do YouTube. Confira e tente de novo."
    if any(p in msg for p in ("getaddrinfo", "connection", "timed out", "network", "resolve")):
        return "Parece que a internet caiu. Verifique a conexão e tente de novo."
    return "Não foi possível baixar este vídeo. Feche o programa, abra de novo e tente mais uma vez."


# ---------------- componentes ----------------
class Botao(tk.Label):
    """Botão grande e colorido (funciona igual no Windows e no Mac)."""

    def __init__(self, pai, texto, comando, cor=AZUL, cor_hover=AZUL_HOVER, cor_texto="white",
                 tamanho=13, pad=(18, 10), **kw):
        super().__init__(pai, text=texto, bg=cor, fg=cor_texto, cursor="hand2",
                         font=(FONTE, tamanho, "bold"), padx=pad[0], pady=pad[1], **kw)
        self.cor, self.cor_hover, self.comando, self.ativo = cor, cor_hover, comando, True
        self.bind("<Enter>", lambda e: self.ativo and self.config(bg=self.cor_hover))
        self.bind("<Leave>", lambda e: self.ativo and self.config(bg=self.cor))
        self.bind("<Button-1>", lambda e: self.ativo and self.comando())

    def ligar(self, sim=True):
        self.ativo = sim
        self.config(bg=self.cor if sim else CINZA_BOTAO, cursor="hand2" if sim else "arrow")


class Opcao(tk.Frame):
    """Cartão clicável para escolher Vídeo ou Áudio."""

    def __init__(self, pai, simbolo, titulo, descricao, comando):
        super().__init__(pai, bg=CARTAO, highlightthickness=2, highlightbackground=BORDA, cursor="hand2")
        self.s = tk.Label(self, text=simbolo, font=(FONTE, 22), bg=CARTAO, fg=AZUL)
        self.t = tk.Label(self, text=titulo, font=(FONTE, 13, "bold"), bg=CARTAO, fg=TEXTO)
        self.d = tk.Label(self, text=descricao, font=(FONTE, 10), bg=CARTAO, fg=TEXTO_2)
        self.s.pack(pady=(10, 0))
        self.t.pack()
        self.d.pack(pady=(0, 10))
        for w in (self, self.s, self.t, self.d):
            w.bind("<Button-1>", lambda e: comando())

    def marcar(self, sim):
        fundo = AZUL_CLARO if sim else CARTAO
        self.config(bg=fundo, highlightbackground=AZUL if sim else BORDA)
        for w in (self.s, self.t, self.d):
            w.config(bg=fundo)


def titulo_passo(pai, numero, texto):
    linha = tk.Frame(pai, bg=CARTAO)
    c = tk.Canvas(linha, width=30, height=30, bg=CARTAO, highlightthickness=0)
    c.create_oval(2, 2, 28, 28, fill=AZUL, outline=AZUL)
    c.create_text(15, 15, text=str(numero), fill="white", font=(FONTE, 12, "bold"))
    c.pack(side="left")
    tk.Label(linha, text=texto, font=(FONTE, 14, "bold"), bg=CARTAO, fg=TEXTO).pack(side="left", padx=10)
    return linha


# ---------------- aplicativo ----------------
class App:
    def __init__(self, root):
        self.root = root
        self.fila = queue.Queue()
        self.pronto = False
        self.baixando = False
        self.tipo = "video"
        self.pasta = pasta_padrao()
        self.ultimo_arquivo = None

        root.title("Baixar vídeos do YouTube")
        root.configure(bg=FUNDO)
        root.resizable(False, False)

        geral = tk.Frame(root, bg=FUNDO, padx=24, pady=20)
        geral.pack(fill="both", expand=True)

        tk.Label(geral, text="Baixar vídeos do YouTube", font=(FONTE, 20, "bold"),
                 bg=FUNDO, fg=TEXTO).pack(anchor="w")
        tk.Label(geral, text="É só seguir os 3 passos abaixo.", font=(FONTE, 11),
                 bg=FUNDO, fg=TEXTO_2).pack(anchor="w", pady=(0, 14))

        # cartão principal
        card = tk.Frame(geral, bg=CARTAO, highlightthickness=1, highlightbackground=BORDA, padx=22, pady=18)
        card.pack(fill="x")

        # passo 1
        titulo_passo(card, 1, "Cole o link do vídeo").pack(anchor="w")
        tk.Label(card, text="No YouTube, clique em  Compartilhar  e depois em  Copiar.",
                 font=(FONTE, 10), bg=CARTAO, fg=TEXTO_2).pack(anchor="w", padx=40, pady=(2, 8))

        linha = tk.Frame(card, bg=CARTAO)
        linha.pack(fill="x", padx=(40, 0))
        caixa = tk.Frame(linha, bg=CARTAO, highlightthickness=2, highlightbackground=BORDA)
        caixa.pack(side="left", fill="x", expand=True)
        self.entrada = tk.Entry(caixa, font=(FONTE, 12), relief="flat", bg=CARTAO, fg=TEXTO,
                                insertbackground=TEXTO, highlightthickness=0, bd=0)
        self.entrada.pack(fill="x", ipady=8, padx=8)
        self.caixa = caixa
        Botao(linha, "Colar link", self.colar, tamanho=12).pack(side="left", padx=(10, 0))
        self.aviso_link = tk.Label(card, text=" ", font=(FONTE, 10, "bold"), bg=CARTAO, fg=TEXTO_2)
        self.aviso_link.pack(anchor="w", padx=40, pady=(4, 0))
        self.entrada.bind("<KeyRelease>", lambda e: self.validar_link())

        # passo 2
        titulo_passo(card, 2, "O que você quer baixar?").pack(anchor="w", pady=(14, 8))
        opcoes = tk.Frame(card, bg=CARTAO)
        opcoes.pack(fill="x", padx=(40, 0))
        self.op_video = Opcao(opcoes, "▶", "Vídeo", "imagem e som", lambda: self.escolher("video"))
        self.op_audio = Opcao(opcoes, "♪", "Só a música", "arquivo MP3", lambda: self.escolher("audio"))
        self.op_video.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.op_audio.pack(side="left", fill="x", expand=True, padx=(6, 0))

        # passo 3
        titulo_passo(card, 3, "Clique para baixar").pack(anchor="w", pady=(16, 8))
        self.botao = Botao(card, "⬇   BAIXAR AGORA", self.iniciar, cor=VERDE, cor_hover=VERDE_HOVER,
                           tamanho=15, pad=(20, 14))
        self.botao.pack(fill="x", padx=(40, 0))

        # área de progresso / resultado
        self.area = tk.Frame(geral, bg=FUNDO)
        self.area.pack(fill="x", pady=(14, 0))
        self.barra = tk.Canvas(self.area, height=14, bg=BORDA, highlightthickness=0)
        self.barra.pack(fill="x")
        self.barra_cheia = self.barra.create_rectangle(0, 0, 0, 14, fill=AZUL, width=0)
        self.status = tk.Label(self.area, text="", font=(FONTE, 11), bg=FUNDO, fg=TEXTO_2,
                               wraplength=520, justify="left")
        self.status.pack(anchor="w", pady=(6, 0))

        self.resultado = tk.Frame(geral, bg=VERDE_CLARO, padx=16, pady=12)
        self.res_texto = tk.Label(self.resultado, text="", font=(FONTE, 12, "bold"), bg=VERDE_CLARO,
                                  fg="#14532D", wraplength=500, justify="left")
        self.res_texto.pack(anchor="w")
        botoes = tk.Frame(self.resultado, bg=VERDE_CLARO)
        botoes.pack(anchor="w", pady=(10, 0))
        Botao(botoes, "Abrir o arquivo", lambda: abrir(self.ultimo_arquivo or self.pasta),
              cor=VERDE, cor_hover=VERDE_HOVER, tamanho=11).pack(side="left")
        Botao(botoes, "Abrir a pasta", lambda: abrir(self.pasta), cor="white", cor_hover="#F0F2F5",
              cor_texto=TEXTO, tamanho=11).pack(side="left", padx=8)
        Botao(botoes, "Baixar outro", self.novo, cor="white", cor_hover="#F0F2F5",
              cor_texto=TEXTO, tamanho=11).pack(side="left")

        # rodapé
        rodape = tk.Frame(geral, bg=FUNDO)
        rodape.pack(fill="x", pady=(14, 0))
        self.rotulo_pasta = tk.Label(rodape, text="", font=(FONTE, 9), bg=FUNDO, fg=TEXTO_2)
        self.rotulo_pasta.pack(side="left")
        trocar = tk.Label(rodape, text="trocar pasta", font=(FONTE, 9, "underline"), bg=FUNDO,
                          fg=AZUL, cursor="hand2")
        trocar.pack(side="left", padx=6)
        trocar.bind("<Button-1>", lambda e: self.trocar_pasta())
        self.atualizar_rotulo_pasta()

        self.escolher("video")
        self.botao.ligar(False)
        self.mostrar_status("Preparando o programa… (na primeira vez pode levar 1 ou 2 minutos)")

        root.bind("<FocusIn>", lambda e: self.colar_automatico())
        root.bind("<Return>", lambda e: self.iniciar())
        self.centralizar()
        threading.Thread(target=self.preparar, daemon=True).start()
        root.after(100, self.ler_fila)

    # ---------- utilidades de tela ----------
    def centralizar(self):
        self.root.update_idletasks()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        x = (self.root.winfo_screenwidth() - w) // 2
        y = max(20, (self.root.winfo_screenheight() - h) // 3)
        self.root.geometry(f"+{x}+{y}")

    def atualizar_rotulo_pasta(self):
        p = self.pasta
        if len(p) > 55:
            p = "…" + p[-54:]
        self.rotulo_pasta.config(text=f"Os arquivos ficam em: {p}")

    def mostrar_status(self, texto, cor=TEXTO_2):
        self.status.config(text=texto, fg=cor)

    def progresso(self, pct):
        largura = self.barra.winfo_width()
        self.barra.coords(self.barra_cheia, 0, 0, largura * pct / 100, 14)

    # ---------- passo 1 ----------
    def colar(self):
        try:
            texto = self.root.clipboard_get().strip()
        except tk.TclError:
            texto = ""
        if not texto:
            self.aviso("Nada copiado ainda. Copie o link no YouTube primeiro.", VERMELHO)
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
            self.validar_link(auto=True)

    def validar_link(self, auto=False):
        texto = self.entrada.get().strip()
        if not texto:
            self.aviso(" ", TEXTO_2)
            self.caixa.config(highlightbackground=BORDA)
            return False
        if PADRAO_LINK.search(texto):
            self.aviso("✓  Colamos o link que você copiou." if auto else "✓  Link certinho!", VERDE)
            self.caixa.config(highlightbackground=VERDE)
            return True
        self.aviso("✗  Isso não parece um link do YouTube.", VERMELHO)
        self.caixa.config(highlightbackground=VERMELHO)
        return False

    def aviso(self, texto, cor):
        self.aviso_link.config(text=texto, fg=cor)

    # ---------- passo 2 ----------
    def escolher(self, tipo):
        self.tipo = tipo
        self.op_video.marcar(tipo == "video")
        self.op_audio.marcar(tipo == "audio")

    def trocar_pasta(self):
        p = filedialog.askdirectory(initialdir=os.path.dirname(self.pasta))
        if p:
            self.pasta = p
            self.atualizar_rotulo_pasta()

    # ---------- passo 3 ----------
    def iniciar(self):
        if self.baixando or not self.pronto:
            return
        if not self.validar_link():
            if not self.entrada.get().strip():
                self.aviso("Primeiro cole o link do vídeo (passo 1).", VERMELHO)
                self.caixa.config(highlightbackground=VERMELHO)
            return
        self.baixando = True
        self.botao.ligar(False)
        self.botao.config(text="Baixando…")
        self.resultado.pack_forget()
        self.progresso(0)
        os.makedirs(self.pasta, exist_ok=True)
        threading.Thread(target=self.baixar, args=(self.entrada.get().strip(), self.tipo, self.pasta),
                         daemon=True).start()

    def novo(self):
        self.resultado.pack_forget()
        self.entrada.delete(0, "end")
        self.validar_link()
        self.progresso(0)
        self.mostrar_status("Pronto para o próximo. Copie outro link no YouTube.")
        self.entrada.focus()

    # ---------- segundo plano ----------
    def preparar(self):
        try:
            instalar_dependencias()
            self.fila.put(("pronto", None))
        except Exception:
            self.fila.put(("falha_preparo", None))

    def baixar(self, url, tipo, pasta):
        import imageio_ffmpeg
        import yt_dlp

        def gancho(d):
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                if total:
                    pct = min(99, d.get("downloaded_bytes", 0) * 100 / total)
                    self.fila.put(("progresso", pct))
                    self.fila.put(("status", f"Baixando… {pct:.0f}%"))
            elif d["status"] == "finished":
                self.fila.put(("status", "Quase lá, preparando o arquivo…"))

        opcoes = {
            "outtmpl": os.path.join(pasta, "%(title)s.%(ext)s"),
            "noplaylist": True,
            "ffmpeg_location": imageio_ffmpeg.get_ffmpeg_exe(),
            "progress_hooks": [gancho],
            "quiet": True,
            "no_warnings": True,
            "windowsfilenames": True,
        }
        opcoes.update(FORMATO_VIDEO if tipo == "video" else FORMATO_AUDIO)

        try:
            self.fila.put(("status", "Procurando o vídeo…"))
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
            self.fila.put(("erro", erro_amigavel(e)))

    def ler_fila(self):
        try:
            while True:
                tipo, valor = self.fila.get_nowait()
                if tipo == "status":
                    self.mostrar_status(valor)
                elif tipo == "progresso":
                    self.progresso(valor)
                elif tipo == "pronto":
                    self.pronto = True
                    self.botao.ligar(True)
                    self.mostrar_status("Tudo pronto! Siga os passos acima.")
                    self.colar_automatico()
                elif tipo == "falha_preparo":
                    self.mostrar_status("Não consegui preparar o programa. Verifique a internet, "
                                        "feche e abra de novo.", VERMELHO)
                elif tipo == "sucesso":
                    titulo, arquivo = valor
                    self.ultimo_arquivo = arquivo
                    self.progresso(100)
                    self.mostrar_status("")
                    oque = "vídeo" if self.tipo == "video" else "áudio"
                    self.res_texto.config(text=f"✓  Pronto! O {oque} foi baixado:\n{titulo}")
                    self.resultado.pack(fill="x", pady=(10, 0), before=self.rotulo_pasta.master)
                    self.fim()
                elif tipo == "erro":
                    self.progresso(0)
                    self.mostrar_status("✗  " + valor, VERMELHO)
                    self.fim()
        except queue.Empty:
            pass
        self.root.after(100, self.ler_fila)

    def fim(self):
        self.baixando = False
        self.botao.config(text="⬇   BAIXAR AGORA")
        self.botao.ligar(True)


if __name__ == "__main__":
    if os.name == "nt":
        try:  # deixa o texto nítido em telas de alta resolução
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    raiz = tk.Tk()
    App(raiz)
    raiz.mainloop()
