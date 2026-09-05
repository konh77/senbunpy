/* 千分の一の国 — 3D の街(碁盤の目)
 *
 * 街は「シミュレーション履歴の再生装置」。装飾ではない。
 * 月 m の街の状態は必ず series[m] から決まる(docs/ui-plan.md §6.5 の結線表)。
 *
 * 設計の約束:
 *   - 金は空を飛ばない。人が手に持って運ぶ
 *   - 文字は空中に浮かせない。3Dの看板に焼き、必ず**正面玄関側**に付ける
 *   - 街路は碁盤の目。人は交差点を折れて街全体を移動する
 *   - 長距離は車に乗る。歩きだけだと月内に着けない
 *   - 建物に入った人は描画しない
 *
 * three.js は CDN ではなく web/vendor/ に同梱(外部通信ゼロを維持)。
 */

import * as THREE from 'three';
import { RoundedBoxGeometry } from './vendor/RoundedBoxGeometry.js';
import { OrbitControls } from './vendor/OrbitControls.js';
import * as BGU from './vendor/BufferGeometryUtils.js';

// --- 街路の骨格(碁盤の目)---------------------------------------------------

const AVE_Z = [-69, -23, 23, 69];        // 東西の通り(z 一定)。間隔46
const ST_X  = [-104, -52, 0, 52, 104];   // 南北の通り(x 一定)。間隔52
const ROAD_H = 4.6;                      // 車道の半幅
const WALK_OFF = 6.4;                    // 通り芯から歩道までの距離
const CAR_OFF = 2.3;                     // 通り芯から車線までの距離
const TRAIN_Z = -92;

const MONTH_MS = 7200;                   // 1ヶ月 = 6フェーズ × 1.2s
const PHASES = ['労働', '生産', '所得', '消費', '財政', '記録'];
const N_AGENTS = 100;
const MAX_CARS = 22;
const CAR_TRIP = 46;                     // これ以上の道のりは車
const TRAIN_TRIP = 175;                  // これ以上はモノレール
const BEAM_Y = 11.5;                     // 桁の高さ

const C = {
  ground: 0xE9E2CE, road: 0x9E9A90, walk: 0xE4DDC9, line: 0xFFF6D8, grass: 0x8FD44E,
  wall: 0xFFF6E2, wall2: 0xFFE9C9, stone: 0xE3DCC6, glass: 0x9FD8F0, lit: 0xFFD84D,
  coral: 0xFE806F, blue: 0x5684FE, pink: 0xFF96FF, lime: 0xCAFF97,
  lav: 0xD0B9FF, yellow: 0xFFC93D, skin: 0xFFD9B0, jobless: 0xB8B2A6,
  coin: 0xFFC93D, ink: 0x141210,
};
const CLOTHES = [C.blue, C.lime, C.pink, C.yellow, C.lav, C.coral];
const HAIRS = [0x2A2320, 0x8A5A32, 0xB0AAA0, 0x4A3A55];
const ROOFS = [C.coral, C.blue, C.pink, C.lime, C.lav, C.yellow];
const CARS = [C.coral, C.blue, C.yellow, C.lime, C.lav, 0xFFFFFF];

const SKY = [
  [0x8FD3F4, 0xE8F7FF], [0x6EC6F0, 0xDFF3FF], [0xFFC46B, 0xFFEBD2],
  [0xFF8E6E, 0xFFCBA6], [0x5B5FA8, 0xB98CC0], [0x232750, 0x4E4E86],
];
const SUN_COL = [0xFFF3D0, 0xFFFFFF, 0xFFD9A0, 0xFF9E6E, 0x8C90D8, 0x6A6EA8];

const SHOPS = [
  ['食料', 'スーパーまるいち'], ['住居', '千分不動産'],
  ['光熱水道', 'お客さまセンター'], ['交通通信', 'けいたい堂'],
  ['教育', 'せんぶん進学舎'], ['教養娯楽', 'ガチャ堂'],
  ['保健医療', 'こいずみ医院'], ['その他', 'なんでも屋'],
];

// --- 状態 -------------------------------------------------------------------

let renderer, scene, camera, controls, sky, sun, hemi, wrapEl;
let buildings = [], agents = [], cars = [], stations = [], train = null, inst = {}, puffs = [];
let loop = null, trainCars = [];
let lawFx = null, fxMeshes = [];   // 施行中の法律とその可視化物
let simClock = 0;                  // 検証用ステッパの時計(呼び出しをまたいで進む)
let winMat, signs = [];
let run = null, data = null, variant = 'treatment';
let month = 0, phaseT = 0, playing = true, raf = null, last = 0;
let onMonth = null, joblessCount = 0, autoOrbit = true, orbitT = 0, camView = 0;

const _m = new THREE.Matrix4(), _q = new THREE.Quaternion(),
      _p = new THREE.Vector3(), _s = new THREE.Vector3(), _v = new THREE.Vector3();
const HIDDEN = new THREE.Matrix4().makeScale(0, 0, 0);
const TOWN_W = ST_X.at(-1) - ST_X[0] + 64;
const TOWN_D = AVE_Z.at(-1) - AVE_Z[0] + 66;

// --- 初期化 -----------------------------------------------------------------

function init(canvasEl) {
  wrapEl = canvasEl.parentElement;
  renderer = new THREE.WebGLRenderer({ canvas: canvasEl, antialias: true });
  renderer.setPixelRatio(Math.min(2, devicePixelRatio));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;

  scene = new THREE.Scene();
  camera = new THREE.OrthographicCamera(-1, 1, 1, -1, -1500, 1500);

  // 窓のマテリアルは建物より先に作る(共有して夜に一括点灯させるため)
  winMat = new THREE.MeshStandardMaterial({ color: C.glass, roughness: 0.14,
    emissive: new THREE.Color(C.lit), emissiveIntensity: 0 });

  buildSky();
  buildLights();
  buildGround();
  buildTrain();        // 環状の桁。駅の位置決めに loop が要る
  buildStations();     // 位置が固定なので街区より先に建てる
  buildBlocks();       // 駅の footprint を避けて配置する
  buildAgents();
  buildParticles();
  buildControls();

  resize();
  // window の resize だけだと、初期化時にパネルが隠れていて幅0だった場合に
  // その後サイズが付いても二度と呼ばれない。要素そのものを監視する
  new ResizeObserver(() => resize()).observe(wrapEl);
  document.addEventListener('visibilitychange', () => document.hidden ? stop() : start());
  start();
}
const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };

function buildControls() {
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.09;
  controls.minPolarAngle = 0.18;
  controls.maxPolarAngle = Math.PI / 2 - 0.06;   // 地面より下に潜らせない
  controls.minZoom = 0.45; controls.maxZoom = 6;
  controls.target.set(0, 4, 0);
  // ユーザーが触ったら自動旋回をやめる(見て回れるようにする、が主目的)
  controls.addEventListener('start', () => { autoOrbit = false; });
}

// --- 空・光 -----------------------------------------------------------------

function buildSky() {
  const cv = document.createElement('canvas');
  cv.width = 4; cv.height = 128;
  sky = { ctx: cv.getContext('2d'), tex: new THREE.CanvasTexture(cv) };
  sky.tex.colorSpace = THREE.SRGBColorSpace;
  scene.add(new THREE.Mesh(new THREE.SphereGeometry(420, 32, 20),
    new THREE.MeshBasicMaterial({ map: sky.tex, side: THREE.BackSide, depthWrite: false, toneMapped: false })));
  paintSky(0, 0);
}

function paintSky(phase, frac) {
  const a = SKY[phase], b = SKY[(phase + 1) % 6];
  const top = new THREE.Color(a[0]).lerp(new THREE.Color(b[0]), frac);
  const bot = new THREE.Color(a[1]).lerp(new THREE.Color(b[1]), frac);
  const g = sky.ctx.createLinearGradient(0, 0, 0, 128);
  g.addColorStop(0, '#' + top.getHexString());
  g.addColorStop(1, '#' + bot.getHexString());
  sky.ctx.fillStyle = g; sky.ctx.fillRect(0, 0, 4, 128);
  sky.tex.needsUpdate = true;
}

function buildLights() {
  hemi = new THREE.HemisphereLight(0xDFF3FF, 0xC9C2A8, 1.4);
  scene.add(hemi, new THREE.AmbientLight(0xFFF0D8, 0.4));
  sun = new THREE.DirectionalLight(0xFFFFFF, 2.4);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  Object.assign(sun.shadow.camera, { left: -110, right: 110, top: 90, bottom: -90, near: 1, far: 500 });
  sun.shadow.bias = -0.0013; sun.shadow.normalBias = 0.06;
  sun.shadow.camera.updateProjectionMatrix();
  scene.add(sun, sun.target);
}

const toy = (color, o = {}) => new THREE.MeshPhysicalMaterial({
  color, roughness: o.rough ?? 0.42, metalness: 0,
  clearcoat: o.clearcoat ?? 0.6, clearcoatRoughness: o.ccr ?? 0.3,
});

// --- 看板(文字は canvas に焼く)---------------------------------------------

function textTexture(text, opt = {}) {
  const W = 512, H = 128;
  const cv = document.createElement('canvas');
  cv.width = W; cv.height = H;
  const g = cv.getContext('2d');
  g.fillStyle = opt.bg || '#FFFCF5'; g.fillRect(0, 0, W, H);
  g.strokeStyle = '#000'; g.lineWidth = 14; g.strokeRect(7, 7, W - 14, H - 14);
  let size = 64;
  const font = s => `900 ${s}px "Hiragino Kaku Gothic ProN","Noto Sans JP",sans-serif`;
  g.font = font(size);
  while (g.measureText(text).width > W - 52 && size > 12) { size -= 3; g.font = font(size); }
  g.fillStyle = opt.fg || '#000';
  g.textAlign = 'center'; g.textBaseline = 'middle';
  g.fillText(text, W / 2, H / 2 + 2);
  const tex = new THREE.CanvasTexture(cv);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = renderer.capabilities.getMaxAnisotropy();
  return tex;
}

/** 建物の正面(玄関側)に看板を付ける。local 座標で置くのでズレようがない */
function addSign(group, text, w, y, frontZ, opt) {
  const tex = textTexture(text, opt);
  const mat = new THREE.MeshBasicMaterial({ map: tex, toneMapped: false });
  const h = w * 0.25;
  const face = new THREE.Mesh(new THREE.PlaneGeometry(w, h), mat);
  face.position.set(0, y, frontZ + 0.3);
  // 裏面にも同じ文字を入れる。片面だけだと反対側からは黒い板にしか見えない
  const rear = new THREE.Mesh(new THREE.PlaneGeometry(w, h), mat);
  rear.position.set(0, y, frontZ - 0.1);
  rear.rotation.y = Math.PI;
  const board = new THREE.Mesh(new RoundedBoxGeometry(w + 0.3, h + 0.3, 0.34, 2, 0.12), toy(C.ink, { rough: 0.7 }));
  board.position.set(0, y, frontZ + 0.1);
  board.castShadow = true;
  group.add(board, face, rear);
  return { mesh: face, rear, opt };
}

/** 地面に立てる掲示板。債務・求職者数はこれ */
function addPost(x, z, rotY, text, opt) {
  const g = new THREE.Group();
  g.position.set(x, 0, z); g.rotation.y = rotY;
  const post = new THREE.Mesh(new THREE.CylinderGeometry(0.24, 0.28, 6, 10), toy(C.ink, { rough: 0.7 }));
  post.position.y = 3; post.castShadow = true; g.add(post);
  const s = addSign(g, text, 8, 6.6, 0, opt);
  scene.add(g);
  return s;
}

// --- 地面と道路 --------------------------------------------------------------

function buildGround() {
  const base = new THREE.Mesh(new RoundedBoxGeometry(TOWN_W, 3.4, TOWN_D, 4, 1.4),
    toy(C.ground, { rough: 0.95, clearcoat: 0.04 }));
  base.position.y = -1.7; base.receiveShadow = true; scene.add(base);

  const roadMat = toy(C.road, { rough: 1, clearcoat: 0 });
  const walkMat = toy(C.walk, { rough: 1, clearcoat: 0 });
  const lineMat = toy(C.line, { rough: 1, clearcoat: 0 });
  const halfW = TOWN_W / 2 - 3, halfD = TOWN_D / 2 - 3;

  const slab = (mat, w, d, x, z, y) => {
    if (w <= 0.2 || d <= 0.2) return;
    const m = new THREE.Mesh(new THREE.BoxGeometry(w, 0.2, d), mat);
    m.position.set(x, y, z); m.receiveShadow = true; scene.add(m);
  };

  // 車道は通し
  for (const z of AVE_Z) slab(roadMat, halfW * 2, ROAD_H * 2, 0, z, 0.08);
  for (const x of ST_X) slab(roadMat, ROAD_H * 2, halfD * 2, x, 0, 0.09);

  // センターラインは交差点の中には引かない
  const nearAny = (v, arr, r) => arr.some(a => Math.abs(v - a) < r);
  for (const z of AVE_Z)
    for (let x = -halfW + 4; x < halfW - 4; x += 8)
      if (!nearAny(x, ST_X, ROAD_H + 3)) slab(lineMat, 3.6, 0.4, x, z, 0.19);
  for (const x of ST_X)
    for (let z = -halfD + 4; z < halfD - 4; z += 8)
      if (!nearAny(z, AVE_Z, ROAD_H + 3)) slab(lineMat, 0.4, 3.6, x, z, 0.2);

  // 歩道: 交差点を貫通させず、区間と角のパッドに分ける。
  // 以前は通しで描いていたため、横断歩道が歩道スラブの下に隠れていた。
  const PAD = 2.8, EDGE = ROAD_H + PAD;
  const seg = (a, b) => [a, b];
  for (const [ii, z] of AVE_Z.entries()) for (const sz of [-1, 1]) {
    const zz = z + sz * SW;
    const xs = [-halfW, ...ST_X.flatMap(x => [x - EDGE, x + EDGE]), halfW];
    for (let k = 0; k < xs.length; k += 2) {
      const [a, b] = seg(xs[k], xs[k + 1]);
      slab(walkMat, b - a, PAD, (a + b) / 2, zz, 0.14);
    }
  }
  for (const [jj, x] of ST_X.entries()) for (const sx of [-1, 1]) {
    const xx = x + sx * SW;
    const zs = [-halfD, ...AVE_Z.flatMap(z => [z - EDGE, z + EDGE]), halfD];
    for (let k = 0; k < zs.length; k += 2) {
      const [a, b] = seg(zs[k], zs[k + 1]);
      slab(walkMat, PAD, b - a, xx, (a + b) / 2, 0.15);
    }
  }
  // 角のパッド
  for (const x of ST_X) for (const z of AVE_Z)
    for (const sx of [-1, 1]) for (const sz of [-1, 1])
      slab(walkMat, PAD, PAD, x + sx * SW, z + sz * SW, 0.15);

  buildCrossings();
  buildPedGraph();
}

