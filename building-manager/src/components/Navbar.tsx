import Link from "next/link";

export function Navbar() {
  return (
    <nav className="bg-slate-800 text-white px-6 py-3 flex items-center gap-6 shadow-md">
      <Link href="/" className="font-bold text-lg tracking-tight hover:text-slate-300 transition-colors">
        🏢 物件管理
      </Link>
      <Link href="/?type=マンション" className="text-sm hover:text-slate-300 transition-colors">
        マンション
      </Link>
      <Link href="/?type=ビル" className="text-sm hover:text-slate-300 transition-colors">
        ビル
      </Link>
    </nav>
  );
}
