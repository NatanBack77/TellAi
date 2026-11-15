/* As 10 cenas do guia de plantio. Cada uma conta a etapa com movimento contínuo (loop). */
import { useMemo, useRef, type ComponentType } from "react";
import { useFrame } from "@react-three/fiber";
import { Float, Sparkles } from "@react-three/drei";
import * as THREE from "three";
import type { TopicoId } from "../../models/topicos.model";
import {
  aleatorio,
  Balanco,
  brotar,
  Broto,
  Caixote,
  Canteiro,
  CORES,
  Espiga,
  Feijao,
  linhasX,
  Mandioca,
  Milho,
  Nuvem,
  Onda,
  Particulas,
  Pin,
  Saco,
  Semente,
  Silo,
  Sol,
  Sulcos,
  suave,
  useTempoLocal,
} from "./pecas";

/* 1. Introdução: o ciclo da planta em volta do canteiro (semente → broto → jovem → adulta). */
function CenaIntroducao() {
  const centro = useRef<THREE.Group>(null);
  const tempo = useTempoLocal();
  useFrame(({ clock }) => {
    const t = tempo(clock.elapsedTime);
    if (centro.current) centro.current.scale.setScalar(0.2 + 0.8 * brotar(t / 2.2));
  });
  const estagios = [
    { a: -2.3, el: <Semente scale={2.2} position={[0, 0.12, 0]} /> },
    { a: -0.8, el: <Broto scale={2.2} /> },
    { a: 0.8, el: <Feijao escala={1.5} /> },
    { a: 2.3, el: <Milho altura={1.1} /> },
  ];
  return (
    <group>
      <Canteiro topo="grama" />
      {estagios.map(({ a, el }, i) => (
        <Balanco key={i} fase={i} position={[Math.sin(a) * 1.45, 0, Math.cos(a) * 1.45]}>
          {el}
        </Balanco>
      ))}
      <group ref={centro}>
        <Balanco forca={0.04}>
          <Milho altura={1.6} />
        </Balanco>
      </group>
      <Sparkles
        count={40}
        scale={[3.6, 2, 3.6]}
        position={[0, 1.2, 0]}
        size={3}
        speed={0.35}
        color={CORES.marca}
      />
    </group>
  );
}

/* 2. Recomendação: três canteiros (milho, feijão, mandioca) e o pino visitando cada um para comparar. */
function CenaRecomendacao() {
  const pin = useRef<THREE.Group>(null);
  const brilho = useRef<THREE.Mesh>(null);
  const colunas = [-1.35, 0, 1.35];
  useFrame(({ clock }) => {
    const t = clock.elapsedTime;
    const ciclo = (t / 2.6) % 3;
    const atual = Math.floor(ciclo);
    const frac = ciclo - atual;
    const de = colunas[atual]!;
    const para = colunas[(atual + 1) % 3]!;
    const mover = suave(THREE.MathUtils.clamp((frac - 0.7) / 0.3, 0, 1));
    const x = THREE.MathUtils.lerp(de, para, mover);
    if (pin.current) {
      pin.current.position.x = x;
      pin.current.position.y = 1.55 + Math.sin(mover * Math.PI) * 0.5 + Math.sin(t * 2.5) * 0.05;
    }
    if (brilho.current) {
      brilho.current.position.x = x;
      const s = 1 + Math.sin(t * 3) * 0.08;
      brilho.current.scale.set(s, s, s);
    }
  });
  const culturas = [
    (k: number) => <Milho key={k} altura={1.05} espigas={false} />,
    (k: number) => <Feijao key={k} escala={1.15} />,
    (k: number) => <Mandioca key={k} />,
  ];
  return (
    <group>
      <Canteiro topo="terra" />
      {/* divisórias */}
      {[-0.68, 0.68].map((x) => (
        <mesh key={x} position={[x, 0.04, 0]} receiveShadow>
          <boxGeometry args={[0.06, 0.06, 4]} />
          <meshStandardMaterial color={CORES.grama} />
        </mesh>
      ))}
      {colunas.map((x, c) =>
        [-1.3, -0.45, 0.4, 1.25].map((z, i) => (
          <Balanco key={`${c}-${i}`} fase={c + i * 0.7} position={[x + (i % 2 ? 0.2 : -0.2), 0, z]}>
            {culturas[c]!(i)}
          </Balanco>
        )),
      )}
      <mesh ref={brilho} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.03, 0]}>
        <ringGeometry args={[0.55, 0.68, 40]} />
        <meshStandardMaterial
          color={CORES.marca}
          emissive={CORES.marca}
          emissiveIntensity={0.9}
          transparent
          opacity={0.85}
          toneMapped={false}
        />
      </mesh>
      <group ref={pin} position={[0, 1.55, 0]}>
        <Pin scale={1.2} />
      </group>
    </group>
  );
}