// --- 交差点: 横断歩道と信号機 ------------------------------------------------

const sigMats = {};   // NS/EW × 赤青。共有して一括で切り替える
let nsGreen = true;
const SW = ROAD_H + 1.4;   // 通り芯から歩道の芯まで

function buildCrossings() {
  // ゼブラ。歩く向きに縞が伸びる(渡る方向に平行)。位置は歩行者グラフの
  // 横断辺とぴったり一致させてある(SW = 歩道の芯)
  const zebraMat = new THREE.MeshStandardMaterial({ color: 0xFFFDF0, roughness: 1 });
  // 縞は歩く向きに**直交**して並ぶ(渡りながら1本ずつ跨ぐ)。
  // 以前は歩く向きと平行に描いていて、向きが逆だった。
  const CW = 4.4;                                  // 横断歩道の幅
  const K = [-3.6, -2.16, -0.72, 0.72, 2.16, 3.6]; // 車道の幅(±4.6)の中に6本
  const geoAve = new THREE.BoxGeometry(CW, 0.06, 0.75);  // 東西の通りを渡る縞
  const geoSt = new THREE.BoxGeometry(0.75, 0.06, CW);   // 南北の通りを渡る縞
  const cap = ST_X.length * AVE_Z.length * 2 * K.length;
  const mAve = new THREE.InstancedMesh(geoAve, zebraMat, cap);
  const mSt = new THREE.InstancedMesh(geoSt, zebraMat, cap);
  let a = 0, b = 0;
  for (const ix of ST_X) for (const iz of AVE_Z) {
    for (const sx of [-1, 1]) for (const k of K) {   // 東西の通りを z 方向に渡る
      _m.makeTranslation(ix + sx * SW, 0.22, iz + k);
      mAve.setMatrixAt(a++, _m);
    }
    for (const sz of [-1, 1]) for (const k of K) {   // 南北の通りを x 方向に渡る
      _m.makeTranslation(ix + k, 0.22, iz + sz * SW);
      mSt.setMatrixAt(b++, _m);
    }
  }
  mAve.count = a; mSt.count = b;
  mAve.receiveShadow = true; mSt.receiveShadow = true;
  scene.add(mAve, mSt);

  // 停止線: 進行方向ごとに、横断歩道の手前へ
  const stopMat = new THREE.MeshStandardMaterial({ color: 0xFFFDF0, roughness: 1 });
  const stopAt = (w, d, x, z) => {
    const m = new THREE.Mesh(new THREE.BoxGeometry(w, 0.06, d), stopMat);
    m.position.set(x, 0.22, z); m.receiveShadow = true; scene.add(m);
  };
  for (const ix of ST_X) for (const iz of AVE_Z) {
    // 東西に走る車の停止線(縦棒)。走行車線側の半分だけ
    for (const sx of [-1, 1]) stopAt(0.55, ROAD_H - 0.4, ix + sx * (SW + 2.4), iz - sx * (ROAD_H / 2));
    // 南北に走る車の停止線(横棒)
    for (const sz of [-1, 1]) stopAt(ROAD_H - 0.4, 0.55, ix + sz * (ROAD_H / 2), iz + sz * (SW + 2.4));
  }

  // 信号機。灯のマテリアルは方向グループで共有し、時間で一括切り替え
  for (const g of ['NS', 'EW']) {
    sigMats[g + 'r'] = new THREE.MeshBasicMaterial({ color: 0x3A1512, toneMapped: false });
    sigMats[g + 'g'] = new THREE.MeshBasicMaterial({ color: 0x123A18, toneMapped: false });
  }
  const poleMat = toy(0x4A4A46, { rough: 0.6 });
  const boxMat = toy(0x2E2E2A, { rough: 0.5 });
  for (const ix of ST_X) for (const iz of AVE_Z) {
    for (const [cx, cz, facing] of [[1, 1, 'NS'], [-1, -1, 'EW']]) {
      const G = new THREE.Group();
      G.position.set(ix + cx * (SW + 1.4), 0, iz + cz * (SW + 1.4));
      G.rotation.y = facing === 'NS' ? (cz > 0 ? Math.PI : 0) : (cx > 0 ? -Math.PI / 2 : Math.PI / 2);
      const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.18, 5.6, 8), poleMat);
      pole.position.y = 2.8; pole.castShadow = true; G.add(pole);
      const head = new THREE.Mesh(new RoundedBoxGeometry(2.2, 0.95, 0.6, 2, 0.2), boxMat);
      head.position.set(0.6, 5.35, 0); head.castShadow = true; G.add(head);
      const mk = (dx, mat) => {
        const lens = new THREE.Mesh(new THREE.CircleGeometry(0.3, 14), mat);
        lens.position.set(0.6 + dx, 5.35, 0.32);
        G.add(lens);
      };
      mk(-0.55, sigMats[facing + 'r']);
      mk(0.55, sigMats[facing + 'g']);
      scene.add(G);
    }
  }
}

function updateSignals(nowSec) {
  // 14秒周期。前半は南北が青(= 車は南北に進み、歩行者は東西の通りを渡れる)
  nsGreen = (nowSec % 14) < 6.6;
  sigMats.NSg.color.setHex(nsGreen ? 0x39E75F : 0x123A18);
  sigMats.NSr.color.setHex(nsGreen ? 0x3A1512 : 0xFF4438);
  sigMats.EWg.color.setHex(nsGreen ? 0x123A18 : 0x39E75F);
  sigMats.EWr.color.setHex(nsGreen ? 0xFF4438 : 0x3A1512);
}

/** 'ave' = 東西の通りを渡る(南北が青のとき可) / 'st' = 南北の通りを渡る */
const signalGreen = kind => kind === 'ave' ? nsGreen : !nsGreen;


// --- 街区に建物を置く --------------------------------------------------------

function buildBlocks() {
  const specs = [
    { kind: 'gov', w: 24, h: 12, d: 14, name: '政府庁舎' },
    { kind: 'factory', w: 20, h: 8, d: 12, name: '第一工場' },
    { kind: 'school', w: 17, h: 7.5, d: 11, name: 'せんぶん小学校' },
    { kind: 'office', w: 12, h: 16, d: 10, name: 'せんぶん商事' },
    { kind: 'hello', w: 14, h: 6.4, d: 10, name: 'ハローワーク' },
    ...SHOPS.map(([cat, name]) => ({ kind: 'shop', w: 13, h: 6, d: 10, cat, name })),
    { kind: 'office', w: 11, h: 13, d: 9, name: 'みなみ商会' },
    { kind: 'office', w: 10, h: 11, d: 9, name: 'きた銀行' },
    { kind: 'factory', w: 16, h: 7, d: 11, name: '第二工場' },
    { kind: 'school', w: 14, h: 7, d: 10, name: 'せんぶん中学校' },
    ...Array.from({ length: 34 }, (_, i) => ({
      kind: 'house', w: 8.6 + (i % 3), h: 5.6 + (i % 4) * 1.1, d: 8.2 + (i % 2) })),
  ];

  const cells = [];
  for (let i = 0; i < AVE_Z.length - 1; i++)
    for (let j = 0; j < ST_X.length - 1; j++)
      cells.push({
        i, j,
        x: (ST_X[j] + ST_X[j + 1]) / 2, z: (AVE_Z[i] + AVE_Z[i + 1]) / 2,
        n: AVE_Z[i], s: AVE_Z[i + 1], w: ST_X[j], e: ST_X[j + 1],
        halfW: (ST_X[j + 1] - ST_X[j]) / 2 - (ROAD_H + 2.8),
        halfD: (AVE_Z[i + 1] - AVE_Z[i]) / 2 - (ROAD_H + 2.8),
      });

  // 候補スロット。**必ず通りに面する**ように、街区の4辺に沿ってだけ置く。
  // 以前は街区の内側にも2列目を作っていたため、道路に面さない建物が多かった。
  const SET = ROAD_H + 2.8;                    // 通り芯から建物正面までの距離
  const slots = [];
  for (const cell of cells) {
    for (const off of [0, -16, 16, -8, 8, -23, 23]) {
      slots.push({ cell, dir: 'S', off });     // 南の通りに面する(+z 向き)
      slots.push({ cell, dir: 'N', off });     // 北の通りに面する(-z 向き)
    }
    for (const off of [0, -13, 13]) {
      slots.push({ cell, dir: 'E', off });     // 東の通りに面する(+x 向き)
      slots.push({ cell, dir: 'W', off });     // 西の通りに面する(-x 向き)
    }
  }

  const placed = buildings.slice();   // 先に建てた駅の footprint を含める
  const fits = (x, z, w, d) => !placed.some(b =>
    ((b.fw ?? b.w) + w) / 2 + 1.2 > Math.abs(b.x - x) &&
    ((b.fd ?? b.d) + d) / 2 + 1.2 > Math.abs(b.z - z));

  // 向きごとの配置。ローカル +z が常に正面(玄関)なので、rotY だけ変える
  const PLAN = {
    S: { rotY: 0,             fw: s => s.w, fd: s => s.d },
    N: { rotY: Math.PI,       fw: s => s.w, fd: s => s.d },
    E: { rotY: Math.PI / 2,   fw: s => s.d, fd: s => s.w },
    W: { rotY: -Math.PI / 2,  fw: s => s.d, fd: s => s.w },
  };

  for (const spec of specs) {
    let hit = null;
    for (const sl of slots) {
      if (sl.used) continue;
      const P = PLAN[sl.dir];
      const fw = P.fw(spec), fd = P.fd(spec);
      let x, z, dx = 0, dz = 0;
      if (sl.dir === 'S' || sl.dir === 'N') {
        if (Math.abs(sl.off) + fw / 2 > sl.cell.halfW) continue;
        x = sl.cell.x + sl.off;
        z = sl.dir === 'S' ? sl.cell.s - SET - fd / 2 : sl.cell.n + SET + fd / 2;
        dz = sl.dir === 'S' ? 1 : -1;
      } else {
        if (Math.abs(sl.off) + fd / 2 > sl.cell.halfD) continue;
        z = sl.cell.z + sl.off;
        x = sl.dir === 'E' ? sl.cell.e - SET - fw / 2 : sl.cell.w + SET + fw / 2;
        dx = sl.dir === 'E' ? 1 : -1;
      }
      if (!fits(x, z, fw, fd)) continue;
      hit = { sl, x, z, fw, fd, dx, dz, rotY: P.rotY };
      break;
    }
    if (!hit) continue;                        // 置けないものは置かない(重ねない)
    hit.sl.used = true;

    const g = new THREE.Group();
    g.position.set(hit.x, 0, hit.z);
    g.rotation.y = hit.rotY;
    scene.add(g);
    // 接する歩道と、その区間を挟む2つの角ノード
    const cl = hit.sl.cell, D = hit.sl.dir;
    let acc, accNodes;
    if (D === 'S') { acc = { x: hit.x, z: AVE_Z[cl.i + 1] - SW };
                     accNodes = [nodeId(cl.i + 1, cl.j, 1, -1), nodeId(cl.i + 1, cl.j + 1, -1, -1)]; }
    else if (D === 'N') { acc = { x: hit.x, z: AVE_Z[cl.i] + SW };
                     accNodes = [nodeId(cl.i, cl.j, 1, 1), nodeId(cl.i, cl.j + 1, -1, 1)]; }
    else if (D === 'E') { acc = { x: ST_X[cl.j + 1] - SW, z: hit.z };
                     accNodes = [nodeId(cl.i, cl.j + 1, -1, 1), nodeId(cl.i + 1, cl.j + 1, -1, -1)]; }
    else { acc = { x: ST_X[cl.j] + SW, z: hit.z };
                     accNodes = [nodeId(cl.i, cl.j, 1, 1), nodeId(cl.i + 1, cl.j, 1, -1)]; }

    const b = Object.assign({ x: hit.x, z: hit.z, face: 1, group: g, top: spec.h,
      fw: hit.fw, fd: hit.fd, acc, accNodes,
      door: new THREE.Vector3(hit.x + hit.dx * (spec.d / 2 + 1.4), 0,
                              hit.z + hit.dz * (spec.d / 2 + 1.4)) }, spec);
    drawBuilding(g, b);
    buildings.push(b);
    placed.push(b);
  }

  greenBlocks(cells);

  const gov = buildings.find(b => b.kind === 'gov');
  const hello = buildings.find(b => b.kind === 'hello');
  if (gov) signs.push(Object.assign(
    addPost(gov.door.x + 15, gov.door.z + gov.face * 2, gov.face > 0 ? 0 : Math.PI, '債務 —'), { role: 'debt' }));
  if (hello) signs.push(Object.assign(
    addPost(hello.door.x + 10, hello.door.z + hello.face * 2, hello.face > 0 ? 0 : Math.PI,
      '求職 —', { bg: '#FFC93D' }), { role: 'jobs' }));
}

