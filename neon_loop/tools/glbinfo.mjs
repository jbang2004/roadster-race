// Lists the nodes / primitives (material, attributes) of a GLB: node tools/glbinfo.mjs file.glb [nameFilter]
import fs from 'node:fs';
const buf = fs.readFileSync(process.argv[2]);
const len = buf.readUInt32LE(12);
const j = JSON.parse(buf.subarray(20, 20 + len).toString());
const re = new RegExp(process.argv[3] ?? '.');
for (const n of j.nodes) {
  if (!re.test(n.name) || n.mesh == null) continue;
  const m = j.meshes[n.mesh];
  for (const p of m.primitives) {
    const at = Object.entries(p.attributes).map(([k, a]) => `${k}:${j.accessors[a].type}`).join(' ');
    console.log(n.name.padEnd(18), (j.materials[p.material]?.name ?? '-').padEnd(12), at, 'count', j.accessors[p.attributes.POSITION].count);
  }
}
