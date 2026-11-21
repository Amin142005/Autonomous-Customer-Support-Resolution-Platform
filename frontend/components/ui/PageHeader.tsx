interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  description?: string;
}

export function PageHeader({ eyebrow, title, description }: PageHeaderProps) {
  return (
    <header>
      {eyebrow ? (
        <p className="text-sm font-medium text-brand">{eyebrow}</p>
      ) : null}
      <h1 className="mt-1 text-2xl font-semibold text-slate-950">{title}</h1>
      {description ? (
        <p className="mt-2 max-w-2xl text-sm text-slate-500">{description}</p>
      ) : null}
    </header>
  );
}