/** 環状線の4か所に高架駅。
 *  改札棟(地上)→ 内蔵の階段コア → 高架ホーム、の3層構成。
 *  昇降は改札棟の中で行う(外から丸見えの裸の階段を置かない)。
 *  footprint は桁の直下にまとめ、交差点・道路には掛からない。 */
function buildStations() {
  const PF_Y = BEAM_Y - 0.4;

  // 駅は「外周歩道の区間の真ん中」に正対させる。
  // こうすると玄関へ行く道が歩道から真っ直ぐ外へ出るだけになり、
  // 車道を横切る経路が原理的に発生しない。
  const mid = (a, b) => (a + b) / 2;
  const anchors = [
    { name: 'きた駅',   x: mid(ST_X[1] + SW, ST_X[2] - SW), z: AVE_Z[0] - SW, ox: 0, oz: -1,
      nodes: [nodeId(0, 1, 1, -1), nodeId(0, 2, -1, -1)] },
    { name: 'ひがし駅', x: ST_X[4] + SW, z: mid(AVE_Z[1] + SW, AVE_Z[2] - SW), ox: 1, oz: 0,
      nodes: [nodeId(1, 4, 1, 1), nodeId(2, 4, 1, -1)] },
    { name: 'みなみ駅', x: mid(ST_X[2] + SW, ST_X[3] - SW), z: AVE_Z[3] + SW, ox: 0, oz: 1,
      nodes: [nodeId(3, 2, 1, 1), nodeId(3, 3, -1, 1)] },
    { name: 'にし駅',   x: ST_X[0] - SW, z: mid(AVE_Z[1] + SW, AVE_Z[2] - SW), ox: -1, oz: 0,
      nodes: [nodeId(1, 0, -1, 1), nodeId(2, 0, -1, -1)] },
  ];

  for (const A of anchors) {
    // 環状線上で、その歩道の真正面にあたる点を探す
    let bt = 0, bd = Infinity;
    for (let k = 0; k < 3000; k++) {
      const t = k / 3000;
      const q = loop.getPointAt(t);
      if (A.ox === 0) {
        if (Math.sign(q.z) !== A.oz) continue;
        const d = Math.abs(q.x - A.x);
        if (d < bd) { bd = d; bt = t; }
      } else {
        if (Math.sign(q.x) !== A.ox) continue;
        const d = Math.abs(q.z - A.z);
        if (d < bd) { bd = d; bt = t; }
      }
    }
    const q = loop.getPointAt(bt);
    // 駅の中心は歩道と同じ横位置に揃える(玄関への道が真っ直ぐになる)
    const cx = A.ox === 0 ? A.x : q.x;
    const cz = A.ox === 0 ? q.z : A.z;
    const rot = Math.atan2(-A.ox, -A.oz);        // ローカル +z が街の中心を向く

    const g = new THREE.Group();
    g.position.set(cx, 0, cz);
    g.rotation.y = rot;
    scene.add(g);
    const add = (mesh, x, y, z) => { mesh.position.set(x, y, z); mesh.castShadow = true;
                                     mesh.receiveShadow = true; g.add(mesh); return mesh; };
    const conc = toy(0xE0DACA, { rough: 0.85, clearcoat: 0.06 });

    // 改札棟(地上)
    add(new THREE.Mesh(new RoundedBoxGeometry(15, 5.2, 8, 3, 0.4), toy(C.wall2, { rough: 0.5 })), 0, 2.6, 3.6);
    add(new THREE.Mesh(new RoundedBoxGeometry(16, 0.8, 9, 2, 0.3), toy(C.coral, { rough: 0.35 })), 0, 5.55, 3.6);
    add(new THREE.Mesh(new RoundedBoxGeometry(3.2, 3.6, 0.5, 2, 0.14), toy(0x8A5A32)), 0, 1.8, 7.7);
    for (const sx of [-5.2, 5.2])
      add(new THREE.Mesh(new THREE.BoxGeometry(3.4, 2.0, 0.16), winMat), sx, 2.9, 7.66);
    addSign(g, A.name, 9.5, 7.2, 7.6);

    // 階段コア(改札の屋根からホームへ。中に階段がある閉じた箱)
    add(new THREE.Mesh(new RoundedBoxGeometry(5.4, PF_Y - 5.0, 5.2, 2, 0.3),
      toy(C.wall, { rough: 0.55 })), 4.2, 5.0 + (PF_Y - 5.0) / 2, 3.4);
    add(new THREE.Mesh(new THREE.BoxGeometry(2.6, 1.6, 0.16), winMat), 4.2, PF_Y - 2.6, 6.05);

    // 高架ホーム
    add(new THREE.Mesh(new RoundedBoxGeometry(26, 1.0, 5.2, 2, 0.3), conc), 0, PF_Y - 0.5, 4.9);
    for (const cxx of [-10, 0, 10])
      add(new THREE.Mesh(new RoundedBoxGeometry(1.4, PF_Y - 1.0, 1.4, 2, 0.28), conc), cxx, (PF_Y - 1.0) / 2, 6.2);
    add(new THREE.Mesh(new RoundedBoxGeometry(26, 1.2, 0.4, 2, 0.15), toy(C.wall, { rough: 0.5 })), 0, PF_Y + 0.6, 7.4);
    add(new THREE.Mesh(new RoundedBoxGeometry(26, 0.6, 6.6, 2, 0.24), toy(C.coral, { rough: 0.35 })), 0, PF_Y + 4.2, 5.2);
    for (const cxx of [-11, -3.7, 3.7, 11])
      add(new THREE.Mesh(new THREE.CylinderGeometry(0.24, 0.24, 3.9, 8), toy(C.ink, { rough: 0.7 })), cxx, PF_Y + 2.15, 7.2);

    const L = (x, y, z) => g.localToWorld(new THREE.Vector3(x, y, z));
    const b = { kind: 'station', name: A.name, group: g, top: PF_Y + 4.5,
      w: 28, d: 15, h: PF_Y + 4.5, x: cx, z: cz,
      door: L(0, 0, 9.2),
      board: L(0, 0, 4.9),
      tanV: new THREE.Vector3(A.oz, 0, -A.ox),   // ホームに沿う向き
      acc: { x: A.x, z: A.z },                    // 外周歩道の区間中央
      accNodes: A.nodes.filter(id => pedNodes[id]),
      pfY: PF_Y, trainT: bt, face: 1 };
    const ca = Math.abs(Math.cos(rot)), sa = Math.abs(Math.sin(rot));
    b.fw = b.w * ca + b.d * sa;
    b.fd = b.w * sa + b.d * ca;
    buildings.push(b);
    stations.push(b);
  }
}

/** 建物が疎な街区に芝地と木を置く。舗装だけだと灰色一色で街に見えない */
function greenBlocks(cells) {
  const trunk = new THREE.CylinderGeometry(0.3, 0.38, 2.6, 8);
  const leaf = new THREE.SphereGeometry(1.9, 12, 10);
  const trunkMat = toy(0x8A5A32), leafMat = toy(C.grass, { rough: 0.75 });
  for (const cell of cells) {
    const near = buildings.filter(b => Math.abs(b.x - cell.x) < 26 && Math.abs(b.z - cell.z) < 26);
    const lawn = new THREE.Mesh(new RoundedBoxGeometry(30, 0.3, 22, 2, 0.5),
      toy(near.length ? 0xD9E8BE : C.grass, { rough: 1, clearcoat: 0 }));
    lawn.position.set(cell.x, 0.12, cell.z);
    lawn.receiveShadow = true;
    scene.add(lawn);
    if (near.length > 2) continue;
    for (let k = 0; k < 4; k++) {
      const g = new THREE.Group();
      const t = new THREE.Mesh(trunk, trunkMat); t.position.y = 1.3; t.castShadow = true;
      const l = new THREE.Mesh(leaf, leafMat); l.position.y = 3.7; l.castShadow = true;
      g.add(t, l);
      g.position.set(cell.x - 10 + (k % 2) * 20, 0, cell.z - 7 + ((k / 2) | 0) * 14);
      scene.add(g);
    }
  }
}

/** 窓は建物の子として local 座標で作り、1つにまとめる。
 *  以前はワールド座標で1つの InstancedMesh に入れていたため、建物からズレて浮いていた。 */
function addWindows(group, w, h, d, cols, rows, y0, y1, avoid = []) {
  const geos = [];
  const WSZ = 1.5;
  // 正面は扉や看板と重なりやすい。ぶつかる窓は置かない
  const clash = (x, y) => avoid.some(r =>
    Math.abs(x - r.x) < (r.w + WSZ) / 2 + 0.25 && Math.abs(y - r.y) < (r.h + WSZ) / 2 + 0.25);
  const put = (x, y, z, ry) => {
    const gg = new THREE.BoxGeometry(WSZ, WSZ, 0.16);
    gg.rotateY(ry); gg.translate(x, y, z);
    geos.push(gg);
  };
  for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
    const x = -w / 2 + (w / (cols + 1)) * (c + 1);
    const y = y0 + ((y1 - y0) / (rows + 1)) * (r + 1);
    if (!clash(x, y)) put(x, y, d / 2 + 0.09, 0);      // 正面
    put(x, y, -d / 2 - 0.09, Math.PI);                  // 背面
  }
  for (let r = 0; r < rows; r++) {
    const y = y0 + ((y1 - y0) / (rows + 1)) * (r + 1);
    for (const sx of [-1, 1]) put(sx * (w / 2 + 0.09), y, 0, sx * Math.PI / 2);
  }
  if (!geos.length) return;
  group.add(new THREE.Mesh(BGU.mergeGeometries(geos), winMat));
}

