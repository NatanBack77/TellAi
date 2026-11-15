import {
  Suspense,
  useImperativeHandle,
  useRef,
  useState,
  type ComponentRef,
  type Ref,
} from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { ContactShadows, Environment, Float, Lightformer, OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import { IconButton } from "@/shared/components/ui/IconButton";
import type { TopicoId } from "../../models/topicos.model";
import { CENAS } from "./cenas";

/**
 * Troca de cena suave: a cena atual encolhe girando, a nova cresce no lugar.
 * O React só re-renderiza uma vez, no meio da transição.
 */
type OrbitControlsImpl = ComponentRef<typeof OrbitControls>;

function TrocaDeCena({ id }: { id: TopicoId }) {
  const ref = useRef<THREE.Group>(null);
  const [exibido, setExibido] = useState(id);
  const escala = useRef(0);

  useFrame((_, dt) => {
    const g = ref.current;
    if (!g) return;
    const saindo = id !== exibido;
    const alvo = saindo ? 0 : 1;
    escala.current = THREE.MathUtils.damp(escala.current, alvo, saindo ? 9 : 5, Math.min(dt, 0.05));
    if (saindo && escala.current < 0.03) {
      escala.current = 0;
      setExibido(id);
    }
    const s = Math.max(0.0001, escala.current);
    g.scale.setScalar(s);
    g.rotation.y = (1 - s) * (saindo ? -0.8 : 0.8);
    g.position.y = (1 - s) * -0.6;
  });

  const Cena = CENAS[exibido];
  return (
    <group ref={ref} scale={0.0001}>
      <Cena key={exibido} />
    </group>
  );
}

const POSICAO_INICIAL = new THREE.Vector3(4.2, 3.2, 4.8);
const ALVO = new THREE.Vector3(0, -0.15, 0);
const DISTANCIA_INICIAL = POSICAO_INICIAL.length();
const MIN_DIST = 5;
const MAX_DIST = 12;

export interface ControleZoom {
  zoom: (fator: number) => void;
  centralizar: () => void;
}

/** Aproxima/afasta a câmera suavemente. Comandado de fora (botões HTML) via ref imperativa. */
function ZoomSuave({ ref }: { ref: Ref<ControleZoom> }) {
  const { camera, controls } = useThree();
  const alvo = useRef<number | null>(null);
  const orbit = () => controls as unknown as OrbitControlsImpl | null;

  useImperativeHandle(ref, () => ({
    zoom: (fator) => {
      const c = orbit();
      const atual = alvo.current ?? (c ? camera.position.distanceTo(c.target) : DISTANCIA_INICIAL);
      alvo.current = THREE.MathUtils.clamp(atual * fator, MIN_DIST, MAX_DIST);
    },
    centralizar: () => {
      const c = orbit();
      camera.position.copy(POSICAO_INICIAL);
      c?.target.copy(ALVO);
      c?.update();
      alvo.current = DISTANCIA_INICIAL;
    },
  }));

  useFrame((_, dt) => {
    if (alvo.current === null) return;
    const c = orbit();
    const centro = c?.target ?? new THREE.Vector3();
    const atual = camera.position.distanceTo(centro);
    const nova = THREE.MathUtils.damp(atual, alvo.current, 6, Math.min(dt, 0.05));
    camera.position.sub(centro).setLength(nova).add(centro);
    c?.update();
    if (Math.abs(nova - alvo.current) < 0.01) alvo.current = null;
  });
  return null;
}

export interface Palco3DProps {
  topico: TopicoId;
}

export default function Palco3D({ topico }: Palco3DProps) {
  const zoomRef = useRef<ControleZoom>(null);

  return (
    <div className="absolute inset-0">
      <Canvas
        shadows
        dpr={[1, 2]}
        camera={{ position: POSICAO_INICIAL.toArray(), fov: 38 }}
        gl={{ antialias: true, alpha: true }}
      >
        <ambientLight intensity={0.35} />
        <hemisphereLight args={["#ffffff", "#b7c7a3", 0.6]} />
        <directionalLight
          position={[4, 7, 3]}
          intensity={2.1}
          castShadow
          shadow-mapSize={[2048, 2048]}
          shadow-camera-left={-4}
          shadow-camera-right={4}
          shadow-camera-top={4}
          shadow-camera-bottom={-4}
          shadow-bias={-0.0004}
        />

        {/* Ambiente de luz feito só com painéis (sem baixar HDR). */}
        <Environment resolution={256}>
          <Lightformer form="rect" intensity={2} position={[0, 5, -5]} scale={[10, 5, 1]} />
          <Lightformer
            form="rect"
            intensity={1}
            position={[-5, 2, 2]}
            rotation-y={Math.PI / 2}
            scale={[8, 3, 1]}
          />
          <Lightformer form="ring" intensity={1.5} color="#e6ffd1" position={[5, 3, 3]} scale={2} />
        </Environment>

        <Suspense fallback={null}>
          <Float
            speed={1.2}
            rotationIntensity={0.08}
            floatIntensity={0.35}
            floatingRange={[-0.05, 0.08]}
          >
            <group position={[0, 0.1, 0]}>
              <TrocaDeCena id={topico} />
            </group>
          </Float>
        </Suspense>

        <ContactShadows
          position={[0, -1.75, 0]}
          opacity={0.35}
          scale={9}
          blur={2.6}
          far={3}
          color="#1f4647"
        />

        <ZoomSuave ref={zoomRef} />
        <OrbitControls
          makeDefault
          enablePan={false}
          autoRotate
          autoRotateSpeed={0.6}
          enableDamping
          dampingFactor={0.08}
          minDistance={MIN_DIST}
          maxDistance={MAX_DIST}
          minPolarAngle={Math.PI / 6}
          maxPolarAngle={Math.PI / 2.15}
          target={ALVO.toArray()}
        />
      </Canvas>

      {/* Zoom (grupo "Zoom" do Figma: home, +, −) */}
      <div className="absolute right-3 bottom-3 flex flex-col gap-3">
        <IconButton
          rotulo="Centralizar a vista"
          icone="home-04"
          onClick={() => zoomRef.current?.centralizar()}
        />
        <div className="flex flex-col gap-1">
          <IconButton rotulo="Aproximar" icone="plus" onClick={() => zoomRef.current?.zoom(0.8)} />
          <IconButton rotulo="Afastar" icone="minus" onClick={() => zoomRef.current?.zoom(1.25)} />
        </div>
      </div>
    </div>
  );
}
