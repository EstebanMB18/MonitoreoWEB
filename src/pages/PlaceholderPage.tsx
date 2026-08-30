interface PlaceholderPageProps {
  eyebrow: string
  title: string
  description: string
}

export function PlaceholderPage({
  eyebrow,
  title,
  description,
}: PlaceholderPageProps) {
  return (
    <section className="placeholder-page">
      <p className="section-eyebrow">{eyebrow}</p>
      <h2>{title}</h2>
      <p>{description}</p>

      <div className="placeholder-panel">
        <span>En construcción</span>
        <p>
          Esta vista ya forma parte de la navegación de NEXUS
          y se implementará en el siguiente bloque funcional.
        </p>
      </div>
    </section>
  )
}