function drawBuilding(g, b) {
  const { w, h, d, kind } = b;
  const fz = d / 2;                              // 正面(local +z)
  const box = (bw, bh, bd, col, x, y, z, r = 0.35) => {
    const m = new THREE.Mesh(new RoundedBoxGeometry(bw, bh, bd, 3, r), toy(col));
    m.position.set(x, y, z); m.castShadow = true; m.receiveShadow = true; g.add(m); return m;
  };
  const avoid = [];                       // 正面にある物(窓を置かない領域)
  const door = (dw = 2.6, dh = 3.4, y0 = 0) => {
    avoid.push({ x: 0, y: y0 + dh / 2, w: dw, h: dh });
    return box(dw, dh, 0.5, 0x8A5A32, 0, y0 + dh / 2, fz, 0.14);
  };
  const sign = (text, sw, sy, sz, opt) => {
    avoid.push({ x: 0, y: sy, w: sw, h: sw * 0.25 });
    return addSign(g, text, sw, sy, sz, opt);
  };

  if (kind === 'house') {
    box(w, h, d, C.wall, 0, h / 2, 0, 0.4);
    const roof = new THREE.Mesh(new THREE.ConeGeometry(w * 0.78, 3.8, 4),
      toy(ROOFS[Math.abs(b.x * 7 | 0) % ROOFS.length]));
    roof.position.y = h + 1.8; roof.rotation.y = Math.PI / 4; roof.castShadow = true; g.add(roof);
    door(2.2, 3);
    addWindows(g, w, h, d, 2, 1, 1.2, h - 0.8, avoid);
    b.top = h + 3.8;

  } else if (kind === 'shop') {
    const idx = SHOPS.findIndex(s => s[1] === b.name);
    box(w, h, d, [C.wall, C.lime, C.wall2, C.lav, C.wall, C.pink, C.wall2, C.yellow][Math.abs(idx) % 8], 0, h / 2, 0, 0.4);
    const awn = box(w + 0.9, 0.6, 3.2, ROOFS[Math.abs(idx) % ROOFS.length], 0, h * 0.56, fz + 1.3, 0.22);
    awn.rotation.x = -0.24;
    box(w * 0.42, 3.0, 0.35, C.glass, -w * 0.24, 1.8, fz, 0.12);
    avoid.push({ x: -w * 0.24, y: 1.8, w: w * 0.42, h: 3.0 });      // ショーウィンドウ
    avoid.push({ x: 0, y: h * 0.56, w: w + 0.9, h: 1.6 });          // 日よけ
    door(2.6, 3.4);
    sign(b.name, w * 0.86, h + 1.3, fz - 0.5);
    if (b.cat === '教養娯楽') {
      const cap = new THREE.Mesh(new THREE.SphereGeometry(1.1, 16, 12), toy(C.pink));
      cap.position.set(-w / 2 + 1.6, 1.3, fz + 1.0); cap.castShadow = true; g.add(cap);
    }
    if (b.cat === '保健医療') {
      // 診療所らしい見た目。**赤十字は使わない**(条約と赤十字標章法で保護された標章のため)。
      // 代わりに玄関の車寄せと、心電図の波形を掲げる。
      box(w * 0.9, 0.5, 4.2, C.wall, 0, h * 0.5, fz + 2.2, 0.18);
      avoid.push({ x: 0, y: h * 0.5, w: w * 0.9, h: 1.4 });
      avoid.push({ x: 0, y: h * 0.79, w: w, h: 2.4 });          // 車寄せの庇
      for (const sx of [-w * 0.34, w * 0.34]) {
        const post = new THREE.Mesh(new THREE.CylinderGeometry(0.26, 0.26, h * 0.5, 10), toy(C.wall));
        post.position.set(sx, h * 0.25, fz + 3.9); post.castShadow = true; g.add(post);
      }
      box(w * 0.94, 0.7, 0.3, 0x3FB6A8, 0, h * 0.72, fz, 0.1);             // 青緑の帯
      // 心電図の波形
      const beat = [[-2.4, 0], [-1.4, 0], [-0.9, 0.85], [-0.35, -0.95], [0.2, 0.45], [0.8, 0], [2.4, 0]];
      for (let i = 0; i < beat.length - 1; i++) {
        const [x1, y1] = beat[i], [x2, y2] = beat[i + 1];
        const len = Math.hypot(x2 - x1, y2 - y1);
        const seg = new THREE.Mesh(new THREE.BoxGeometry(len, 0.26, 0.2), toy(0x1E8E82));
        seg.position.set((x1 + x2) / 2, h * 0.86 + (y1 + y2) / 2, fz + 0.16);
        seg.rotation.z = Math.atan2(y2 - y1, x2 - x1);
        g.add(seg);
      }
    }
    addWindows(g, w, h, d, 2, 1, 4.2, h - 0.6, avoid);
    b.top = h + 2.6;

  } else if (kind === 'gov') {
    // 古典様式: 基壇 → 本体 → 前面の柱廊 → 三角破風 → ドーム
    const bodyH = h * 0.72;
    box(w + 2.2, 1.2, d + 2.2, C.stone, 0, 0.6, 0, 0.25);            // 基壇
    box(w, bodyH, d, C.wall2, 0, 1.2 + bodyH / 2, 0, 0.25);          // 本体
    // 正面の階段
    for (let i = 0; i < 3; i++)
      box(w * 0.42, 0.42, 1.1, C.stone, 0, 0.21 + i * 0.4, fz + 2.0 - i * 1.0, 0.06);

    // 柱廊(6本)。柱は基壇の上に立つ
    const colH = bodyH * 0.78;
    for (let i = 0; i < 6; i++) {
      const cx = -w * 0.36 + i * (w * 0.72 / 5);
      const col = new THREE.Mesh(new THREE.CylinderGeometry(0.55, 0.62, colH, 14), toy(C.wall));
      col.position.set(cx, 1.2 + colH / 2, fz + 1.1); col.castShadow = true; g.add(col);
      box(1.6, 0.34, 1.6, C.stone, cx, 1.2 + colH + 0.17, fz + 1.1, 0.06);   // 柱頭
    }
    // 軒(エンタブレチュア)
    box(w * 0.86, 1.1, 3.0, C.stone, 0, 1.2 + colH + 0.9, fz + 1.1, 0.1);

    // 三角破風。四角錐だとテントに見えるので、ちゃんとした三角にする
    const ped = new THREE.Shape();
    const pw = w * 0.44, ph = 2.9;
    ped.moveTo(-pw, 0); ped.lineTo(pw, 0); ped.lineTo(0, ph); ped.closePath();
    const pg = new THREE.ExtrudeGeometry(ped, { depth: 2.6, bevelEnabled: false });
    pg.translate(0, 0, -1.3);
    const pm = new THREE.Mesh(pg, toy(C.stone));
    pm.position.set(0, 1.2 + colH + 1.45, fz + 1.1); pm.castShadow = true; g.add(pm);

    // ドーム
    const drum = new THREE.Mesh(new THREE.CylinderGeometry(w * 0.16, w * 0.16, 2.6, 20), toy(C.wall2));
    drum.position.y = 1.2 + bodyH + 1.3; drum.castShadow = true; g.add(drum);
    const dome = new THREE.Mesh(new THREE.SphereGeometry(w * 0.17, 22, 14, 0, 6.283, 0, Math.PI / 2), toy(C.coral, { rough: 0.3 }));
    dome.position.y = 1.2 + bodyH + 2.6; dome.castShadow = true; g.add(dome);
    const finial = new THREE.Mesh(new THREE.SphereGeometry(0.55, 12, 10), toy(C.yellow, { rough: 0.2, clearcoat: 1 }));
    finial.position.y = 1.2 + bodyH + 2.6 + w * 0.17 + 0.4; g.add(finial);

    door(3.6, 4.4, 1.2);
    sign(b.name, w * 0.34, 1.2 + bodyH * 0.62, fz);
    addWindows(g, w, bodyH, d, 4, 2, 2.4, bodyH * 0.9, avoid);
    b.top = 1.2 + bodyH + 2.6 + w * 0.17 + 1;

  } else if (kind === 'school') {
    // 校舎(横長・窓が多い)+ 体育館 + 時計 + 国旗掲揚台
    box(w, h, d, C.wall2, 0, h / 2, 0, 0.3);
    box(w + 0.8, 0.9, d + 0.8, C.blue, 0, h + 0.45, 0, 0.28);
    for (let i = 0; i < 3; i++)                                    // 各階の帯
      box(w + 0.1, 0.35, d + 0.1, C.lav, 0, 1.6 + i * (h - 2.4) / 2, 0, 0.08);
    // 体育館(切妻の別棟)
    const gym = box(w * 0.42, h * 0.72, d * 0.8, C.wall, -w * 0.72, h * 0.36, -1.2, 0.3);
    const gr = new THREE.Mesh(new THREE.CylinderGeometry(0.001, w * 0.3, 2.2, 4), toy(C.lav));
    gr.position.set(-w * 0.72, h * 0.72 + 1.1, -1.2); gr.rotation.y = Math.PI / 4; gr.castShadow = true; g.add(gr);
    // 時計
    const clock = new THREE.Mesh(new THREE.CylinderGeometry(1.15, 1.15, 0.3, 20), toy(0xFFFFFF));
    clock.rotation.x = Math.PI / 2; clock.position.set(0, h * 0.82, fz + 0.18); g.add(clock);
    avoid.push({ x: 0, y: h * 0.82, w: 2.6, h: 2.6 });
    const hand = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.8, 0.1), toy(C.ink));
    hand.position.set(0, h * 0.82 + 0.32, fz + 0.34); g.add(hand);
    // 掲揚台
    const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.14, 0.14, 8, 8), toy(0xDDDDDD));
    pole.position.set(w * 0.62, 4, fz + 3.2); pole.castShadow = true; g.add(pole);
    box(2.2, 1.3, 0.16, C.coral, w * 0.62 + 1.2, 7.2, fz + 3.2, 0.05);
    door(3, 3.6); sign(b.name, w * 0.6, h * 0.5, fz);
    addWindows(g, w, h, d, 6, 2, 1.4, h - 0.9, avoid);
    b.top = h + 1;

  } else if (kind === 'hello') {
    box(w, h, d, C.wall, 0, h / 2, 0, 0.4);
    box(w + 0.7, 0.9, d + 0.7, C.lime, 0, h + 0.45, 0, 0.28);
    door(3.2, 3.6); sign(b.name, w * 0.72, h * 0.7, fz, { bg: '#CAFF97' });
    addWindows(g, w, h, d, 3, 1, 1.4, h - 0.8, avoid);
    b.top = h + 1;

  } else if (kind === 'factory') {
    box(w, h, d, C.coral, 0, h / 2, 0, 0.35);
    b.chimneys = [];
    for (const t of [-0.3, 0.3]) {
      const ch = new THREE.Mesh(new THREE.CylinderGeometry(0.9, 1.05, 8, 14), toy(C.wall2));
      ch.position.set(w * t, h + 3.6, -2); ch.castShadow = true; g.add(ch);
      const bd = new THREE.Mesh(new THREE.CylinderGeometry(0.96, 0.96, 1.1, 14), toy(C.coral));
      bd.position.set(w * t, h + 6.8, -2); g.add(bd);
      const wp = new THREE.Vector3(w * t, h + 7.8, -2);
      g.localToWorld(wp); b.chimneys.push(wp);
    }
    door(3.4, 3.8); sign(b.name, w * 0.4, h * 0.74, fz);
    addWindows(g, w, h, d, 4, 2, 1.2, h - 1, avoid);
    b.top = h + 8;

  } else if (kind === 'office') {
    box(w, h, d, C.blue, 0, h / 2, 0, 0.3);
    box(w + 0.6, 0.8, d + 0.6, C.wall, 0, h + 0.4, 0, 0.24);
    box(3.2, 3.6, 0.6, C.glass, 0, 1.8, fz, 0.14);
    avoid.push({ x: 0, y: 1.8, w: 3.2, h: 3.6 });
    sign(b.name, w * 0.7, h * 0.3, fz);
    addWindows(g, w, h, d, 3, 5, 4.6, h - 1, avoid);
    b.top = h + 1;

  } else if (kind === 'station') {
    box(w, h, d, C.wall2, 0, h / 2, 0, 0.35);
    box(w + 1.4, 0.7, d + 1.4, C.coral, 0, h + 0.35, 0, 0.24);
    door(4, 4); sign(b.name, w * 0.6, h * 0.72, fz);
    addWindows(g, w, h, d, 4, 1, 1.4, h - 1, avoid);
    b.top = h + 0.9;
  }
}

// --- 電車(見た目のため。線路は街の北側)-------------------------------------

/** 外周を一周する環状線。角は丸めて滑らかに走らせる */
function buildLoopCurve() {
  const rx = TOWN_W / 2 - 9, rz = TOWN_D / 2 - 9;
  const pts = [];
  const N = 64;
  for (let i = 0; i < N; i++) {
    const t = (i / N) * Math.PI * 2;
    // 角を丸めた長方形(スーパー楕円)
    const c = Math.cos(t), sN = Math.sin(t);
    const k = 4;
    const x = Math.sign(c) * Math.pow(Math.abs(c), 2 / k) * rx;
    const z = Math.sign(sN) * Math.pow(Math.abs(sN), 2 / k) * rz;
    pts.push(new THREE.Vector3(x, 0.9, z));
  }
  return new THREE.CatmullRomCurve3(pts, true, 'centripetal');
}

function buildTrain() {
  loop = buildLoopCurve();
  const up = new THREE.Vector3(0, 1, 0);

  // 桁(コンクリートの1本桁)。跨座式モノレールなので車両はこれに跨る
  const segGeo = new RoundedBoxGeometry(2.6, 2.8, 3.4, 2, 0.25);
  const beam = new THREE.InstancedMesh(segGeo, toy(0xE0DACA, { rough: 0.85, clearcoat: 0.08 }), 240);
  for (let i = 0; i < 240; i++) {
    const t = i / 240;
    const p = loop.getPointAt(t), tan = loop.getTangentAt(t);
    _q.setFromAxisAngle(up, Math.atan2(tan.x, tan.z));
    _m.compose(_p.set(p.x, BEAM_Y, p.z), _q, _s.set(1, 1, 1));
    beam.setMatrixAt(i, _m);
  }
  beam.castShadow = true; beam.receiveShadow = true; scene.add(beam);

  // 支柱(T字)
  const pierN = 26;
  for (let i = 0; i < pierN; i++) {
    const t = i / pierN;
    const p = loop.getPointAt(t), tan = loop.getTangentAt(t);
    const g = new THREE.Group();
    g.position.set(p.x, 0, p.z);
    g.rotation.y = Math.atan2(tan.x, tan.z);
    const col = new THREE.Mesh(new RoundedBoxGeometry(2.2, BEAM_Y - 1.4, 2.2, 2, 0.4),
      toy(0xD6CFBE, { rough: 0.9, clearcoat: 0.05 }));
    col.position.y = (BEAM_Y - 1.4) / 2; col.castShadow = true;
    const head = new THREE.Mesh(new RoundedBoxGeometry(4.6, 1.1, 2.6, 2, 0.3), toy(0xD6CFBE, { rough: 0.9 }));
    head.position.y = BEAM_Y - 1.75; head.castShadow = true;
    g.add(col, head); scene.add(g);
  }

  // 車両。桁をまたぐスカート付き
  const g2 = new THREE.Group();
  trainCars = [];
  for (let i = 0; i < 4; i++) {
    const car = new THREE.Group();
    const shell = new THREE.Mesh(new RoundedBoxGeometry(12.5, 3.9, 4.6, 4, 1.5),
      toy(i === 0 ? C.coral : C.wall, { rough: 0.24, clearcoat: 0.9 }));
    shell.position.y = BEAM_Y + 1.7; shell.castShadow = true;
    const skirt = new THREE.Mesh(new RoundedBoxGeometry(12.2, 2.6, 4.5, 3, 0.5),
      toy(i === 0 ? C.coral : C.wall2, { rough: 0.3 }));
    skirt.position.y = BEAM_Y - 0.2; skirt.castShadow = true;
    const strip = new THREE.Mesh(new THREE.BoxGeometry(11, 1.25, 4.72), winMat);
    strip.position.y = BEAM_Y + 2.2;
    const band = new THREE.Mesh(new THREE.BoxGeometry(12.3, 0.4, 4.68), toy(C.blue, { rough: 0.3 }));
    band.position.y = BEAM_Y + 0.55;
    car.add(shell, skirt, strip, band);
    g2.add(car); trainCars.push(car);
  }
  scene.add(g2);
  train = { group: g2, t: 0, state: 'run', timer: 0, cool: 0, riders: [] };
}

function updateTrain(dts) {
  if (!train || !loop) return;
  const L = loop.getLength();

  if (train.state === 'stop') {
    train.timer -= dts;
    if (train.timer <= 0) { train.state = 'run'; train.cool = 0.35; }
  } else {
    const step = (34 * dts) / L;
    train.t = (train.t + step) % 1;
    train.cool = Math.max(0, (train.cool ?? 0) - dts);
    if (train.cool <= 0) {
      // 通りかかった駅には必ず止まる
      for (const st of stations) {
        let d = st.trainT - train.t;
        if (d < -0.5) d += 1; if (d > 0.5) d -= 1;
        if (Math.abs(d) < step) {
          train.t = st.trainT; train.state = 'stop'; train.timer = 2.4;
          exchangePassengers(st);
          break;
        }
      }
    }
  }

  trainCars.forEach((car, i) => {
    const t = (train.t - (i * 13.4) / L + 1) % 1;
    const p = loop.getPointAt(t), tan = loop.getTangentAt(t);
    car.position.set(p.x, 0, p.z);
    car.rotation.y = Math.atan2(tan.x, tan.z) - Math.PI / 2;
  });
}