/* 3. Clima e época: o sol percorre o céu, a nuvem passa e chove sobre a roça. */
function CenaClima() {
  const sol = useRef<THREE.Group>(null);
  const nuvem = useRef<THREE.Group>(null);
  useFrame(({ clock }) => {
    const t = clock.elapsedTime;
    const a = ((t / 9) % 1) * Math.PI;
    if (sol.current) sol.current.position.set(Math.cos(a) * 2.6, 1.2 + Math.sin(a) * 1.6, -1.2);
    if (nuvem.current) nuvem.current.position.x = Math.sin(t * 0.35) * 0.9;
  });
  const plantas = useMemo(() => {
    const r = aleatorio(5);
    return Array.from(
      { length: 12 },
      () => [(r() - 0.5) * 3.4, 0, (r() - 0.5) * 3.4] as [number, number, number],
    );
  }, []);
  return (
    <group>
      <Canteiro topo="grama" />
      {plantas.map((p, i) => (
        <Balanco key={i} fase={i} position={p}>
          <Feijao escala={0.9} />
        </Balanco>
      ))}
      <group ref={sol}>
        <Sol />
      </group>
      <group ref={nuvem} position={[0, 2.5, 0.3]}>
        <Nuvem scale={1.3} cor="#e9eef3" />
        <Particulas
          quantidade={70}
          origem={[0, -0.6, 0]}
          area={[1.4, 1.6, 0.9]}
          velocidade={-3.2}
          limite={-2.4}
          cor={CORES.agua}
        />
      </group>
      {[
        [-0.4, 0.4],
        [0.5, -0.2],
        [0.1, 0.8],
      ].map(([x, z], i) => (
        <Onda key={i} atraso={i * 0.5} position={[x!, 0.03, z!]} />
      ))}
    </group>
  );
}

