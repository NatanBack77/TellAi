/* Peças 3D procedurais (sem modelos externos) usadas pelas cenas do guia de plantio.
 * Convenção: o topo do canteiro fica em y = 0 e ele vai de -2 a 2 em x e z. */
import { useMemo, useRef, type ReactNode } from "react";
import { useFrame, type ThreeElements } from "@react-three/fiber";
import { RoundedBox } from "@react-three/drei";
import * as THREE from "three";

export const CORES = {
  terraLado: "#7a5236",
  terraFundo: "#5e3d27",
  terraTopo: "#6b4428",
  terraArada: "#5a3820",
  grama: "#86b85a",
  gramaEscura: "#6a9a45",
  folha: "#5f9e3a",
  folhaClara: "#8cc152",
  caule: "#7aa84a",
  milhoEspiga: "#f2c94c",
  palha: "#c9b27a",
  madeira: "#a0703f",
  madeiraEscura: "#7d5430",
  agua: "#5fb4e3",
  marca: "#9eea6c",
  marcaEscura: "#1f4647",
  metal: "#c7cfd6",
  saco: "#d9c49b",
} as const;

export const tamanhoCanteiro = 4;

/* ------------------------------------------------------------------ util */

/** Tempo desde que o componente montou (para animações que começam do zero a cada cena). */
export function useTempoLocal() {
  const inicio = useRef<number | null>(null);
  return (relogio: number) => {
    inicio.current ??= relogio;
    return relogio - inicio.current;
  };
}

/** Easing suave (0..1 → 0..1). */
export const suave = (x: number) => {
  const t = THREE.MathUtils.clamp(x, 0, 1);
  return 1 - Math.pow(1 - t, 3);
};

/** Elástico curto, para "brotar". */
export const brotar = (x: number) => {
  const t = THREE.MathUtils.clamp(x, 0, 1);
  if (t === 0 || t === 1) return t;
  return Math.pow(2, -9 * t) * Math.sin((t * 10 - 0.75) * ((2 * Math.PI) / 3)) + 1;
};