/** 停車中の乗り降り。ここが「人が電車に乗る」の実体 */
function exchangePassengers(st) {
  for (let i = train.riders.length - 1; i >= 0; i--) {
    const a = train.riders[i];
    if (a.alightSt !== st) continue;
    train.riders.splice(i, 1);
    // 改札棟の玄関に現れて、目的地へ歩き出す
    a.x = st.door.x; a.z = st.door.z; a.yOff = 0;
    a.vis = 0; a.alightSt = null;
    a.dest = a.trainTo; a.trainTo = null;
    a.path = pedRoute(a.x, a.z, a.dest);
    a.pi = 0; a.gateNext = 'walk'; a.state = 'appearing';
  }
  for (const a of agents) {
    if (a.state !== 'waiting' || a.boardSt !== st || train.riders.length >= 44) continue;
    a.state = 'onTrain'; a.vis = 0; a.boardSt = null;
    train.riders.push(a);
  }
}


// --- 歩行者ネットワーク ------------------------------------------------------
// 歩道と横断歩道だけでできたグラフ。**車道を斜め横断する経路は存在しない。**
// 交差点の各角にノードを置き、
//   ・歩道の辺 = 自由に通れる
//   ・横断の辺 = 信号が青のときだけ通れる
// として最短経路を引く。

const NI = AVE_Z.length, NJ = ST_X.length;
const nodeId = (i, j, sx, sz) => (((i * NJ) + j) * 4) + (sx > 0 ? 2 : 0) + (sz > 0 ? 1 : 0);
let pedNodes = [], pedAdj = [];

function buildPedGraph() {
  pedNodes = new Array(NI * NJ * 4);
  pedAdj = [];
  for (let i = 0; i < NI; i++) for (let j = 0; j < NJ; j++)
    for (const sx of [-1, 1]) for (const sz of [-1, 1]) {
      const id = nodeId(i, j, sx, sz);
      pedNodes[id] = { id, x: ST_X[j] + sx * SW, z: AVE_Z[i] + sz * SW, i, j, sx, sz };
      pedAdj[id] = [];
    }
  const link = (a, b, cross) => {
    const A = pedNodes[a], B = pedNodes[b];
    const w = Math.hypot(A.x - B.x, A.z - B.z) + (cross ? 6 : 0);   // 横断はやや避ける
    pedAdj[a].push({ to: b, w, cross });
    pedAdj[b].push({ to: a, w, cross });
  };

  for (let i = 0; i < NI; i++) for (let j = 0; j < NJ; j++) {
    // 交差点内: 横断歩道
    for (const sx of [-1, 1]) link(nodeId(i, j, sx, -1), nodeId(i, j, sx, 1), 'ave');
    for (const sz of [-1, 1]) link(nodeId(i, j, -1, sz), nodeId(i, j, 1, sz), 'st');
    // 街区に沿う歩道
    if (j + 1 < NJ) for (const sz of [-1, 1])
      link(nodeId(i, j, 1, sz), nodeId(i, j + 1, -1, sz), null);
    if (i + 1 < NI) for (const sx of [-1, 1])
      link(nodeId(i, j, sx, 1), nodeId(i + 1, j, sx, -1), null);
  }
}

/** いま乗っている歩道に直角でスナップし、その区間を挟む2ノードを返す。
 *  最寄りノードへ直線で向かうと車道を斜めに横切ってしまうため、
 *  必ず「歩道の上」を起点にする。 */
function snapToSidewalk(x, z) {
  let best = null;
  for (let i = 0; i < NI; i++) for (const sz of [-1, 1]) {
    const line = AVE_Z[i] + sz * SW, d = Math.abs(z - line);
    if (!best || d < best.d) best = { d, kind: 'ave', i, sz, x, z: line };
  }
  for (let j = 0; j < NJ; j++) for (const sx of [-1, 1]) {
    const line = ST_X[j] + sx * SW, d = Math.abs(x - line);
    if (!best || d < best.d) best = { d, kind: 'st', j, sx, x: line, z };
  }
  const ids = [];
  if (best.kind === 'ave') {
    let j = 0;
    for (let k = 0; k < NJ; k++) if (ST_X[k] <= best.x) j = k;
    const jl = Math.max(0, Math.min(NJ - 1, j)), jr = Math.max(0, Math.min(NJ - 1, j + 1));
    ids.push(nodeId(best.i, jl, jl === j ? 1 : -1, best.sz));
    if (jr !== jl) ids.push(nodeId(best.i, jr, -1, best.sz));
    best.x = Math.max(ST_X[0], Math.min(ST_X[NJ - 1], best.x));
  } else {
    let i = 0;
    for (let k = 0; k < NI; k++) if (AVE_Z[k] <= best.z) i = k;
    const it = Math.max(0, Math.min(NI - 1, i)), ib = Math.max(0, Math.min(NI - 1, i + 1));
    ids.push(nodeId(it, best.j, best.sx, it === i ? 1 : -1));
    if (ib !== it) ids.push(nodeId(ib, best.j, best.sx, -1));
    best.z = Math.max(AVE_Z[0], Math.min(AVE_Z[NI - 1], best.z));
  }
  best.nodes = [...new Set(ids)].filter(id => pedNodes[id]);
  if (!best.nodes.length) best.nodes = [nodeNear(x, z).id];
  return best;
}

/** 位置から最寄りノード(スナップできないときの保険) */
function nodeNear(x, z) {
  let best = null, bd = Infinity;
  for (const n of pedNodes) {
    const d = (n.x - x) ** 2 + (n.z - z) ** 2;
    if (d < bd) { bd = d; best = n; }
  }
  return best;
}


function dijkstra(from, toIds) {
  const dist = new Float64Array(pedNodes.length).fill(Infinity);
  const prev = new Int32Array(pedNodes.length).fill(-1);
  const prevCross = new Array(pedNodes.length).fill(null);
  const seen = new Uint8Array(pedNodes.length);
  for (const f of from) dist[f.id ?? f] = f.d ?? 0;
  const goal = new Set(toIds);
  for (;;) {
    let u = -1, bd = Infinity;
    for (let k = 0; k < dist.length; k++) if (!seen[k] && dist[k] < bd) { bd = dist[k]; u = k; }
    if (u < 0) break;
    seen[u] = 1;
    if (goal.has(u)) {
      const out = [];
      for (let c = u; c !== -1; c = prev[c])
        out.push({ x: pedNodes[c].x, z: pedNodes[c].z, cross: prevCross[c] });
      return out.reverse();
    }
    for (const e of pedAdj[u]) {
      const nd = dist[u] + e.w;
      if (nd < dist[e.to]) { dist[e.to] = nd; prev[e.to] = u; prevCross[e.to] = e.cross; }
    }
  }
  return null;
}

/** 歩行者の経路。歩道と横断歩道だけを通る */
function pedRoute(x, z, dest) {
  const s0 = snapToSidewalk(x, z);
  const from = s0.nodes.map(id => ({ id, d: Math.hypot(pedNodes[id].x - s0.x, pedNodes[id].z - s0.z) }));
  const toIds = (dest.accNodes && dest.accNodes.length)
    ? dest.accNodes.filter(id => pedNodes[id])
    : [nodeNear(dest.door.x, dest.door.z).id];
  const path = dijkstra(from, toIds.length ? toIds : [nodeNear(dest.door.x, dest.door.z).id]);

  const pts = [{ x: s0.x, z: s0.z, cross: null }];
  if (path) for (const q of path) pts.push(q);
  if (dest.acc) pts.push({ x: dest.acc.x, z: dest.acc.z, cross: null });
  pts.push({ x: dest.door.x, z: dest.door.z, cross: null });
  // 歩道の幅の中で少しばらけさせる(横断歩道の点はずらさない)
  for (const q of pts) if (!q.cross) { q.x += (Math.random() - 0.5) * 1.4; q.z += (Math.random() - 0.5) * 1.4; }
  return pts;
}


// --- 経路(碁盤の目を折れて進む)----------------------------------------------

const nearestIdx = (arr, v) => {
  let k = 0, best = Infinity;
  arr.forEach((a, i) => { const d = Math.abs(a - v); if (d < best) { best = d; k = i; } });
  return k;
};

/** 現在地 → 目的地 の折れ線。歩道/車線のオフセットは lane で決める */
function route(sx, sz, tx, tz, off) {
  const ai = nearestIdx(AVE_Z, sz), ak = nearestIdx(AVE_Z, tz), sj = nearestIdx(ST_X, tx);
  const z1 = AVE_Z[ai] + off, x2 = ST_X[sj] + off, z3 = AVE_Z[ak] + off;
  const pts = [];
  pts.push([sx, z1]);          // 最寄りの東西通りへ出る
  pts.push([x2, z1]);          // 東西に進む
  if (ak !== ai) pts.push([x2, z3]);   // 南北に進む
  pts.push([tx, z3]);          // 目的地の x へ
  pts.push([tx, tz]);          // 玄関へ
  return pts;
}

// 経路には2つの形がある: 車は [x, z] の配列、歩行者は {x, z, cross}。
// 歩行者グラフを入れたとき、ここが [0]/[1] のままで距離が NaN になり、
// 車と電車が一度も使われなくなっていた。
const px_ = q => (q.x !== undefined ? q.x : q[0]);
const pz_ = q => (q.z !== undefined ? q.z : q[1]);
const routeLen = pts => {
  let L = 0;
  for (let i = 1; i < pts.length; i++)
    L += Math.hypot(px_(pts[i]) - px_(pts[i - 1]), pz_(pts[i]) - pz_(pts[i - 1]));
  return L;
};


/** 車の経路。**左側通行**。車線は進行方向で決まる。
 *  以前は歩行者用に持っていた a.off の符号で決めていたため、
 *  半分の車が対向車線を逆走していた。 */
function carRoute(sx, sz, tx, tz) {
  const sg = v => (v < 0 ? -1 : 1);
  const ai = nearestIdx(AVE_Z, sz), ak = nearestIdx(AVE_Z, tz);

  // 同じ通りの中だけを走る場合。行き先の向きで車線を1本に決める。
  // 以前は往路と復路の向きから別々に車線を決めていたため、
  // 途中でセンターラインをまたいで逆走していた。
  if (ai === ak) {
    const dir = sg(tx - sx);
    const z = AVE_Z[ai] - dir * CAR_OFF;
    return [[sx, z], [tx, z]];
  }

  const sj = nearestIdx(ST_X, tx);
  const dx1 = sg(ST_X[sj] - sx);
  const dz = sg(AVE_Z[ak] - AVE_Z[ai]);
  const dx2 = sg(tx - ST_X[sj]);
  const z1 = AVE_Z[ai] - dx1 * CAR_OFF;   // 東西に走る車線
  const x2 = ST_X[sj] + dz * CAR_OFF;     // 南北に走る車線
  const z3 = AVE_Z[ak] - dx2 * CAR_OFF;
  return [[sx, z1], [x2, z1], [x2, z3], [tx, z3]];
}


// --- 住人 -------------------------------------------------------------------

function buildAgents() {
  let seed = 42;
  const rnd = () => (seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;
  const pick = k => { const l = buildings.filter(b => k.includes(b.kind)); return l[(rnd() * l.length) | 0]; };

  for (let i = 0; i < N_AGENTS; i++) {
    const r = rnd();
    const band = r < 0.13 ? 'child' : r < 0.72 ? 'adult' : 'elder';
    const home = pick(['house']);
    const a = {
      band,
      scale: band === 'child' ? 0.72 : band === 'elder' ? 0.92 : 1,
      cloth: (rnd() * CLOTHES.length) | 0, hair: (rnd() * HAIRS.length) | 0,
      lane: (rnd() - 0.5) * 1.7,        // 歩道の幅の中で横に散る
      home, work: band === 'child' ? pick(['school']) : pick(['factory', 'office', 'shop', 'gov', 'station']),
      store: pick(['shop']),
      // 扉は車道端から 6.0。ばらつきを大きく取ると車道の上に湧いてしまう
      x: home.door.x + (rnd() - 0.5) * 1.6, z: home.door.z + (rnd() - 0.5) * 1.6,
      path: null, pi: 0, dest: null, state: 'idle',
      heading: 0, targetHeading: 0,
      carry: 0, employed: true, vis: 1, car: null,
      trainTo: null, boardSt: null, alightSt: null, toPlatform: false,
      yOff: 0, gate: null, gateNext: null, pickup: false,
      delay: rnd() * 0.9, wait: 0,
      speed: (band === 'elder' ? 9 : band === 'child' ? 13 : 11) + rnd() * 3,
      bob: rnd() * 6.28, step: rnd() * 6.28,
      goesIn: rnd() < 0.62,
    };
    agents.push(a);
  }

  const mk = (geo, mat, n, shadow = true) => {
    const m = new THREE.InstancedMesh(geo, mat, n);
    m.castShadow = shadow; m.frustumCulled = false;
    m.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    scene.add(m); return m;
  };
  inst.body = mk(new RoundedBoxGeometry(1.45, 1.55, 1.05, 3, 0.42), toy(0xffffff), N_AGENTS);
  inst.head = mk(new THREE.SphereGeometry(1.02, 22, 16), toy(C.skin, { rough: 0.5 }), N_AGENTS);
  inst.hair = mk(new THREE.SphereGeometry(1.07, 22, 14, 0, 6.283, 0, 1.35), toy(0xffffff, { rough: 0.55 }), N_AGENTS);
  inst.eye = mk(new THREE.SphereGeometry(0.235, 12, 10), new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.25 }), N_AGENTS * 2, false);
  inst.pupil = mk(new THREE.SphereGeometry(0.125, 10, 8), new THREE.MeshStandardMaterial({ color: 0x1A1A1A, roughness: 0.3 }), N_AGENTS * 2, false);
  inst.leg = mk(new RoundedBoxGeometry(0.42, 0.9, 0.42, 2, 0.17), toy(0x3A3226), N_AGENTS * 2);
  inst.carry = mk(new THREE.CylinderGeometry(0.62, 0.62, 0.2, 18),
    new THREE.MeshPhysicalMaterial({ color: C.coin, roughness: 0.2, metalness: 0.15, clearcoat: 1,
      emissive: new THREE.Color(0x6B4A00), emissiveIntensity: 0.5 }), N_AGENTS);
  inst.bag = mk(new RoundedBoxGeometry(0.95, 1.05, 0.6, 2, 0.18), toy(0xFFFFFF, { rough: 0.6 }), N_AGENTS);
  inst.tag = mk(new THREE.PlaneGeometry(3.0, 1.25),
    new THREE.MeshBasicMaterial({ map: textTexture('求職', { bg: '#FFC93D' }), toneMapped: false, side: THREE.DoubleSide }), N_AGENTS, false);

  const col = new THREE.Color();
  agents.forEach((a, i) => {
    inst.body.setColorAt(i, col.setHex(CLOTHES[a.cloth]));
    inst.hair.setColorAt(i, col.setHex(HAIRS[a.hair]));
  });
  inst.body.instanceColor.needsUpdate = true;
  inst.hair.instanceColor.needsUpdate = true;

  // 車(長距離の足)
  for (let i = 0; i < MAX_CARS; i++) {
    const g = new THREE.Group();
    const body = new THREE.Mesh(new RoundedBoxGeometry(5.4, 1.9, 2.6, 3, 0.62), toy(CARS[i % CARS.length], { rough: 0.3 }));
    body.position.y = 1.5; body.castShadow = true;
    const cabin = new THREE.Mesh(new RoundedBoxGeometry(3.0, 1.4, 2.3, 3, 0.5), toy(0xBFE4F5, { rough: 0.15 }));
    cabin.position.set(-0.3, 2.6, 0); cabin.castShadow = true;
    g.add(body, cabin);
    for (const [wx, wz] of [[1.7, 1.35], [1.7, -1.35], [-1.7, 1.35], [-1.7, -1.35]]) {
      const wheel = new THREE.Mesh(new THREE.CylinderGeometry(0.62, 0.62, 0.5, 12), toy(0x2A2320, { rough: 0.8 }));
      wheel.rotation.x = Math.PI / 2; wheel.position.set(wx, 0.62, wz); g.add(wheel);
    }
    g.visible = false; scene.add(g);
    cars.push({ group: g, busy: false, rider: null, path: null, pi: 0 });
  }
}

