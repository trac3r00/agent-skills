#!/usr/bin/env python3
"""scaffold-3d: generate a self-contained Three.js scene as one HTML file.

Emits a single HTML file with Three.js from CDN, OrbitControls, lighting,
and the requested primitive objects arranged in a layout — the starting
point an agent or designer iterates on instead of writing boilerplate.
No build step; open the file in a browser.

Usage:
    scaffold_3d.py --objects cube,sphere,plane --out scene.html [--json]
    scaffold_3d.py --objects torus,cone --camera 4,3,6 --bg 0x101018

Objects: cube, sphere, plane, torus, cone, cylinder, points (particle field).

Exit codes: 0 written, 2 unknown object/usage error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

GEOMETRIES = {
    "cube": ("BoxGeometry(1, 1, 1)", "Lambert"),
    "sphere": ("SphereGeometry(0.7, 32, 32)", "Lambert"),
    "plane": ("PlaneGeometry(8, 8)", "Lambert"),
    "torus": ("TorusGeometry(0.6, 0.25, 16, 48)", "Lambert"),
    "cone": ("ConeGeometry(0.6, 1.4, 32)", "Lambert"),
    "cylinder": ("CylinderGeometry(0.4, 0.4, 1.2, 32)", "Lambert"),
}

TEMPLATE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>3D Scene — TITLE</title>
<style>body{{margin:0;overflow:hidden}}canvas{{display:block}}</style>
</head>
<body>
<script type="importmap">
{{"imports": {{"three": "https://unpkg.com/three@0.160.0/build/three.module.js",
             "three/addons/": "https://unpkg.com/three@0.160.0/examples/jsm/"}}}}
</script>
<script type="module">
import * as THREE from 'three';
import {{ OrbitControls }} from 'three/addons/controls/OrbitControls.js';

const scene = new THREE.Scene();
scene.background = new THREE.Color(BGCOLOR);

const camera = new THREE.PerspectiveCamera(60, innerWidth/innerHeight, 0.1, 100);
camera.position.set(CAMERA);

const renderer = new THREE.WebGLRenderer({{ antialias: true }});
renderer.setSize(innerWidth, innerHeight);
renderer.setPixelRatio(devicePixelRatio);
document.body.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;

scene.add(new THREE.AmbientLight(0xffffff, 0.45));
const key = new THREE.DirectionalLight(0xffffff, 1.1);
key.position.set(4, 6, 5);
scene.add(key);
const fill = new THREE.DirectionalLight(0x8899ff, 0.35);
fill.position.set(-4, 2, -3);
scene.add(fill);

OBJECTS

const grid = new THREE.GridHelper(10, 20, 0x333344, 0x222228);
scene.add(grid);

function animate() {{
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}}
animate();

addEventListener('resize', () => {{
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
}});
</script>
</body>
</html>
"""


def object_block(name: str, i: int) -> str:
    if name == "points":
        return """
{
  const n = 2000;
  const pos = new Float32Array(n * 3);
  for (let k = 0; k < n * 3; k += 3) {
    pos[k] = (Math.random() - 0.5) * 8;
    pos[k+1] = Math.random() * 4;
    pos[k+2] = (Math.random() - 0.5) * 8;
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  const m = new THREE.PointsMaterial({ color: 0x66ccff, size: 0.02 });
  scene.add(new THREE.Points(g, m));
}"""
    geo, mat = GEOMETRIES[name]
    x = (i % 4) * 1.8 - 2.7
    z = (i // 4) * 1.8 - 0.9
    return f"""
{{
  const geo = new THREE.{geo};
  const mat = new THREE.Mesh{mat}Material({{ color: 0x{0x4f8fd9 + i * 0x1a2b3c & 0xffffff:06x} }});
  const mesh = new THREE.Mesh(geo, mat);
  mesh.position.set({x:.1f}, 0.7, {z:.1f});
  scene.add(mesh);
}}"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--objects", required=True, help="comma-separated")
    ap.add_argument("--out", required=True)
    ap.add_argument("--camera", default="4,3,6")
    ap.add_argument("--bg", default="0x101018")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    objects = [o.strip() for o in args.objects.split(",") if o.strip()]
    unknown = [o for o in objects if o not in GEOMETRIES and o != "points"]
    if unknown:
        print(f"unknown object(s): {', '.join(unknown)} "
              f"(have: {', '.join(sorted(GEOMETRIES))}, points)", file=sys.stderr)
        return 2
    cam = args.camera if "," in args.camera else "4,3,6"

    blocks = "\n".join(object_block(o, i) for i, o in enumerate(objects))
    html = (TEMPLATE
            .replace("TITLE", ", ".join(objects))
            .replace("BGCOLOR", args.bg)
            .replace("CAMERA", cam)
            .replace("OBJECTS", blocks))
    out = Path(args.out)
    out.write_text(html)
    if args.json:
        print(json.dumps({"written": str(out), "objects": objects,
                          "bytes": len(html)}, indent=2))
    else:
        print(f"written: {out} ({len(html):,} bytes) — open in a browser")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