/* 4. Preparo do solo: um pequeno trator puxa o arado e os sulcos vão se formando atrás. */
function CenaPreparo() {
  const trator = useRef<THREE.Group>(null);
  const rodas = useRef<THREE.Group>(null);
  const tempo = useTempoLocal();
  const progresso = useRef(0);
  const sulcos = useRef<THREE.Group>(null);
  useFrame(({ clock }, dt) => {
    const t = tempo(clock.elapsedTime);
    const p = (t % 6) / 5; // 5 s andando + 1 s parado
    progresso.current = THREE.MathUtils.clamp(p, 0, 1);
    const z = -2 + progresso.current * 3.9;
    if (trator.current) trator.current.position.z = z + 0.55;
    if (rodas.current) rodas.current.children.forEach((r) => (r.rotation.x += dt * 4));
    if (sulcos.current) {
      sulcos.current.children.forEach((s) => {
        const c = Math.max(0.01, progresso.current);
        s.scale.set(1, c, 0.55);
        s.position.z = -1.8 + (3.6 * c) / 2;
      });
    }
  });
  return (
    <group>
      <Canteiro topo="arada" />
      <group ref={sulcos}>
        {linhasX(5).map((x) => (
          <mesh
            key={x}
            position={[x, 0.02, 0]}
            rotation={[Math.PI / 2, 0, 0]}
            castShadow
            receiveShadow
          >
            <capsuleGeometry args={[0.16, 3.28, 4, 10]} />
            <meshStandardMaterial color={CORES.terraTopo} roughness={1} />
          </mesh>
        ))}
      </group>
      <group ref={trator} position={[0, 0, -1.4]}>
        {/* arado: barra com discos */}
        <mesh position={[0, 0.12, -0.45]} castShadow>
          <boxGeometry args={[3.6, 0.06, 0.08]} />
          <meshStandardMaterial color="#4a5560" metalness={0.5} roughness={0.4} />
        </mesh>
        {linhasX(5).map((x) => (
          <mesh key={x} position={[x, 0.08, -0.45]} rotation={[0, 0, Math.PI / 2]}>
            <cylinderGeometry args={[0.11, 0.11, 0.03, 16]} />
            <meshStandardMaterial color="#9aa5ae" metalness={0.7} roughness={0.3} />
          </mesh>
        ))}
        <mesh position={[0, 0.16, -0.2]}>
          <boxGeometry args={[0.06, 0.05, 0.5]} />
          <meshStandardMaterial color="#4a5560" />
        </mesh>
        {/* trator */}
        <group position={[0, 0, 0.25]}>
          <mesh position={[0, 0.32, 0]} castShadow>
            <boxGeometry args={[0.55, 0.26, 0.85]} />
            <meshStandardMaterial color={CORES.marcaEscura} roughness={0.5} />
          </mesh>
          <mesh position={[0, 0.58, -0.15]} castShadow>
            <boxGeometry args={[0.46, 0.32, 0.4]} />
            <meshStandardMaterial color={CORES.marca} roughness={0.4} />
          </mesh>
          <mesh position={[0, 0.58, 0.06]}>
            <boxGeometry args={[0.4, 0.22, 0.02]} />
            <meshStandardMaterial color="#cfe9ff" metalness={0.2} roughness={0.1} />
          </mesh>
          <mesh position={[0.16, 0.55, 0.32]}>
            <cylinderGeometry args={[0.025, 0.025, 0.3, 8]} />
            <meshStandardMaterial color="#333" />
          </mesh>
          <group ref={rodas}>
            {[
              [0.33, 0.24, -0.22, 0.24],
              [-0.33, 0.24, -0.22, 0.24],
              [0.3, 0.14, 0.3, 0.14],
              [-0.3, 0.14, 0.3, 0.14],
            ].map(([x, y, z, r], i) => (
              <mesh key={i} position={[x!, y!, z!]} rotation={[0, 0, Math.PI / 2]} castShadow>
                <cylinderGeometry args={[r!, r!, 0.12, 20]} />
                <meshStandardMaterial color="#222" roughness={0.9} />
              </mesh>
            ))}
          </group>
        </group>
      </group>
      <Particulas
        quantidade={30}
        origem={[0, 0.25, 0]}
        area={[3.4, 0.4, 3.4]}
        velocidade={0.25}
        limite={0.7}
        cor="#8a6a4c"
        tamanho={[0.025, 0.025, 0.025]}
        forma="grao"
        semente={9}
      />
    </group>
  );
}

/* 5. Semeadura: sementes caem uma a uma nos sulcos e brotam logo depois. */
function CenaSemeadura() {
  const pontos = useMemo(
    () =>
      linhasX(4).flatMap((x, l) =>
        [-1.3, -0.45, 0.4, 1.25].map((z, i) => ({ x: x * 0.95, z, atraso: (l * 4 + i) * 0.28 })),
      ),
    [],
  );
  const refs = useRef<(THREE.Group | null)[]>([]);
  const tempo = useTempoLocal();
  useFrame(({ clock }) => {
    const t = tempo(clock.elapsedTime) % 9;
    pontos.forEach((p, i) => {
      const g = refs.current[i];
      if (!g) return;
      const semente = g.children[0]!;
      const broto = g.children[1]!;
      const queda = THREE.MathUtils.clamp((t - p.atraso) / 0.55, 0, 1);
      semente.position.y = THREE.MathUtils.lerp(2.2, 0.08, queda * queda);
      semente.visible = queda > 0 && t - p.atraso < 2.2;
      const b = brotar((t - p.atraso - 1.4) / 1.2);
      broto.scale.setScalar(Math.max(0.0001, b * 1.6));
    });
  });
  return (
    <group>
      <Canteiro topo="arada" />
      <Sulcos linhas={4} comprimento={3.6} cor={CORES.terraTopo} />
      {pontos.map((p, i) => (
        <group key={i} ref={(el) => void (refs.current[i] = el)} position={[p.x, 0.12, p.z]}>
          <Semente scale={1.2} />
          <Broto />
        </group>
      ))}
    </group>
  );
}