function buildParticles() {
  inst.puff = new THREE.InstancedMesh(new THREE.SphereGeometry(1, 10, 8),
    new THREE.MeshStandardMaterial({ color: 0xE8E4DA, roughness: 1, transparent: true, opacity: 0.5 }), 40);
  inst.puff.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  inst.puff.frustumCulled = false;
  scene.add(inst.puff);
}


// --- 法律の効果 --------------------------------------------------------------
// 「施行後」の世界で、施行月以降だけ現れる。baseline には決して出さない。

const lawActive = () => !!(lawFx && variant === 'treatment' && month >= (lawFx.enact ?? 0));

function fxTag(parent, text, w, x, y, z, bg) {
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(w, w * 0.25),
    new THREE.MeshBasicMaterial({ map: textTexture(text, { bg }), toneMapped: false, side: THREE.DoubleSide }));
  mesh.position.set(x, y, z);
  parent.add(mesh); fxMeshes.push(mesh);
  return mesh;
}

function setLaw(fx) {
  for (const m of fxMeshes) m.parent && m.parent.remove(m);
  fxMeshes = [];
  lawFx = fx;
  if (!fx) return;

  // どの法律でも: 庁舎前に「施行中」の立て看板
  const gov = buildings.find(b => b.kind === 'gov');
  if (gov) {
    const out = new THREE.Vector3(gov.door.x - gov.x, 0, gov.door.z - gov.z).normalize();
    const G = new THREE.Group();
    G.position.set(gov.door.x + out.x * 2 + 10 * Math.abs(out.z),
                   0, gov.door.z + out.z * 2 + 10 * Math.abs(out.x));
    G.rotation.y = Math.atan2(out.x, out.z);
    const post = new THREE.Mesh(new THREE.CylinderGeometry(0.22, 0.26, 5.4, 10), toy(C.ink, { rough: 0.7 }));
    post.position.y = 2.7; post.castShadow = true; G.add(post);
    scene.add(G); fxMeshes.push(G);
    fxTag(G, '施行中「' + (fx.name || '法律') + '」', 11, 0, 5.9, 0, '#FE806F');
  }

  if (fx.type === 'gacha') {
    const shop = buildings.find(b => b.cat === '教養娯楽');
    if (shop) {
      fxTag(shop.group, '18歳未満 お断り', 8.5, 0, shop.h + 3.2, shop.d / 2 + 0.35, '#FFC93D');
      for (const [y, rz] of [[1.5, 0.09], [2.5, -0.09]]) {   // 店頭を塞ぐ横木
        const bar = new THREE.Mesh(new RoundedBoxGeometry(shop.w * 0.8, 0.45, 0.4, 2, 0.15),
          toy(C.coral, { rough: 0.4 }));
        bar.position.set(0, y, shop.d / 2 + 1.0); bar.rotation.z = rz; bar.castShadow = true;
        shop.group.add(bar); fxMeshes.push(bar);
      }
    }
  } else if (fx.type === 'vat') {
    for (const b of buildings) {                 // 各店の軒先に新税率の札
      if (b.kind !== 'shop') continue;
      const down = b.cat === '食料';
      fxTag(b.group, down ? '8% → 0%' : '10% → 12%', 5.6,
            -b.w * 0.26, b.h + 2.9, b.d / 2 + 0.35, down ? '#CAFF97' : '#FE806F');
    }
  } else if (fx.type === 'benefit') {
    if (gov) fxTag(gov.group, 'こども給付 受付中', 9.5, 0, 3.6, gov.d / 2 + 2.0, '#CAFF97');
  }

  refreshFx();
}

function refreshFx() {
  const on = lawActive();
  for (const m of fxMeshes) m.visible = on;
}

// --- ディレクター -----------------------------------------------------------

function seriesAt(m) {
  if (!data) return null;
  const s = data.series;
  const i = Math.max(0, Math.min(s.gdp.length - 1, m));
  return { unemployment: s.unemployment[i], cpi: s.cpi[i], gdp: s.gdp[i], gdp0: s.gdp[0],
           debt: s.gov_debt[i], balance: s.gov_balance[i], gini: s.gini[i] };
}

function setSign(role, text, opt) {
  const s = signs.find(x => x.role === role);
  if (!s) return;
  s.mesh.material.map.dispose();
  s.mesh.material.map = textTexture(text, Object.assign({}, s.opt, opt));
  s.mesh.material.needsUpdate = true;   // 表裏でマテリアルを共有しているので1回で足りる
}

function applyMonth(m) {
  const d = seriesAt(m);
  if (!d) return;
  const adults = agents.filter(a => a.band !== 'child');
  // 失業率をそのまま人数にすると1〜2人で見えないので街の縮尺として4倍する。
  // 倍率は表示上の誇張で指標そのものではない(HUD の % が正)。
  joblessCount = Math.max(0, Math.min(adults.length, Math.round(adults.length * d.unemployment * 4)));
  adults.forEach((a, i) => { a.employed = i >= joblessCount; });
  for (const a of agents) if (a.band === 'child') a.employed = true;
  const col = new THREE.Color();
  agents.forEach((a, i) => inst.body.setColorAt(i, col.setHex(a.employed ? CLOTHES[a.cloth] : C.jobless)));
  inst.body.instanceColor.needsUpdate = true;

  setSign('debt', '債務 ' + (d.debt / 1e12).toFixed(2) + '兆');
  setSign('jobs', '求職 ' + joblessCount + '人',
    { bg: joblessCount > adults.length * 0.12 ? '#FE806F' : '#FFC93D' });
  refreshFx();
}

function go(a, b) {
  // 施行中のガチャ規制: 未成年は店の前で追い返される
  if (b && b.cat === '教養娯楽' && a.band === 'child' && lawActive() && lawFx.type === 'gacha')
    b = a.home;
  if (!b || (a.state === 'inside' && a.dest === b)) return;
  a.dest = b;
  a.wait = a.delay;
  a.path = pedRoute(a.x, a.z, b);
  a.pi = 0;
  a.state = a.state === 'inside' ? 'leaving' : 'walk';
  // 遠い移動は電車。最寄り駅から乗り、目的地に一番近い駅で降りる
  // 改札(door)までの距離で最寄り駅を決める。platform は駅の作り直しで無くなった
  const dist2 = (st, x, z) => (st.door.x - x) ** 2 + (st.door.z - z) ** 2;
  const nearestSt = (x, z) => stations.reduce(
    (best, st) => (best === null || dist2(st, x, z) < dist2(best, x, z)) ? st : best, null);

  if (b.kind !== 'station' && stations.length > 1 && routeLen(a.path) > TRAIN_TRIP) {
    const bs = nearestSt(a.x, a.z), as_ = nearestSt(b.door.x, b.door.z);
    if (bs && as_ && bs !== as_) {
      a.trainTo = b; a.boardSt = bs; a.alightSt = as_; a.dest = bs;
      a.path = pedRoute(a.x, a.z, bs);
      a.pi = 0; a.state = 'walk'; a.toPlatform = true;
      return;
    }
  }
  a.toPlatform = false;
  if (!a.car && routeLen(a.path) > CAR_TRIP) tryBoard(a);
}

function tryBoard(a) {
  const car = cars.find(c => !c.busy);
  if (!car) return;
  const path = carRoute(a.x, a.z, a.dest.door.x, a.dest.door.z);
  const sp = path[0];
  // 発車位置に他の車がいるなら見送る(重なって湧かない)
  if (cars.some(o => o.busy && Math.hypot(o.group.position.x - sp[0], o.group.position.z - sp[1]) < 8)) return;
  car.busy = true; car.rider = a; car.path = path;
  car.pi = 1;                                  // 歩道→車道の斜め移動はしない
  car.group.position.set(sp[0], 0, sp[1]);
  const nx = path[1] ? path[1][0] - sp[0] : 1, nz = path[1] ? path[1][1] - sp[1] : 0;
  car.group.rotation.y = Math.atan2(nx, nz) - Math.PI / 2;
  car.group.visible = true;
  a.car = car; a.state = 'riding'; a.vis = 0;
}

const FREE = a => a.state === 'idle' || a.state === 'inside';

function onPhase(p) {
  if (!data) return;
  const hello = buildings.find(b => b.kind === 'hello');
  const gov = buildings.find(b => b.kind === 'gov');

  // ③所得 の給料だけは居場所に関係なく配る(台帳の出来事なので)
  if (p === 2) for (const a of agents) if (a.employed && a.band !== 'child' && !a.carry) a.carry = 1;

  for (const a of agents) {
    if (!FREE(a)) continue;                      // 移動中の人の行き先は奪わない
    if (p === 0 || p === 1) go(a, a.employed ? a.work : hello);
    else if (p === 2 || p === 3) go(a, a.employed ? a.store : a.home);
    else if (p === 4) {
      if (a.carry === 1 && Math.random() < 0.34) go(a, gov);
      // 給付法の施行中: 手ぶらの大人が庁舎へ受け取りに行く
      else if (!a.carry && lawActive() && lawFx.type === 'benefit'
               && a.band === 'adult' && Math.random() < 0.22) { a.pickup = true; go(a, gov); }
      else go(a, a.home);
    }
    else go(a, a.home);
  }
}

/** 手が空いた人に次の用事を出す。街全体を動き回らせるための呼吸 */
function keepBusy(a) {
  const p = phaseIndex();
  const hello = buildings.find(b => b.kind === 'hello');
  const pool = p <= 1 ? [a.employed ? a.work : hello]
             : p <= 3 ? [a.store, a.work]
             : [a.home, a.store];
  go(a, pool[(Math.random() * pool.length) | 0]);
}

// --- 動き(なめらかに)------------------------------------------------------

const lerpAngle = (a, b, t) => {
  let d = ((b - a + Math.PI) % (Math.PI * 2)) - Math.PI;
  if (d < -Math.PI) d += Math.PI * 2;
  return a + d * t;
};

/** 折れ線を進む。到達したら次の点へ。行き過ぎないので震えない */
function advance(o, dts, speed) {
  let move = speed * dts;
  o.waitSignal = false;
  while (move > 0 && o.path && o.pi < o.path.length) {
    const wp = o.path[o.pi];
    const px = wp.x ?? wp[0], pz = wp.z ?? wp[1];

    // 横断歩道に入る前に信号を見る。渡り始めたら青のまま渡り切る
    if (wp.cross && !o.crossing) {
      if (!signalGreen(wp.cross)) { o.waitSignal = true; return false; }
      o.crossing = true;
    }

    const dx = px - o.x, dz = pz - o.z;
    const dist = Math.hypot(dx, dz);
    if (dist < 1e-4) { o.pi++; o.crossing = false; continue; }
    // 最後の点(扉)は少し手前で到着とみなす。全員が同じ1点に集まらない
    if (!wp.cross && o.pi === o.path.length - 1 && dist < 1.6) { o.pi++; continue; }
    o.targetHeading = Math.atan2(dx, dz);
    if (dist <= move) { o.x = px; o.z = pz; move -= dist; o.pi++; o.crossing = false; }
    else { o.x += (dx / dist) * move; o.z += (dz / dist) * move; move = 0; }
  }
  return o.path && o.pi >= o.path.length;
}

