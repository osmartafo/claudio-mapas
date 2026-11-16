// STORY · personajes de caricatura para los cortos (motor de la skill shorts-animados-3d, licencia MIT, ver
// LICENSE-caricatura.txt). Cada personaje es una tarjeta dibujada a mano (cabeza de frijol, contorno ciruela, cara con
// expresiones) que vive dentro del mundo 3D, voltea siempre a la cámara, parpadea, habla moviendo la boca y toma el
// tono de la luz de la escena. Se compila con esbuild a ../caricatura.js (three queda externo: usa el mismo de la escena).
import * as THREE from "three";
import { Pen, bodyFront, blobPts, headBlob, mul, mix, shade, cabezaDe, INK, Outfit, Expr, MouthK } from "./toon";
import { cardShade, CARD_K } from "./cardshade";
import { CHAR } from "./shade";

export { CHAR, CARD_K };
const PIELES = ["#ffe2c2", "#f5c9a0", "#e7b48c", "#c99067", "#9c6a48", "#7a4f35"];
const ROPA = ["#3f6fb0", "#c4544c", "#4f8a5b", "#7b5ac9", "#d08a3a", "#2f4858", "#a8466e", "#5b6b7a"];
const PELO = ["#2b1d18", "#4a3020", "#1d1a24", "#6b4423", "#8a5a2b", "#3a2a24"];
const hash = (s: string) => { let h = 7; for (const c of s) h = (h * 31 + c.charCodeAt(0)) >>> 0; return h; };

type O = Record<string, any>;
const EXPR: Record<string, Expr> = {
  neutral: "neutral", triste: "sad", herido: "hurt", dolido: "hurt", llora: "cry", llorando: "cry", miedo: "scared",
  asustado: "scared", sorpresa: "shock", sorprendido: "shock", enojo: "angry", enojado: "angry", sonrie: "tender",
  sonriendo: "tender", feliz: "smile_closed", rie: "laugh", nervioso: "nervous", serio: "stern", tierno: "tender",
};

function vestuario(o: O): Outfit {
  const h = hash(o.id || "x");
  const ropa = o.color_ropa || o.color || ROPA[h % ROPA.length];
  const pelo = o.color_pelo || PELO[(h >> 3) % PELO.length];
  const piel = o.piel || PIELES[(h >> 5) % PIELES.length];
  const f: Outfit = { jacket: ropa, pants: mix(ropa, "#2a2734", 0.65), boots: "#3a2a24", skin: piel,
    hat: o.peinado === "gorra" ? "cap" : o.peinado === "calvo" ? null : "hair", hair: pelo, cap: mix(ropa, "#ffffff", 0.15),
    build: o.nino ? "kid" : o.complexion === "robusto" ? "stout" : "adult" };
  if (o.vestido) f.dress = typeof o.vestido === "string" ? o.vestido : ropa;
  if (o.bigote) f.moustache = pelo;
  return f;
}

export type Estado = { u: number; seg: number; habla: boolean; facing: -1 | 0 | 1; espaldas: boolean; look: number; expr?: string };

/** pelo largo o chongo: se pinta detrás de la cabeza antes del cuerpo */
function peloDetras(p: Pen, o: O, f: Outfit, seed: number, mode: string) {
  if (o.peinado !== "largo" && o.peinado !== "chongo") return;
  const c = cabezaDe(f, seed, mode), H = headBlob(seed, c.a, 0), col = f.hair || "#2b1d18";
  if (o.peinado === "largo") {
    const pts = blobPts(300, c.hc + 0.45 * c.b, { ...H, a: H.a * 1.14, b: H.b * 1.38, nTop: 2.0, nBot: 3.2, egg: 0.05, asym: 0, rot: 0 });
    p.gradFill(pts, col, mul(col, [0.62, 0.62, 0.7]), -2.1);
    p.inkRing(pts, 6, 0.6);
  } else {
    p.ell(300 + 0.15 * c.a, c.crown + 0.12 * c.b, 0.42 * c.a, 0.4 * c.a, col, 6);
  }
}