/* 6. Irrigação: caixa d'água, mangueiras de gotejamento e gotas caindo no pé de cada planta. */
function CenaIrrigacao() {
  const nivel = useRef<THREE.Mesh>(null);
  useFrame(({ clock }) => {
    if (nivel.current) nivel.current.scale.y = 0.55 + Math.sin(clock.elapsedTime * 0.8) * 0.08;
  });
  const linhas = linhasX(4).map((x) => x * 0.8);
  const plantas = linhas.flatMap((x) => [-1.1, -0.2, 0.7].map((z) => [x, z] as const));
  return (
    <group>
      <Canteiro topo="terra" />
      {/* caixa d'água */}
      <group position={[1.55, 0, 1.55]}>
        <mesh position={[0, 0.45, 0]}>
          <cylinderGeometry args={[0.32, 0.32, 0.9, 28]} />
          <meshStandardMaterial color="#e8f4fb" transparent opacity={0.35} roughness={0.1} />
        </mesh>
        <mesh ref={nivel} position={[0, 0.25, 0]} scale={[1, 0.55, 1]}>
          <cylinderGeometry args={[0.3, 0.3, 0.9, 28]} />
          <meshStandardMaterial color={CORES.agua} transparent opacity={0.85} />
        </mesh>
        <mesh position={[0, 0.92, 0]}>
          <cylinderGeometry args={[0.34, 0.34, 0.05, 28]} />
          <meshStandardMaterial color={CORES.marcaEscura} />
        </mesh>
      </group>
      {/* mangueira principal + linhas */}
      <mesh position={[0.1, 0.05, 1.55]} rotation={[0, 0, Math.PI / 2]}>
        <cylinderGeometry args={[0.03, 0.03, 2.9, 8]} />
        <meshStandardMaterial color="#2c2f33" />
      </mesh>
      {linhas.map((x) => (
        <mesh key={x} position={[x, 0.05, 0.15]} rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[0.022, 0.022, 2.8, 8]} />
          <meshStandardMaterial color="#2c2f33" />
        </mesh>
      ))}
      {plantas.map(([x, z], i) => (
        <group key={i} position={[x, 0, z]}>
          <Balanco fase={i}>
            <Feijao escala={1.1} />
          </Balanco>
          <Particulas
            quantidade={4}
            origem={[0.1, 0.2, 0]}
            area={[0.02, 0.2, 0.02]}
            velocidade={-0.8}
            limite={0.05}
            cor={CORES.agua}
            tamanho={[0.022, 0.03, 0.022]}
            semente={i + 2}
          />
          <Onda atraso={i * 0.37} position={[0.1, 0.04, 0]} scale={0.6} />
        </group>
      ))}
    </group>
  );
}

/* 7. Adubação: o adubo cai do saco, e os nutrientes sobem do solo para as plantas. */
function CenaAdubacao() {
  const saco = useRef<THREE.Group>(null);
  const plantas = useRef<THREE.Group>(null);
  useFrame(({ clock }) => {
    const t = clock.elapsedTime;
    if (saco.current) {
      saco.current.position.x = Math.sin(t * 0.6) * 1.2;
      saco.current.rotation.z = -0.9 + Math.sin(t * 2) * 0.05;
    }
    if (plantas.current) {
      const s = 1 + Math.max(0, Math.sin(t * 1.4)) * 0.06;
      plantas.current.children.forEach((c) => c.scale.setScalar(s));
    }
  });
  const pos = linhasX(3).flatMap((x) => [-1.1, 0, 1.1].map((z) => [x * 0.75, z] as const));
  return (
    <group>
      <Canteiro topo="terra" />
      <group ref={plantas}>
        {pos.map(([x, z], i) => (
          <group key={i} position={[x, 0, z]}>
            <Balanco fase={i}>
              <Feijao escala={1.25} />
            </Balanco>
          </group>
        ))}
      </group>
      <group ref={saco} position={[0, 2.3, 0]}>
        <Saco cor="#f1f5f9" rotation={[0, 0, 0]} />
        <Particulas
          quantidade={40}
          origem={[0.3, -0.9, 0]}
          area={[0.25, 1.8, 0.25]}
          velocidade={-2.6}
          limite={-2.25}
          cor="#e2e8f0"
          tamanho={[0.035, 0.035, 0.035]}
          forma="grao"
          semente={4}
        />
        <Particulas
          quantidade={25}
          origem={[0.3, -0.9, 0]}
          area={[0.25, 1.8, 0.25]}
          velocidade={-2.4}
          limite={-2.25}
          cor="#93c5fd"
          tamanho={[0.035, 0.035, 0.035]}
          forma="grao"
          semente={8}
        />
      </group>
      {/* nutrientes subindo */}
      <Particulas
        quantidade={60}
        origem={[0, 0.3, 0]}
        area={[3.2, 0.6, 3.2]}
        velocidade={0.5}
        limite={1.3}
        cor={CORES.marca}
        tamanho={[0.03, 0.03, 0.03]}
        forma="grao"
        emissiva
        semente={12}
      />
    </group>
  );
}