/** 車が停止線で止まるべきか。進行方向の信号が赤で、交差点の手前にいるとき */
function carMustStop(x, z, hx, hz) {
  if (Math.abs(hx) >= Math.abs(hz)) {          // 東西に走行
    if (!nsGreen) return false;                // 東西が青
    for (const ix of ST_X) {
      const d = (ix - x) * Math.sign(hx || 1);
      if (d > SW + 1.2 && d < SW + 7) return true;
    }
  } else {                                     // 南北に走行
    if (nsGreen) return false;
    for (const iz of AVE_Z) {
      const d = (iz - z) * Math.sign(hz || 1);
      if (d > SW + 1.2 && d < SW + 7) return true;
    }
  }
  return false;
}

/** 人同士が重ならないように、近すぎる相手を押し分ける */
function separateAgents() {
  const R = 1.45;
  for (let pass = 0; pass < 4; pass++)
  for (let i = 0; i < agents.length; i++) {
    const a = agents[i];
    if (a.vis <= 0.05 || a.crossing) continue;   // 横断中は押さない
    for (let j = i + 1; j < agents.length; j++) {
      const b = agents[j];
      if (b.vis <= 0.05 || b.crossing) continue;
      let dx = b.x - a.x, dz = b.z - a.z;
      const d2 = dx * dx + dz * dz;
      if (d2 > R * R || d2 < 1e-6) continue;
      const d = Math.sqrt(d2), push = (R - d) * 0.5;
      dx /= d; dz /= d;
      a.x -= dx * push; a.z -= dz * push;
      b.x += dx * push; b.z += dz * push;
    }
  }
  // 押し分けの結果、車道にはみ出した人を歩道へ戻す(横断中は除く)
  for (const a of agents) {
    if (a.vis <= 0.05 || a.crossing) continue;
    for (const z of AVE_Z) {
      const dz = a.z - z;
      if (Math.abs(dz) < ROAD_H + 0.3) { a.z = z + Math.sign(dz || 1) * (ROAD_H + 0.3); break; }
    }
    for (const x of ST_X) {
      const dx = a.x - x;
      if (Math.abs(dx) < ROAD_H + 0.3) { a.x = x + Math.sign(dx || 1) * (ROAD_H + 0.3); break; }
    }
  }
}

function updateAgents(dts) {
  for (let i = 0; i < agents.length; i++) {
    const a = agents[i];

    if (a.wait > 0) { a.wait -= dts; a.moving = false; }
    else if (a.state === 'riding' || a.state === 'onTrain') { a.moving = false; }
    else if (a.state === 'appearing') {
      a.vis = Math.min(1, a.vis + dts * 3.2);
      a.moving = false;
      if (a.vis >= 1) { a.state = a.gateNext || 'idle'; a.gateNext = null; }
    }
    else if (a.state === 'waiting') {
      a.moving = false;
      // 電車が来なければ諦めて自力で向かう。ホームで永久に待たせない
      a.waitT = (a.waitT ?? 0) + dts;
      if (a.waitT > 14) {
        const to = a.trainTo, st = a.boardSt;
        a.trainTo = null; a.boardSt = null; a.alightSt = null; a.waitT = 0;
        // 改札から地上に出る
        a.x = st ? st.door.x : a.x; a.z = st ? st.door.z : a.z; a.yOff = 0;
        a.vis = 0; a.gateNext = 'idle'; a.state = 'appearing'; a.rest = 0;
        a.dest = to || a.home;
      }
    }
    else if (a.state === 'leaving') {
      a.vis = Math.min(1, a.vis + dts * 3.5);
      if (a.vis >= 1) a.state = 'walk';
      a.moving = false;
    } else if (a.state === 'walk') {
      const done = advance(a, dts, a.speed);
      a.moving = !a.waitSignal;                  // 赤なら足を止める
      if (a.moving) a.step += dts * 8;
      if (done) {
        if (a.toPlatform) {
          // 改札棟に入り、中の階段で昇って、ホームに現れる
          const st = a.boardSt;
          const spread = (Math.random() - 0.5) * 18;
          a.gate = { x: st.board.x + st.tanV.x * spread, z: st.board.z + st.tanV.z * spread,
                     y: st.pfY, next: 'waiting' };
          a.dest = st; a.state = 'entering'; a.toPlatform = false; a.waitT = 0;
        }
        else { a.state = a.goesIn ? 'entering' : 'idle'; a.rest = 0.6 + Math.random() * 2.4; }
      }
    } else if (a.state === 'entering') {
      a.vis -= dts * 2.6;
      a.moving = false;
      if (a.vis <= 0) {
        a.vis = 0;
        if (a.gate) {                          // 改札の中の階段で移動した
          a.x = a.gate.x; a.z = a.gate.z; a.yOff = a.gate.y;
          a.gateNext = a.gate.next; a.gate = null;
          a.state = 'appearing';
        } else {
          a.state = 'inside';
          if (a.dest.kind === 'gov' && a.carry === 1) a.carry = 0;
          else if (a.dest.kind === 'gov' && a.pickup && lawActive() && lawFx.type === 'benefit' && a.carry === 0) {
            a.carry = 1; a.pickup = false;     // 給付金を受け取って出てくる
          }
          else if (a.dest.kind === 'shop' && a.carry === 1) a.carry = 2;
          else if (a.dest.kind === 'house') a.carry = 0;
          a.rest = 1.2 + Math.random() * 3.0;
        }
      }
    } else {
      a.moving = false;
      // 立ち止まったら少し休んで、次の用事へ出かける
      if (a.state === 'idle' || a.state === 'inside') {   // 'waiting' は電車待ちなので動かさない
        a.rest = (a.rest ?? 0) - dts;
      a.idleT = (a.idleT ?? Math.random() * 6.28) + dts * 0.7;
        if (a.rest <= 0) keepBusy(a);
      }
    }

    a.heading = lerpAngle(a.heading, a.targetHeading, Math.min(1, dts * 9));
    a.bob += dts * (a.moving ? 6.5 : 1.6);

  }

  separateAgents();          // 移動し終えてから押し分ける

  for (let i = 0; i < agents.length; i++) {
    const a = agents[i];
    // 建物の中・車の中は描かない
    if (a.vis <= 0.01) {
      for (const k of ['body', 'head', 'hair', 'carry', 'bag', 'tag']) inst[k].setMatrixAt(i, HIDDEN);
      for (const k of ['eye', 'pupil', 'leg']) { inst[k].setMatrixAt(i * 2, HIDDEN); inst[k].setMatrixAt(i * 2 + 1, HIDDEN); }
      continue;
    }

    const sc = a.scale * a.vis;
    const hop = a.moving ? Math.abs(Math.sin(a.bob)) * 0.14 : Math.sin(a.bob) * 0.03;
    const y = 1.18 * sc + hop + 0.2 + (a.yOff || 0);
    _q.setFromAxisAngle(_v.set(0, 1, 0), a.heading);
    _s.set(sc, sc, sc);
    // 進行方向に対して横にずらす。同じ経路を歩く人同士が重ならない
    const lx = Math.cos(a.heading) * (a.lane || 0);
    const lz = -Math.sin(a.heading) * (a.lane || 0);
    const ax = a.x + lx, az = a.z + lz;

    _m.compose(_p.set(ax, y, az), _q, _s); inst.body.setMatrixAt(i, _m);
    const hy = y + 1.26 * sc;
    _m.compose(_p.set(ax, hy, az), _q, _s); inst.head.setMatrixAt(i, _m);
    _m.compose(_p.set(ax, hy + 0.08 * sc, az), _q, _s); inst.hair.setMatrixAt(i, _m);

    // 目は進行方向の顔面に付ける
    const fwdX = Math.sin(a.heading), fwdZ = Math.cos(a.heading);
    const rgtX = Math.cos(a.heading), rgtZ = -Math.sin(a.heading);
    for (let e = 0; e < 2; e++) {
      const s2 = e ? 0.37 : -0.37;
      const ex = ax + fwdX * 0.88 * sc + rgtX * s2 * sc;
      const ez = az + fwdZ * 0.88 * sc + rgtZ * s2 * sc;
      _m.compose(_p.set(ex, hy + 0.15 * sc, ez), _q, _s); inst.eye.setMatrixAt(i * 2 + e, _m);
      _m.compose(_p.set(ex + fwdX * 0.13 * sc, hy + 0.15 * sc, ez + fwdZ * 0.13 * sc), _q, _s);
      inst.pupil.setMatrixAt(i * 2 + e, _m);
    }
    const sw = a.moving ? Math.sin(a.step) * 0.5 : 0;
    for (let l = 0; l < 2; l++) {
      const s2 = l ? 0.37 : -0.37, f = l ? sw : -sw;
      _m.compose(_p.set(ax + rgtX * s2 * sc + fwdX * f * sc, 0.45 * sc + hop * 0.4 + 0.2 + (a.yOff || 0),
                        az + rgtZ * s2 * sc + fwdZ * f * sc), _q, _s);
      inst.leg.setMatrixAt(i * 2 + l, _m);
    }

    const hx = ax + rgtX * 1.0 * sc + fwdX * 0.4 * sc;
    const hz = az + rgtZ * 1.0 * sc + fwdZ * 0.4 * sc;
    if (a.carry === 1) {
      _q.setFromAxisAngle(_v.set(1, 0, 0), Math.PI / 2);
      _m.compose(_p.set(hx, y + 0.15 * sc, hz), _q, _s); inst.carry.setMatrixAt(i, _m);
      inst.bag.setMatrixAt(i, HIDDEN);
    } else if (a.carry === 2) {
      _m.compose(_p.set(hx, y + 0.05 * sc, hz), _q.identity(), _s); inst.bag.setMatrixAt(i, _m);
      inst.carry.setMatrixAt(i, HIDDEN);
    } else { inst.carry.setMatrixAt(i, HIDDEN); inst.bag.setMatrixAt(i, HIDDEN); }

    if (!a.employed && a.band !== 'child') {
      _q.setFromAxisAngle(_v.set(0, 1, 0), Math.atan2(
        camera.position.x - ax, camera.position.z - az));               // 札はカメラを向く
      _m.compose(_p.set(ax, hy + 1.5 * sc, az), _q, _s.set(sc, sc, sc));
      inst.tag.setMatrixAt(i, _m);
    } else inst.tag.setMatrixAt(i, HIDDEN);
  }
  for (const k of ['body', 'head', 'hair', 'eye', 'pupil', 'leg', 'carry', 'bag', 'tag'])
    inst[k].instanceMatrix.needsUpdate = true;
}

/** 前を走る車と、渡っている歩行者。どちらかが近ければ止まる */
function carBlocked(self, x, z, hx, hz) {
  const L = Math.hypot(hx, hz) || 1;
  const fx = hx / L, fz = hz / L;
  const ahead = (ox, oz, gap) => {
    const dx = ox - x, dz = oz - z;
    const fwd = dx * fx + dz * fz;              // 進行方向の距離
    const lat = Math.abs(dx * fz - dz * fx);    // 横方向のずれ
    return fwd > 0 && fwd < gap && lat < 2.4;
  };
  for (const o of cars) {
    if (o === self || !o.busy) continue;
    if (ahead(o.group.position.x, o.group.position.z, 9.5)) return true;
  }
  for (const a of agents) {
    if (a.vis <= 0.05) continue;
    if (ahead(a.x, a.z, 7)) return true;        // 横断中の人には譲る
  }
  return false;
}

function updateCars(dts) {
  for (const c of cars) {
    if (!c.busy) continue;
    const px = c.group.position.x, pz = c.group.position.z;
    const wp = c.path[c.pi];
    const hx = wp ? (wp.x ?? wp[0]) - px : 1, hz = wp ? (wp.z ?? wp[1]) - pz : 0;
    if (carMustStop(px, pz, hx, hz)) continue;      // 赤信号なら停止線で待つ
    if (carBlocked(c, px, pz, hx, hz)) continue;   // 前車・横断中の歩行者

    const o = { x: px, z: pz, path: c.path, pi: c.pi,
                targetHeading: c.group.rotation.y + Math.PI / 2 };
    const done = advance(o, dts, 34);
    c.pi = o.pi;
    c.group.position.set(o.x, 0, o.z);
    c.group.rotation.y = lerpAngle(c.group.rotation.y, o.targetHeading - Math.PI / 2, Math.min(1, dts * 7));
    if (done) {
      const a = c.rider;
      if (a) {
        // 車道の真ん中ではなく歩道に降ろす
        const sn = snapToSidewalk(o.x, o.z);
        a.x = sn.x; a.z = sn.z; a.vis = 1; a.car = null;
        a.path = pedRoute(a.x, a.z, a.dest);
        a.pi = 0; a.state = 'walk';
      }
      c.busy = false; c.rider = null; c.group.visible = false;
    }
  }
}

function updateParticles(dts) {
  const d = seriesAt(month);
  if (d) {
    const rate = d.gdp / (d.gdp0 || 1);
    for (const b of buildings) {
      if (!b.chimneys) continue;
      if (Math.random() < rate * dts * 2.2 && puffs.length < 38)
        puffs.push({ p: b.chimneys[(Math.random() * b.chimneys.length) | 0].clone(),
                     t: 0, dur: 3, r: 0.8 + Math.random() * 0.6, vx: (Math.random() - 0.5) });
    }
  }
  for (let i = puffs.length - 1; i >= 0; i--) { puffs[i].t += dts; if (puffs[i].t > puffs[i].dur) puffs.splice(i, 1); }
  for (let i = 0; i < inst.puff.count; i++) {
    const s = puffs[i];
    if (!s) { inst.puff.setMatrixAt(i, HIDDEN); continue; }
    const t = s.t / s.dur, r = s.r * (1 + t * 2.4);
    _m.compose(_p.set(s.p.x + s.vx * t * 6, s.p.y + t * 10, s.p.z), _q.identity(), _s.set(r, r, r));
    inst.puff.setMatrixAt(i, _m);
  }
  inst.puff.instanceMatrix.needsUpdate = true;
}

// --- カメラ -----------------------------------------------------------------