export function crearPersonaje(o: O, genero: string) {
  const f = vestuario(o), seed = (hash(o.id || "x") % 97) + 1;
  const pose = o.pose || "de_pie";
  const mode = pose === "sentado" || pose === "cabizbajo" || pose === "acostado" ? "sit" : pose === "caminando" ? "stroll" : "stand";
  const c = cabezaDe(f, seed, mode);
  const sole = 975, alto = (o.altura || 1.7) * (o.nino ? 0.7 : 1);
  const tall = sole - cabezaDe(f, seed, "stand").crown;               // unidades de dibujo de la coronilla a los pies (de pie)
  const m = alto / tall;                                               // metros por unidad
  const cardH = 1000 * m, cardW = 600 * m;
  let base: Expr = EXPR[(o.expresion || "").toLowerCase()] || "neutral";
  if (!o.expresion) {
    if (pose === "cabizbajo" || pose === "manos_cara") base = genero === "amor" ? "hurt" : "sad";
    else if (genero === "amor") base = /^#(4d8bff|5|6|7|8|9a)/i.test(o.luz || "") ? "sad" : o.luz ? "tender" : "neutral";
    else if (genero === "terror") base = o.cara === "ojos_brillo" ? "stern" : "nervous";
  }
  if (o.cara === "ojos_brillo") f.skin = "#9aa0a8";
  const K = 2;                                                         // resolución: 1200 x 2000 px por dibujo
  const cache = new Map<string, THREE.CanvasTexture>();
  const mat = cardShade(new THREE.MeshLambertMaterial({ transparent: false, alphaTest: 0.5, side: THREE.DoubleSide }));
  const geo = new THREE.PlaneGeometry(cardW, cardH);
  geo.translate(0, cardH / 2 - 0.025 * cardH, 0);                      // los pies (y = 975 de 1000) quedan en el piso
  const tarjeta = new THREE.Mesh(geo, mat);
  tarjeta.castShadow = false; tarjeta.receiveShadow = false;
  tarjeta.userData.outlineParameters = { visible: false };
  const raiz = new THREE.Group(); const giro = new THREE.Group(); raiz.add(giro); giro.add(tarjeta);
  // sentado: la tarjeta sube a la altura del asiento y se adelanta hacia la cámara para que la silla quede detrás
  if (mode === "sit") { tarjeta.position.set(0, (o.asiento ?? 0.45) - 0.17, 0.32); }
  else tarjeta.position.z = 0.06;
  tarjeta.userData.z0 = tarjeta.position.z;
  // sombra de contacto suave en el piso
  const cv = document.createElement("canvas"); cv.width = cv.height = 64; const g = cv.getContext("2d")!;
  const gr = g.createRadialGradient(32, 32, 2, 32, 32, 32); gr.addColorStop(0, "rgba(0,0,0,0.75)"); gr.addColorStop(1, "rgba(0,0,0,0)");
  g.fillStyle = gr; g.fillRect(0, 0, 64, 64);
  const sombra = new THREE.Mesh(new THREE.PlaneGeometry(cardW * 0.62, cardW * 0.26),
    new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(cv), transparent: true, depthWrite: false, opacity: 0.55 }));
  sombra.rotation.x = -Math.PI / 2; sombra.position.y = 0.012; raiz.add(sombra);
  // marcador de la cabeza para la cámara automática (infoPersonaje le suma 0.13 m)
  const cabeza = new THREE.Object3D();
  cabeza.position.set(0, (sole - c.hc) * m - 0.13 + tarjeta.position.y, 0); raiz.add(cabeza);
  raiz.userData.cabeza = cabeza; raiz.userData.toon = true;
  raiz.userData.medidas = { cabeza: (sole - c.hc) * m, medio: c.b * m, alto };
  const fase = (seed % 13) * 0.37;
  let ultima = "";

  function dibujo(clave: string, opts: any) {
    let t = cache.get(clave);
    if (!t) {
      const lienzo = document.createElement("canvas"); lienzo.width = 600 * K; lienzo.height = 1000 * K;
      const x = lienzo.getContext("2d")!; x.setTransform(K, 0, 0, K, 0, 0);
      const p = new Pen(x);
      peloDetras(p, o, f, seed, mode);
      bodyFront(p, f, opts);
      t = new THREE.CanvasTexture(lienzo); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4;
      cache.set(clave, t);
      if (cache.size > 28) { const k0 = cache.keys().next().value as string; if (k0 !== clave) { cache.get(k0)!.dispose(); cache.delete(k0); } }
    }
    return t;
  }

  function actualizar(e: Estado) {
    const s = e.seg + fase;
    const expr = (e.expr && EXPR[e.expr]) || base;
    const parpadeo = ((s % (3.3 + (seed % 5) * 0.31)) < 0.13) ? 1 : 0;
    let boca: MouthK | undefined;
    if (e.habla) { const ciclo = Math.floor(s * 8.5) % 4; boca = (["o", "O", "dash", "smile"] as MouthK[])[ciclo]; if (expr === "cry" || expr === "hurt" || expr === "sad") boca = (["o", "wave", "O", "frown"] as MouthK[])[ciclo]; }
    const lagrima = expr === "cry" ? 0.35 + 0.65 * ((s * 0.4) % 1) : 0;
    const look = Math.round(e.look * 4) / 4;
    const phase = mode === "stroll" ? Math.floor(((s * 1.6) % 1) * 12) / 12 : 0;
    const headTilt = pose === "cabizbajo" ? 9 : e.habla ? Math.round(3 * Math.sin(s * 5)) : 0;
    const tilt = Math.round(1.5 * Math.sin(s * 1.3) * 2) / 2;          // respira, se mece un poco
    const wave = pose === "senalando" ? 0.6 : undefined;
    const clave = [expr, boca || "-", parpadeo, e.facing, e.espaldas ? 1 : 0, look, phase, headTilt, tilt, Math.round(lagrima * 4)].join("|");
    if (clave !== ultima) {
      ultima = clave;
      mat.map = dibujo(clave, { expr, boca, blink: parpadeo, facing: e.facing, espaldas: e.espaldas, look, phase, headTilt, tilt, wave,
        mode, seed, lagrima, lift: 40 });
      mat.needsUpdate = true;
    }
  }
  return { raiz, giro, tarjeta, actualizar };
}

/** tono de las tarjetas según el ambiente: cuánto las tiñe la luz y qué tan brillantes quedan */
export function tonoTarjetas(tinte: [number, number, number], ganancia: number, sombra = 0.86) {
  CHAR.uCharTint.value.set(...tinte); CHAR.uCharShade.value = sombra;
  CARD_K.uNorm.value = 0; CARD_K.uGain.value = ganancia; CARD_K.uPx.value = 0.5;
}
export { INK, shade };
