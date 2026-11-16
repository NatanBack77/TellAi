import { useMemo } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import type { Municipio } from "../models/municipio.model";

interface MapaPontos3DProps {
  todos: readonly Municipio[];
  destacados: ReadonlySet<string>;
  selecionadoId: string | null;
  onSelecionar: (id: string) => void;
}

/** Converte lat/lon em posições [x, z] da cena, centralizando a nuvem de pontos. */
function calcularPosicoes(pontos: readonly Municipio[]) {
  const posicoes = new Map<string, [number, number]>();
  if (pontos.length === 0) return posicoes;
  const lats = pontos.map((p) => p.lat);
  const lons = pontos.map((p) => p.lon);
  const cLat = (Math.min(...lats) + Math.max(...lats)) / 2;
  const cLon = (Math.min(...lons) + Math.max(...lons)) / 2;
  const escala = 2.2;
  for (const p of pontos)
    posicoes.set(p.ponto_id, [(p.lon - cLon) * escala, -(p.lat - cLat) * escala]);
  return posicoes;
}

export default function MapaPontos3D({
  todos,
  destacados,
  selecionadoId,
  onSelecionar,
}: MapaPontos3DProps) {
  const posicoes = useMemo(() => calcularPosicoes(todos), [todos]);

  return (
    <Canvas camera={{ position: [0, 9, 9], fov: 45 }} dpr={[1, 2]}>
      <color attach="background" args={["#183a2b"]} />
      <ambientLight intensity={0.6} />
      <directionalLight position={[5, 10, 5]} intensity={1.2} />
      <gridHelper args={[20, 20, "#4f8c42", "#214834"]} />

      {todos.map((m) => {
        const ativo = destacados.has(m.ponto_id);
        const selecionado = m.ponto_id === selecionadoId;
        const altura = selecionado ? 1.2 : ativo ? 0.5 : 0.15;
        const [x, z] = posicoes.get(m.ponto_id) ?? [0, 0];
        return (
          <mesh
            key={m.ponto_id}
            position={[x, altura / 2, z]}
            onClick={(e) => {
              e.stopPropagation();
              onSelecionar(m.ponto_id);
            }}
          >
            <boxGeometry args={[0.18, altura, 0.18]} />
            <meshStandardMaterial color={selecionado ? "#d9ef72" : ativo ? "#8dba3b" : "#46594d"} />
          </mesh>
        );
      })}

      <OrbitControls
        enablePan={false}
        minDistance={5}
        maxDistance={20}
        maxPolarAngle={Math.PI / 2.2}
      />
    </Canvas>
  );
}