/* 8. Desenvolvimento e manutenção: as plantas crescem em onda e a lupa passa vistoriando. */
function CenaManutencao() {
  const pos = useMemo(
    () =>
      linhasX(4).flatMap((x, l) =>
        [-1.3, -0.45, 0.4, 1.25].map((z, i) => ({ x: x * 0.95, z, k: l + i })),
      ),
    [],
  );
  const refs = useRef<(THREE.Group | null)[]>([]);
  const lupa = useRef<THREE.Group>(null);
  useFrame(({ clock }) => {
    const t = clock.elapsedTime;
    pos.forEach((p, i) => {
      const g = refs.current[i];
      if (g) g.scale.setScalar(0.45 + 0.55 * (0.5 + 0.5 * Math.sin(t * 0.9 - p.k * 0.5)));
    });
    if (lupa.current) {
      lupa.current.position.set(
        Math.cos(t * 0.5) * 1.3,
        1.5 + Math.sin(t * 1.5) * 0.12,
        Math.sin(t * 0.5) * 1.3,
      );
      lupa.current.lookAt(0, 3, 0);
    }
  });
  return (
    <group>
      <Canteiro topo="grama" />
      <Sulcos linhas={4} cor={CORES.terraTopo} />
      {pos.map((p, i) => (
        <group key={i} ref={(el) => void (refs.current[i] = el)} position={[p.x, 0.1, p.z]}>
          <Balanco fase={i}>
            <Milho altura={0.9} espigas={false} />
          </Balanco>
        </group>
      ))}
      <group ref={lupa}>
        <mesh>
          <torusGeometry args={[0.3, 0.045, 12, 40]} />
          <meshStandardMaterial color={CORES.marcaEscura} metalness={0.3} roughness={0.4} />
        </mesh>
        <mesh>
          <circleGeometry args={[0.29, 32]} />
          <meshStandardMaterial color="#dff3ff" transparent opacity={0.35} roughness={0} />
        </mesh>
        <mesh position={[0, -0.55, 0]}>
          <cylinderGeometry args={[0.045, 0.05, 0.5, 12]} />
          <meshStandardMaterial color={CORES.madeira} />
        </mesh>
      </group>
    </group>
  );
}

