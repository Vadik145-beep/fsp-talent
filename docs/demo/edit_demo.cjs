// Склейка демо-видео: вырезает паузы (cut), ускоряет отмеченные куски (speed), склеивает фазы в один MP4 (H.264).
//
//   node docs/demo/edit_demo.cjs --out DIR --dst путь/к/fsp-talent-demo.mp4 [--dry]
//
// Берёт DIR/<фаза>.webm и DIR/<фаза>.events.json от record_demo.cjs, ffmpeg запускается в Docker
// (образ linuxserver/ffmpeg, переопределить — FFMPEG_IMAGE). Печатает таймкоды титров в итоговом видео.
const fs = require('fs')
const path = require('path')
const { execFileSync } = require('child_process')

const arg = (k, d) => {
  const i = process.argv.indexOf(k)
  return i > 0 ? process.argv[i + 1] : d
}
const OUT = path.resolve(arg('--out', 'demo-out'))
const DST = path.resolve(arg('--dst', path.join(OUT, 'fsp-talent-demo.mp4')))
const DRY = process.argv.includes('--dry')
const IMAGE = process.env.FFMPEG_IMAGE || 'linuxserver/ffmpeg'
const PHASES = (arg('--phases', 'register,candidate,recruiter,invite,accept,apply,admin')).split(',')
// Сдвиг: видео Playwright начинается чуть раньше, чем скрипт засекает T0.
const OFFSET = Number(arg('--offset', '0.25'))
const MARGIN = 0.12

function segmentsOf(events) {
  const segs = []
  let keepFrom = 0
  let cutDepth = 0
  let speed = 1
  const end = events.find((e) => e.type === 'end').t
  const close = (t) => {
    if (keepFrom !== null && t - keepFrom > 0.25) segs.push({ a: keepFrom, b: t, speed })
  }
  for (const e of events) {
    if (e.type === 'cut_start') {
      if (cutDepth === 0) close(e.t + MARGIN)
      cutDepth += 1
      keepFrom = null
    } else if (e.type === 'cut_end') {
      cutDepth = Math.max(0, cutDepth - 1)
      if (cutDepth === 0) keepFrom = e.t - MARGIN
    } else if (e.type === 'speed_start' || e.type === 'speed_end') {
      if (cutDepth === 0 && keepFrom !== null) {
        close(e.t)
        keepFrom = e.t
      }
      speed = e.type === 'speed_start' ? e.factor : 1
    }
  }
  if (cutDepth === 0 && keepFrom !== null) close(end)
  return segs
}

const fmt = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`
const cuts = [] // {ph, a, b, speed, hold}
let outT = 0
const marks = []
for (const ph of PHASES) {
  const meta = JSON.parse(fs.readFileSync(path.join(OUT, `${ph}.events.json`), 'utf8'))
  const segs = segmentsOf(meta.events)
  for (const e of meta.events.filter((x) => x.type === 'title')) {
    let acc = outT
    for (const s of segs) {
      if (e.t >= s.b) acc += (s.b - s.a) / s.speed
      else {
        if (e.t > s.a) acc += (e.t - s.a) / s.speed
        break
      }
    }
    marks.push(`${fmt(acc)}  ${e.text}`)
  }
  // hold — заморозить последний кадр фазы на N секунд (если фаза оборвалась слишком рано)
  const hold = meta.events.find((x) => x.type === 'hold')
  segs.forEach((s, k) => {
    const h = hold && k === segs.length - 1 ? hold.sec : 0
    cuts.push({ ph, a: s.a + OFFSET, b: s.b + OFFSET, speed: s.speed, hold: h })
    outT += (s.b - s.a) / s.speed + h
  })
}
console.log(`сегментов: ${cuts.length}, длительность ≈ ${fmt(outT)} (${outT.toFixed(1)} с)`)
console.log('таймкоды титров:\n' + marks.join('\n'))
if (DRY) process.exit(0)

fs.mkdirSync(path.dirname(DST), { recursive: true })
const docker = (args, entry) => execFileSync('docker', ['run', '--rm', '-v', `${OUT}:/work`, '-v', `${path.dirname(DST)}:/dst`,
  ...(entry ? ['--entrypoint', entry] : []), IMAGE, ...args], { stdio: 'inherit', env: { ...process.env, MSYS_NO_PATHCONV: '1' } })
const X264 = '-c:v libx264 -threads 4 -pix_fmt yuv420p'
// Проход 1: webm от Playwright (VP8, редкие ключевые кадры) → промежуточный H.264 с ключевым кадром каждую секунду,
// чтобы резать быстро и точно.
const lines = ['set -e', 'cd /work', 'mkdir -p seg']
for (const ph of PHASES) {
  const src = path.join(OUT, `${ph}.webm`)
  const mid = path.join(OUT, `${ph}.inter.mp4`)
  if (fs.existsSync(mid) && fs.statSync(mid).mtimeMs > fs.statSync(src).mtimeMs) continue
  lines.push(`echo "промежуточный: ${ph}"`)
  lines.push(`ffmpeg -y -hide_banner -loglevel error -i ${ph}.webm -r 25 ${X264} -preset veryfast -crf 14 -g 25 -keyint_min 25 ${ph}.inter.mp4`)
}
// Проход 2: каждый кусок — свой файл (обрезка, ускорение, заморозка), одинаковые параметры кодирования.
const list = []
cuts.forEach((c, k) => {
  const name = `seg/${String(k).padStart(3, '0')}.mp4`
  const vf = [`setpts=(PTS-STARTPTS)/${c.speed}`, 'fps=30']
  if (c.hold) vf.push(`tpad=stop_mode=clone:stop_duration=${c.hold}`)
  lines.push(`ffmpeg -y -hide_banner -loglevel error -ss ${c.a.toFixed(2)} -to ${c.b.toFixed(2)} -i ${c.ph}.inter.mp4 -an -vf "${vf.join(',')}" ${X264} -preset medium -crf 24 -g 60 ${name}`)
  list.push(`file '${name}'`)
})
fs.writeFileSync(path.join(OUT, 'concat.txt'), list.join('\n') + '\n')
// Проход 3: склейка без перекодирования.
lines.push(`echo "склейка ${cuts.length} кусков"`)
lines.push(`ffmpeg -y -hide_banner -loglevel error -f concat -safe 0 -i concat.txt -c copy -movflags +faststart /dst/${path.basename(DST)}`)
fs.writeFileSync(path.join(OUT, 'edit.sh'), lines.join('\n') + '\n')
docker(['/work/edit.sh'], 'sh')
const mb = fs.statSync(DST).size / 1024 / 1024
console.log(`готово: ${DST}, ${mb.toFixed(1)} МБ`)
