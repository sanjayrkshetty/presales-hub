export function PageSkeleton() {
  return (
    <div className="p-4 flex flex-col gap-4 animate-pulse">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-20 rounded bg-bg-tertiary" />
        ))}
      </div>
      <div className="grid grid-cols-12 gap-4 flex-1">
        <div className="col-span-12 lg:col-span-3 h-64 rounded bg-bg-tertiary" />
        <div className="col-span-12 lg:col-span-6 h-64 rounded bg-bg-tertiary" />
        <div className="col-span-12 lg:col-span-3 h-64 rounded bg-bg-tertiary" />
      </div>
    </div>
  );
}