/* 9. Colheita: as espigas saltam dos pés maduros e caem no caixote. */
function CenaColheita() {
  const pes = useMemo(
    () => linhasX(4).flatMap((x) => [-1.25, -0.35, 0.55].map((z) => [x * 0.85, z] as const)),
    [],
  );
  const espigas = useRef<(THREE.Group | null)[]>([]);
  const monte = useRef<THREE.Group>(null);
  const caixote: [number, number, number] = [0, 0, 1.55];
  const tempo = useTempoLocal();
  useFrame(({ clock }) => {
    const t = tempo(clock.elapsedTime) % 10;
    let colhidas = 0;
    pes.forEach(([x, z], i) => {
      const e = espigas.current[i];
      if (!e) return;
      const inicio = i * 0.6;
      const f = THREE.MathUtils.clamp((t - inicio) / 0.9, 0, 1);
      const sx = x + 0.06;
      const sy = 0.62;
      e.position.set(
        THREE.MathUtils.lerp(sx, caixote[0] + ((i % 4) - 1.5) * 0.12, f),
        THREE.MathUtils.lerp(sy, 0.3, f) + Math.sin(f * Math.PI) * 1.1,
        THREE.MathUtils.lerp(z, caixote[2], f),
      );
      e.rotation.z = -0.35 + f * 6;
      e.visible = f < 1;
      if (f >= 1) colhidas++;
    });
    if (monte.current) monte.current.scale.setScalar(Math.max(0.0001, colhidas / pes.length));
  });
  return (
    <group>
      <Canteiro topo="terra" />
      {pes.map(([x, z], i) => (
        <Balanco key={i} fase={i} position={[x, 0, z]} forca={0.03}>
          <Milho altura={1.2} maduro espigas={false} />
        </Balanco>
      ))}
      {pes.map((_, i) => (
        <group key={i} ref={(el) => void (espigas.current[i] = el)}>
          <Espiga />
        </group>
      ))}
      <Caixote position={caixote} />
      <group ref={monte} position={[caixote[0], 0.38, caixote[2]]}>
        {[-0.2, 0, 0.2].map((x) =>
          [-0.1, 0.1].map((z) => (
            <Espiga key={`${x}${z}`} position={[x, 0, z]} rotation={[Math.PI / 2, 0, 0.3]} />
          )),
        )}
      </group>
    </group>
  );
}

/* 10. Pós-colheita: grãos secando no terreiro, sacos empilhando e o silo guardando. */
function CenaPosColheita() {
  const sacos = useRef<(THREE.Group | null)[]>([]);
  const pilha = useMemo(
    () =>
      [
        [0, 0, 0],
        [0.58, 0, 0],
        [0.29, 0.32, 0],
        [0, 0, 0.42],
        [0.58, 0, 0.42],
        [0.29, 0.32, 0.42],
      ] as const,
    [],
  );
  const tempo = useTempoLocal();
  useFrame(({ clock }) => {
    const t = tempo(clock.elapsedTime) % 8;
    pilha.forEach(([, y], i) => {
      const s = sacos.current[i];
      if (!s) return;
      const f = THREE.MathUtils.clamp((t - i * 0.7) / 0.6, 0, 1);
      s.position.y = y + (1 - brotar(f)) * 2.2;
      s.visible = f > 0;
    });
  });
  const graos = useMemo(() => {
    const r = aleatorio(21);
    return Array.from(
      { length: 140 },
      () => [(r() - 0.5) * 1.5, 0.04, (r() - 0.5) * 1.1] as [number, number, number],
    );
  }, []);
  return (
    <group>
      <Canteiro topo="grama" />
      <Silo position={[-1.25, 0, -1.1]} />
      {/* terreiro de secagem */}
      <group position={[-0.6, 0, 1.05]}>
        <mesh position={[0, 0.02, 0]} receiveShadow>
          <boxGeometry args={[1.8, 0.03, 1.3]} />
          <meshStandardMaterial color="#d6d3c4" />
        </mesh>
        {graos.map((p, i) => (
          <mesh key={i} position={p}>
            <sphereGeometry args={[0.03, 6, 5]} />
            <meshStandardMaterial color={i % 3 ? CORES.milhoEspiga : "#e8b23a"} />
          </mesh>
        ))}
      </group>
      <Float speed={2} rotationIntensity={0.4} floatIntensity={0.6}>
        <Sol position={[1.6, 2.6, -1.2]} scale={0.7} />
      </Float>
      <group position={[0.75, 0, -0.6]}>
        {pilha.map(([x, y, z], i) => (
          <group key={i} ref={(el) => void (sacos.current[i] = el)} position={[x, y, z]}>
            <Saco />
          </group>
        ))}
      </group>
      <Caixote position={[1.3, 0, 1.2]} rotation={[0, 0.4, 0]} />
    </group>
  );
}

export const CENAS: Record<TopicoId, ComponentType> = {
  introducao: CenaIntroducao,
  recomendacao: CenaRecomendacao,
  clima: CenaClima,
  "preparo-solo": CenaPreparo,
  semeadura: CenaSemeadura,
  irrigacao: CenaIrrigacao,
  adubacao: CenaAdubacao,
  manutencao: CenaManutencao,
  colheita: CenaColheita,
  "pos-colheita": CenaPosColheita,
};
