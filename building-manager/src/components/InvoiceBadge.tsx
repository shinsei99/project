export function InvoiceBadge({ status }: { status: string }) {
  const isStored = status === "保管済";
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${isStored ? "bg-blue-100 text-blue-800" : "bg-red-100 text-red-700"}`}>
      {isStored ? "📄 Excel保管済" : "— 詳細なし"}
    </span>
  );
}
