import { Helmet } from "react-helmet-async";

const SITE_NAME = "Sulco";

interface SeoProps {
  title?: string;
  description?: string;
}

/** Título e metatags por página. Cada View declara o seu. */
export function Seo({ title, description }: SeoProps) {
  const fullTitle = title ? `${title} · ${SITE_NAME}` : SITE_NAME;
  return (
    <Helmet>
      <title>{fullTitle}</title>
      {description && <meta name="description" content={description} />}
      <meta property="og:title" content={fullTitle} />
      {description && <meta property="og:description" content={description} />}
    </Helmet>
  );
}