/** Gera números pseudoaleatórios estáveis (mesma cena = mesmo arranjo). */
export function aleatorio(semente: number) {
  let s = semente;
  return () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

/** Balança suavemente o conteúdo, como vento. */
export function Balanco({
  children,
  fase = 0,
  forca = 0.06,
  ...props
}: { children: ReactNode; fase?: number; forca?: number } & ThreeElements["group"]) {
  const ref = useRef<THREE.Group>(null);
  useFrame(({ clock }) => {
    if (!ref.current) return;
    const t = clock.elapsedTime + fase;
    ref.current.rotation.z = Math.sin(t * 1.3) * forca;
    ref.current.rotation.x = Math.sin(t * 0.9 + 1) * forca * 0.6;
  });
  return (
    <group ref={ref} {...props}>
      {children}
    </group>
  );
}

/* -------------------------------------------------------------- canteiro */

export type TopoCanteiro = "grama" | "terra" | "arada";

/** Bloco de terra flutuante com camadas, base de todas as cenas. */
export function Canteiro({ topo = "grama" }: { topo?: TopoCanteiro }) {
  const corTopo =
    topo === "grama" ? CORES.grama : topo === "arada" ? CORES.terraArada : CORES.terraTopo;
  return (
    <group>
      <RoundedBox
        args={[4.2, 0.55, 4.2]}
        radius={0.14}
        smoothness={4}
        position={[0, -0.95, 0]}
        castShadow
        receiveShadow
      >
        <meshStandardMaterial color={CORES.terraFundo} roughness={1} />
      </RoundedBox>
      <RoundedBox
        args={[4.25, 0.55, 4.25]}
        radius={0.14}
        smoothness={4}
        position={[0, -0.45, 0]}
        castShadow
        receiveShadow
      >
        <meshStandardMaterial color={CORES.terraLado} roughness={1} />
      </RoundedBox>
      <RoundedBox
        args={[4.3, 0.22, 4.3]}
        radius={0.1}
        smoothness={4}
        position={[0, -0.1, 0]}
        receiveShadow
        castShadow
      >
        <meshStandardMaterial color={corTopo} roughness={0.95} />
      </RoundedBox>
      {/* pedrinhas nas laterais dão textura sem imagem */}
      <Pedrinhas />
    </group>
  );
}

function Pedrinhas() {
  const pedras = useMemo(() => {
    const r = aleatorio(7);
    return Array.from({ length: 26 }, () => {
      const lado = Math.floor(r() * 4);
      const u = (r() - 0.5) * 3.9;
      const y = -0.3 - r() * 0.9;
      const p: [number, number, number] =
        lado === 0
          ? [u, y, 2.14]
          : lado === 1
            ? [u, y, -2.14]
            : lado === 2
              ? [2.14, y, u]
              : [-2.14, y, u];
      return { p, s: 0.04 + r() * 0.06, c: r() > 0.5 ? "#9b7a5c" : "#4f3422" };
    });
  }, []);
  return (
    <>
      {pedras.map((pd, i) => (
        <mesh key={i} position={pd.p} scale={pd.s}>
          <dodecahedronGeometry args={[1, 0]} />
          <meshStandardMaterial color={pd.c} roughness={1} flatShading />
        </mesh>
      ))}
    </>
  );
}

/** Sulcos (leiras) paralelos sobre o canteiro. `progresso` 0..1 estica no comprimento. */
export function Sulcos({
  linhas = 5,
  comprimento = 3.6,
  progresso = 1,
  cor = CORES.terraTopo,
}: {
  linhas?: number;
  comprimento?: number;
  progresso?: number;
  cor?: string;
}) {
  const passo = 3.4 / (linhas - 1);
  const c = Math.max(0.001, comprimento * progresso);
  return (
    <group>
      {Array.from({ length: linhas }, (_, i) => (
        <mesh
          key={i}
          position={[-1.7 + i * passo, 0.02, -comprimento / 2 + c / 2]}
          rotation={[Math.PI / 2, 0, 0]}
          scale={[1, c / comprimento, 0.55]}
          castShadow
          receiveShadow
        >
          <capsuleGeometry args={[0.16, comprimento - 0.32, 4, 10]} />
          <meshStandardMaterial color={cor} roughness={1} />
        </mesh>
      ))}
    </group>
  );
}

/** Posições (x) das linhas dos sulcos, para plantar em cima delas. */
export const linhasX = (linhas = 5) =>
  Array.from({ length: linhas }, (_, i) => -1.7 + (i * 3.4) / (linhas - 1));

/* ---------------------------------------------------------------- plantas */

function Folha({
  comprimento = 0.35,
  largura = 0.13,
  cor = CORES.folha,
  ...props
}: { comprimento?: number; largura?: number; cor?: string } & ThreeElements["mesh"]) {
  return (
    <mesh castShadow {...props} scale={[largura, 0.025, comprimento]}>
      <sphereGeometry args={[1, 10, 8]} />
      <meshStandardMaterial color={cor} roughness={0.7} side={THREE.DoubleSide} />
    </mesh>
  );
}

export function Semente({ cor = "#c08a4a", ...props }: { cor?: string } & ThreeElements["mesh"]) {
  return (
    <mesh castShadow {...props}>
      <sphereGeometry args={[0.07, 12, 10]} />
      <meshStandardMaterial color={cor} roughness={0.5} />
    </mesh>
  );
}

/** Broto com duas folhinhas. */
export function Broto({
  cor = CORES.folhaClara,
  ...props
}: { cor?: string } & ThreeElements["group"]) {
  return (
    <group {...props}>
      <mesh position={[0, 0.12, 0]} castShadow>
        <cylinderGeometry args={[0.015, 0.02, 0.24, 6]} />
        <meshStandardMaterial color={CORES.caule} />
      </mesh>
      <Folha
        position={[0.09, 0.24, 0]}
        rotation={[0, Math.PI / 2, 0.5]}
        comprimento={0.11}
        largura={0.06}
        cor={cor}
      />
      <Folha
        position={[-0.09, 0.24, 0]}
        rotation={[0, Math.PI / 2, -0.5]}
        comprimento={0.11}
        largura={0.06}
        cor={cor}
      />
    </group>
  );
}

/** Pé de milho estilizado. `maduro` deixa as folhas amareladas e mostra espigas. */
export function Milho({
  altura = 1.4,
  maduro = false,
  espigas = true,
  ...props
}: { altura?: number; maduro?: boolean; espigas?: boolean } & ThreeElements["group"]) {
  const corFolha = maduro ? "#b9b85a" : CORES.folha;
  const folhas = [0.25, 0.42, 0.58, 0.74, 0.88];
  return (
    <group {...props}>
      <mesh position={[0, altura / 2, 0]} castShadow>
        <cylinderGeometry args={[0.025, 0.045, altura, 7]} />
        <meshStandardMaterial color={maduro ? "#a9a35a" : CORES.caule} />
      </mesh>
      {folhas.map((h, i) => (
        <group key={h} position={[0, altura * h, 0]} rotation={[0, i * 2.4, 0]}>
          <Folha
            position={[0, 0.06, 0.2]}
            rotation={[-0.55, 0, 0]}
            comprimento={0.32}
            largura={0.06}
            cor={corFolha}
          />
        </group>
      ))}
      {/* pendão */}
      <group position={[0, altura + 0.06, 0]}>
        {[0, 1, 2].map((i) => (
          <mesh key={i} rotation={[0.4, i * 2.1, 0]} position={[0, 0.05, 0]}>
            <cylinderGeometry args={[0.008, 0.008, 0.16, 4]} />
            <meshStandardMaterial color={CORES.palha} />
          </mesh>
        ))}
      </group>
      {espigas && (
        <Espiga position={[0.06, altura * 0.52, 0]} rotation={[0, 0, -0.35]} maduro={maduro} />
      )}
    </group>
  );
}

export function Espiga({ maduro = true, ...props }: { maduro?: boolean } & ThreeElements["group"]) {
  return (
    <group {...props}>
      <mesh castShadow>
        <capsuleGeometry args={[0.045, 0.14, 4, 10]} />
        <meshStandardMaterial color={maduro ? CORES.milhoEspiga : "#d8e08a"} roughness={0.6} />
      </mesh>
      <mesh position={[0, -0.05, 0]} scale={[1.15, 1, 1.15]}>
        <capsuleGeometry args={[0.045, 0.1, 4, 10]} />
        <meshStandardMaterial color={maduro ? "#cdb36b" : "#8bbf55"} roughness={0.8} />
      </mesh>
    </group>
  );
}

/** Pé de feijão: moita de folhas arredondadas. */
export function Feijao({ escala = 1, ...props }: { escala?: number } & ThreeElements["group"]) {
  const folhas = useMemo(() => {
    const r = aleatorio(11);
    return Array.from({ length: 9 }, (_, i) => ({
      p: [(r() - 0.5) * 0.36, 0.14 + r() * 0.22, (r() - 0.5) * 0.36] as [number, number, number],
      rot: [r() * 0.8 - 0.4, i, r() * 0.8 - 0.4] as [number, number, number],
      c: r() > 0.5 ? CORES.folha : CORES.folhaClara,
    }));
  }, []);
  return (
    <group scale={escala} {...props}>
      <mesh position={[0, 0.12, 0]}>
        <cylinderGeometry args={[0.02, 0.03, 0.24, 6]} />
        <meshStandardMaterial color={CORES.caule} />
      </mesh>
      {folhas.map((f, i) => (
        <Folha key={i} position={f.p} rotation={f.rot} comprimento={0.13} largura={0.1} cor={f.c} />
      ))}
    </group>
  );
}

/** Mandioca: hastes finas com folhas em estrela (palmadas). */
export function Mandioca({ ...props }: ThreeElements["group"]) {
  const hastes = [
    { r: [0.15, 0, 0.1], h: 0.95 },
    { r: [-0.12, 1.2, -0.08], h: 0.8 },
    { r: [0.05, 2.4, -0.15], h: 0.7 },
  ] as const;
  return (
    <group {...props}>
      {hastes.map((hs, i) => (
        <group key={i} rotation={hs.r as unknown as [number, number, number]}>
          <mesh position={[0, hs.h / 2, 0]} castShadow>
            <cylinderGeometry args={[0.015, 0.025, hs.h, 6]} />
            <meshStandardMaterial color="#9c6b4a" />
          </mesh>
          <group position={[0, hs.h, 0]}>
            {[0, 1, 2, 3, 4].map((k) => (
              <group key={k} rotation={[0, (k / 5) * Math.PI * 2, 0]}>
                <Folha
                  position={[0, 0, 0.12]}
                  rotation={[-0.3, 0, 0]}
                  comprimento={0.13}
                  largura={0.035}
                  cor={CORES.folha}
                />
              </group>
            ))}
          </group>
        </group>
      ))}
    </group>
  );
}

/* ------------------------------------------------------------------- céu */

export function Nuvem({ cor = "#ffffff", ...props }: { cor?: string } & ThreeElements["group"]) {
  const bolas: [number, number, number, number][] = [
    [0, 0, 0, 0.42],
    [0.4, -0.05, 0.05, 0.32],
    [-0.42, -0.06, 0, 0.3],
    [0.15, 0.22, -0.05, 0.3],
    [-0.18, 0.15, 0.12, 0.26],
  ];
  return (
    <group {...props}>
      {bolas.map(([x, y, z, r], i) => (
        <mesh key={i} position={[x, y, z]} castShadow>
          <sphereGeometry args={[r, 18, 14]} />
          <meshStandardMaterial color={cor} roughness={0.9} />
        </mesh>
      ))}
    </group>
  );
}

export function Sol(props: ThreeElements["group"]) {
  const raios = useRef<THREE.Group>(null);
  useFrame((_, dt) => {
    if (raios.current) raios.current.rotation.z += dt * 0.4;
  });
  return (
    <group {...props}>
      <mesh>
        <sphereGeometry args={[0.32, 24, 18]} />
        <meshStandardMaterial
          color="#ffd54a"
          emissive="#ffb703"
          emissiveIntensity={1.4}
          toneMapped={false}
        />
      </mesh>
      <group ref={raios}>
        {Array.from({ length: 10 }, (_, i) => (
          <mesh key={i} rotation={[0, 0, (i / 10) * Math.PI * 2]} position={[0, 0, 0]}>
            <boxGeometry args={[0.04, 0.95, 0.02]} />
            <meshStandardMaterial
              color="#ffd54a"
              emissive="#ffb703"
              emissiveIntensity={0.8}
              transparent
              opacity={0.65}
            />
          </mesh>
        ))}
      </group>
    </group>
  );
}

/* -------------------------------------------------------------- partículas */

interface ParticulasProps {
  quantidade: number;
  /** Onde nascem: centro e tamanho da caixa. */
  origem: [number, number, number];
  area: [number, number, number];
  /** Velocidade vertical (negativa = cai). */
  velocidade: number;
  /** Altura em que a partícula "morre" e renasce. */
  limite: number;
  cor: string;
  tamanho?: [number, number, number];
  semente?: number;
  forma?: "gota" | "grao";
  emissiva?: boolean;
}

/** Partículas com instancing (chuva, gotas, adubo, nutrientes). */
export function Particulas({
  quantidade,
  origem,
  area,
  velocidade,
  limite,
  cor,
  tamanho = [0.02, 0.09, 0.02],
  semente = 3,
  forma = "gota",
  emissiva = false,
}: ParticulasProps) {
  const ref = useRef<THREE.InstancedMesh>(null);
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const dados = useMemo(() => {
    const r = aleatorio(semente);
    return Array.from({ length: quantidade }, () => ({
      x: origem[0] + (r() - 0.5) * area[0],
      y: origem[1] + (r() - 0.5) * area[1],
      z: origem[2] + (r() - 0.5) * area[2],
      v: velocidade * (0.75 + r() * 0.5),
    }));
  }, [quantidade, origem, area, velocidade, semente]);

  useFrame((_, dt) => {
    const m = ref.current;
    if (!m) return;
    const passo = Math.min(dt, 0.05);
    dados.forEach((p, i) => {
      p.y += p.v * passo;
      const passou = p.v < 0 ? p.y < limite : p.y > limite;
      if (passou) p.y = origem[1] + (Math.random() - 0.5) * area[1];
      dummy.position.set(p.x, p.y, p.z);
      dummy.scale.set(...tamanho);
      dummy.updateMatrix();
      m.setMatrixAt(i, dummy.matrix);
    });
    m.instanceMatrix.needsUpdate = true;
  });

  return (
    <instancedMesh
      ref={ref}
      args={[undefined, undefined, quantidade]}
      castShadow={forma === "grao"}
    >
      {forma === "gota" ? (
        <capsuleGeometry args={[1, 1, 3, 6]} />
      ) : (
        <sphereGeometry args={[1, 8, 6]} />
      )}
      <meshStandardMaterial
        color={cor}
        roughness={0.3}
        transparent={forma === "gota"}
        opacity={forma === "gota" ? 0.85 : 1}
        emissive={emissiva ? cor : "#000000"}
        emissiveIntensity={emissiva ? 1.2 : 0}
        toneMapped={!emissiva}
      />
    </instancedMesh>
  );
}

/** Anel de onda na água/solo, expandindo e sumindo em loop. */
export function Onda({
  atraso = 0,
  cor = CORES.agua,
  ...props
}: { atraso?: number; cor?: string } & ThreeElements["mesh"]) {
  const ref = useRef<THREE.Mesh>(null);
  useFrame(({ clock }) => {
    const m = ref.current;
    if (!m) return;
    const t = ((clock.elapsedTime + atraso) % 1.6) / 1.6;
    m.scale.setScalar(0.05 + t * 0.35);
    (m.material as THREE.MeshStandardMaterial).opacity = (1 - t) * 0.8;
  });
  return (
    <mesh ref={ref} rotation={[-Math.PI / 2, 0, 0]} {...props}>
      <torusGeometry args={[1, 0.08, 6, 28]} />
      <meshStandardMaterial color={cor} transparent opacity={0.8} />
    </mesh>
  );
}

/* --------------------------------------------------------------- objetos */

/** Alfinete de mapa (componente "Map pin" do Figma) em 3D. */
export function Pin(props: ThreeElements["group"]) {
  return (
    <group {...props}>
      <mesh position={[0, 0.42, 0]} castShadow>
        <sphereGeometry args={[0.22, 24, 18]} />
        <meshStandardMaterial color={CORES.marcaEscura} roughness={0.35} metalness={0.1} />
      </mesh>
      <mesh position={[0, 0.17, 0]} rotation={[Math.PI, 0, 0]} castShadow>
        <coneGeometry args={[0.16, 0.36, 24]} />
        <meshStandardMaterial color={CORES.marcaEscura} roughness={0.35} />
      </mesh>
      <mesh position={[0, 0.42, 0.19]}>
        <sphereGeometry args={[0.08, 16, 12]} />
        <meshStandardMaterial
          color={CORES.marca}
          emissive={CORES.marca}
          emissiveIntensity={0.8}
          toneMapped={false}
        />
      </mesh>
    </group>
  );
}

export function Caixote({ ...props }: ThreeElements["group"]) {
  return (
    <group {...props}>
      {[-0.13, 0, 0.13].map((y) => (
        <group key={y}>
          <mesh position={[0, y + 0.18, 0.3]} castShadow>
            <boxGeometry args={[0.8, 0.09, 0.04]} />
            <meshStandardMaterial color={CORES.madeira} />
          </mesh>
          <mesh position={[0, y + 0.18, -0.3]} castShadow>
            <boxGeometry args={[0.8, 0.09, 0.04]} />
            <meshStandardMaterial color={CORES.madeira} />
          </mesh>
          <mesh position={[0.38, y + 0.18, 0]} castShadow>
            <boxGeometry args={[0.04, 0.09, 0.6]} />
            <meshStandardMaterial color={CORES.madeira} />
          </mesh>
          <mesh position={[-0.38, y + 0.18, 0]} castShadow>
            <boxGeometry args={[0.04, 0.09, 0.6]} />
            <meshStandardMaterial color={CORES.madeira} />
          </mesh>
        </group>
      ))}
      <mesh position={[0, 0.03, 0]} receiveShadow>
        <boxGeometry args={[0.8, 0.04, 0.64]} />
        <meshStandardMaterial color={CORES.madeiraEscura} />
      </mesh>
    </group>
  );
}

export function Saco({ cor = CORES.saco, ...props }: { cor?: string } & ThreeElements["group"]) {
  return (
    <group {...props}>
      <RoundedBox
        args={[0.55, 0.32, 0.38]}
        radius={0.12}
        smoothness={4}
        position={[0, 0.16, 0]}
        castShadow
      >
        <meshStandardMaterial color={cor} roughness={1} />
      </RoundedBox>
      <mesh position={[0, 0.24, 0.19]}>
        <boxGeometry args={[0.22, 0.12, 0.01]} />
        <meshStandardMaterial color={CORES.marcaEscura} />
      </mesh>
    </group>
  );
}

export function Silo(props: ThreeElements["group"]) {
  return (
    <group {...props}>
      <mesh position={[0, 0.7, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[0.45, 0.45, 1.4, 32]} />
        <meshStandardMaterial color={CORES.metal} metalness={0.6} roughness={0.35} />
      </mesh>
      {[0.25, 0.55, 0.85, 1.15].map((y) => (
        <mesh key={y} position={[0, y, 0]}>
          <torusGeometry args={[0.455, 0.012, 6, 40]} />
          <meshStandardMaterial color="#9aa5ae" metalness={0.7} roughness={0.3} />
        </mesh>
      ))}
      <mesh position={[0, 1.62, 0]} castShadow>
        <coneGeometry args={[0.52, 0.45, 32]} />
        <meshStandardMaterial color={CORES.marcaEscura} metalness={0.3} roughness={0.5} />
      </mesh>
    </group>
  );
}
