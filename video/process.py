"""Забързва видео, добавя логото на ЦПО и субтитри (стил като в cards.py).

Употреба: [SUBS=субтитри.srt] [CARDS=папка] python3 process.py вход.mp4 изход.mp4 [скорост=1.25] [logo-cpo.png]
"""
import os, subprocess, sys, tempfile, json
from PIL import Image

src, out = sys.argv[1], sys.argv[2]
speed = float(sys.argv[3]) if len(sys.argv) > 3 else 1.25
logo_path = sys.argv[4] if len(sys.argv) > 4 else os.path.join(os.path.dirname(__file__), 'logo-cpo.png')
tmp = tempfile.mkdtemp()

def run(*a): subprocess.run(a, check=True)

info = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
    '-show_entries', 'stream=width,height', '-of', 'json', src]))['streams'][0]
W, H = info['width'], info['height']; k = min(W, H) / 1080; VERT = H > W

# бяло лого (както на крайния кадър), височина 80px при 1080p
lg = Image.open(logo_path).convert('RGBA'); lg = lg.crop(lg.getbbox())
w = Image.new('RGBA', lg.size, (255, 255, 255, 0)); w.putalpha(lg.getchannel('A'))
lh = int((90 if VERT else 80) * k); w = w.resize((int(lg.width * lh / lg.height), lh), Image.LANCZOS)
w.save(f'{tmp}/logo.png')

# 1) забързване
fast = f'{tmp}/fast.mp4'
run('ffmpeg', '-y', '-v', 'error', '-i', src, '-filter_complex',
    f'[0:v]setpts=PTS/{speed}[v];[0:a]atempo={speed}[a]', '-map', '[v]', '-map', '[a]',
    '-c:v', 'libx264', '-crf', '18', '-c:a', 'aac', fast)

# 2) субтитри: готов .srt (SUBS=файл.srt, времената за оригиналната скорост) или разпознаване на говора
class Seg:
    def __init__(s, a, b, t): s.start, s.end, s.text = a, b, t
def read_srt(p):
    def sec(x): h, m, r = x.strip().replace(',', '.').split(':'); return int(h) * 3600 + int(m) * 60 + float(r)
    for b in open(p, encoding='utf-8-sig').read().strip().split('\n\n'):
        l = b.strip().splitlines(); a, z = l[1].split('-->')
        yield Seg(sec(a) / speed, sec(z) / speed, ' '.join(l[2:]))
if os.environ.get('SUBS'):
    segs = list(read_srt(os.environ['SUBS']))
else:
    # huggingface.co е блокиран в облачната среда, затова моделът се тегли от огледалото
    os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')
    from faster_whisper import WhisperModel
    model = WhisperModel(os.environ.get('WHISPER_MODEL', 'medium'), compute_type='int8')
    import numpy as np  # звукът се подава като масив (PyAV в средата е несъвместим)
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', fast, '-ac', '1', '-ar', '16000', '-f', 's16le', '-'])
    segs, _ = model.transcribe(np.frombuffer(raw, np.int16).astype(np.float32) / 32768, language='bg', vad_filter=True)

def ts(t):
    h, m = divmod(t, 3600); m, s = divmod(m, 60); return f'{int(h)}:{int(m):02d}:{s:05.2f}'

# стил: бял Inter SemiBold 54, полупрозрачна черна кутия долу в центъра
fs = int((66 if VERT else 54) * k); mv = int(H * 0.2) if VERT else int(125 * k)  # вертикално: над бутоните на Reels/TikTok
ass = [f'[Script Info]\nScriptType: v4.00+\nPlayResX: {W}\nPlayResY: {H}\n\n[V4+ Styles]',
       'Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV',
       f'Style: Default,Inter SemiBold,{fs},&H00FFFFFF,&H69000000,&H69000000,0,3,{int(14*k)},0,2,{int(60*k)},{int(60*k)},{mv}',
       '\n[Events]\nFormat: Layer, Start, End, Style, Text']
srt = []
for i, s in enumerate(segs, 1):
    t = s.text.strip()
    ass.append(f'Dialogue: 0,{ts(s.start)},{ts(s.end)},Default,{t}')
    srt.append(f'{i}\n{ts(s.start).replace(".", ",")}0 --> {ts(s.end).replace(".", ",")}0\n{t}\n')
open(f'{tmp}/subs.ass', 'w').write('\n'.join(ass) + '\n')
open(os.path.splitext(out)[0] + '.srt', 'w').write('\n'.join(srt))

# 3) лого горе вдясно + субтитри
x, y = int(W - 50 * k - w.width), int((150 if VERT else 50) * k)
run('ffmpeg', '-y', '-v', 'error', '-i', fast, '-i', f'{tmp}/logo.png', '-filter_complex',
    f'[0:v][1:v]overlay={x}:{y},subtitles={tmp}/subs.ass:fontsdir=/usr/share/fonts/opentype/inter[v]',
    '-map', '[v]', '-map', '0:a', '-c:v', 'libx264', '-crf', '18', '-c:a', 'copy', f'{tmp}/main.mp4')

# 4) начален (3 с) и финален (4 с) кадър от cards.py, ако CARDS=папка с intro.png и end.png
cards = os.environ.get('CARDS')
if not cards:
    os.replace(f'{tmp}/main.mp4', out)
else:
    sc = f'scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p,setsar=1'
    run('ffmpeg', '-y', '-v', 'error',
        '-loop', '1', '-t', '3', '-i', f'{cards}/intro.png', '-i', f'{tmp}/main.mp4',
        '-loop', '1', '-t', '4', '-i', f'{cards}/end.png',
        '-f', 'lavfi', '-t', '3', '-i', 'anullsrc=r=48000:cl=stereo',
        '-f', 'lavfi', '-t', '4', '-i', 'anullsrc=r=48000:cl=stereo', '-filter_complex',
        f'[0:v]{sc}[a0];[1:v]{sc}[a1];[2:v]{sc}[a2];[1:a]aresample=48000,aformat=channel_layouts=stereo[m];'
        '[a0][3:a][a1][m][a2][4:a]concat=n=3:v=1:a=1[v][a]',
        '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-crf', '18', '-c:a', 'aac', out)
print('Готово:', out)
