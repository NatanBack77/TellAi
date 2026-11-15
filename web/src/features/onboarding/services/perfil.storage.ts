import { apagarStorage, gravarStorage, lerStorage } from "@/shared/lib/storage";
import { perfilSchema, type Perfil } from "../models/perfil.model";

const CHAVE = "sulco:perfil";

/** Service de persistência do perfil (localStorage). */
export const perfilStorage = {
  ler: (): Perfil | null => lerStorage(CHAVE, perfilSchema),
  existe: () => perfilStorage.ler() !== null,
  salvar: (perfil: Perfil) => gravarStorage(CHAVE, perfil),
  apagar: () => apagarStorage(CHAVE),
};
