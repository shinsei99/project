export function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    "入居中": "bg-green-100 text-green-800 border-green-200",
    "空室": "bg-gray-100 text-gray-700 border-gray-200",
    "リフォーム中": "bg-yellow-100 text-yellow-800 border-yellow-200",
  };
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${styles[status] ?? "bg-gray-100 text-gray-700 border-gray-200"}`}>
      {status}
    </span>
  );
}
