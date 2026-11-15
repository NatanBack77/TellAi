import { Link } from "@tanstack/react-router";
import { Seo } from "@/shared/components/seo/Seo";

export function NotFoundView() {
  return (
    <section className="grid min-h-dvh place-content-center gap-3 text-center">
      <Seo title="Página não encontrada" />
      <h1 className="text-2xl font-semibold">Página não encontrada</h1>
      <Link to="/" className="text-leaf underline">
        Voltar para o início
      </Link>
    </section>
  );
}
