"""Субтитри + лого на ЦПО + забързване, в стила на „Мокри помещения“.

Употреба: [ASS=субтитри.ass | SUBS=субтитри.srt] [CARDS=папка] [LOGO_HUE=330 | LOGO_COLOR=1CB5B5] [LOGO_SIDE=right|left]
          python3 process.py вход.mp4 изход.mp4 [скорост=1.1] [logo-cpo.png]

Субтитрите се изгарят върху оригиналния клип (таймингите са спрямо него), после се забързва.
Без ASS/SUBS говорът се разпознава автоматично (faster-whisper, български).
"""
import colorsys, json, os, subprocess, sys, tempfile
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
src, out = sys.argv[1], sys.argv[2]
speed = float(sys.argv[3]) if len(sys.argv) > 3 else 1.1
logo_path = sys.argv[4] if len(sys.argv) > 4 else os.path.join(HERE, 'logo-cpo.png')
tmp = tempfile.mkdtemp()

def run(*a): subprocess.run(a, check=True)

info = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
    '-show_entries', 'stream=width,height', '-of', 'json', src]))['streams'][0]
W, H = info['width'], info['height']; k = W / 1080

# лого: оригиналните цветове, или с друг нюанс (LOGO_HUE в градуси, 330 = циклама)
lg = Image.open(logo_path).convert('RGBA'); lg = lg.crop(lg.getbbox())
hue = os.environ.get('LOGO_HUE')
if hue:
    a = np.asarray(lg).astype(float) / 255
    hsv = np.array([colorsys.rgb_to_hsv(*p) for p in a[..., :3].reshape(-1, 3)])
    hsv[:, 0] = float(hue) / 360; hsv[:, 1] = np.maximum(hsv[:, 1], 0.85); hsv[:, 2] = 0.6 + 0.4 * hsv[:, 2]
    rgb = np.array([colorsys.hsv_to_rgb(*p) for p in hsv]).reshape(a.shape[:2] + (3,))
    lg = Image.fromarray((np.dstack([rgb, a[..., 3]]) * 255).astype(np.uint8), 'RGBA')
col = os.environ.get('LOGO_COLOR')  # цялото лого в един цвят, напр. 1CB5B5 (акцентите в субтитрите)
if col:
    a = np.asarray(lg).astype(float)
    a[..., :3] = [int(col[i:i + 2], 16) for i in (0, 2, 4)]
    lg = Image.fromarray(a.astype(np.uint8), 'RGBA')
lw = int(400 * k); lg = lg.resize((lw, int(lg.height * lw / lg.width)), Image.LANCZOS)
lg.save(f'{tmp}/logo.png')
lx = W - int(50 * k) - lw if os.environ.get('LOGO_SIDE', 'right') == 'right' else int(50 * k)
ly = int(110 * k)

# субтитри
HEAD = f'''[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,Oswald,96,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,6,3,2,70,70,500,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
POP = '{\\fscx85\\fscy85\\t(0,140,\\fscx100\\fscy100)}'

def ts(t):
    h, m = divmod(t, 3600); m, s = divmod(m, 60); return f'{int(h)}:{int(m):02d}:{s:05.2f}'

def segments():
    if os.environ.get('SUBS'):
        def sec(x): h, m, r = x.strip().replace(',', '.').split(':'); return int(h) * 3600 + int(m) * 60 + float(r)
        for b in open(os.environ['SUBS'], encoding='utf-8-sig').read().strip().split('\n\n'):
            l = b.strip().splitlines(); a, z = l[1].split('-->')
            yield sec(a), sec(z), ' '.join(l[2:])
        return
    # huggingface.co е блокиран в облачната среда, затова моделът се тегли от огледалото
    os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')
    from faster_whisper import WhisperModel
    model = WhisperModel(os.environ.get('WHISPER_MODEL', 'medium'), compute_type='int8')
    # звукът се подава като масив (PyAV в средата е несъвместим)
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', src, '-ac', '1', '-ar', '16000', '-f', 's16le', '-'])
    segs, _ = model.transcribe(np.frombuffer(raw, np.int16).astype(np.float32) / 32768, language='bg', vad_filter=True)
    for s in segs: yield s.start, s.end, s.text.strip()

ass = os.environ.get('ASS')
if not ass:
    ass = f'{tmp}/subs.ass'
    with open(ass, 'w', encoding='utf-8') as f:
        f.write(HEAD)
        for a, z, t in segments():
            f.write(f'Dialogue: 0,{ts(a)},{ts(z)},Sub,,0,0,0,,{POP}{t.upper()}\n')

# лого + субтитри върху оригинала, после забързване
fonts = os.path.join(HERE, 'fonts')
run('ffmpeg', '-y', '-v', 'error', '-i', src, '-i', f'{tmp}/logo.png', '-filter_complex',
    f'[0:v]setsar=1,subtitles={ass}:fontsdir={fonts}[s];[1:v]format=rgba,colorchannelmixer=aa=0.95[w];'
    f'[s][w]overlay={lx}:{ly},setpts=PTS/{speed}[v];[0:a]atempo={speed}[a]',
    '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-crf', '18', '-c:a', 'aac', f'{tmp}/main.mp4')

# начален (3 с) и финален (4 с) кадър от cards.py, ако CARDS=папка с intro.png и end.png
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
