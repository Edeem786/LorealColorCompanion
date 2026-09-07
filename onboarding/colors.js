// sRGB → normalized OKLab. Fixed conversion, no learned model.
function toLab(rgb) {
  const [r,g,b] = rgb.map(v => { v /= 255; return v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4; });
  const l = Math.cbrt(.4122214708*r + .5363325363*g + .0514459929*b);
  const m = Math.cbrt(.2119034982*r + .6806995451*g + .1073969566*b);
  const s = Math.cbrt(.0883024619*r + .2817188376*g + .6299787005*b);
  return [Math.max(0, Math.min(1,.2104542553*l + .793617785*m - .0040720468*s)),
    1.9779984951*l - 2.428592205*m + .4505937099*s,
    .0259040371*l + .7827717662*m - .808675766*s];
}
function hex(rgb) { return '#' + rgb.map(v => Math.round(v).toString(16).padStart(2,'0')).join(''); }
function palette(data) {
  const bins = new Map();
  for (let i=0;i<data.length;i+=4) {
    if (data[i+3] < 250) continue;
    const rgb = [data[i],data[i+1],data[i+2]], lab = toLab(rgb);
    const key = lab.map(v => Math.floor(v/.025)).join(',');
    const bin = bins.get(key) || {count:0, sum:[0,0,0]};
    bin.count++; rgb.forEach((v,j) => bin.sum[j]+=v); bins.set(key,bin);
  }
  const result=[];
  for (const bin of [...bins.values()].sort((a,b)=>b.count-a.count)) {
    const rgb=bin.sum.map(v=>Math.round(v/bin.count)), color=toLab(rgb);
    if (result.every(p=>Math.hypot(...p.color.map((v,i)=>v-color[i])) >= .045))
      result.push({rgb,color,hex:hex(rgb)});
    if (result.length===3) break;
  }
  return result;
}
if (typeof module !== 'undefined') module.exports={toLab,palette};
