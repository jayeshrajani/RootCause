"use client";

import { useEffect, useRef } from "react";

import { cn } from "@/lib/utils";

const ROWS = 58;
const POINTS = 200;
const X_SPAN = 26;
const Z_NEAR = 4.5;
const Z_FAR = -14;
const HOTSPOT = { x: 0.9, z: -1.2 };

function height(x: number, z: number, t: number) {
  const base =
    0.32 * Math.sin(x * 0.55 + t * 0.35) * Math.cos(z * 0.45 + t * 0.25) +
    0.16 * Math.sin(x * 1.2 - z * 0.8 + t * 0.5);
  const d2 = (x - HOTSPOT.x) ** 2 + (z - HOTSPOT.z) ** 2;
  return base + 0.55 * Math.exp(-d2 / 1.1);
}

/** Crop rows rendered as animated contour lines, with a highlighted stress patch. */
export function FieldRows({ className }: { className?: string }) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    let disposed = false;
    let cleanup = () => {};

    void import("three").then((THREE) => {
      if (disposed) return;
      const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

      const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      renderer.setClearColor(0x000000, 0);
      renderer.domElement.style.display = "block";
      container.appendChild(renderer.domElement);

      const scene = new THREE.Scene();
      const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 100);
      let cameraZ = 6.2;
      let cameraY = 3.4;
      let lookZ = -1.5;
      camera.position.set(0, cameraY, cameraZ);

      const lineColor = new THREE.Color("#163626");
      const hotColor = new THREE.Color("#cf8336");
      const rows: { positions: Float32Array; attr: InstanceType<typeof THREE.BufferAttribute>; z: number }[] = [];
      const disposables: { dispose: () => void }[] = [];

      for (let r = 0; r < ROWS; r++) {
        const z = Z_NEAR + (Z_FAR - Z_NEAR) * (r / (ROWS - 1));
        const positions = new Float32Array(POINTS * 3);
        const colors = new Float32Array(POINTS * 3);
        for (let i = 0; i < POINTS; i++) {
          const x = -X_SPAN / 2 + (X_SPAN * i) / (POINTS - 1);
          positions[i * 3] = x;
          positions[i * 3 + 2] = z;
          const d = Math.hypot(x - HOTSPOT.x, z - HOTSPOT.z);
          const mix = Math.max(0, 1 - d / 1.6);
          const c = lineColor.clone().lerp(hotColor, mix);
          colors.set([c.r, c.g, c.b], i * 3);
        }
        const geometry = new THREE.BufferGeometry();
        const attr = new THREE.BufferAttribute(positions, 3);
        geometry.setAttribute("position", attr);
        geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));
        const depth = r / (ROWS - 1);
        const material = new THREE.LineBasicMaterial({
          vertexColors: true,
          transparent: true,
          opacity: Math.max(0, 0.9 - depth),
        });
        scene.add(new THREE.Line(geometry, material));
        rows.push({ positions, attr, z });
        disposables.push(geometry, material);
      }

      const ringGeometry = new THREE.RingGeometry(0.42, 0.46, 64);
      const ringMaterial = new THREE.MeshBasicMaterial({
        color: hotColor,
        transparent: true,
        side: THREE.DoubleSide,
      });
      const ring = new THREE.Mesh(ringGeometry, ringMaterial);
      ring.rotation.x = -Math.PI / 2;
      scene.add(ring);
      disposables.push(ringGeometry, ringMaterial);

      const pointer = { x: 0, y: 0 };
      const onPointerMove = (event: PointerEvent) => {
        pointer.x = (event.clientX / window.innerWidth) * 2 - 1;
        pointer.y = (event.clientY / window.innerHeight) * 2 - 1;
      };
      window.addEventListener("pointermove", onPointerMove, { passive: true });

      const resize = () => {
        const { width, height: h } = container.getBoundingClientRect();
        if (!width || !h) return;
        renderer.setSize(width, h, false);
        renderer.domElement.style.width = "100%";
        renderer.domElement.style.height = "100%";
        camera.aspect = width / h;
        const portrait = camera.aspect < 1.1;
        const wide = camera.aspect > 2.4;
        camera.fov = portrait ? 50 : wide ? 30 : 38;
        cameraZ = portrait ? 5.6 : 6.2;
        cameraY = portrait ? 5.4 : 3.4;
        lookZ = portrait ? -3.6 : wide ? -2.2 : -1.5;
        camera.updateProjectionMatrix();
      };
      const resizeObserver = new ResizeObserver(resize);
      resizeObserver.observe(container);
      resize();

      let visible = true;
      const intersection = new IntersectionObserver(([entry]) => {
        visible = entry?.isIntersecting ?? true;
      });
      intersection.observe(container);

      const draw = (t: number) => {
        for (const { positions, attr, z } of rows) {
          for (let i = 0; i < POINTS; i++) positions[i * 3 + 1] = height(positions[i * 3]!, z, t);
          attr.needsUpdate = true;
        }
        const pulse = (t * 0.6) % 1;
        ring.position.set(HOTSPOT.x, height(HOTSPOT.x, HOTSPOT.z, t) + 0.04, HOTSPOT.z);
        ring.scale.setScalar(0.6 + pulse * 1.6);
        ringMaterial.opacity = 0.9 * (1 - pulse);

        camera.position.x += (pointer.x * 0.9 - camera.position.x) * 0.04;
        camera.position.y += (cameraY - pointer.y * 0.35 - camera.position.y) * 0.04;
        camera.position.z = cameraZ;
        camera.lookAt(0, 0, lookZ);
        renderer.render(scene, camera);
      };

      let frame = 0;
      const start = performance.now();
      const loop = () => {
        frame = requestAnimationFrame(loop);
        if (visible) draw((performance.now() - start) / 1000);
      };
      if (reduceMotion) draw(2);
      else loop();

      cleanup = () => {
        cancelAnimationFrame(frame);
        window.removeEventListener("pointermove", onPointerMove);
        resizeObserver.disconnect();
        intersection.disconnect();
        disposables.forEach((d) => d.dispose());
        renderer.dispose();
        renderer.domElement.remove();
      };
    });

    return () => {
      disposed = true;
      cleanup();
    };
  }, []);

  return <div ref={containerRef} className={cn("relative", className)} aria-hidden />;
}