/** カメラの向きのまま、街全体が確実に収まる正射影サイズを求める */
function fitToTown(aspect) {
  const b = { x: TOWN_W / 2 - 6, y0: -3, y1: 27, z0: TRAIN_Z - 5, z1: AVE_Z.at(-1) + 16 };
  const q = camera.quaternion.clone().invert();
  let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
  for (const sx of [-b.x, b.x]) for (const sy of [b.y0, b.y1]) for (const sz of [b.z0, b.z1]) {
    _v.set(sx, sy, sz).applyQuaternion(q);
    x0 = Math.min(x0, _v.x); x1 = Math.max(x1, _v.x);
    y0 = Math.min(y0, _v.y); y1 = Math.max(y1, _v.y);
  }
  const hw = (x1 - x0) / 2, hh = (y1 - y0) / 2;
  return { view: Math.max(hw, hh * aspect) * 0.97, cx: (x0 + x1) / 2, cy: (y0 + y1) / 2 };
}

function resize() {
  const w = wrapEl.clientWidth | 0, h = wrapEl.clientHeight | 0;
  // パネルが隠れていると 0 になる。そのまま計算すると aspect が NaN になり
  // 射影行列が壊れて画面が真っ黒になるので、触らずに戻る
  if (w < 2 || h < 2) return;
  renderer.setSize(w, h, false);
  const aspect = w / h;

  if (!controls.__init) {
    camera.position.set(150, 128, 186);
    camera.lookAt(controls.target);
    controls.__init = true;
    // 初期表示だけ街の中心に合わせる。以後はユーザーの操作に任せる
    const f = fitToTown(aspect);
    controls.target.x += f.cx * 0.0;              // 中心合わせは lookAt 側で済む
    camView = f.view;
  }
  const view = camView || Math.max(TOWN_W, TOWN_D) * 0.62;
  camera.left = -view; camera.right = view;
  camera.top = view / aspect; camera.bottom = -view / aspect;
  camera.updateProjectionMatrix();
  controls.update();
}

// --- 再生 -------------------------------------------------------------------

function setRun(result, which) {
  run = result; variant = which || 'treatment';
  data = result.runs[variant] || result.runs.baseline;
  month = 0; phaseT = 0; applyMonth(0); onPhase(0);
}
function setVariant(w) { if (run && run.runs[w]) { variant = w; data = run.runs[w]; applyMonth(month); } }
function seek(m) {
  month = Math.max(0, Math.min((data ? data.months.length : 1) - 1, m | 0));
  phaseT = 0; applyMonth(month); onPhase(phaseIndex());
  if (onMonth) onMonth(month, phaseIndex());
}
const phaseIndex = () => Math.min(5, Math.floor(phaseT / (MONTH_MS / 6)));
function start() { if (!raf) { last = performance.now(); raf = requestAnimationFrame(tick); } }
function stop() { if (raf) { cancelAnimationFrame(raf); raf = null; } }
function setPlaying(p) { playing = p; }

function tick(now) {
  const dt = Math.min(64, now - last); last = now;
  const dts = dt / 1000;

  if (playing && data) {
    const prev = phaseIndex();
    phaseT += dt;
    if (phaseT >= MONTH_MS) { phaseT = 0; month = (month + 1) % data.months.length; applyMonth(month); }
    const p = phaseIndex();
    if (p !== prev) onPhase(p);
    if (onMonth) onMonth(month, p);
  }

  const p = phaseIndex(), frac = (phaseT % (MONTH_MS / 6)) / (MONTH_MS / 6);
  paintSky(p, frac);
  const dayT = (p + frac) / 6, ang = Math.PI * (0.08 + dayT * 0.9);
  sun.position.set(Math.cos(ang) * 120, Math.max(10, Math.sin(ang) * 110), 70);
  sun.intensity = 0.7 + Math.max(0, Math.sin(ang)) * 2.2;
  sun.color.setHex(SUN_COL[p]);
  const night = p >= 4 ? (p === 4 ? 0.4 + frac * 0.5 : 0.9) : (p === 3 ? frac * 0.4 : 0);
  hemi.intensity = 1.4 - night * 0.7;
  winMat.emissiveIntensity = night * 3.2;

  if (autoOrbit) {
    orbitT += dts * 0.035;
    const r = Math.hypot(150, 186);
    camera.position.x = Math.sin(orbitT + 0.68) * r;
    camera.position.z = Math.cos(orbitT + 0.68) * r;
    camera.position.y = 128;
    camera.lookAt(controls.target);
  }
  controls.update();

  updateSignals(now / 1000);
  updateAgents(dts);
  updateCars(dts);
  updateTrain(dts);
  updateParticles(dts);
  renderer.render(scene, camera);
  raf = requestAnimationFrame(tick);
}

export const Town = {
  _step: sec => {
    for (let t = 0; t < sec; t += 1 / 60) {
      simClock += 1 / 60;
      updateSignals(simClock);
      updateAgents(1 / 60); updateCars(1 / 60); updateTrain(1 / 60);
    }
  },
  _jump: (m, ph) => { seek(m); phaseT = ph * (MONTH_MS / 6) + 40; applyMonth(m); onPhase(ph); },
  /** 交差点を真上から見る(横断歩道の検分用) */
  _cross: (jx = 2, iz = 1) => {
    autoOrbit = false;
    const x = ST_X[jx], z = AVE_Z[iz];
    controls.target.set(x, 0, z);
    camera.position.set(x + 0.01, 120, z + 0.01);
    camera.zoom = 9; camera.updateProjectionMatrix(); controls.update();
    return `(${x}, ${z})`;
  },
  _find: (name, dist = 46) => {
    const b = buildings.find(x => (x.name || '').includes(name) || (x.cat || '') === name);
    if (!b) return 'not found';
    autoOrbit = false;
    controls.target.set(b.x, 5, b.z);
    camera.position.set(b.x + dist * 0.7, 34, b.z + dist);
    camera.zoom = 3.4; camera.updateProjectionMatrix(); controls.update();
    return b.name || b.kind;
  },
  _look: (i, dist = 60) => {
    const st = stations[i]; if (!st) return 'no station';
    autoOrbit = false;
    controls.target.set(st.board.x, 8, st.board.z);
    const dir = new THREE.Vector3(st.board.x, 0, st.board.z).normalize();
    camera.position.set(st.board.x + dir.x * dist + 20, 46, st.board.z + dir.z * dist + 40);
    camera.zoom = 3.2; camera.updateProjectionMatrix(); controls.update();
    return st.name;
  },
  _cam: () => ({ pos: camera.position.toArray().map(v => +v.toFixed(1)),
                 target: controls.target.toArray().map(v => +v.toFixed(1)),
                 zoom: +camera.zoom.toFixed(3), auto: autoOrbit,
                 view: [camera.left, camera.right, camera.top, camera.bottom].map(v => +v.toFixed(1)) }),
  _overlaps: () => {
    const out = [];
    for (let i = 0; i < buildings.length; i++) for (let j = i + 1; j < buildings.length; j++) {
      const a = buildings[i], b = buildings[j];
      const ox = ((a.fw ?? a.w) + (b.fw ?? b.w)) / 2 - Math.abs(a.x - b.x);
      const oz = ((a.fd ?? a.d) + (b.fd ?? b.d)) / 2 - Math.abs(a.z - b.z);
      if (ox > 0 && oz > 0) out.push(`${a.name || a.kind}×${b.name || b.kind} (${ox.toFixed(1)},${oz.toFixed(1)})`);
    }
    return out;
  },
  /** 信号無視の検査: 車道の上にいる歩行者が、その横断に対して青かどうか */
  /** 信号の状態と、いま横断待ちをしている人の内訳 */
  /** 重なりの検査: 車同士 / 車と人 / 人同士 */
  /** 逆走している車の中身を見る */
  _wrong: () => {
    const out = [];
    for (const A of cars) {
      if (!A.busy || out.length >= 5) continue;
      const wp = A.path[A.pi]; if (!wp) continue;
      const px = A.group.position.x, pz = A.group.position.z;
      const hx = (wp[0] ?? wp.x) - px, hz = (wp[1] ?? wp.z) - pz;
      let bad = null;
      if (Math.abs(hx) > Math.abs(hz) && Math.abs(hx) > 0.5) {
        const iz = AVE_Z[nearestIdx(AVE_Z, pz)], side = pz - iz;
        if (Math.sign(side) === Math.sign(hx) && Math.abs(side) > 0.6)
          bad = { 軸: '東西', 進行: hx > 0 ? '+x' : '-x', 車線側: +side.toFixed(1), 通り: iz };
      } else if (Math.abs(hz) > 0.5) {
        const ix = ST_X[nearestIdx(ST_X, px)], side = px - ix;
        if (Math.sign(side) !== Math.sign(hz) && Math.abs(side) > 0.6)
          bad = { 軸: '南北', 進行: hz > 0 ? '+z' : '-z', 車線側: +side.toFixed(1), 通り: ix };
      }
      if (bad) out.push(Object.assign(bad, { pi: A.pi, n: A.path.length,
        pos: [+px.toFixed(1), +pz.toFixed(1)], wp: [+(wp[0] ?? wp.x).toFixed(1), +(wp[1] ?? wp.z).toFixed(1)] }));
    }
    return out;
  },
  _collide: () => {
    const out = { 車と車: 0, 車と人: 0, 人と人: 0, 逆走: 0 };
    const on = agents.filter(a => a.vis > 0.05);
    for (let i = 0; i < cars.length; i++) {
      const A = cars[i]; if (!A.busy) continue;
      for (let j = i + 1; j < cars.length; j++) {
        const B = cars[j]; if (!B.busy) continue;
        if (A.group.position.distanceTo(B.group.position) < 4.6) out.車と車++;
      }
      for (const a of on)
        if (Math.hypot(A.group.position.x - a.x, A.group.position.z - a.z) < 2.6) out.車と人++;
      // 逆走: 進行方向に対して車線が左側にあるか
      const wp = A.path[A.pi];
      if (wp) {
        const hx = (wp[0] ?? wp.x) - A.group.position.x, hz = (wp[1] ?? wp.z) - A.group.position.z;
        if (Math.abs(hx) > Math.abs(hz) && Math.abs(hx) > 0.5) {
          const iz = AVE_Z[nearestIdx(AVE_Z, A.group.position.z)];
          const side = A.group.position.z - iz;
          if (Math.sign(side) === Math.sign(hx) && Math.abs(side) > 0.6) out.逆走++;
        } else if (Math.abs(hz) > 0.5) {
          const ix = ST_X[nearestIdx(ST_X, A.group.position.x)];
          const side = A.group.position.x - ix;
          if (Math.sign(side) !== Math.sign(hz) && Math.abs(side) > 0.6) out.逆走++;
        }
      }
    }
    for (let i = 0; i < on.length; i++) for (let j = i + 1; j < on.length; j++)
      if (Math.hypot(on[i].x - on[j].x, on[i].z - on[j].z) < 1.15) out.人と人++;
    return out;
  },
  _sig: () => {
    let ave = 0, st = 0;
    for (const a of agents) {
      if (!a.waitSignal || !a.path || !a.path[a.pi]) continue;
      if (a.path[a.pi].cross === 'ave') ave++; else if (a.path[a.pi].cross === 'st') st++;
    }
    return { nsGreen, 東西の通りを渡る待ち: ave, 南北の通りを渡る待ち: st };
  },
  _jaywalk: () => {
    const bad = [];
    for (const a of agents) {
      if (a.vis <= 0.01 || a.crossing) continue;   // 青で入って渡り切る途中は除く
      const onAve = AVE_Z.some(z => Math.abs(a.z - z) < ROAD_H);   // 東西の車道上
      const onSt  = ST_X.some(x => Math.abs(a.x - x) < ROAD_H);    // 南北の車道上
      if (!onAve && !onSt) continue;
      // 横断歩道の位置にいるか
      const atCrossAve = ST_X.some(x => Math.abs(a.x - (x - SW)) < 2.6 || Math.abs(a.x - (x + SW)) < 2.6);
      const atCrossSt  = AVE_Z.some(z => Math.abs(a.z - (z - SW)) < 2.6 || Math.abs(a.z - (z + SW)) < 2.6);
      const rec = k => bad.push({ kind: k, state: a.state, x: +a.x.toFixed(1), z: +a.z.toFixed(1),
                                  pi: a.pi, n: a.path ? a.path.length : 0,
                                  wp: a.path && a.path[a.pi] ? { x: +a.path[a.pi].x.toFixed(1),
                                       z: +a.path[a.pi].z.toFixed(1), cross: a.path[a.pi].cross } : null });
      if (onAve && !onSt) { if (!atCrossAve) rec('横断歩道外(東西)'); else if (!nsGreen) rec('赤で東西横断'); }
      else if (onSt && !onAve) { if (!atCrossSt) rec('横断歩道外(南北)'); else if (nsGreen) rec('赤で南北横断'); }
    }
    return { violations: bad.length, detail: bad.slice(0, 6) };
  },
  _fx: () => ({ type: lawFx && lawFx.type, active: lawActive(),
                meshes: fxMeshes.length, visible: fxMeshes.filter(m => m.visible).length }),
  _debug: () => ({ buildings: buildings.length, agents: agents.length,
                   inside: agents.filter(a => a.state === 'inside').length,
                   riding: agents.filter(a => a.state === 'riding').length,
                   carsBusy: cars.filter(c => c.busy).length,
                   onTrain: train ? train.riders.length : 0,
                   waiting: agents.filter(a => a.state === 'waiting').length,
                   carrying: agents.filter(a => a.carry).length }),
  init, setRun, setVariant, seek, setPlaying, start, stop, setLaw,
  get month() { return month; },
  get phase() { return phaseIndex(); },
  get phaseName() { return PHASES[phaseIndex()]; },
  get length() { return data ? data.months.length : 0; },
  get variant() { return variant; },
  set onMonth(fn) { onMonth = fn; },
};
