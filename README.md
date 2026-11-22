# Baixador do YouTube

Programa simples para baixar vídeos e músicas do YouTube, feito para quem não tem muita familiaridade com computador.

![Tela do programa](docs/tela.png)

## Como usar (Windows)

1. Baixe o programa: **[BaixadorYouTube.exe](../../releases/latest/download/BaixadorYouTube.exe)**
2. Dê dois cliques no arquivo baixado.
   - Se aparecer a tela azul "O Windows protegeu o computador", clique em **Mais informações** e depois em **Executar assim mesmo**. Isso acontece com programas novos que ainda não são conhecidos pelo Windows.
3. Siga os 3 passos da tela:
   1. Cole o link do vídeo (no YouTube: **Compartilhar → Copiar**)
   2. Escolha **Vídeo** ou **Só a música**
   3. Clique em **Baixar agora**

Os arquivos ficam em **Downloads › Vídeos do YouTube**.

## Rodando pelo código (qualquer sistema)

Precisa do [Python](https://www.python.org/downloads/) 3.9 ou mais novo.

```
python Baixador_YouTube.pyw
```

Na primeira vez ele instala sozinho o que precisa (`yt-dlp` e `imageio-ffmpeg`).

## Como o .exe é gerado

O GitHub Actions (`.github/workflows/gerar-exe.yml`) monta o `BaixadorYouTube.exe` automaticamente sempre que o código muda e toda segunda-feira, para sempre usar a versão mais nova do `yt-dlp`. O arquivo fica disponível em **Releases**.

## Aviso

Use apenas para vídeos que você tem direito de baixar, como os seus próprios ou os liberados pelo autor, e respeite os termos de uso do YouTube.
